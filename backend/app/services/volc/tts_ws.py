"""
火山方舟豆包语音 - WebSocket 双向流式 TTS 合成

声音复刻 2.0 的合成走 WS 二进制协议 (HTTP /api/v3/tts 不存在):
  端点: wss://openspeech.bytedance.com/api/v3/tts/bidirection
  鉴权: header X-Api-Key / X-Api-App-Id / X-Api-Resource-Id
  流程: StartConnection -> StartSession(音色/编码) -> TaskRequest(文本)
        -> FinishSession -> 收 TTSResponse 音频帧 -> SessionFinished

对外只暴露 synthesize_ws(), 内部同步封装 (业务侧是同步 SQLAlchemy 代码)
"""
import asyncio
import json
import uuid
import logging
from typing import Optional

from app.core.config import settings
from app.services.volc.tts_protocol import (
    EventType,
    MsgType,
    receive_message,
    start_connection,
    start_session,
    task_request,
    finish_session,
    finish_connection,
)

logger = logging.getLogger(__name__)

WS_PATH = "/api/v3/tts/bidirection"
RESOURCE_ID = "volc.megatts.timbre"  # 声音复刻音色资源


def _ws_url() -> str:
    base = (settings.VOLC_TTS_BASE_URL or "https://openspeech.bytedance.com").rstrip("/")
    return base.replace("https://", "wss://").replace("http://", "ws://") + WS_PATH


def _ws_headers() -> dict:
    return {
        "X-Api-Key": settings.VOLC_TTS_API_KEY or "",
        "X-Api-App-Id": settings.VOLC_TTS_APP_ID or "",
        "X-Api-Resource-Id": RESOURCE_ID,
        "X-Api-Request-Id": str(uuid.uuid4()),
    }


async def _synthesize_async(custom_speaker_id: str, text: str, encoding: str = "mp3",
                            timeout: int = 30) -> bytes:
    """WS 合成核心: 返回完整音频 bytes; 失败抛异常"""
    import websockets

    session_id = str(uuid.uuid4())
    audio_chunks = []

    async with websockets.connect(
        _ws_url(), additional_headers=_ws_headers(),
        open_timeout=timeout, close_timeout=5, max_size=None,
    ) as ws:
        # 1. 建连接
        await start_connection(ws)
        msg = await receive_message(ws)
        if msg.event != EventType.ConnectionStarted:
            raise RuntimeError(f"建连接失败: {msg}")

        # 2. 开会话 (指定音色 + 音频格式)
        session_payload = json.dumps({
            "user": {"uid": "phx_synth"},
            "req_params": {
                "speaker": custom_speaker_id,
                "audio_params": {"format": encoding, "sample_rate": 24000},
            },
        }).encode()
        await start_session(ws, session_payload, session_id)
        msg = await receive_message(ws)
        if msg.event != EventType.SessionStarted:
            raise RuntimeError(f"开会话失败: {msg}")

        # 3. 送文本
        await task_request(ws, json.dumps({
            "user": {"uid": "phx_synth"},
            "req_params": {
                "text": text,
                "speaker": custom_speaker_id,
                "audio_params": {"format": encoding, "sample_rate": 24000},
            },
        }).encode(), session_id)
        await finish_session(ws, session_id)

        # 4. 收音频帧直到会话结束
        while True:
            msg = await receive_message(ws)
            if msg.type == MsgType.AudioOnlyServer and msg.event == EventType.TTSResponse:
                audio_chunks.append(msg.payload)
            elif msg.event == EventType.SessionFinished:
                break
            elif msg.event == EventType.SessionFailed or msg.type == MsgType.Error:
                raise RuntimeError(f"合成失败: {msg}")

        await finish_connection(ws)

    if not audio_chunks:
        raise RuntimeError("未收到音频数据")
    return b"".join(audio_chunks)


def synthesize_ws(custom_speaker_id: str, text: str, encoding: str = "mp3") -> Optional[bytes]:
    """
    同步入口: 成功返回音频 bytes, 任何失败返回 None (让上层 fallback)
    """
    if not settings.VOLC_TTS_API_KEY or not custom_speaker_id or not text:
        return None
    timeout = settings.VOLC_TTS_TIMEOUT or 30
    try:
        return asyncio.run(
            asyncio.wait_for(
                _synthesize_async(custom_speaker_id, text, encoding, timeout),
                timeout=timeout,
            )
        )
    except Exception as e:
        logger.warning(f"WS TTS 合成失败, 走 fallback: {e}")
        return None
