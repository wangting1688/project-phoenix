"""
本地 TTS：CosyVoice2 zero-shot 音色克隆（替代火山引擎付费 API）

背景
----
火山 TTS 是按量付费且依赖账号授权，2026-08-17 起返回
`45000030 requested resource not granted`（官方音色与克隆音色均被拒），
整条生产链路因此阻塞。CosyVoice2 全本地运行、无调用费用、数据不出本机。

方案
----
模型在本机 GPU（RTX 5090），而生产后端在 Linux 云主机，因此复用口型同步
已有的架构：本机 worker 暴露 HTTP 端点，线上经反向 SSH 隧道派发。
- 线上（本模块 remote 分支）：POST /tts，拿回 mp3
- 本机（worker）：调用 CosyVoice2 合成

zero-shot 克隆只需一段参考音频 + 该段的逐字文稿，无需训练。

关键约束（来自对照项目的实测教训，违反会直接产出乱码）
----------------------------------------------------
1. `ref_text` 必须是参考音频的**真实逐字内容**。音文错配会让模型把错误的
   音素映射当作发音基准，输出整段无法辨识的声音。所以本模块在没有可信
   文稿时，用 ASR 转写参考音频，绝不凭猜测填写。
2. CosyVoice2 自带的 `speed` 参数**不单调**（实测 1.45 -> 4.66 字/秒，
   但 1.6 -> 2.84）。因此一律 speed=1.0 合成，再用 ffmpeg atempo
   精确命中目标语速（变速不变调）。
3. `inference_zero_shot` 的 prompt 必须传**文件路径**，不能传预加载 tensor
   （内部会以 24k 重新 load_wav，传 tensor 报 TypeError）。
4. 变速倍率控制在 1.5 倍以内。需要更大倍率说明原生语速异常，
   应先检查参考音频与文稿是否匹配，而不是硬拉。
"""
import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import Optional, Tuple

FFMPEG = os.environ.get("FFMPEG_BIN", "ffmpeg")


def _cfg(name: str, default: str = "") -> str:
    """读配置：先看环境变量，再回落到 pydantic Settings（.env 由它加载）。

    本模块在两种进程里运行：本机 worker（按路径直加载，只有环境变量）
    和线上后端（.env 经 Settings 加载，不进 os.environ）。
    只读 os.environ 会导致线上拿不到 TTS_REMOTE_HTTP 而误判服务不可用。
    """
    v = os.environ.get(name)
    if v:
        return v.strip()
    try:
        from app.core.config import settings
        v = getattr(settings, name, None)
        if v is not None:
            return str(v).strip()
    except Exception:
        pass
    return default


# 远程本地 TTS 服务地址（线上经反向隧道指向本机 worker）
TTS_REMOTE_HTTP = _cfg("TTS_REMOTE_HTTP")
# 首个请求要加载 5.4GB 权重（约 3 分钟），超时必须给足余量；
# 之前设 1800 秒仍偶发失败是因为上游 HTTP 层先断，不是这里不够。
TTS_HTTP_TIMEOUT = int(_cfg("TTS_HTTP_TIMEOUT", "1800"))

# 本机 CosyVoice2 位置
COSY_DIR = os.environ.get("COSY_DIR", r"D:/luogen_demo/CosyVoice")
COSY_MODEL = os.environ.get(
    "COSY_MODEL", os.path.join(COSY_DIR, "pretrained_models", "CosyVoice2-0.5B"))
# CosyVoice2 的依赖（hyperpyyaml/conformer/wetext/matcha 等）装在全局 Python 3.11，
# 不在本项目的 .venv_lipsync 里。与 luogen 引擎同样的处理：用子进程调它自己的
# 解释器，避免把两套依赖强行塞进同一个环境（numpy 版本尤其容易互相顶掉）。
COSY_PY = os.environ.get(
    "COSY_PY",
    r"C:/Users/ProArt/AppData/Local/Programs/Python/Python311/python.exe")

# 参考音频截取位置。避开素材开头（常有寒暄/停顿），取语音较稳的一段。
TTS_REF_START = float(os.environ.get("TTS_REF_START", "14"))
TTS_REF_DURATION = float(os.environ.get("TTS_REF_DURATION", "12"))

# 目标语速（字/秒）。自然口播约 4.5~5.0，低于 3 会明显拖沓。
TTS_TARGET_CPS = float(os.environ.get("TTS_TARGET_CPS", "4.4"))
# 单次变速上限，超过说明参考音频可能有问题
TTS_MAX_TEMPO = float(os.environ.get("TTS_MAX_TEMPO", "1.5"))


# ---------------------------------------------------------------------------
# 文本切分
# ---------------------------------------------------------------------------

def split_sentences(text: str, max_len: int = 60, min_len: int = 24):
    """把文案切成合成单元。

    每个切分点都会产生一次可听的停顿，所以按句号逐句切会让口播显得碎而慢。
    这里把短句合并到至少 min_len 字，兼顾韵律连贯与模型可处理长度。
    """
    text = re.sub(r"\s+", "", text or "")
    if not text:
        return []
    parts = [p for p in re.split(r"(?<=[。！？；])", text) if p.strip()]

    merged, buf = [], ""
    for p in parts:
        if len(buf) + len(p) <= max_len and len(buf) < min_len:
            buf += p
        else:
            if buf:
                merged.append(buf)
            buf = p
    if buf:
        merged.append(buf)

    out = []
    for p in merged:
        while len(p) > max_len:
            cut = max((p.rfind(c, 0, max_len) for c in "，、,"), default=-1)
            if cut <= 10:
                cut = max_len
            out.append(p[:cut + 1])
            p = p[cut + 1:]
        if p:
            out.append(p)
    return out


def _char_count(text: str) -> int:
    return len(re.sub(r"[\s，。、！？；：,.!?;:\"'（）()]", "", text or ""))


def measure_pace(wav_path, text) -> Tuple[float, float, int]:
    """返回 (字/秒, 时长秒, 字数)。"""
    import soundfile as sf
    a, sr = sf.read(str(wav_path))
    dur = len(a) / sr
    chars = _char_count(text)
    return chars / max(dur, 1e-6), dur, chars


def tempo_stretch(in_path, out_path, factor: float) -> Path:
    """用 atempo 变速不变调。atempo 单级稳定区间 0.5~2.0，超出则串联。"""
    f = float(factor)
    chain = []
    while f > 2.0:
        chain.append("atempo=2.0")
        f /= 2.0
    while f < 0.5:
        chain.append("atempo=0.5")
        f /= 0.5
    chain.append(f"atempo={f:.4f}")
    r = subprocess.run(
        [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(in_path),
         "-filter:a", ",".join(chain), str(out_path)],
        capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"atempo 失败: {r.stderr[-400:]}")
    return Path(out_path)


# ---------------------------------------------------------------------------
# 参考音频与逐字稿
# ---------------------------------------------------------------------------

def extract_reference(video_or_audio, out_wav, start: float = 0.0,
                      duration: float = 12.0) -> Optional[Path]:
    """从素材里截一段 16k 单声道参考音频。

    参考音频取自与视频同一条素材，音色天然匹配；12 秒足够 zero-shot 克隆。
    """
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
         "-ss", str(start), "-t", str(duration), "-i", str(video_or_audio),
         "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(out_wav)],
        capture_output=True, text=True, timeout=300)
    if r.returncode != 0 or not out_wav.exists() or out_wav.stat().st_size == 0:
        print(f"[tts] 参考音频提取失败: {r.stderr[-300:]}")
        return None
    return out_wav


def verify_intelligibility(audio_path, expect_text: str,
                           threshold: float = 0.55) -> Tuple[bool, float, str]:
    """用 ASR 回读合成音频，判断内容是否可辨识。

    这是可自动化的质量门禁：机器都听不懂，人一定也听不懂。
    典型故障是参考音频与其逐字稿不匹配（例如上游传了空文稿），
    此时模型会按错误的音素映射发音，输出整段乱码——而任务状态仍是成功，
    乱码会一路进到成片。所以在返回前必须验一次。

    阈值 0.55 偏宽松：中文同音字很多，ASR 本身也会写错字
    （实测正常合成约 77%~88%，乱码约 10% 以下），足以区分两者。
    """
    import difflib
    try:
        got = transcribe(audio_path)
    except Exception as e:
        # 门禁自身故障不应拦住正常合成，放行并留下记录
        print(f"[tts] 回读校验跳过（ASR 失败: {e}）")
        return True, 1.0, ""
    strip = lambda t: re.sub(r"[\s，。、！？；：,.!?;:\"'（）()]", "", t or "")
    want, real = strip(expect_text), strip(got)
    if not want or not real:
        return False, 0.0, got
    ratio = difflib.SequenceMatcher(None, want, real).ratio()
    ok = ratio >= threshold
    print(f"[tts] 回读校验 {'通过' if ok else '未通过'}: 相似度 {ratio*100:.1f}% "
          f"(阈值 {threshold*100:.0f}%)")
    if not ok:
        print(f"[tts]   期望: {want[:60]}")
        print(f"[tts]   回读: {real[:60]}")
    return ok, ratio, got


def pick_reference(video_or_audio, work_dir, duration: float = 12.0,
                   candidates=(6.0, 14.0, 18.0)) -> Tuple[Optional[Path], str]:
    """从素材里挑一段最合适的参考音频，并给出它的逐字稿。

    不同区间的发音清晰度差别很大，直接影响克隆质量与原生语速。
    实测同一条素材：起点 6s 的原生语速 3.02 字/秒（需 1.46 倍变速，接近上限
    且损伤可听度），而起点 18s 只需 1.29 倍，ASR 回读相似度也更高
    （77.4% vs 64.5%）。所以这里按"ASR 转写字数最多"来选——
    字数多说明这段语音密度高、吐字清楚，原生语速也更接近自然值。
    """
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    best = (None, "", 0)
    for start in candidates:
        wav = work_dir / f"ref_{int(start)}.wav"
        if not extract_reference(video_or_audio, wav, start=start, duration=duration):
            continue
        try:
            text = transcribe(wav)
        except Exception as e:
            print(f"[tts] 参考段 {start}s 转写失败: {e}")
            continue
        n = _char_count(text)
        print(f"[tts] 候选参考 {start}s: {n} 字")
        if n > best[2]:
            best = (wav, text, n)
    if best[0] is None:
        # 全部失败时退回固定区间，至少给出一个可用参考
        wav = work_dir / "ref_fallback.wav"
        if extract_reference(video_or_audio, wav, start=candidates[0], duration=duration):
            return wav, ""
        return None, ""
    print(f"[tts] 选用参考音频: {best[0].name}（{best[2]} 字）")
    return best[0], best[1]


def transcribe(audio_path, model_size: str = "base") -> str:
    """用 whisper 转写参考音频，得到逐字稿。

    绝不能凭想象填 ref_text：音文错配会让 zero-shot 克隆输出乱码。
    """
    ff_dir = str(Path(FFMPEG).parent)
    if ff_dir and ff_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ff_dir + os.pathsep + os.environ.get("PATH", "")
    import whisper
    model = whisper.load_model(model_size)
    res = model.transcribe(str(audio_path), language="zh", fp16=False)
    text = re.sub(r"\s+", "", res.get("text", ""))
    print(f"[tts] ASR 转写参考音频: {text[:60]}")
    return text


# ---------------------------------------------------------------------------
# 本机合成（worker 侧执行）
# ---------------------------------------------------------------------------

_model = None


def _load_model():
    """加载 CosyVoice2 并常驻（约 5.4GB 权重，避免每次任务重复加载）。"""
    global _model
    if _model is not None:
        return _model
    import sys
    # Matcha-TTS 必须先入 sys.path，CosyVoice 内部依赖它
    for p in (os.path.join(COSY_DIR, "third_party", "Matcha-TTS"), COSY_DIR):
        if p not in sys.path:
            sys.path.insert(0, p)
    from cosyvoice.cli.cosyvoice import CosyVoice2
    print(f"[tts] 加载 CosyVoice2: {COSY_MODEL}")
    _model = CosyVoice2(COSY_MODEL, load_jit=False, load_trt=False, fp16=False)
    print("[tts] CosyVoice2 加载完成，常驻内存")
    return _model


def synthesize_local(text: str, ref_wav, ref_text: str, out_path,
                     target_cps: Optional[float] = None) -> Optional[Path]:
    """本机合成入口：转交给 CosyVoice2 自己的解释器执行。"""
    ref_wav = Path(ref_wav)
    out_path = Path(out_path)
    if not ref_wav.exists():
        print(f"[tts] 参考音频不存在: {ref_wav}")
        return None
    if not (ref_text or "").strip():
        # 空文稿绝不放行：zero-shot 会按错误音素映射发音，输出整段乱码。
        # 上游若拿不到文稿，应把音频交给 worker 侧 ASR，而不是传空串。
        print("[tts] 缺少参考音频逐字稿(ref_text)，拒绝合成")
        return None
    if not Path(COSY_PY).exists():
        print(f"[tts] CosyVoice 解释器不存在: {COSY_PY}")
        return None

    out_path.parent.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).resolve().parent / "cosyvoice_runner.py"
    cmd = [COSY_PY, "-u", str(script),
           "--ref-wav", str(ref_wav.resolve()),
           "--out", str(out_path.resolve()),
           "--target-cps", str(target_cps if target_cps is not None else TTS_TARGET_CPS),
           "--max-tempo", str(TTS_MAX_TEMPO)]
    env = os.environ.copy()
    env["PATH"] = str(Path(FFMPEG).parent) + os.pathsep + env.get("PATH", "")
    env["COSY_DIR"] = COSY_DIR
    env["COSY_MODEL"] = COSY_MODEL
    env["FFMPEG_BIN"] = FFMPEG
    for k in ("PYTHONPATH", "PYTHONHOME"):
        env.pop(k, None)

    # 文案与逐字稿走 stdin，避免命令行长度限制与引号转义问题
    payload = (text or "") + "\n\x00SPLIT\x00\n" + (ref_text or "")
    proc = subprocess.run(cmd, input=payload, env=env,
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          timeout=int(os.environ.get("TTS_LOCAL_TIMEOUT", "1800")))
    if proc.stdout:
        for line in proc.stdout.splitlines()[-12:]:
            print(f"[tts] {line}")
    if not (out_path.exists() and out_path.stat().st_size > 0):
        tail = (proc.stderr or proc.stdout or "")[-800:]
        print(f"[tts] 合成失败 rc={proc.returncode}\n{tail}")
        return None
    return out_path


def _synthesize_inproc(text: str, ref_wav, ref_text: str, out_path,
                       target_cps: Optional[float] = None) -> Optional[Path]:
    """在 CosyVoice2 自己的解释器内执行（由 cosyvoice_runner.py 调用）。"""
    import torch
    import torchaudio

    ref_wav = Path(ref_wav)
    if not ref_wav.exists():
        print(f"[tts] 参考音频不存在: {ref_wav}")
        return None
    if not (ref_text or "").strip():
        # 没有逐字稿时宁可失败也不瞎填：错配会输出乱码
        print("[tts] 缺少参考音频逐字稿(ref_text)，拒绝合成")
        return None

    sents = split_sentences(text)
    if not sents:
        print("[tts] 文案为空")
        return None

    model = _load_model()
    # prompt 必须是路径字符串：CosyVoice2 内部会以 24k 重新 load_wav
    prompt = str(ref_wav.resolve())

    print(f"[tts] 合成 {len(sents)} 段")
    chunks = []
    for i, s in enumerate(sents, 1):
        for r in model.inference_zero_shot(s, ref_text, prompt,
                                           stream=False, speed=1.0):
            chunks.append(r["tts_speech"])
        print(f"[tts]   [{i}/{len(sents)}] {s[:20]}")
    if not chunks:
        print("[tts] 未产出音频")
        return None

    audio = torch.cat(chunks, dim=1)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    raw_wav = out_path.with_suffix(".raw.wav")
    torchaudio.save(str(raw_wav), audio, model.sample_rate)

    # 语速矫正：speed=1.0 合成后用 atempo 精确命中目标
    final_wav = raw_wav
    cps = target_cps if target_cps is not None else TTS_TARGET_CPS
    if cps:
        cur, dur, chars = measure_pace(raw_wav, text)
        factor = cps / cur if cur > 0 else 1.0
        if factor > TTS_MAX_TEMPO:
            # 说明原生语速异常慢，多半是参考音频/文稿有问题，硬拉会损伤可听度
            print(f"[tts] 原生语速仅 {cur:.2f} 字/秒，需 x{factor:.2f} 超过上限 "
                  f"{TTS_MAX_TEMPO}，截断到上限（请检查参考音频与逐字稿是否匹配）")
            factor = TTS_MAX_TEMPO
        if abs(factor - 1.0) > 0.02:
            sped = out_path.with_suffix(".sped.wav")
            tempo_stretch(raw_wav, sped, factor)
            final_wav = sped
            new_cps, dur, _ = measure_pace(final_wav, text)
            print(f"[tts] 语速 {cur:.2f} -> {new_cps:.2f} 字/秒 (x{factor:.3f})")

    # 交付 mp3：与既有链路一致（火山返回的也是 mp3）
    r = subprocess.run(
        [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(final_wav),
         "-ar", "16000", "-ac", "1", "-b:a", "64k", str(out_path)],
        capture_output=True, text=True, timeout=600)
    for tmp in {raw_wav, final_wav}:
        try:
            tmp.unlink()
        except OSError:
            pass
    if r.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
        print(f"[tts] 转 mp3 失败: {r.stderr[-300:]}")
        return None
    return out_path


# ---------------------------------------------------------------------------
# 远程派发（线上后端 -> 本机 worker）
# ---------------------------------------------------------------------------

def available() -> bool:
    """远程 TTS 服务是否可用。"""
    if not TTS_REMOTE_HTTP:
        return False
    try:
        import urllib.request
        with urllib.request.urlopen(
                TTS_REMOTE_HTTP.rstrip("/") + "/health", timeout=10) as r:
            if r.status != 200:
                return False
            import json
            data = json.loads(r.read().decode("utf-8", "replace"))
            return bool(data.get("tts_available"))
    except Exception as e:
        print(f"[tts] 远程 TTS 服务不可用: {e}")
        return False


def _looks_like_audio(data: bytes, content_type: str = "") -> bool:
    """确认响应体是音频而不是错误 JSON。

    同口型链路的教训：错误响应被当成媒体文件落盘，故障会被推迟到下游才暴露。
    """
    if len(data) < 256:
        return False
    if content_type and "json" in content_type.lower():
        return False
    if data[:1] in (b"{", b"["):
        return False
    # mp3: ID3 标签或帧同步字
    return data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")


def synthesize_remote(text: str, ref_wav, ref_text: str, out_path) -> Optional[Path]:
    """把合成请求经隧道派发到本机 worker。"""
    import urllib.error
    import urllib.request

    ref_wav = Path(ref_wav)
    base = TTS_REMOTE_HTTP.rstrip("/")
    boundary = "----phx_tts_%s" % uuid.uuid4().hex

    def _field(name, value):
        return (f"--{boundary}\r\nContent-Disposition: form-data; "
                f'name="{name}"\r\n\r\n{value}\r\n').encode()

    def _file(name, filename, data, ctype):
        head = (f"--{boundary}\r\nContent-Disposition: form-data; "
                f'name="{name}"; filename="{filename}"\r\n'
                f"Content-Type: {ctype}\r\n\r\n").encode()
        return head + data + b"\r\n"

    try:
        body = (_field("text", text)
                + _field("ref_text", ref_text or "")
                + _file("ref_wav", "ref.wav", ref_wav.read_bytes(), "audio/wav")
                + f"--{boundary}--\r\n".encode())
    except Exception as e:
        print(f"[tts] 读取参考音频失败: {e}")
        return None

    req = urllib.request.Request(base + "/tts", data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        try:
            with urllib.request.urlopen(req, timeout=TTS_HTTP_TIMEOUT) as r:
                data = r.read()
                ctype = r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            print(f"[tts] 远程 HTTP {e.code}: {e.read()[:300]}")
            return None
        if not _looks_like_audio(data, ctype):
            print(f"[tts] 远程未返回音频(ctype={ctype!r}): {data[:200]}")
            return None
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)
        return out_path
    except Exception as e:
        print(f"[tts] 远程合成失败: {e}")
        return None
