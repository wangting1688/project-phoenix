"""
用户声纹服务 - 火山方舟豆包语音 Voice Cloning

调用关系:
- 训练: POST {BASE_URL}/api/v3/tts/voice_clone
        Header: Content-Type=application/json, X-Api-Key=<key>, X-Api-Request-Id=<uuid>
        Body:   { speaker_id: "custom_speaker_id", custom_speaker_id,
                  audio: { data: <base64>, format }, text, language, ... }
        Response: { code, message, status (1=Training 2=Success 3=Failed 4=Active),
                    available_training_times, demo_audio }
- 合成: POST {BASE_URL}/api/v3/tts
        Header: X-Api-Key, X-Api-Request-Id
        Body:   { app:{appid,token,cluster}, user:{uid}, audio:{voice_type,encoding,...},
                  request:{reqid,text,text_type,operation}, speaker_id, custom_speaker_id }
        Response.data: base64 mp3

行为约定:
- 任何一步缺配置/调用失败, 自动降级到 macOS say fallback, 不阻塞业务
- 训练接口的成功状态码 2/4 才标记 profile.status='active'
"""
import os
import re
import uuid
import shutil
import subprocess
import tempfile
import time
import base64
import json
import urllib.request
import urllib.error
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
    return Path(settings.STORAGE_PATH).resolve()


def _samples_dir(user_id: int) -> Path:
    d = _storage_root() / "voice_samples" / str(user_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _demos_dir(user_id: int) -> Path:
    d = _storage_root() / "voice_demos" / str(user_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _is_volc_configured() -> bool:
    """训练/合成共用同一 X-Api-Key, 一个就够"""
    return bool(settings.VOLC_TTS_API_KEY) and bool(settings.VOLC_TTS_BASE_URL)


def _volc_post(path: str, body: Dict[str, Any], timeout: int = None) -> Dict[str, Any]:
    """
    统一封装: 调火山 openspeech REST 接口
    返回 dict (含 code/message 等字段); 失败抛 RuntimeError
    """
    if not _is_volc_configured():
        raise RuntimeError("火山语音未配置 (缺 VOLC_TTS_API_KEY)")
    url = settings.VOLC_TTS_BASE_URL.rstrip("/") + path
    data = json.dumps(body).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": settings.VOLC_TTS_API_KEY,
        "X-Api-Request-Id": str(uuid.uuid4()),
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    timeout = timeout or settings.VOLC_TTS_TIMEOUT
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # 火山业务错误也带 code/message, 解析出来
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            raise RuntimeError(f"HTTP {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"网络错误: {e.reason}")
    except TimeoutError:
        raise RuntimeError(f"调用超时 (>{timeout}s)")


# ===== 训练接口 =====
def _call_volc_train(profile: UserVoiceProfile, sample_bytes: bytes, sample_format: str,
                     reference_text: str = "") -> Dict[str, Any]:
    """
    调火山方舟 voice_clone 训练接口
    返回字段:
      code (0=成功/业务错), status (1/2/3/4), message, available_training_times, demo_audio
    """
    body = {
        "speaker_id": "custom_speaker_id",  # 固定值
        "custom_speaker_id": profile.custom_speaker_id,
        "audio": {
            "data": base64.b64encode(sample_bytes).decode("ascii"),
            "format": sample_format,
        },
        "text": reference_text or profile.reference_text or "",
        "language": profile.language or 0,
        "demo_text": profile.demo_text,
    }
    resp = _volc_post("/api/v3/tts/voice_clone", body, timeout=30)
    # 火山统一返回 {code, message, ...业务字段}
    if resp.get("code") != 0 and resp.get("code") is not None:
        # 业务错, 包装回, 让上层标记 failed
        return {
            "code": resp.get("code", -1),
            "message": resp.get("message", "训练失败"),
            "status": 3,  # Failed
            "available_training_times": resp.get("available_training_times", 0),
            "demo_audio": None,
        }
    return {
        "code": 0,
        "message": resp.get("message", "ok"),
        "status": resp.get("status", 1),  # 1=Training 2=Success 3=Failed 4=Active
        "available_training_times": resp.get("available_training_times", 0),
        "demo_audio": resp.get("demo_audio"),
    }


# ===== TTS 合成接口 =====
def _call_volc_synthesize(custom_speaker_id: str, text: str, lang: int = 0) -> Optional[bytes]:
    """
    调火山方舟 TTS 合成 (声音复刻 2.0 走 WebSocket 双向流式)
    失败/未配置 返回 None (让上层走 fallback)
    """
    if not _is_volc_configured() or not custom_speaker_id:
        return None
    from app.services.volc.tts_ws import synthesize_ws
    return synthesize_ws(custom_speaker_id, text, encoding="mp3")


# ===== macOS say fallback (本地 dev) =====
def _fallback_tts(text: str, output_path: Path) -> Path:
    """macOS `say` 生成语音, ffmpeg 转 mp3. 非 macOS 抛 NotImplementedError"""
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
    """生成符合火山命名规范的 custom_speaker_id (8-256 字符, 字母开头)"""
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "", name)[:30] or "voice"
    suffix = uuid.uuid4().hex[:12]
    return f"phx_{user_id}_{safe_name}_{suffix}"


def upload_sample(db, user_id, file_bytes, filename, name, demo_text, language=0, reference_text=""):
    if not file_bytes or len(file_bytes) < 1024:
        raise ValueError("样本文件过小 (<1KB), 请重新上传")
    if len(file_bytes) > MAX_SAMPLE_BYTES:
        raise ValueError(f"样本文件过大 (>{MAX_SAMPLE_BYTES // 1024 // 1024}MB)")
    if _count_user_profiles(db, user_id) >= MAX_PROFILES_PER_USER:
        raise ValueError(f"最多 {MAX_PROFILES_PER_USER} 个声纹档案")
    fmt = _validate_audio_format(filename)
    if not name or len(name) > 100:
        raise ValueError("声纹名字 1-100 字符")
    if not demo_text or len(demo_text) > 300 or len(demo_text) < 4:
        raise ValueError("试听文本需 4-300 字")

    profile = UserVoiceProfile(
        user_id=user_id,
        name=name,
        custom_speaker_id=_gen_custom_speaker_id(user_id, name),
        sample_path="",
        language=language,
        reference_text=reference_text,
        demo_text=demo_text,
        status="training",
        volc_status=1,
    )
    db.add(profile)
    db.flush()

    sample_path = _samples_dir(user_id) / f"{profile.id}.{fmt}"
    sample_path.write_bytes(file_bytes)
    profile.sample_path = str(sample_path)

    db.commit()
    db.refresh(profile)

    # 火山配置齐时立即触发训练; 否则保留 training 状态
    if _is_volc_configured():
        try:
            return train_voice(db, profile.id, user_id)
        except Exception:
            # 训练失败保留 training, 不阻塞上传
            return profile
    return profile


def train_voice(db, profile_id, user_id):
    profile = db.query(UserVoiceProfile).filter(
        UserVoiceProfile.id == profile_id,
        UserVoiceProfile.user_id == user_id,
        UserVoiceProfile.status != "deleted",
    ).first()
    if not profile:
        raise ValueError("声纹档案不存在")
    if not profile.sample_path or not Path(profile.sample_path).exists():
        raise ValueError("样本文件丢失, 请重新上传")

    if not _is_volc_configured():
        # 未配置火山, 保持 training 占位, 给前端明确提示
        profile.error_message = "火山语音未配置 (缺 VOLC_TTS_API_KEY), 当前走 fallback"
        db.commit()
        db.refresh(profile)
        return profile

    sample_bytes = Path(profile.sample_path).read_bytes()
    fmt = Path(profile.sample_path).suffix.lstrip(".")

    try:
        result = _call_volc_train(profile, sample_bytes, fmt, profile.reference_text or "")
    except Exception as e:
        profile.error_message = f"训练调用失败: {e}"
        profile.volc_status = 3  # Failed
        profile.status = "failed"
        db.commit()
        db.refresh(profile)
        return profile

    profile.volc_status = result.get("status", 1)
    profile.available_training_times = result.get("available_training_times", 0)
    if result.get("code") != 0:
        profile.error_message = result.get("message", "训练失败")
    else:
        profile.error_message = None

    if result.get("status") in (2, 4):  # Success / Active
        profile.status = "active"
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


def synthesize(db, custom_speaker_id, text, output_path, language=0):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if custom_speaker_id and _is_volc_configured():
        mp3_bytes = _call_volc_synthesize(custom_speaker_id, text, language)
        if mp3_bytes:
            output_path.write_bytes(mp3_bytes)
            return output_path
        # fallback below
    return _fallback_tts(text, output_path)


def test_synthesize(db, profile_id, user_id, text):
    profile = db.query(UserVoiceProfile).filter(
        UserVoiceProfile.id == profile_id,
        UserVoiceProfile.user_id == user_id,
        UserVoiceProfile.status != "deleted",
    ).first()
    if not profile:
        raise ValueError("声纹档案不存在")
    custom_id = profile.custom_speaker_id if profile.status == "active" else None

    out = _demos_dir(user_id) / f"test_{profile_id}_{int(time.time())}.mp3"
    return synthesize(
        db,
        custom_speaker_id=custom_id,
        text=text or profile.demo_text,
        output_path=out,
        language=profile.language or 0,
    )


def list_profiles(db, user_id):
    return db.query(UserVoiceProfile).filter(
        UserVoiceProfile.user_id == user_id,
        UserVoiceProfile.status != "deleted",
    ).order_by(UserVoiceProfile.created_at.desc()).all()


def delete_profile(db, profile_id, user_id):
    profile = db.query(UserVoiceProfile).filter(
        UserVoiceProfile.id == profile_id,
        UserVoiceProfile.user_id == user_id,
    ).first()
    if not profile:
        return False
    profile.status = "deleted"
    if profile.sample_path and Path(profile.sample_path).exists():
        try:
            Path(profile.sample_path).unlink()
        except OSError:
            pass
    db.commit()
    return True
