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
import time
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

# 合成片段的最小净字数。低于它的片段会被并到相邻段：
# 一是回读门禁在极短文本上统计样本太小容易误杀，二是听感上像结巴。
# 与 verify_intelligibility 里的短句豁免阈值保持同一个数量级。
PREF_MIN_CHARS = int(os.environ.get("TTS_PREF_MIN_CHARS", "8"))


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

    # 尾句过短时回并到前一句：本地合成是按段生成的，一段只剩 3~5 个字时，
    # 回读门禁的相似度统计样本太小（3 个字错 1 个就掉到 33%），容易被误杀。
    # 仅在不超上限时合并，避免把两段拼成模型难处理的超长句。
    if (len(merged) >= 2 and _char_count(merged[-1]) < PREF_MIN_CHARS
            and len(merged[-2]) + len(merged[-1]) <= max_len):
        merged[-2] = merged[-2] + merged[-1]
        merged.pop()

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


def _to_simplified(text: str) -> str:
    """繁体转简体。缺库时原样返回，不因此让门禁失效。"""
    if not text:
        return text
    try:
        import zhconv
        return zhconv.convert(text, "zh-cn")
    except Exception:
        return text


def verify_intelligibility(audio_path, expect_text: str,
                           threshold: Optional[float] = None) -> Tuple[bool, float, str]:
    """用 ASR 回读合成音频，判断内容是否可辨识。

    这是可自动化的质量门禁：机器都听不懂，人一定也听不懂。
    典型故障是参考音频与其逐字稿不匹配（例如上游传了空文稿），
    此时模型会按错误的音素映射发音，输出整段乱码——而任务状态仍是成功，
    乱码会一路进到成片。所以在返回前必须验一次。

    阈值默认 0.50（可用 TTS_INTELLIGIBILITY_THRESHOLD 覆盖）：
    中文同音字多，ASR 本身也会写错字（实测正常 77%~88%，乱码约 10% 以下）。
    个别句子在 50% 上下属于勉强可辨识，放行；明显乱码仍会被拦。

    净字数 < 8 的片段走另一条判据（字符覆盖率 ≥ 50%），原因见下方注释：
    样本太小，SequenceMatcher 会稳定误杀正常音频。
    """
    if threshold is None:
        threshold = float(os.environ.get("TTS_INTELLIGIBILITY_THRESHOLD", "0.50"))
    import difflib
    try:
        got = transcribe(audio_path)
    except Exception as e:
        # 门禁自身故障不应拦住正常合成，放行并留下记录
        print(f"[tts] 回读校验跳过（ASR 失败: {e}）")
        return True, 1.0, ""

    def strip(t):
        t = re.sub(r"[\s，。、！？；：,.!?;:\"'（）()【】\[\]]", "", t or "")
        # ⚠️ 必须做繁简归一：whisper 对中文常输出繁体（实测「黄金开头」→
        # 「黃金開頭」），逐字比对会把纯字形差异当成识别错误。
        # 同一条正常配音实测 53.3% -> 80.0%，直接决定是否被误判为失败。
        return _to_simplified(t)

    want, real = strip(expect_text), strip(got)
    if not want or not real:
        return False, 0.0, got

    n = len(want)
    # 极短文本不能用 SequenceMatcher 的相似度：分母太小，1 个字不一致
    # 相似度就从 100% 掉到 30% 上下。实测线上任务 93 的第 9 句「那咋办？」
    # 净 3 字，合成音频人耳完全听得清，回读相似度却只有 33.3%，被门禁误杀，
    # 连带整条视频失败（而这类短句在口语文案里很常见）。
    # 对净字数 < 8 的片段改用「字符覆盖率」：期望文本里的字有多少出现在
    # 回读结果中，≥ 50% 即视为可辨识；真乱码（音文错配）是一个字都覆盖不上。
    if n < 8:
        from collections import Counter
        cw, cr = Counter(want), Counter(real)
        hit = sum(min(c, cr[ch]) for ch, c in cw.items())
        ratio = hit / n
        ok = ratio >= 0.50
        print(f"[tts] 回读校验(短句 n={n}) {'通过' if ok else '未通过'}: "
              f"字符覆盖 {hit}/{n} = {ratio*100:.1f}% (阈值 50%)")
        if not ok:
            print(f"[tts]   期望: {want}")
            print(f"[tts]   回读: {real}")
        return ok, ratio, got

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


# whisper 只用于回读校验，几秒音频的转写在 CPU 上完全够快，
# 但它默认会占用 GPU（实测 base 模型约 976MiB 显存且不主动释放）。
# 口型推理需要近 20GB / 全卡 24GB，这近 1GB 足以把它推过临界点 ——
# 线上任务 33 就是这样炸的：TTS 与回读跑完，紧接着口型报
# cuDNN CUDNN_STATUS_INTERNAL_ERROR_HOST_ALLOCATION_FAILED。
# 故这里强制 CPU，把显存整块留给口型。可用 WHISPER_DEVICE 覆盖。
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")


# 已加载的 whisper 模型，按 (model_size, device) 缓存。
# 一次配音请求会转写两轮（参考音频取逐字稿 + 成品回读校验），
# 每轮都 load_model 等于把加载成本付两遍。跑在 CPU 上时模型不占显存，
# 常驻复用是纯赚；跑在 GPU 上则仍旧用完即放，避免挤占口型推理的显存。
_whisper_cache = {}


def transcribe(audio_path, model_size: str = "base") -> str:
    """用 whisper 转写参考音频，得到逐字稿。

    绝不能凭想象填 ref_text：音文错配会让 zero-shot 克隆输出乱码。
    """
    ff_dir = str(Path(FFMPEG).parent)
    if ff_dir and ff_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ff_dir + os.pathsep + os.environ.get("PATH", "")
    import whisper
    on_cpu = WHISPER_DEVICE == "cpu"
    key = (model_size, WHISPER_DEVICE)
    model = _whisper_cache.get(key) if on_cpu else None
    if model is None:
        model = whisper.load_model(model_size, device=WHISPER_DEVICE)
        if on_cpu:
            _whisper_cache[key] = model
    try:
        res = model.transcribe(str(audio_path), language="zh", fp16=False)
        text = re.sub(r"\s+", "", res.get("text", ""))
    finally:
        # 在 GPU 上必须立刻放手：worker 是常驻进程，不释放就一直占着显存，
        # 而口型推理需要近 20GB，这近 1GB 足以把它推过临界点。
        if not on_cpu:
            del model
            release_gpu_memory()
    print(f"[tts] ASR 转写参考音频: {text[:60]}")
    return text


def release_gpu_memory() -> None:
    """归还缓存显存。口型推理是显存大户，任何前置步骤都该主动让位。"""
    try:
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception:
        pass


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


# ---------------------------------------------------------------------------
# 常驻合成服务（worker 侧）
#
# CosyVoice2 跑在自己的 Python 3.11 解释器里（依赖与本项目隔离），
# 所以只能以子进程方式调用。一次性子进程的问题是：导入 + 权重加载约 8 秒，
# 而一条 30 字文案的实际合成只要几秒 —— 每条配音都在重付这 8 秒。
# 这里维持一个常驻子进程，模型只加载一次，后续请求按行传 JSON。
# 进程意外退出时自动重建；始终保留一次性路径作为回退，
# 因为配音是主链路，不能因为这个优化本身出问题就整条断掉。
# ---------------------------------------------------------------------------

TTS_SERVE = os.environ.get("TTS_SERVE", "1").strip() == "1"
_serve_proc = None
_serve_lock = None


# 常驻进程响应行的标记。合成过程中的中文诊断日志同样打在 stdout，
# 没有标记就无法区分"响应"和"日志"，会把日志行当响应解析而误判失败。
_SERVE_TAG = "PHXRESP "


def _read_serve_response(proc):
    """读到下一条带标记的响应；日志行原样转发到 worker 日志。

    返回 None 表示子进程 stdout 已结束（进程退出）。
    """
    import json
    while True:
        line = proc.stdout.readline()
        if not line:
            return None
        line = line.rstrip("\r\n")
        if not line.startswith(_SERVE_TAG):
            if line.strip():
                print(f"[tts] {line}")
            continue
        try:
            return json.loads(line[len(_SERVE_TAG):])
        except Exception:
            print(f"[tts] 常驻合成响应无法解析: {line[:200]!r}")
            return {"ok": False, "error": "malformed response"}


def _serve_runner():
    """取（必要时启动）常驻合成子进程。返回 None 表示不可用，调用方回退。"""
    global _serve_proc
    if not TTS_SERVE:
        return None
    if _serve_proc is not None and _serve_proc.poll() is None:
        return _serve_proc
    if not Path(COSY_PY).exists():
        return None

    script = Path(__file__).resolve().parent / "cosyvoice_runner.py"
    env = os.environ.copy()
    env["PATH"] = str(Path(FFMPEG).parent) + os.pathsep + env.get("PATH", "")
    env["COSY_DIR"] = COSY_DIR
    env["COSY_MODEL"] = COSY_MODEL
    env["FFMPEG_BIN"] = FFMPEG
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    for k in ("PYTHONPATH", "PYTHONHOME"):
        env.pop(k, None)
    try:
        proc = subprocess.Popen(
            [COSY_PY, "-u", str(script), "--serve"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=None,  # 诊断日志直通 worker 日志，便于排查
            text=True, encoding="utf-8", errors="replace", env=env)
    except Exception as e:
        print(f"[tts] 常驻合成进程启动失败（回退一次性模式）: {e}")
        return None

    # 等就绪握手：模型加载要几秒，这里等不到就说明环境有问题，直接回退
    try:
        deadline = time.time() + float(os.environ.get("TTS_SERVE_BOOT", "180"))
        while time.time() < deadline:
            resp = _read_serve_response(proc)
            if resp is None:
                break
            if resp.get("ready"):
                print("[tts] 常驻合成进程已就绪")
                _serve_proc = proc
                return proc
    except Exception as e:
        print(f"[tts] 等待常驻进程就绪异常: {e}")
    try:
        proc.kill()
    except Exception:
        pass
    print("[tts] 常驻合成进程未就绪，回退一次性模式")
    return None


def shutdown_serve() -> bool:
    """停掉常驻合成进程，把它占的显存交还给口型推理。

    CosyVoice2 常驻会吃约 3.7GB 显存。口型推理要近 20GB / 全卡 24GB，
    这 3.7GB 足以把它挤到余量里慢跑：实测同一条 20 秒素材，
    常驻进程在时推理 6.1 分钟，让位后 4.3 分钟。
    所以配音"常驻"与口型"独占显卡"必须让后者优先——下一次配音请求
    会自动把它重新拉起，只多付一次约 8 秒的加载。
    """
    global _serve_proc
    proc, _serve_proc = _serve_proc, None
    if proc is None or proc.poll() is not None:
        return False
    try:
        # 先关 stdin 让它自己走完循环，超时再强杀
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
            proc.wait(timeout=10)
        print("[tts] 已停止常驻合成进程，显存交还口型推理")
        return True
    except Exception as e:
        print(f"[tts] 停止常驻合成进程失败: {e}")
        return False


def _synthesize_via_serve(text, ref_wav, ref_text, out_path,
                          target_cps, variant: int = 0) -> Optional[Path]:
    """走常驻子进程合成。任何异常都返回 None，由调用方回退。"""
    global _serve_proc, _serve_lock
    import json
    import threading

    if _serve_lock is None:
        _serve_lock = threading.Lock()
    proc = _serve_runner()
    if proc is None:
        return None

    req = json.dumps({
        "text": text,
        "ref_wav": str(Path(ref_wav).resolve()),
        "ref_text": ref_text,
        "out": str(Path(out_path).resolve()),
        "target_cps": target_cps if target_cps is not None else TTS_TARGET_CPS,
        "max_tempo": TTS_MAX_TEMPO,
        "variant": int(variant),
    }, ensure_ascii=False)

    # 串行化：共用一个 stdin/stdout 管道，并发写会让响应错配到别的请求上
    with _serve_lock:
        try:
            proc.stdin.write(req + "\n")
            proc.stdin.flush()
            resp = _read_serve_response(proc)
        except Exception as e:
            print(f"[tts] 常驻合成通信失败（回退一次性模式）: {e}")
            _serve_proc = None
            return None
    if resp is None:
        print("[tts] 常驻合成进程已退出（回退一次性模式）")
        _serve_proc = None
        return None
    if not resp.get("ok"):
        print(f"[tts] 常驻合成失败: {resp.get('error')}")
        return None
    out = Path(resp.get("out") or out_path)
    if out.exists() and out.stat().st_size > 0:
        return out
    return None


def synthesize_local(text: str, ref_wav, ref_text: str, out_path,
                     target_cps: Optional[float] = None,
                     variant: int = 0) -> Optional[Path]:
    """本机合成入口：转交给 CosyVoice2 自己的解释器执行。

    variant 用于重试时换随机种子：同一个输入重复合成是确定性的，原样重发
    等于白等，所以调用方每次重试都要换一个 variant（0 = 首次）。
    """
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

    # ⚠️ 逐字稿必须先归一为简体，且必须在本进程做：
    # CosyVoice2 的中文前端按简体字表做文本归一/音素映射，繁体字对不上，
    # prompt 文本与 prompt 音频 token 错位，模型就从错位处续写——实测同一段
    # 16.32s 参考音频，繁体旧稿合成出来前面多 20 个字的垃圾（「心情短幾趟,
    # 你看明把一虎一骨,財夫肉化」），转成简体后回到 87.2% 干净。
    # 归一只在**装了 zhconv 的解释器**里真正生效：CosyVoice 自己的
    # Python 3.11 环境没有 zhconv（实测 ModuleNotFoundError），所以放在
    # _synthesize_inproc 里是空转——那里只能算兜底。
    ref_text = _to_simplified(ref_text)
    if not Path(COSY_PY).exists():
        print(f"[tts] CosyVoice 解释器不存在: {COSY_PY}")
        return None

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 先走常驻进程：省掉每条配音 8 秒的模型加载。失败则落回一次性子进程，
    # 保证这个优化本身不会成为配音链路的新故障点。
    res = _synthesize_via_serve(text, ref_wav, ref_text, out_path, target_cps, variant)
    if res is not None:
        return res

    script = Path(__file__).resolve().parent / "cosyvoice_runner.py"
    cmd = [COSY_PY, "-u", str(script),
           "--ref-wav", str(ref_wav.resolve()),
           "--out", str(out_path.resolve()),
           "--target-cps", str(target_cps if target_cps is not None else TTS_TARGET_CPS),
           "--max-tempo", str(TTS_MAX_TEMPO),
           "--variant", str(int(variant))]
    env = os.environ.copy()
    env["PATH"] = str(Path(FFMPEG).parent) + os.pathsep + env.get("PATH", "")
    env["COSY_DIR"] = COSY_DIR
    env["COSY_MODEL"] = COSY_MODEL
    env["FFMPEG_BIN"] = FFMPEG
    # 子进程的 stdin/stdout 必须是 utf-8：默认会取系统 ANSI 编码（简中为 GBK），
    # 导致传入文案被解成乱码、打印中文日志时抛 UnicodeEncodeError。
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
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
                       target_cps: Optional[float] = None,
                       variant: int = 0) -> Optional[Path]:
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

    # ⚠️ 逐字稿必须归一为简体再喂给模型。实测（2026-10-13，同一段 16.32s 参考音频
    # 只换逐字稿）：
    #   库内简体稿 -> 回读相似度 94.7%，干净
    #   同内容的繁体稿 -> 合成的音频前面多出 20 个字的垃圾（如「心情短幾趟,
    #     你看明把一虎一骨,財夫肉化」）再才是正文
    #  该繁体稿用 zhconv 转成简体后 -> 又回到 87.2% 干净
    # 原因是 CosyVoice2 的中文前端按简体字表做文本归一/音素映射，繁体字对不上，
    # prompt 文本与 prompt 音频的 token 对不齐，LLM 就从错位处续写。
    # 而 whisper 对中文默认输出繁体——所以"没给逐字稿就自己转写"这条兜底路径
    # 必然踩坑。
    # 注意：本函数跑在 CosyVoice 自己的解释器里，那里**没有 zhconv**
    # （实测 ModuleNotFoundError），所以这里只是兜底；真正生效的是
    # 调用方进程（worker / 本项目 venv）里的那一层归一。
    ref_text = _to_simplified(ref_text)

    # 重试换策略：CosyVoice2 的 flow matching 从一个随机噪声起步，同输入同
    # 种子必然产出同一条音频。调用方每次重试递增 variant，这里据此换种子，
    # 才能拿到一条"真正不一样"的音频去重新过门禁。
    if variant:
        seed = 1234 + int(variant) * 7919
        torch.manual_seed(seed)
        try:
            torch.cuda.manual_seed_all(seed)
        except Exception:
            pass
        print(f"[tts] 重试换种子 variant={variant} seed={seed}")

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
        # 必须显式声明 charset=utf-8。中文字段若不声明，服务端按 latin-1
        # 解码会得到乱码文本，模型照着乱码发音 —— 表现为合成"成功"但
        # 回读相似度只有 4%，而同样的文案在本机直跑却有 84%。
        head = (f"--{boundary}\r\nContent-Disposition: form-data; "
                f'name="{name}"\r\n'
                f"Content-Type: text/plain; charset=utf-8\r\n\r\n")
        return head.encode("utf-8") + str(value).encode("utf-8") + b"\r\n"

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
    # CosyVoice 回读相似度门控有随机性（同一请求可能这次50%、下次通过），
    # HTTP 500/非音频时重试，避免一次偶发失败直接走到 501。
    import time as _time
    last_err = ""
    for attempt in range(1, 4):
        try:
            try:
                with urllib.request.urlopen(req, timeout=TTS_HTTP_TIMEOUT) as r:
                    data = r.read()
                    ctype = r.headers.get("Content-Type", "")
            except urllib.error.HTTPError as e:
                last_err = f"HTTP {e.code}: {e.read()[:200]}"
                print(f"[tts] 远程 {last_err}，第{attempt}次重试...")
                _time.sleep(2)
                continue
            if not _looks_like_audio(data, ctype):
                last_err = f"非音频(ctype={ctype!r}): {data[:160]}"
                print(f"[tts] 远程未返回音频，{last_err}，第{attempt}次重试...")
                _time.sleep(2)
                continue
            out_path = Path(out_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(data)
            return out_path
        except Exception as e:
            last_err = str(e)
            print(f"[tts] 远程合成异常: {e}，第{attempt}次重试...")
            _time.sleep(2)
    print(f"[tts] 远程合成重试3次仍失败: {last_err}")
    return None
