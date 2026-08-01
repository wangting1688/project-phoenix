"""
火山方舟豆包语音 - HTTP 单向流式 TTS 合成 (已验证可用)

端点: POST /api/v3/tts/unidirectional
鉴权: X-Api-Key + X-Api-App-Id + X-Api-Resource-Id
响应: 换行分隔的流式 JSON, 每行 {"code":0,"data":"<base64音频块>"}
      结束标志 code=20000000

用途:
- 官方精品音色合成 (resource_id=volc.service_type.10029), 已开通可用
- 自定义克隆音色需 volc.megatts.timbre 资源, 待授权
"""
import json
import uuid
import base64
import logging
import urllib.request
import urllib.error
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

PATH = "/api/v3/tts/unidirectional"
RESOURCE_BIGTTS = "volc.service_type.10029"     # 大模型语音合成 (官方音色)
RESOURCE_CLONE_TRAIN = "volc.megatts.timbre"    # 声音复刻 - 训练音色
# 声音复刻 - 合成. 实测: default 走账号自带免费并发额度 (2~5 并发);
# voiceclone 是付费并发资源, 未采购时报 45000292 quota exceeded
RESOURCE_CLONE_SYNTH = "volc.megatts.default"

# 官方默认音色 (声纹未就绪时的兜底)
DEFAULT_SPEAKER = "zh_female_shuangkuaisisi_moon_bigtts"

STREAM_END_CODE = 20000000


def synthesize_http(
    text: str,
    speaker: str = DEFAULT_SPEAKER,
    resource_id: str = RESOURCE_BIGTTS,
    encoding: str = "mp3",
    sample_rate: int = 24000,
) -> Optional[bytes]:
    """
    合成语音, 返回完整音频 bytes; 失败返回 None
    """
    if not settings.VOLC_TTS_API_KEY or not text:
        return None

    url = (settings.VOLC_TTS_BASE_URL or "https://openspeech.bytedance.com").rstrip("/") + PATH
    payload = {
        "user": {"uid": "phx_synth"},
        "req_params": {
            "text": text,
            "speaker": speaker,
            "audio_params": {"format": encoding, "sample_rate": sample_rate},
        },
    }
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": settings.VOLC_TTS_API_KEY,
        "X-Api-App-Id": settings.VOLC_TTS_APP_ID or "",
        "X-Api-Resource-Id": resource_id,
        "X-Api-Request-Id": str(uuid.uuid4()),
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=settings.VOLC_TTS_TIMEOUT or 30) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        logger.warning(f"火山 TTS HTTP {e.code}: {detail}")
        return None
    except Exception as e:
        logger.warning(f"火山 TTS 调用失败: {e}")
        return None

    # 解析流式响应: 每行一个 JSON, data 为 base64 音频块
    chunks = []
    for line in raw.split(b"\n"):
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        code = item.get("code")
        if code == STREAM_END_CODE:
            break
        if code != 0:
            logger.warning(f"火山 TTS 业务错误 code={code} msg={item.get('message')}")
            return None
        data_b64 = item.get("data")
        if data_b64:
            try:
                chunks.append(base64.b64decode(data_b64))
            except Exception:
                continue

    if not chunks:
        logger.warning("火山 TTS 未返回音频数据")
        return None
    return b"".join(chunks)
