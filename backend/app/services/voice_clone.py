"""
用户声纹服务 - 火山方舟豆包语音 Voice Cloning

调用关系:
- 训练: POST {base_url}/api/v3/tts/voice_clone
        Header X-Api-Key, Body { speaker_id, custom_speaker_id, audio, text, language, ... }
        Response status: 1=Training 2=Success 3=Failed 4=Active
- 合成: POST {base_url}/api/v3/tts (C2 阶段对接)
        Body { app, speaker_id, custom_speaker_id, text, format, sample_rate }

C1 阶段:
- 完整 DB CRUD + 文件存储 + service API
- train/synthesize 暂用本地 fallback (macOS say), 火山调用先 stub
C2 阶段:
- 替换 fallback 为真实火山 API
"""
import os
import re
import uuid
import shutil
import subprocess
import tempfile
import time
import base64
from pathlib import Path
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.voice_profile import UserVoiceProfile


# ===== 业务规则常量 =====
MAX_PROFILES_PER_USER = 3
ALLOWED_AUDIO_FORMATS = {"mp3", "wav", "ogg", "m4a", "aac", "pcm"}
MIN_SAMPLE_SECONDS = 3
MAX_SAMPLE_SECONDS = 60
MAX_SAMPLE_BYTES = 10 * 1024 * 1024  # 火山限制 10MB


def _storage_root() -> Path:
    """backend/storage 根目录"""
    return Path(settings.STORAGE_PATH).resolve()


def _samples_dir(user_id: int) -> Path:
    """样本存储路径: storage/voice_samples/{user_id}/"""
    d = _storage_root() / "voice_samples" / str(user_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _demos_dir(user_id: int) -> Path:
    """试听音频路径: storage/voice_demos/{user_id}/"""
    d = _storage_root() / "voice_demos" / str(user_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


# ===== 训练接口调用 (C2 stub, C1 仅占位) =====
def _call_volc_train(profile: UserVoiceProfile, sample_bytes: bytes, sample_format: str) -> Dict[str, Any]:
    """
    调火山方舟 voice_clone 训练接口
    C1 stub: 返回训练中状态, 不真调
    C2: 替换为真实 HTTP 调用
    """
    # C2 阶段实现
    return {
        "code": 0,
        "message": "training",
        "speaker_id": "custom_speaker_id",
        "custom_speaker_id": profile.custom_speaker_id,
        "status": 1,  # Training
        "available_training_times": 99,
        "demo_audio": None,
    }


# ===== TTS 合成接口调用 (C2 stub) =====
def _call_volc_synthesize(custom_speaker_id: str, text: str, lang: int = 0) -> Optional[bytes]:
    """
    调火山方舟 TTS 合成接口
    C1 stub: 返回 None (触发 fallback)
    C2: 替换为真实 HTTP 调用, 返回 mp3 bytes
    """
    # C2 阶段实现
    return None


# ===== macOS say fallback (本地 dev) =====
def _fallback_tts(text: str, output_path: Path) -> Path:
    """
    macOS `say` 生成语音, ffmpeg 转 mp3
    非 macOS 抛 NotImplementedError
    """
    import platform
    if platform.system() != "Darwin":
        raise NotImplementedError("非 macOS 平台, 请等待 C2 火山接入")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_aiff = output_path.with_suffix(".aiff")
    proc = subprocess.run(
        ["say", "-v", "Sin-ji", "-o", str(tmp_aiff), text],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0 or not tmp_aiff.exists():
        raise RuntimeError(f"say 失败: {proc.stderr}")

    conv = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-i", str(tmp_aiff),
         "-ar", "16000", "-ac", "1", "-b:a", "64k",
         str(output_path)],
        capture_output=True, text=True, timeout=30,
    )
    tmp_aiff.unlink(missing_ok=True)
    if conv.returncode != 0:
        raise RuntimeError(f"aiff->mp3 失败: {conv.stderr[-300:]}")
    return output_path


# ===== 业务方法 =====
def _validate_custom_speaker_id(s: str) -> str:
    """校验 custom_speaker_id 命名规范 (火山 8-256 字符, 字母开头, 数字/_/-)"""
    if not s or len(s) < 8 or len(s) > 256:
        raise ValueError("custom_speaker_id 长度需 8-256 字符")
    if not re.match(r"^[a-zA-Z]", s):
        raise ValueError("custom_speaker_id 必须以英文字母开头")
    if s[0] in "-_" or s[-1] in "-_":
        raise ValueError("custom_speaker_id 首末不能是 - 或 _")
    if not re.match(r"^[a-zA-Z0-9_-]+$", s):
        raise ValueError("custom_speaker_id 仅支持数字/大小写字母/-/_")
    return s


def _validate_audio_format(filename: str) -> str:
    """从文件名取后缀, 校验格式"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_AUDIO_FORMATS:
        raise ValueError(f"不支持的音频格式: {ext}, 仅支持 {ALLOWED_AUDIO_FORMATS}")
    return ext


def _count_user_profiles(db: Session, user_id: int) -> int:
    return db.query(UserVoiceProfile).filter(
        UserVoiceProfile.user_id == user_id,
        UserVoiceProfile.status != "deleted",
    ).count()


def _gen_custom_speaker_id(user_id: int, name: str) -> str:
    """生成 custom_speaker_id: phx_{user_id}_{name}_{short_uuid}
    火山限制 8-256 字符, 字母开头, 数字/_/-"""
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "", name)[:30] or "voice"
    short = uuid.uuid4().hex[:8]
    sid = f"phx{user_id}{safe_name}{short}"  # 字母开头
    if len(sid) < 8:
        sid = sid + "0" * (8 - len(sid))
    return sid[:256]


def upload_sample(
    db: Session,
    user_id: int,
    file_bytes: bytes,
    filename: str,
    name: str,
    demo_text: str = "你好, 这是我的专属声音测试。",
    language: int = 0,
    reference_text: str = "",
) -> UserVoiceProfile:
    """
    上传音频样本, 创建声纹档案 (C1 阶段状态: training, 等 C2 真正调训练接口)
    """
    if _count_user_profiles(db, user_id) >= MAX_PROFILES_PER_USER:
        raise ValueError(f"每用户最多 {MAX_PROFILES_PER_USER} 个声纹, 请先删除旧的")

    if len(file_bytes) > MAX_SAMPLE_BYTES:
        raise ValueError(f"样本文件不能超过 {MAX_SAMPLE_BYTES // 1024 // 1024}MB")
    if len(file_bytes) < 1024:
        raise ValueError("样本文件过小 (<1KB), 请重新上传")

    fmt = _validate_audio_format(filename)
    if not name or len(name) > 100:
        raise ValueError("声纹名字 1-100 字符")
    if not demo_text or len(demo_text) > 300 or len(demo_text) < 4:
        raise ValueError("试听文本需 4-300 字")

    # 落盘到 storage/voice_samples/{user_id}/
    profile = UserVoiceProfile(
        user_id=user_id,
        name=name,
        custom_speaker_id=_gen_custom_speaker_id(user_id, name),
        sample_path="",  # 暂存, 拿到 id 再写文件
        language=language,
        reference_text=reference_text,
        demo_text=demo_text,
        status="training",
        volc_status=1,  # Training
    )
    db.add(profile)
    db.flush()  # 拿 id

    sample_path = _samples_dir(user_id) / f"{profile.id}.{fmt}"
    sample_path.write_bytes(file_bytes)
    profile.sample_path = str(sample_path)

    db.commit()
    db.refresh(profile)

    # C2 阶段: 此处调 _call_volc_train 触发实际训练
    # C1 阶段: 保留 training 状态, 等 C2 异步触发
    return profile


def train_voice(db: Session, profile_id: int, user_id: int) -> UserVoiceProfile:
    """
    触发/重新触发训练 (C2 阶段实现, C1 仅占位)
    """
    profile = db.query(UserVoiceProfile).filter(
        UserVoiceProfile.id == profile_id,
        UserVoiceProfile.user_id == user_id,
        UserVoiceProfile.status != "deleted",
    ).first()
    if not profile:
        raise ValueError("声纹档案不存在")
    if not profile.sample_path or not Path(profile.sample_path).exists():
        raise ValueError("样本文件丢失, 请重新上传")

    sample_bytes = Path(profile.sample_path).read_bytes()
    fmt = Path(profile.sample_path).suffix.lstrip(".")

    result = _call_volc_train(profile, sample_bytes, fmt)

    profile.volc_status = result.get("status", 1)
    profile.available_training_times = result.get("available_training_times", 0)
    profile.error_message = result.get("message") if result.get("code") != 0 else None

    if result.get("status") in (2, 4):  # Success / Active
        profile.status = "active"
        # 保存试听音频
        demo_b64 = result.get("demo_audio")
        if demo_b64:
            demo_path = _demos_dir(user_id) / f"{profile.id}.mp3"
            demo_path.write_bytes(base64.b64decode(demo_b64))
            profile.demo_audio_path = str(demo_path)
    elif result.get("status") == 3:
        profile.status = "failed"

    db.commit()
    db.refresh(profile)
    return profile


def synthesize(
    db: Session,
    custom_speaker_id: Optional[str],
    text: str,
    output_path: Path,
    language: int = 0,
) -> Path:
    """
    TTS 合成: 优先用火山克隆声纹, fallback macOS say
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if custom_speaker_id:
        mp3_bytes = _call_volc_synthesize(custom_speaker_id, text, language)
        if mp3_bytes:
            output_path.write_bytes(mp3_bytes)
            return output_path
        # fallback if volc call failed
    # fallback
    return _fallback_tts(text, output_path)


def test_synthesize(
    db: Session,
    profile_id: int,
    user_id: int,
    text: str,
) -> Path:
    """试听合成 (用 profile 的 custom_speaker_id)"""
    profile = db.query(UserVoiceProfile).filter(
        UserVoiceProfile.id == profile_id,
        UserVoiceProfile.user_id == user_id,
        UserVoiceProfile.status != "deleted",
    ).first()
    if not profile:
        raise ValueError("声纹档案不存在")
    # C1 阶段: 即使 training 状态也允许 fallback 试听, 让用户验证上传链路
    # C2 阶段: 火山真正接好后会用 cloned voice, 没接好就 fallback macOS say
    custom_id = profile.custom_speaker_id if profile.status == "active" else None

    out = _demos_dir(user_id) / f"test_{profile_id}_{int(time.time())}.mp3"
    return synthesize(
        db,
        custom_speaker_id=custom_id,
        text=text or profile.demo_text,
        output_path=out,
        language=profile.language or 0,
    )


def list_profiles(db: Session, user_id: int) -> List[UserVoiceProfile]:
    return db.query(UserVoiceProfile).filter(
        UserVoiceProfile.user_id == user_id,
        UserVoiceProfile.status != "deleted",
    ).order_by(UserVoiceProfile.created_at.desc()).all()


def delete_profile(db: Session, profile_id: int, user_id: int) -> bool:
    profile = db.query(UserVoiceProfile).filter(
        UserVoiceProfile.id == profile_id,
        UserVoiceProfile.user_id == user_id,
    ).first()
    if not profile:
        return False
    # 软删: 保留 DB 记录 + 试听文件, 删除样本文件
    profile.status = "deleted"
    if profile.sample_path and Path(profile.sample_path).exists():
        try:
            Path(profile.sample_path).unlink()
        except OSError:
            pass
    db.commit()
    return True
