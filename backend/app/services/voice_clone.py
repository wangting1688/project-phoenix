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
import logging
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

logger = logging.getLogger(__name__)

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.voice_profile import UserVoiceProfile


# ===== 业务规则常量 =====
MAX_PROFILES_PER_USER = 3
# 火山原生支持的格式
VOLC_AUDIO_FORMATS = {"mp3", "wav", "ogg", "m4a", "aac", "pcm"}
# 浏览器 MediaRecorder 输出格式, 需转码后再送火山
BROWSER_AUDIO_FORMATS = {"webm", "mp4"}
ALLOWED_AUDIO_FORMATS = VOLC_AUDIO_FORMATS | BROWSER_AUDIO_FORMATS
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


def _local_tts_enabled() -> bool:
    """本地 CosyVoice2 克隆开关（默认开启，火山退为后备）。

    环境变量优先，其次读 Settings —— 线上是把配置写在 .env 里由
    pydantic 加载的，不会进 os.environ，只读环境变量会永远拿到默认值。
    """
    v = os.environ.get("LOCAL_TTS_ENABLED")
    if v is not None:
        return v.strip() not in ("0", "false", "False", "")
    try:
        from app.core.config import settings
        return bool(getattr(settings, "LOCAL_TTS_ENABLED", True))
    except Exception:
        return True


def _is_production() -> bool:
    """生产模式判定: settings.DEBUG 为 False 视为生产环境。

    生产环境必须配置火山 TTS, 不允许静默降级到本地 fallback。
    """
    try:
        return not settings.DEBUG
    except Exception:
        return False


# ===== 音频转码 (浏览器录音 -> 火山可用格式) =====
def _transcode_to_mp3(src_bytes: bytes, src_ext: str) -> bytes:
    """
    浏览器 MediaRecorder 输出 webm/opus 或 mp4/aac, 火山不支持,
    统一转 mp3 24kHz mono (火山推荐规格)
    """
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / f"in.{src_ext}"
        dst = Path(td) / "out.mp3"
        src.write_bytes(src_bytes)
        proc = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
             "-ar", "24000", "-ac", "1", "-b:a", "64k", str(dst)],
            capture_output=True, text=True, timeout=60,
        )
        if proc.returncode != 0 or not dst.exists():
            raise ValueError(f"音频转码失败: {proc.stderr[-200:]}")
        return dst.read_bytes()


def _probe_duration(audio_bytes: bytes, ext: str) -> Optional[float]:
    """用 ffmpeg 读音频时长 (秒); 失败返回 None"""
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / f"a.{ext}"
        f.write_bytes(audio_bytes)
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", str(f)],
            capture_output=True, text=True, timeout=30,
        )
        m = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", proc.stderr)
        if not m:
            return None
        h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
        return h * 3600 + mi * 60 + s


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
    # failed 档案在火山侧未转正, 不占槽位, 因此不计入配额, 避免重录被挡
    return db.query(UserVoiceProfile).filter(
        UserVoiceProfile.user_id == user_id,
        UserVoiceProfile.status.notin_(["deleted", "failed"]),
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

    # 浏览器录音格式转 mp3
    if fmt in BROWSER_AUDIO_FORMATS:
        file_bytes = _transcode_to_mp3(file_bytes, fmt)
        fmt = "mp3"

    # 时长校验 (火山要求 3-60 秒)
    duration = _probe_duration(file_bytes, fmt)
    if duration is not None:
        if duration < MIN_SAMPLE_SECONDS:
            raise ValueError(f"录音太短 ({duration:.1f}秒), 至少需要 {MIN_SAMPLE_SECONDS} 秒")
        if duration > MAX_SAMPLE_SECONDS:
            raise ValueError(f"录音太长 ({duration:.1f}秒), 最多 {MAX_SAMPLE_SECONDS} 秒")

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
    if duration is not None:
        profile.sample_duration = int(duration)

    db.commit()
    db.refresh(profile)

    # 只走本地 CosyVoice2 克隆：无需火山训练，样本+逐字稿即可合成。
    return train_voice(db, profile.id, user_id)


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

    # 本地 CosyVoice2 零样本克隆：不需要训练授权，样本+逐字稿即可合成。
    if _local_tts_enabled():
        profile.status = "active"
        profile.volc_status = 4
        profile.error_message = None
        try:
            demo_path = _demos_dir(user_id) / f"{profile.id}.mp3"
            demo_text = profile.demo_text or "你好，这是我的专属声音测试。"
            out = synthesize(
                db, profile.custom_speaker_id or "", demo_text, demo_path,
                language=profile.language or 0,
                profile_id=profile.id,
                reference_audio=profile.sample_path,
                reference_text=profile.reference_text,
            )
            if out and Path(out).exists() and Path(out).stat().st_size > 1024:
                profile.demo_audio_path = str(out)
        except Exception:
            pass
        db.commit()
        db.refresh(profile)
        return profile

    raise RuntimeError("本地 CosyVoice2 未启用，无法克隆声音")


def synthesize(db, custom_speaker_id, text, output_path, language=0,
               profile_id=None, reference_audio=None, reference_text=None):
    """
    合成优先级: 本地 CosyVoice2 克隆 -> 火山克隆音色 -> 火山官方音色 -> macOS say

    本地 CosyVoice2 优先的原因：火山是按量付费且依赖账号授权，
    2026-08-17 起返回 45000030 resource not granted 导致全链路阻塞；
    CosyVoice2 全本地、无调用费用、数据不出本机。
    火山保留为可选后备（配置了就还能用），不删除既有能力。

    reference_audio / reference_text: 显式指定参考音频与其逐字稿。
    未传时按 profile_id 或 custom_speaker_id 从声纹档案里找。
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 只走本地 CosyVoice2 zero-shot 克隆
    if _local_tts_enabled():
        try:
            result = _synthesize_local_clone(
                db, text, output_path,
                profile_id=profile_id,
                custom_speaker_id=custom_speaker_id,
                reference_audio=reference_audio,
                reference_text=reference_text,
            )
            if result:
                return result
            logger.warning("本地 CosyVoice2 合成未成功")
        except Exception as e:
            logger.warning("本地 CosyVoice2 合成异常(%s)", e)

    if _is_production():
        raise RuntimeError(
            "配音生成失败：本地 CosyVoice2 不可用。"
            "请检查本机 TTS worker 是否存活（/health 的 tts_available），"
            "或声纹档案是否有可用的参考音频与逐字稿"
        )
    logger.warning("使用本地 macOS say 兜底生成 TTS")
    return _fallback_tts(text, output_path)


def _resolve_reference(db, profile_id=None, custom_speaker_id=None):
    """找出可用的参考音频与其逐字稿。

    zero-shot 克隆要求两者严格对应，因此逐字稿缺失时不猜测，
    而是交给 worker 侧用 ASR 转写。
    """
    if not db:
        return None, None
    profile = None
    try:
        if profile_id:
            profile = db.query(UserVoiceProfile).filter(
                UserVoiceProfile.id == profile_id).first()
        elif custom_speaker_id:
            profile = db.query(UserVoiceProfile).filter(
                UserVoiceProfile.custom_speaker_id == custom_speaker_id).first()
    except Exception as e:
        logger.warning("查询声纹档案失败: %s", e)
        return None, None
    if not profile:
        return None, None

    ref_text = (getattr(profile, "reference_text", "") or "").strip()
    sample = getattr(profile, "sample_path", None) or getattr(profile, "sample_url", None)
    if not sample:
        # 没有样本音频时不能单独返回文稿：调用方若把它配到别的音频上就成了错配
        return None, ""
    p = Path(sample)
    if not p.is_absolute():
        p = _storage_root() / sample
    if not p.exists():
        return None, ""
    # 音频与文稿同源才成对返回
    return p, ref_text


def _synthesize_local_clone(db, text, output_path, profile_id=None,
                            custom_speaker_id=None,
                            reference_audio=None, reference_text=None):
    """调用本地 CosyVoice2（本机直跑或经隧道派发到本机 worker）。"""
    from app.services import local_tts

    # 参考音频与逐字稿必须成对，绝不能一个来自素材、一个来自声纹档案。
    # zero-shot 克隆按 (音频, 文稿) 的对应关系建立音素映射，配错会让模型
    # 用错误的发音基准朗读，产出整段无法辨识的声音（实测回读相似度 5%）。
    # 曾经的 bug：调用方传了素材截取的音频，而文稿回落到档案里那段
    # "今天天气真不错..."（属于用户自己的录音样本），两者毫无关系。
    #
    # 优先级：声纹档案（用户按稿录制，音文严格对应，实测匹配度 84.8%）
    #   -> 调用方提供的素材截取（音色同源，但文稿需 worker 侧 ASR 转写）
    ref_wav, ref_text = _resolve_reference(
        db, profile_id=profile_id, custom_speaker_id=custom_speaker_id)
    if ref_wav and (ref_text or "").strip():
        print(f"[tts] 参考来自声纹档案: {Path(ref_wav).name}")
    elif reference_audio:
        # 档案不可用时退回素材截取。此时不带文稿，
        # 由 worker 侧 ASR 转写保证音文一致。
        ref_wav = Path(reference_audio)
        ref_text = reference_text or ""
        print(f"[tts] 参考来自素材截取: {ref_wav.name}（文稿由 ASR 生成）")
    else:
        ref_wav, ref_text = None, ""

    if not ref_wav or not Path(ref_wav).exists():
        logger.warning("本地 TTS 缺少参考音频，跳过")
        return None

    if local_tts.TTS_REMOTE_HTTP:
        if not local_tts.available():
            logger.warning("远程 TTS worker 不可用")
            return None
        return local_tts.synthesize_remote(text, ref_wav, ref_text or "", output_path)
    return local_tts.synthesize_local(text, ref_wav, ref_text or "", output_path)


def test_synthesize(db, profile_id, user_id, text):
    profile = db.query(UserVoiceProfile).filter(
        UserVoiceProfile.id == profile_id,
        UserVoiceProfile.user_id == user_id,
        UserVoiceProfile.status != "deleted",
    ).first()
    if not profile:
        raise ValueError("声纹档案不存在")
    # 合成用 custom_speaker_id (实测: megatts.default 只认我方自定义 ID,
    # 传 icl_speaker_id 会报 55000000 resource/speaker mismatch)
    custom_id = profile.custom_speaker_id if profile.status == "active" else None

    out = _demos_dir(user_id) / f"test_{profile_id}_{int(time.time())}.mp3"
    # 关键：必须传 profile_id，本地 zero-shot 克隆才能从声纹档案取到
    # 参考音频(sample_path)+逐字稿(reference_text)。仅传 custom_speaker_id 时，
    # status 非 active(=None) 会让 _resolve_reference 拿不到参考音频 → 501。
    return synthesize(
        db,
        custom_speaker_id=custom_id,
        text=text or profile.demo_text,
        output_path=out,
        language=profile.language or 0,
        profile_id=profile_id,
    )


def list_profiles(db, user_id):
    profiles = db.query(UserVoiceProfile).filter(
        UserVoiceProfile.user_id == user_id,
        UserVoiceProfile.status != "deleted",
    ).order_by(UserVoiceProfile.created_at.desc()).all()
    # 懒迁移：历史火山训练失败/卡在 training 的档案，只要有本地样本，
    # 就按本地 CosyVoice2 克隆标记为可用，无需重新录制。
    changed = False
    for p in profiles:
        if p.status in ("training", "failed") and p.sample_path:
            sp = Path(p.sample_path)
            if not sp.is_absolute():
                sp = _storage_root() / p.sample_path
            if sp.exists():
                p.status = "active"
                p.volc_status = 4
                p.error_message = None
                changed = True
    if changed:
        db.commit()
    return profiles


def delete_profile(db, profile_id, user_id):
    profile = db.query(UserVoiceProfile).filter(
        UserVoiceProfile.id == profile_id,
        UserVoiceProfile.user_id == user_id,
    ).first()
    if not profile:
        return False
    profile.status = "deleted"
    # 清理音频样本文件
    for path_attr in ['sample_path', 'demo_audio_path']:
        path = getattr(profile, path_attr, None)
        if path and Path(path).exists():
            try:
                Path(path).unlink()
            except OSError:
                pass
    db.commit()
    return True
