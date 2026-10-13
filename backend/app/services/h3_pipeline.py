# -*- coding: utf-8 -*-
"""
h3_pipeline.py — 真人科普口播长片定稿流水线（MiniMax H3 + CosyVoice）

把在「真人科普测试」里验证过的流程固化成参数化模块，供 project-Phoenix 直接 import。

定稿流程（见长期记忆 2026-09-08-final-50s-lip-sync-workflow）：
  1. (可选)定场图：用 H3 i2v 从人像照片生成一张"人在场景里"的统一锚点帧
  2. 文案按句号切句 -> CosyVoice 逐句克隆配音
  3. 每句时长 -> 帧数(规则 n%17==5)
  4. H3 i2v 批量【独立首帧】：每段都用同一张定场图做首帧(无链式漂移、场景统一)，
     音频锚点 MiniMaxH3AddGuide 喂该句音频，4步turbo
  5. 每段画面用 ffmpeg -t 精确裁到与该句等长 -> concat 硬切(不用xfade) -> 铺同源拼接音轨
     => 段边界=句边界，口型全程对齐，不累积错位

两种用法：
  CLI:  python h3_pipeline.py --person a.png --script s.txt --scene "..." --out final.mp4
  import: from h3_pipeline import H3Pipeline; H3Pipeline(...).run(...)

只依赖 requests + ffmpeg(外部) + 常驻 ComfyUI(8188) + CosyVoice(18080)。全本地。
"""
from __future__ import annotations
import argparse, json, os, re, shutil, subprocess, sys, time, uuid
from pathlib import Path
from typing import List, Optional

import requests

# ---------------- 默认配置（本机） ----------------
COMFY_URL = "http://127.0.0.1:8188"
TTS_URL = "http://127.0.0.1:18080/tts"
REF_WAV = r"D:\phx_tts\ref.wav"
FFMPEG = r"D:\汪挺\project-Phoenix\project-phoenix\backend\storage\models\ffmpeg\ffmpeg.exe"
COMFY_INPUT = r"E:\ComfyUI_windows_portable\ComfyUI\input"
COMFY_OUTPUT = r"E:\ComfyUI_windows_portable\ComfyUI\output"

UNET = "minimax_h3_fl2va_int8_convrot.safetensors"
CLIP = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
VAE_VIDEO = "minimax_h3_video_vae_fp16.safetensors"
VAE_AUDIO = "minimax_h3_audio_vae_fp32.safetensors"
LORA_4STEP = "minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors"
LORA_8STEP = "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"


def log(msg: str):
    print(f"[h3 {time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------- ffmpeg / 音频工具 ----------------
def run_ff(cmd: List[str]) -> str:
    p = subprocess.run([FFMPEG, "-y", *cmd], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError("ffmpeg 失败: " + (p.stderr or "")[-700:])
    return p.stdout


def probe_duration(path: Path) -> float:
    p = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True, errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", p.stderr)
    if not m:
        raise RuntimeError(f"无法读取时长: {path}")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def frames_for_duration(dur: float, fps: int = 24) -> int:
    n = int(dur * fps) + 1
    while n % 17 != 5:
        n += 1
    return n


# 单个语音片段的最小净字数。低于这个长度的片段有两个硬问题：
#   1) 克隆配音的回读门禁在极短文本上失效——SequenceMatcher 只有几个字符可比，
#      错 1 个字相似度就从 100% 掉到 33%。线上任务 93 的第 9 句「那咋办？」
#      净 3 字，人耳完全听得清，却被门禁判为乱码，导致整条视频失败；
#   2) 3 个字一句的停顿让口播听起来像结巴。
SEG_MIN_CHARS = 10
# 合并后的上限。超过这个长度分镜会太长，且 CosyVoice2 单次合成的韵律会变差。
SEG_MAX_CHARS = 60


def _net_chars(s: str) -> int:
    """净字数：去掉标点与空白后实际要念出来的字数。"""
    return len(re.sub(r"[^\w\u4e00-\u9fff]", "", s or ""))


def split_sentences(text: str, min_chars: int = SEG_MIN_CHARS,
                    max_chars: int = SEG_MAX_CHARS) -> List[str]:
    """按句末标点切句，并把过短的句子合并到相邻句。

    每个片段会生成一段独立的画面 + 一次 TTS 请求，所以切分粒度直接决定
    配音质量与失败率。纯粹的"按句号切"在口语文案上会切出「那咋办？」这类
    极短句（实测会稳定触发门禁误杀），必须合并。
    """
    text = text.replace("\r", "\n")
    # 按句末标点切，保留标点
    parts = re.split(r"(?<=[。！？!?；;])", text)
    raw = []
    for p in parts:
        p = p.strip()
        # 过滤纯标点/空白段（例如结尾多出的“。”），避免生成空句 TTS 失败
        if p and not re.fullmatch(r"[，。！？、；：,.!?;:…\s]+", p):
            raw.append(p)
    if not raw:
        return []

    # 短句一律并入相邻句：优先并入前一句（语序与停顿位置最自然）。
    # 前一句已达标且再并会超长时，留给后一句去并——所以这里用缓冲累积。
    out: List[str] = []
    buf = ""
    for p in raw:
        if not buf:
            buf = p
            continue
        total = _net_chars(buf) + _net_chars(p)
        if (_net_chars(buf) < min_chars or _net_chars(p) < min_chars) and total <= max_chars:
            buf += p
        else:
            out.append(buf)
            buf = p
    if buf:
        out.append(buf)
    return out


def _strip_punct(text: str) -> str:
    """去掉标点，抖音式字幕干净工整；只保留汉字/数字/字母/空格。"""
    return re.sub(r"[^\w\s\u4e00-\u9fff]", "", text).strip()


def _ass_time(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _escape_filter_path(p) -> str:
    return str(p).replace("\\", "/").replace(":", "\\:")


def _split_punct_aware(text: str, limit: int) -> List[str]:
    """在标点/空格处断行，断不开再按字数硬切，避免整段冲出画面。

    硬切时优先在靠近中间、且不会把数字串或英文字母单词从中间劈开的位置断，
    避免出现「4\\N0岁」这种多余字符。
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    out: List[str] = []
    rest = text
    while len(rest) > limit:
        cut = -1
        for i in range(limit - 1, max(int(limit * 0.5), 1) - 1, -1):
            if rest[i] in "，。！？；：、,;.!?: ":
                cut = i + 1
                break
        if cut <= 0:
            # 找不到标点也尽量对半分；优先选择不拆数字串/英文单词的位置
            mid = min(limit, (len(rest) + 1) // 2)
            cut = -1
            for i in range(mid, max(int(mid * 0.5), 1) - 1, -1):
                if i >= len(rest):
                    continue
                prev_is_digit = rest[i - 1].isdigit() if i > 0 else False
                cur_is_digit = rest[i].isdigit()
                if not (prev_is_digit and cur_is_digit):
                    cut = i
                    break
            if cut <= 0:
                cut = mid
        piece = rest[:cut].strip()
        if piece:
            out.append(piece)
        rest = rest[cut:].strip()
    if rest:
        out.append(rest)
    return out


def _highlight_emphasis(text: str, emphasis: List[str]) -> str:
    """把重点词用 ASS 覆盖标签标亮（金色加粗、放大）。"""
    for w in emphasis or []:
        clean = _strip_punct(w)
        if clean and clean in text:
            text = text.replace(
                clean,
                "{\\b1\\c&H00FFD700&\\fs+8}" + clean + "{\\r}",
            )
    return text


def _derive_emphasis(text: str) -> List[str]:
    """从文案里兜底提取重点词：数字/量词 + 强转折词，保证字幕有高亮。"""
    words = set()
    for m in re.findall(r"[0-9]+(?:\s*[%岁克天个月次分倍斤])?", text or ""):
        w = m.strip()
        if w:
            words.add(w)
    for strong in ("别", "关键", "必须", "千万不要", "不要", "首先", "记住", "最容易"):
        if strong in (text or ""):
            words.add(strong)
    return list(words)[:10]


def _xfade_concat(paths: List[Path], out: Path, transition: float = 0.4):
    """用 xfade 交叉溶解拼接多段视频，段间柔和过渡而不是硬切。"""
    if len(paths) == 1:
        shutil.copyfile(str(paths[0]), str(out))
        return
    inputs = []
    for p in paths:
        inputs += ["-i", str(p)]
    flt = ""
    prev = "0:v"
    acc = probe_duration(paths[0])
    for i in range(1, len(paths)):
        offset = max(acc - transition, 0.0)
        label = f"vx{i}"
        flt += (f"[{prev}][{i}:v]xfade=transition=fade:"
                f"duration={transition:.3f}:offset={offset:.3f}[{label}];")
        prev = label
        acc = acc + probe_duration(paths[i]) - transition
    run_ff(inputs + ["-filter_complex", flt, "-map", f"[{prev}]",
                     "-c:v", "libx264", "-crf", "17",
                     "-pix_fmt", "yuv420p", "-r", "24",
                     "-t", f"{acc:.3f}", str(out)])


def _image_has_text(path: Path) -> bool:
    """用 Windows OCR 检测画面里是否出现文字（定场图质量门）。

    定场图被所有分段当首帧复用，H3 偶尔会在图上画出无意义文字，
    一处有字整片都有。OCR 跑在独立子进程里并 os._exit，避免 WinRT
    清理时把常驻 worker 一起带崩。没有 winsdk/OCR 环境时跳过检测。
    """
    probe = r"""
import asyncio, json, os, sys
from pathlib import Path
try:
    from winsdk.windows.storage import StorageFile, FileAccessMode
    from winsdk.windows.graphics.imaging import BitmapDecoder
    from winsdk.windows.media.ocr import OcrEngine
except Exception:
    print(json.dumps({"text": False, "error": "no_winsdk"}))
    os._exit(0)

async def main():
    p = Path(sys.argv[1])
    f = await StorageFile.get_file_from_path_async(str(p.resolve()))
    s = await f.open_async(FileAccessMode.READ)
    d = await BitmapDecoder.create_async(s)
    b = await d.get_software_bitmap_async()
    e = OcrEngine.try_create_from_user_profile_languages()
    if e is None:
        print(json.dumps({"text": False, "error": "no_engine"}))
        return
    r = await e.recognize_async(b)
    lines = []
    for line in r.lines:
        words = list(line.words)
        # 单字/极短行多为衣服花纹等误报，至少要 3 个词才算"疑似文字"
        if len(words) >= 3:
            lines.append(line.text)
    print(json.dumps({"text": bool(lines), "lines": lines[:5]}))

asyncio.run(main())
os._exit(0)
"""
    try:
        proc = subprocess.run(
            [sys.executable, "-u", "-c", probe, str(path)],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace")
        tail = [ln for ln in (proc.stdout or "").strip().splitlines() if ln.strip()][-1]
        data = json.loads(tail)
        if data.get("lines"):
            log("定场图检测到疑似文字: " + " / ".join(str(x)[:12] for x in data["lines"]))
        return bool(data.get("text"))
    except Exception as e:
        log(f"定场图文字检测不可用，跳过: {e}")
        return False


def _build_subtitle_ass(seg_specs: List[dict], width: int, height: int,
                        font_name: str = "Microsoft YaHei",
                        emphasis: Optional[List[str]] = None) -> str:
    """生成底部、无标点、抖音式短句字幕的 ASS 内容。

    对齐方式用 ASS Alignment=2（底部居中）；每行按竖屏宽度算字号动态取 8~12 字，
    最多两行，超出再拆成下一条并按字符比例分配该段配音时长。
    """
    font_size = max(24, int(height * 0.04))
    margin_v = max(36, int(height * 0.10))   # 底部安全边距，避开平台控件
    margin_h = max(24, int(width * 0.06))    # 左右安全边距
    outline = max(2, int(font_size * 0.08))
    shadow = max(1, int(font_size * 0.04))
    max_chars = max(8, min(12, int((width - 2 * margin_h) / font_size)))
    max_lines = 2

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,{outline},{shadow},2,{margin_h},{margin_h},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    cursor = 0.0
    first_shown = True
    for sp in seg_specs:
        dur = max(float(sp.get("dur") or 0), 0.1)
        start, end = cursor, cursor + dur
        cursor = end
        text = sp.get("text") or ""
        raw_lines = _split_punct_aware(text, max_chars)
        clean_lines = [x for x in (_strip_punct(r) for r in raw_lines) if x]
        if not clean_lines:
            continue
        blocks = [
            clean_lines[i:i + max_lines]
            for i in range(0, len(clean_lines), max_lines)
        ]
        displays = ["\\N".join(_highlight_emphasis(x, emphasis) for x in b)
                    for b in blocks]
        total = sum(len(d.replace("\\N", "")) for d in displays) or 1
        t = start
        for disp in displays:
            e = min(end, t + dur * len(disp.replace("\\N", "")) / total)
            if e - t < 0.15:
                e = min(end, t + 0.8)
            # 首句钩子大字：开头 0~2.2s 用大字号+金色+淡入淡出，做视觉钩子
            if first_shown and t < 2.2:
                big = int(font_size * 1.3)
                disp = "{\\fs%d\\b1\\c&H00FFE066&\\fad(250,250)}%s{\\r}" % (big, disp)
                first_shown = False
            lines.append(
                f"Dialogue: 0,{_ass_time(t)},{_ass_time(e)},Default,,0,0,0,,{disp}"
            )
            t = e
    return "\n".join(lines) + "\n"


# ---------------- ComfyUI 客户端 ----------------
class ComfyClient:
    def __init__(self, url: str = COMFY_URL):
        self.url = url

    def wait_online(self, timeout: int = 300):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if requests.get(self.url + "/system_stats", timeout=6).status_code == 200:
                    return True
            except Exception:
                pass
            time.sleep(5)
        raise RuntimeError("ComfyUI 未就绪")

    def submit(self, workflow: dict) -> str:
        r = requests.post(self.url + "/prompt", json={"prompt": workflow}, timeout=30)
        data = r.json()
        if data.get("error") or data.get("node_errors"):
            raise RuntimeError("工作流校验失败: " + json.dumps(data, ensure_ascii=False)[:800])
        return data["prompt_id"]

    def wait(self, prompt_id: str, poll: int = 5) -> dict:
        while True:
            h = requests.get(self.url + f"/history/{prompt_id}", timeout=15).json()
            if prompt_id in h:
                st = (h[prompt_id].get("status") or {})
                if st.get("status_str") == "error":
                    msgs = st.get("messages") or []
                    err = [m[1].get("exception_message", "") for m in msgs if m and m[0] == "execution_error"]
                    raise RuntimeError("ComfyUI 执行错误: " + "; ".join(err))
                if h[prompt_id].get("outputs"):
                    return h[prompt_id]
            time.sleep(poll)

    @staticmethod
    def output_files(result: dict) -> List[Path]:
        files = []
        for _node, out in (result.get("outputs") or {}).items():
            for key in ("gifs", "videos", "images"):
                for it in out.get(key, []) or []:
                    fn = it.get("filename")
                    if fn:
                        files.append(Path(COMFY_OUTPUT) / fn)
        return files


# ---------------- H3 工作流模板 ----------------
def _base_nodes(unet=UNET, lora=LORA_4STEP):
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": "default"}},
        "45": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": lora, "strength_model": 1.0}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": CLIP, "type": "minimax"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE_VIDEO}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": VAE_AUDIO}},
    }


def anchor_workflow(image_name: str, prompt: str, width: int, height: int, seed: int, steps: int = 8) -> dict:
    wf = _base_nodes(lora=LORA_8STEP)
    wf.update({
        "6": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "20": {"class_type": "ImageScale", "inputs": {"image": ["6", 0], "upscale_method": "lanczos", "width": width, "height": height, "crop": "center"}},
        "5": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {"clip": ["2", 0], "vae": ["3", 0], "prompt": prompt, "width": width, "height": height, "length": 39, "first_frame": ["20", 0]}},
        "9": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "10": {"class_type": "BasicGuider", "inputs": {"model": ["45", 0], "conditioning": ["5", 0]}},
        "11": {"class_type": "BasicScheduler", "inputs": {"model": ["45", 0], "scheduler": "beta", "steps": steps, "denoise": 1.0}},
        "12": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "13": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["9", 0], "guider": ["10", 0], "sampler": ["12", 0], "sigmas": ["11", 0], "latent_image": ["5", 1]}},
        "14": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["3", 0]}},
        "16": {"class_type": "CreateVideo", "inputs": {"images": ["14", 0], "fps": 24}},
        "17": {"class_type": "SaveVideo", "inputs": {"video": ["16", 0], "filename_prefix": "h3p_anchor_" + str(seed), "format": "mp4", "codec": "auto"}},
    })
    return wf


def segment_workflow(image_name: str, audio_name: str, prompt: str, width: int, height: int,
                     length: int, seed: int, tag: str, steps: int = 4) -> dict:
    wf = _base_nodes(lora=LORA_4STEP)
    wf.update({
        "6": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "20": {"class_type": "ImageScale", "inputs": {"image": ["6", 0], "upscale_method": "lanczos", "width": width, "height": height, "crop": "center"}},
        "40": {"class_type": "LoadAudio", "inputs": {"audio": audio_name}},
        "5": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {"clip": ["2", 0], "vae": ["3", 0], "prompt": prompt, "width": width, "height": height, "length": length, "first_frame": ["20", 0]}},
        "41": {"class_type": "MiniMaxH3AddGuide", "inputs": {"positive": ["5", 0], "audio_vae": ["4", 0], "latent": ["5", 1], "audio": ["40", 0], "frame_idx": 0}},
        "9": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "10": {"class_type": "BasicGuider", "inputs": {"model": ["45", 0], "conditioning": ["41", 0]}},
        "11": {"class_type": "BasicScheduler", "inputs": {"model": ["45", 0], "scheduler": "beta", "steps": steps, "denoise": 1.0}},
        "12": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "13": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["9", 0], "guider": ["10", 0], "sampler": ["12", 0], "sigmas": ["11", 0], "latent_image": ["5", 1]}},
        "14": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["3", 0]}},
        "15": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["13", 0], "vae": ["4", 0]}},
        "16": {"class_type": "CreateVideo", "inputs": {"images": ["14", 0], "fps": 24, "audio": ["15", 0]}},
        "17": {"class_type": "SaveVideo", "inputs": {"video": ["16", 0], "filename_prefix": "h3p_seg_" + tag, "format": "mp4", "codec": "auto"}},
    })
    return wf


# ---------------- 显存预检（Ollama / ComfyUI 共用一块 GPU） ----------------
H3_MIN_FREE_MIB = int(os.environ.get("H3_MIN_FREE_MIB", "512"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")


def _gpu_free_mib_smi() -> Optional[int]:
    """用 nvidia-smi 读取当前可用显存（MiB）。取不到返回 None，不阻塞。"""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            text=True, timeout=10, encoding="utf-8", errors="replace")
        return int(float(out.strip().splitlines()[0].strip()))
    except Exception:
        return None


def _unload_ollama():
    """让本机 Ollama 卸载已加载的大模型，把显存让给 H3 生成。"""
    try:
        r = requests.get(OLLAMA_URL + "/api/ps", timeout=5)
        models = (r.json() or {}).get("models", []) if r.status_code == 200 else []
        for m in models:
            name = m.get("name")
            if not name:
                continue
            try:
                requests.post(OLLAMA_URL + "/api/generate",
                              json={"model": name, "keep_alive": 0}, timeout=5)
            except Exception:
                pass
    except Exception:
        pass


def _comfy_free_memory():
    """让 ComfyUI 卸载常驻模型释放显存。失败不阻塞，仅尽力而为。"""
    try:
        requests.post(COMFY_URL + "/free",
                      json={"unload_models": True, "free_memory": True},
                      timeout=10)
    except Exception:
        pass


def _ensure_h3_vram(min_free_mib: Optional[int] = None) -> int:
    """H3 生成前预检显存；不够先让 Ollama 让位，仍不够就明确报错。"""
    min_free = min_free_mib if min_free_mib is not None else H3_MIN_FREE_MIB
    free = _gpu_free_mib_smi()
    if free is None:
        return 0  # 拿不到显存信息就不拦，避免误伤
    if free < min_free:
        log(f"H3 前显存不足: free {free}MiB < {min_free}MiB，尝试让 Ollama 让位")
        _unload_ollama()
        import time
        time.sleep(2)
        free = _gpu_free_mib_smi() or free
    if free < min_free:
        raise RuntimeError(
            f"显存不足：当前可用 {free}MiB，H3 生成至少需要 {min_free}MiB。"
            "请等待当前任务结束后重试。"
        )
    return free


# ---------------- 主编排 ----------------
class H3Pipeline:
    def __init__(self, workdir: str, comfy_url: str = COMFY_URL, tts_url: str = TTS_URL,
                 ref_wav: str = REF_WAV, ref_text: str = ""):
        self.workdir = Path(workdir).resolve(); self.workdir.mkdir(parents=True, exist_ok=True)
        self.segdir = self.workdir / "segments"; self.segdir.mkdir(exist_ok=True)
        self.comfy = ComfyClient(comfy_url)
        self.tts_url = tts_url
        self.ref_wav = ref_wav
        self.ref_text = ref_text or ""
        self.tag = uuid.uuid4().hex[:8]

    def _to_input(self, src: Path, name: str) -> str:
        dst = Path(COMFY_INPUT) / name
        shutil.copyfile(src, dst)
        return name

    def tts(self, text: str, idx: int, retries: int = 4) -> Path:
        """逐句配音。

        重试必须换策略，不能原样重发：CosyVoice2 对同一输入是确定性的，
        同一段音频重新合成回读相似度几乎不变。线上任务 93 第 9 句
        「那咋办？」首测 33.3% 未过，后面 3 次一模一样，白等 12 秒后报
        「重试4次仍失败」。这里每次重试都带一个新的 variant，worker 侧据此
        换随机种子（flow matching 的初始噪声），产出真正的另一条音频。
        """
        mp3 = self.workdir / f"voice_{idx:02d}.mp3"
        last = ""
        for attempt in range(1, retries + 1):
            with open(self.ref_wav, "rb") as f:
                files = {"ref_wav": ("ref.wav", f, "audio/wav")}
                data = {"text": text, "ref_text": self.ref_text,
                        "variant": str(attempt - 1)}
                r = requests.post(self.tts_url, files=files, data=data, timeout=300)
            if r.status_code == 200 and "audio" in r.headers.get("content-type", "") and r.content:
                mp3.write_bytes(r.content)
                if attempt > 1:
                    log(f"  句{idx} 第{attempt}次（换随机种子）配音通过")
                return mp3
            last = r.text[:200]
            log(f"  句{idx} TTS 第{attempt}次未过({last[:60]})，换种子重试...")
            time.sleep(3)
        log(f"  句{idx} 配音最终失败，最后一次响应: {last}")
        # 抛给用户的话必须是能看懂、能行动的：说清是第几句、哪句话、下一步怎么做。
        # 技术细节（相似度、门禁阈值）只进日志，不糊到界面上。
        raise RuntimeError(
            f"第 {idx} 句配音没通过清晰度校验：「{text[:18]}」。"
            f"系统已自动重试 {retries} 次仍未成功，请重新生成；"
            f"若连续失败，可把这句话改写得更长一些或换一个声音样本。"
        )

    def make_anchor(self, person: Path, scene: str, width: int, height: int,
                    seed: int, hair_hint: str = "") -> Path:
        """生成统一场景定场图，返回抽出的锚点帧 jpg。"""
        hair = hair_hint or "the person's hairstyle and hairline"
        prompt = (f"A vertical medium shot of the exact same person as in the first frame, placed in {scene}. "
                  f"NO text, NO subtitles, NO captions, NO letters, NO numbers, NO logos, NO posters, "
                  f"NO illustrations anywhere in the frame - pure photorealistic scene only. "
                  f"CRITICAL: keep the person's face and {hair} pixel-consistent and identical to the first frame, "
                  f"keep the exact same clothing, outfit, colors and accessories as the first frame; "
                  f"do not change gender, age, skin tone, features or clothes. "
                  f"Calm steady pose, gentle expression, eyes toward the camera, mouth closed and relaxed. "
                  f"Face and hair sharp and clear, natural skin tone, photorealistic, high detail. "
                  f"No subtitles, no title, no watermark, no logos, no text, no letters or numbers anywhere; "
                  f"no illustrations, posters or pictures inside the frame; background must stay plain and clean, "
                  f"no signs, no writing, no screens showing content; photorealistic video only.")
        img_name = self._to_input(person, f"h3p_{self.tag}_person.png")
        max_tries = int(os.environ.get("H3_ANCHOR_MAX_TRIES", "3"))
        anchor = self.workdir / "anchor.jpg"
        for attempt in range(max_tries):
            cur_seed = seed + attempt * 997
            wf = anchor_workflow(img_name, prompt, width, height, cur_seed)
            pid = self.comfy.submit(wf)
            log(f"定场图生成中 (seed={cur_seed}, 尝试 {attempt + 1}/{max_tries}) ...")
            res = self.comfy.wait(pid)
            vids = [f for f in self.comfy.output_files(res) if f.suffix == ".mp4"]
            if not vids:
                raise RuntimeError("定场图未产出视频")
            # 抽约 80% 处帧（脱离首帧照片、动作已平稳）
            run_ff(["-ss", "1.3", "-i", str(vids[0]), "-frames:v", "1", "-q:v", "2", str(anchor)])
            if not _image_has_text(anchor):
                log(f"定场锚点帧无文字: {anchor}")
                return anchor
            log(f"定场图含文字，换种子重生成 (下一 seed={cur_seed + 997})")
        log("警告：定场图多次重生成仍含文字，继续使用当前结果")
        return anchor

    def run(self, person_image: str, script_text: str, scene: str, final_output: str,
            anchor_image: Optional[str] = None, width: int = 512, height: int = 960,
            hair_hint: str = "", seed_base: int = 400000,
            emphasis: Optional[List[str]] = None) -> Path:
        # H3 和本机 Ollama 共用一块 GPU：先生成前预检显存，不够先让 Ollama 让位。
        _ensure_h3_vram()
        if not emphasis:
            emphasis = _derive_emphasis(script_text)
        self.comfy.wait_online()
        person = Path(person_image)
        if not person.exists():
            raise FileNotFoundError(person)

        # 1) 锚点帧
        if anchor_image:
            anchor = Path(anchor_image)
            log(f"使用指定锚点帧: {anchor}")
        else:
            anchor = self.make_anchor(person, scene, width, height, seed_base, hair_hint)
        anchor_name = self._to_input(anchor, f"h3p_{self.tag}_anchor.jpg")

        # 2) 切句 + 逐句 TTS
        sents = split_sentences(script_text)
        log(f"文案切为 {len(sents)} 句")
        seg_specs = []
        for i, s in enumerate(sents, 1):
            mp3 = self.tts(s, i)
            dur = probe_duration(mp3)
            length = frames_for_duration(dur)
            audio_name = self._to_input(mp3, f"h3p_{self.tag}_seg{i:02d}.mp3")
            seg_specs.append({"i": i, "text": s, "mp3": mp3, "dur": dur, "length": length, "audio": audio_name})
            log(f"  句{i}: {dur:.2f}s -> {length}帧")

        # 3) 批量独立首帧生成（顺序提交+等待，避免显存抢占）
        hair = hair_hint or "the person's hairstyle and hairline"
        n_sents = len(seg_specs)
        seg_videos = []
        for idx, sp in enumerate(seg_specs, 1):
            i = sp["i"]
            # 景别/镜头按段落位置变化：首尾更近、中间中景，增强节奏感
            if idx == 1:
                shot = "close-up"
                motion = "slow push-in from a stable medium framing, gentle and smooth"
            elif idx == n_sents:
                shot = "close-up"
                motion = "gentle push-in, warm and intimate"
            else:
                shot = "medium shot"
                motion = "stable camera with very subtle movement, natural"
            seg_prompt = (
                f"A vertical {shot} of the exact same person as in the first frame, placed in {scene}. "
                f"NO text, NO subtitles, NO captions, NO letters, NO numbers, NO logos, NO posters, "
                f"NO illustrations anywhere in the frame - pure photorealistic scene only. "
                f"CRITICAL IDENTITY LOCK: the face must stay pixel-consistent and identical to the first frame "
                f"through the whole clip - same eyes, nose, mouth, face shape, skin tone, same age and gender; "
                f"keep {hair}; keep the exact same clothing, outfit, colors and accessories as the first frame "
                f"through the whole clip; do not drift or subtly change any feature, do not change clothes, "
                f"do not beautify. "
                f"He speaks with perfectly lip-synced speech matching the provided audio, gentle natural expression, "
                f"subtle natural gestures, eyes to lens. {motion}. "
                f"Face sharp, stable natural skin tone, photorealistic, high detail. "
                f"The mouth must visibly open and close, clearly lip-synced with the speech the whole time. "
                f"No subtitles, no title, no watermark, no logos, no text, no letters or numbers anywhere; "
                f"no illustrations, posters or pictures inside the frame; background must stay plain and clean, "
                f"no signs, no writing, no screens showing content; photorealistic video only."
            )
            wf = segment_workflow(anchor_name, sp["audio"], seg_prompt, width, height,
                                  sp["length"], seed_base + i * 7, f"{self.tag}_{i:02d}")
            pid = self.comfy.submit(wf)
            log(f"段 {i}/{len(sents)} 生成中 (len={sp['length']}) ...")
            res = self.comfy.wait(pid, poll=5)
            vids = [f for f in self.comfy.output_files(res) if f.suffix == ".mp4"]
            if not vids:
                raise RuntimeError(f"段 {i} 未产出")
            seg_videos.append(vids[0])

        # 4) 每段去音轨 + 裁到该句等长
        trimmed = []
        for sp, v in zip(seg_specs, seg_videos):
            out = self.segdir / f"t{sp['i']:02d}.mp4"
            run_ff(["-i", str(v), "-t", f"{sp['dur']:.3f}", "-an",
                    "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-r", "24", str(out)])
            trimmed.append(out)

        # 5) 段间拼接：默认硬切保证口型精确；H3_XFADE_SECONDS>0 时用 xfade 柔和过渡
        video_only = self.workdir / "video_only.mp4"
        xfade_sec = float(os.environ.get("H3_XFADE_SECONDS", "0"))
        if xfade_sec > 0:
            _xfade_concat(trimmed, video_only, transition=xfade_sec)
        else:
            listfile = self.workdir / "concat.txt"
            listfile.write_text(
                "\n".join(f"file '{p.as_posix()}'" for p in trimmed),
                encoding="utf-8")
            run_ff(["-f", "concat", "-safe", "0", "-i", str(listfile),
                    "-c:v", "libx264", "-crf", "17",
                    "-pix_fmt", "yuv420p", "-r", "24", str(video_only)])

        # 6) 同源音轨 concat（驱动画面的同 N 句克隆音频）
        voice_list = self.workdir / "voices.txt"
        voice_list.write_text("\n".join(f"file '{sp['mp3'].as_posix()}'" for sp in seg_specs), encoding="utf-8")
        voice_all = self.workdir / "voice_all.mp3"
        run_ff(["-f", "concat", "-safe", "0", "-i", str(voice_list),
                "-c:a", "libmp3lame", "-b:a", "128k", str(voice_all)])

        # 7) 合成成片
        final = Path(final_output)
        final.parent.mkdir(parents=True, exist_ok=True)
        bgm = os.environ.get("H3_BGM_PATH", "").strip()
        bgm_volume = float(os.environ.get("H3_BGM_VOLUME", "0.12"))
        if bgm and os.path.exists(bgm):
            log(f"混入背景音乐: {bgm} (音量 {bgm_volume})")
            run_ff(["-i", str(video_only), "-i", str(voice_all), "-i", bgm,
                    "-filter_complex",
                    f"[1:a]volume=1.0[a1];[2:a]volume={bgm_volume}[bg];"
                    f"[a1][bg]amix=inputs=2:duration=first[aout]",
                    "-map", "0:v:0", "-map", "[aout]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                    "-shortest", str(final)])
        else:
            run_ff(["-i", str(video_only), "-i", str(voice_all),
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                    "-shortest", str(final)])

        # 8) 烧录底部抖音式字幕（底部居中、工整、无标点）
        ass_file = self.workdir / "subtitles.ass"
        ass_file.write_text(
            _build_subtitle_ass(seg_specs, width, height, emphasis=emphasis),
            encoding="utf-8")
        fontsdir = None
        for cand in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc",
                     r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simsun.ttc"):
            if os.path.exists(cand):
                fontsdir = str(Path(cand).parent)
                break
        sub_arg = _escape_filter_path(ass_file)
        vf = f"ass='{sub_arg}':fontsdir='{_escape_filter_path(fontsdir)}'" if fontsdir \
            else f"ass='{sub_arg}'"
        final_sub = self.workdir / "final_sub.mp4"
        run_ff(["-i", str(final), "-vf", vf,
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-pix_fmt", "yuv420p", "-r", "24", "-c:a", "copy",
                "-movflags", "+faststart", str(final_sub)])
        shutil.move(str(final_sub), str(final))
        log(f"底部字幕已烧录: {final} ({probe_duration(final):.2f}s)")

        log(f"成片完成: {final} ({probe_duration(final):.2f}s)")
        return final


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--person", required=True, help="人像照片（首帧/定妆照）")
    ap.add_argument("--script", help="文案文本文件（与 --text 二选一）")
    ap.add_argument("--text", help="直接给文案字符串")
    ap.add_argument("--scene", required=True, help="英文场景+动作描述")
    ap.add_argument("--out", required=True, help="输出成片 mp4")
    ap.add_argument("--workdir", default=None, help="中间文件目录")
    ap.add_argument("--anchor", default=None, help="可选：直接指定统一锚点帧，跳过定场图生成")
    ap.add_argument("--width", type=int, default=512)
    ap.add_argument("--height", type=int, default=960)
    ap.add_argument("--hair", default="", help="可选英文发型锁定描述")
    ap.add_argument("--seed", type=int, default=400000)
    a = ap.parse_args()

    if a.text:
        script = a.text
    else:
        script = Path(a.script).read_text(encoding="utf-8")
    wd = a.workdir or str(Path(a.out).with_suffix("") + "_work")
    H3Pipeline(workdir=wd).run(
        person_image=a.person, script_text=script, scene=a.scene, final_output=a.out,
        anchor_image=a.anchor, width=a.width, height=a.height, hair_hint=a.hair, seed_base=a.seed)


if __name__ == "__main__":
    main()


