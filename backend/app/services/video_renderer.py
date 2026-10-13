"""
视频渲染服务 - ffmpeg 字幕烧录 + 后期接 TTS 配音

设计:
- 纯函数式, 不依赖 DB, 输入 CompositionPlan 字典, 输出 mp4 文件路径
- 同步执行 (本地 dev 5 段素材 + drawtext ~5-15s)
- 字幕用 drawtext 烧, 避免 Pillow 依赖; 中文字体走 macOS /System/Library/Fonts/PingFang.ttc
- TTS 配音: 留 hook, 后续 edge-tts 接入
"""
import os
import re
import shutil
import subprocess
import tempfile
import time
import platform
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 中文字体候选，按"字形观感优先"排序：先黑体类（短视频字幕通用），再兜底。
# 注意生产机是 CentOS 系，路径与 Debian 不同（/usr/share/fonts/wqy-microhei/…
# 而不是 /usr/share/fonts/truetype/wqy/…）。原列表里 Debian 与 macOS 路径占多数，
# 线上其实只有最后一项碰巧命中，属于运气而非设计，故显式补全常见发行版路径。
_FONT_CANDIDATES = [
    # macOS 开发机
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    # CentOS / RHEL 系（生产机）
    "/usr/share/fonts/wqy-microhei/wqy-microhei.ttc",
    "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc",
    "/usr/share/fonts/adobe-source-han-sans-cn/SourceHanSansCN-Regular.otf",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
    # Debian / Ubuntu 系
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    # Windows 开发机
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]


def _probe_video_meta(fp: Path) -> Optional[Tuple[int, int, float]]:
    """用 ffmpeg -i 探测视频分辨率与时长（无 ffprobe 环境）。

    返回 (width, height, duration_sec)；失败返回 None。
    若带 rotate:90/270 元数据（手机竖拍常见），交换宽高得到真实显示尺寸。
    """
    try:
        r = subprocess.run(
            ["ffmpeg", "-i", str(fp)],
            capture_output=True, text=True, timeout=15,
        )
        err = r.stderr
        res_m = re.search(r"(\d{2,5})x(\d{2,5})", err)
        if not res_m:
            return None
        w, h = int(res_m.group(1)), int(res_m.group(2))
        rot_m = re.search(r"rotate\s*:\s*(\d+)", err)
        if rot_m and int(rot_m.group(1)) in (90, 270):
            w, h = h, w
        dur_m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", err)
        dur: Optional[float] = None
        if dur_m:
            hh, mm, ss = (float(x) for x in dur_m.groups())
            dur = hh * 3600 + mm * 60 + ss
        return (w, h, dur)
    except Exception:
        return None


def _probe_duration_any(fp: Path) -> float:
    """成片时长（秒）。ffprobe 优先，不可用时回落 ffmpeg -i。

    生产机只装了 ffmpeg，没有 ffprobe，所以不能只依赖前者，
    否则时长探测会永久静默失败并悄悄回落到计划值。
    """
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(fp)],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0 and r.stdout.strip():
            return float(r.stdout.strip())
    except Exception:
        pass
    meta = _probe_video_meta(fp)
    if meta and meta[2]:
        return float(meta[2])
    return 0.0


def generate_tts_mp3(text: str, output_path: Path) -> Path:
    """
    用 macOS `say` 命令生成中文 TTS, 再 ffmpeg 转 mp3 16kHz mono.
    非 macOS 平台抛 NotImplementedError (后续接 edge-tts).

    Args:
        text: 要合成的文本
        output_path: 输出的 mp3 路径
    Returns:
        output_path
    """
    if platform.system() != "Darwin":
        raise NotImplementedError("当前平台未实现 TTS, 仅支持 macOS say")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_aiff = output_path.with_suffix(".aiff")

    # macOS 自带 voice 中 Sin-ji 是粤语, 可说中文 (zh_HK)
    # Tingting/Mei-Jia 不一定存在, 探测到啥用啥
    voices = ["Sin-ji"]  # zh_HK
    proc = None
    for voice in voices:
        try:
            proc = subprocess.run(
                ["say", "-v", voice, "-o", str(tmp_aiff), text],
                capture_output=True, text=True, timeout=30,
            )
            if proc.returncode == 0 and tmp_aiff.exists():
                break
        except Exception:
            continue
    if proc is None or proc.returncode != 0 or not tmp_aiff.exists():
        # fallback: 默认 voice
        proc = subprocess.run(
            ["say", "-o", str(tmp_aiff), text],
            capture_output=True, text=True, timeout=30,
        )
    if proc.returncode != 0 or not tmp_aiff.exists():
        raise RuntimeError(f"TTS 失败: {proc.stderr if proc else 'no proc'}")

    # aiff -> mp3 16k mono
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

    if not output_path.exists() or output_path.stat().st_size < 100:
        raise RuntimeError(f"TTS 输出文件异常: {output_path}")

    return output_path


def _find_chinese_font() -> str:
    for p in _FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(
        "未找到中文字体, 请安装 PingFang/STHeiti/Noto CJK 后重试"
    )


def _sanitize_text(text: str) -> str:
    """
    清理 drawtext 文本中的危险字符。
    ffmpeg filter_complex 用逗号分隔滤镜链，所以 text 里不能有逗号。
    drawtext text='...' 单引号包裹，不能有单引号。
    反斜杠也要去掉，避免转义问题。
    """
    return (
        text.replace("\\", " ")
        .replace("'", " ")
        .replace(",", "，")   # 英文逗号 → 中文逗号（不破坏 filter 结构）
        .replace(":", "：")
        .replace("\n", " ")
        .replace(";", "；")
    )


# 单行最多几个字。短视频竖屏画面窄，一行超过约 16 字就会挤到边缘，
# 观众来不及看完；行业通行做法是 12~16 字一行、最多两行。
SUB_MAX_CHARS_PER_LINE = int(os.environ.get("SUB_MAX_CHARS_PER_LINE", "14"))
# 一条字幕最多几行。超过就该拆成下一条，而不是堆三四行盖住画面。
SUB_MAX_LINES = int(os.environ.get("SUB_MAX_LINES", "2"))
# 次级断句标点：句号问号切完仍过长时，在这些位置继续拆。
_SUB_BREAK_CHARS = "，、；：,;:"


def _split_long_text(text: str, limit: int) -> List[str]:
    """把过长的字幕文本拆成若干短句。

    优先在标点处断，读起来才自然；找不到合适标点再按字数硬切。
    原来的分句只按句号问号切，一句 47 字（约 3000px 宽）直接冲出 1088px 画面，
    这是"字幕太长"的根因。
    """
    text = text.strip()
    if len(text) <= limit:
        return [text] if text else []

    out: List[str] = []
    rest = text
    while len(rest) > limit:
        # 在 [limit*0.5, limit] 区间里找最靠后的标点，避免切出一两个字的碎片
        cut = -1
        for i in range(limit - 1, max(int(limit * 0.5), 1) - 1, -1):
            if rest[i] in _SUB_BREAK_CHARS:
                cut = i + 1  # 标点跟在上一句尾部
                break
        if cut <= 0:
            cut = limit
        piece = rest[:cut].strip().strip("".join(_SUB_BREAK_CHARS))
        if piece:
            out.append(piece)
        rest = rest[cut:].strip()
    rest = rest.strip("".join(_SUB_BREAK_CHARS))
    if rest:
        out.append(rest)
    return out


def _wrap_lines(text: str, limit: int) -> str:
    """按字数折行，返回用 ASS 换行符 \\N 连接的文本。"""
    lines = [text[i:i + limit] for i in range(0, len(text), limit)]
    return "\\N".join(lines)


def _rescale_subtitles(subtitles: List[Dict[str, Any]],
                       audio_dur: float) -> List[Dict[str, Any]]:
    """把字幕时间轴按真实配音时长整体缩放。

    上游 build_subtitles 用「字数 // 4」估时长，与真实语速无关：本条素材
    估出 69 秒而配音实际 66 秒，逐句误差累积后字幕明显跑在口型前后。
    这里按 真实时长/估算总长 统一缩放，让首尾对齐、中间按比例分布。
    比逐句强对齐粗，但不需要额外的语音对齐依赖，且能消除累积漂移。
    """
    if not subtitles or audio_dur <= 0:
        return subtitles
    est_total = max(float(s.get("end_sec") or 0) for s in subtitles)
    if est_total <= 0:
        return subtitles
    k = audio_dur / est_total
    # 比例太接近 1 就不动，避免无意义的微调掩盖真实问题
    if abs(k - 1.0) < 0.02:
        return subtitles
    print(f"[render] 字幕时间轴按配音校准: 估算 {est_total:.1f}s -> "
          f"实际 {audio_dur:.1f}s（x{k:.3f}）")
    out = []
    for s in subtitles:
        out.append({
            **s,
            "start_sec": float(s.get("start_sec") or 0) * k,
            "end_sec": float(s.get("end_sec") or 0) * k,
        })
    return out


def _normalize_subtitles(subtitles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """把上游字幕规整成"每条不超过两行、每行不超过 14 字"的短句。

    时长按字数比例分摊到拆出来的各段，保持与配音节奏大致同步。
    """
    per_entry = SUB_MAX_CHARS_PER_LINE * SUB_MAX_LINES
    out: List[Dict[str, Any]] = []
    for sub in subtitles:
        raw = (sub.get("text") or "").strip()
        if not raw:
            continue
        start = float(sub.get("start_sec") or 0)
        end = float(sub.get("end_sec") or start + 2)
        if end <= start:
            end = start + 2
        pieces = _split_long_text(raw, per_entry)
        if not pieces:
            continue
        total_chars = sum(len(p) for p in pieces) or 1
        cursor = start
        span = end - start
        for p in pieces:
            share = span * len(p) / total_chars
            # 太短会一闪而过看不清；0.8 秒是可读下限
            seg_end = min(end, cursor + max(share, 0.8))
            out.append({
                "text": p,
                "start_sec": cursor,
                "end_sec": seg_end,
            })
            cursor = seg_end
    return out


def _escape_filter_path(p) -> str:
    """把路径转成能安全嵌进 ffmpeg filter 选项的形式。

    filter 用冒号分隔选项，所以 Windows 盘符的冒号必须转义（D: -> D\\:），
    反斜杠一律换成正斜杠。实测漏掉任一处都会报
    "Error parsing filterchain"，而且 fontsdir 与字幕路径都需要处理。
    """
    return str(p).replace("\\", "/").replace(":", "\\:")


def _ass_escape(text: str) -> str:
    """ASS 事件行里的危险字符。

    与 drawtext 不同，ASS 不受 ffmpeg filter 语法限制（无需替换逗号冒号），
    只要避开花括号（覆盖标签）与真实换行即可，所以标点能原样保留。
    """
    return (text.replace("\\", "")
                .replace("{", "(")
                .replace("}", ")")
                .replace("\n", " ")
                .replace("\r", " "))


def _strip_punctuation(text: str) -> str:
    """去掉标点，抖音式字幕干净工整；只保留汉字/数字/字母/空格。"""
    return re.sub(r"[^\w\s\u4e00-\u9fff]", "", text).strip()


def _ass_time(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _build_ass(subtitles: List[Dict[str, Any]], width: int, height: int,
               font_path: str) -> str:
    """生成 ASS 字幕内容。

    改用 libass 而不是继续堆 drawtext：drawtext 没有换行能力，一条长句只能
    整行铺开并冲出画面；libass 是 Aegisub/VLC 同一套渲染引擎，原生支持
    折行、描边、阴影与安全边距，且生产机的 ffmpeg 已带 ass/subtitles 滤镜。
    """
    # 字号按画面高度取，竖屏 1920 高时约 60px，换分辨率不用改代码
    font_size = max(28, int(height * 0.032))
    margin_v = max(40, int(height * 0.12))     # 底部安全区，避开平台控件
    margin_h = max(30, int(width * 0.06))      # 左右安全边距
    outline = max(2, int(font_size * 0.06))
    shadow = max(1, int(font_size * 0.03))
    font_name = Path(font_path).stem

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{outline},{shadow},2,{margin_h},{margin_h},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for sub in subtitles:
        text = _wrap_lines(_strip_punctuation(_ass_escape(sub["text"])),
                           SUB_MAX_CHARS_PER_LINE)
        lines.append(
            f"Dialogue: 0,{_ass_time(sub['start_sec'])},"
            f"{_ass_time(sub['end_sec'])},Default,,0,0,0,,{text}"
        )
    return "\n".join(lines) + "\n"


def _drawtext_filter(text: str, start_sec: float, end_sec: float, font: str) -> str:
    """构造一条 drawtext filter 表达式, enable 控制时间窗口"""
    safe = _sanitize_text(text)
    return (
        f"drawtext=fontfile={font}:"
        f"text='{safe}':"
        f"fontcolor=white:fontsize=64:"
        f"box=1:boxcolor=black@0.55:boxborderw=18:"
        f"x=(w-text_w)/2:y=h*0.78:"
        f"enable='between(t,{start_sec},{end_sec})'"
    )


def _resolve_footage_path(file_path: str, storage_root: Path) -> Optional[Path]:
    """素材路径可能是绝对路径或相对 storage 目录, 都尝试解析"""
    if not file_path:
        return None
    p = Path(file_path)
    if p.is_absolute() and p.exists():
        return p
    # 相对 storage 目录
    candidate = storage_root / file_path.lstrip("/")
    if candidate.exists():
        return candidate
    return None


def render_video(
    plan: Dict[str, Any],
    project_id: int,
    user_id: int,
    storage_root: Path,
    tts_text: Optional[str] = None,
    tts_audio_path: Optional[Path] = None,
    custom_speaker_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    同步执行 ffmpeg 渲染, 返回 {output_path, duration, has_audio}

    Args:
        plan: CompositionPlan dict (含 scene_plan / subtitles / output_format)
        project_id: 项目 ID (用于输出文件名)
        user_id: 用户 ID (用于关联 storage/footage)
        storage_root: backend/ 根目录 (用于解析 file_path="storage/footage/...")
        tts_text: 要合成的文案 (会自动调用 TTS 生成 mp3)
        tts_audio_path: 已生成好的 TTS mp3 路径 (跳过生成步骤)
    """
    storage_root = Path(storage_root)
    # 输出固定走 storage/output/ (与 main.py 的 /static 鉴权路由对应)
    output_dir = storage_root / "storage" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # TTS 生成 (如需要)
    # 优先级: 用户克隆声纹 -> 火山官方精品音色 -> macOS say
    has_audio = False
    if tts_audio_path and Path(tts_audio_path).exists():
        has_audio = True
    elif tts_text:
        try:
            tts_out = output_dir / f"tts_{project_id}_{int(time.time())}.mp3"
            from app.services.voice_clone import synthesize as vc_synthesize
            from app.core.database import SessionLocal
            _db = SessionLocal()
            try:
                vc_synthesize(
                    db=_db,
                    custom_speaker_id=custom_speaker_id,
                    text=tts_text,
                    output_path=tts_out,
                )
            finally:
                _db.close()
            tts_audio_path = tts_out
            has_audio = True
        except NotImplementedError as e:
            print(f"[video_renderer] TTS 跳过: {e}")
        except Exception as e:
            print(f"[video_renderer] TTS 生成失败, 继续无音视频: {e}")

    scene_plan = plan.get("scene_plan") or []
    subtitles = plan.get("subtitles") or []
    output_format = plan.get("output_format") or {}

    resolution = output_format.get("resolution", "1080x1920")
    w, h = (int(x) for x in resolution.split("x"))
    fps = int(output_format.get("fps", 30))

    if not scene_plan:
        raise ValueError("plan.scene_plan 为空, 无可渲染素材")

    font = _find_chinese_font()

    # 1) 准备每个 scene 的输入 (trim 0~duration)
    input_args: List[str] = []
    valid_scenes: List[Dict[str, Any]] = []
    for scene in scene_plan:
        fp = _resolve_footage_path(scene.get("footage_path", ""), storage_root)
        if not fp:
            continue
        duration = max(1, int(scene.get("duration") or 5))
        input_args += ["-ss", "0", "-t", str(duration), "-i", str(fp)]
        valid_scenes.append({**scene, "_duration": duration, "_resolved": str(fp)})

    if not valid_scenes:
        raise ValueError("所有素材路径都解析失败, 无可渲染输入")

    # 分辨率一律跟随源素材，不做上采样也不做下采样。
    # 过去只处理"源更低"的情况，于是口型中间件 1088x2336 被压回默认的
    # 1080x1920：口型阶段辛苦保住的像素在渲染阶段又丢掉，成片依旧发糊。
    # 现在两个方向都跟随源，只把奇数边补成偶数（libx264 要求）。
    src_meta = _probe_video_meta(Path(valid_scenes[0]["_resolved"]))
    if src_meta:
        sw, sh, _ = src_meta
        if sw and sh and (sw, sh) != (w, h):
            w, h = sw - (sw % 2), sh - (sh % 2)
            resolution = f"{w}x{h}"
            print(f"[render] 输出分辨率跟随源素材: {resolution}")

    n = len(valid_scenes)
    # 每个输入先 scale 到目标分辨率, 再 concat (素材原始尺寸可能不一致)
    scale_chain = ""
    concat_inputs = ""
    for i in range(n):
        scale_chain += f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setpts=PTS-STARTPTS[v{i}];"
        concat_inputs += f"[v{i}]"
    scale_chain = scale_chain.rstrip(";")
    concat_filter = scale_chain + ";" + f"{concat_inputs}concat=n={n}:v=1:a=0[cv]"

    # 2) 字幕：先规整成短句，再交给 libass 渲染。
    # 不再用 drawtext —— 它没有折行能力，一条 47 字的长句会排到约 3000px 宽而
    # 冲出 1088px 的竖屏画面（这是"字幕太长"的根因）。libass 支持折行、描边、
    # 安全边距，且生产机 ffmpeg 已带 ass 滤镜。
    # 先按真实配音时长校准，再拆分折行；顺序不能反，
    # 否则拆分后的分摊时长会建立在错误的总长上。
    if has_audio and tts_audio_path and Path(tts_audio_path).exists():
        subtitles = _rescale_subtitles(
            subtitles, _probe_duration_any(Path(tts_audio_path)))
    norm_subs = _normalize_subtitles(subtitles)
    ass_path: Optional[Path] = None
    if norm_subs:
        ass_path = output_dir / f"sub_{project_id}_{int(time.time())}.ass"
        ass_path.write_text(_build_ass(norm_subs, w, h, font), encoding="utf-8")
        print(f"[render] 字幕 {len(subtitles)} 条 -> 规整为 {len(norm_subs)} 条短句"
              f"（每行 <= {SUB_MAX_CHARS_PER_LINE} 字，最多 {SUB_MAX_LINES} 行）")
        # ass 滤镜的路径参数要转义盘符冒号（filter 用冒号分隔选项）。
        # fontsdir 同样要转义，漏掉它在 Windows 上会报 Error parsing filterchain。
        ass_arg = _escape_filter_path(ass_path)
        fonts_arg = _escape_filter_path(Path(font).parent)
        vf_arg = (concat_filter + ";" + "[cv]"
                  + f"ass='{ass_arg}':fontsdir='{fonts_arg}'"
                  + "[outv]")
    else:
        vf_arg = concat_filter.replace("[cv]", "[outv]")

    # 3) 音频处理
    audio_args: List[str] = []
    map_args = ["-map", "[outv]"]
    if has_audio and tts_audio_path and Path(tts_audio_path).exists():
        # TTS 配音 - 缩短到视频总长
        total_dur = sum(s["_duration"] for s in valid_scenes)
        audio_args += ["-i", str(tts_audio_path)]
        # vf_arg 末尾是 ...[outv], 直接在末尾追加 audio filter
        # atrim 截到视频长, 不足部分用 apad 补静音 (TTS 短于视频时长)
        # audio index = n (video 数) + 0 = TTS 是最后一个 input
        audio_idx = n
        # apad 不带长度参数：补静音直到输出结束，最终长度由下面的 -t 限定。
        #
        # 原来写 apad=whole_len={total_dur * 24000}，而 whole_len 的单位是采样数、
        # 必须按音频真实采样率换算。本地 CosyVoice2 交付的是 16kHz，于是音轨被补到
        # 72 x 24000/16000 = 108 秒，成片容器声明 108 秒而画面只有 72 秒。
        # 也不能改用 whole_dur（秒）：生产机的 ffmpeg 是 2018 年静态构建，
        # 实测报 "Option 'whole_dur' not found"。
        # 交给 -t 截断则与两个版本都兼容，且不依赖采样率。
        audio_filter = (
            f"[{audio_idx}:a]atrim=0:{total_dur},asetpts=PTS-STARTPTS,apad[aout]"
        )
        vf_arg = vf_arg + ";" + audio_filter
        map_args = ["-map", "[outv]", "-map", "[aout]"]

    # 4) 拼装 ffmpeg 命令
    out_filename = f"render_{project_id}_{int(time.time())}.mp4"
    out_path = output_dir / out_filename

    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    cmd += input_args
    cmd += audio_args  # TTS 必须在 video inputs 之后, audio_idx 才正确
    cmd += ["-filter_complex", vf_arg]
    cmd += map_args
    # crf 18 + preset medium：口型中间件是 9Mbps 的高质量源，
    # 用 crf23/fast 交付会把嘴部细节再压掉一轮（实测成片掉到 2.8Mbps）。
    cmd += [
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        "-s", resolution,
        "-movflags", "+faststart",
    ]
    if has_audio and tts_audio_path and Path(tts_audio_path).exists():
        # 显式 -t 限死总时长，不能只靠 -shortest：线上 ffmpeg 是 2018 年的静态
        # 构建，-shortest 对 filter_complex 产生的音轨不生效（本地 ffmpeg 9 会
        # 截断，所以这个问题在本地复现不出来）。缺了它，被 apad 补长的音轨会
        # 原样写进容器：成片画面 72 秒而容器声明 108 秒，播放器进度条走到
        # 108 秒、后 36 秒画面停住空转。
        cmd += ["-c:a", "aac", "-b:a", "128k", "-shortest", "-t", str(total_dur)]
    else:
        cmd += ["-an"]  # 无音频
    cmd.append(str(out_path))

    # 5) 执行
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg 失败 (rc={proc.returncode}): {proc.stderr[-500:]}")

    if not out_path.exists() or out_path.stat().st_size < 1024:
        raise RuntimeError(f"ffmpeg 输出文件异常: {out_path} ({out_path.stat().st_size if out_path.exists() else 0} bytes)")

    # 6) 取成片真实时长。
    # 生产机没有 ffprobe（实测 which ffprobe 为空），原来这里 except 静默吞掉，
    # 于是 duration 一直回落到"计划时长"而非成片实际长度 —— 成片容器 108 秒
    # 却入库 72 秒，两边不一致时反而掩盖了渲染缺陷。改为 ffprobe 不可用时
    # 用 ffmpeg -i 解析（本项目其他地方也用这个办法），并把偏差打出来。
    planned_dur = sum(s["_duration"] for s in valid_scenes)
    total_dur = planned_dur
    probed = _probe_duration_any(out_path)
    if probed > 0:
        total_dur = probed
        if abs(probed - planned_dur) > 1.5:
            print(f"[render] 警告: 成片时长 {probed:.1f}s 与计划 {planned_dur}s "
                  f"偏差过大，请检查音轨补齐与 -t 截断是否生效")
    else:
        print(f"[render] 无法探测成片时长，按计划时长 {planned_dur}s 记账")

    # 6.5) 生成封面缩略图（取第 1 秒帧）
    cover_filename = out_filename.replace(".mp4", "_cover.jpg")
    cover_path = output_dir / cover_filename
    cover_url = None
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-ss", "1", "-i", str(out_path),
                "-vframes", "1", "-q:v", "5",
                "-vf", "scale=360:-2",
                str(cover_path),
            ],
            capture_output=True, text=True, timeout=15,
        )
        if cover_path.exists() and cover_path.stat().st_size > 0:
            cover_url = f"/static/output/{cover_filename}"
    except Exception:
        pass

    return {
        "output_path": str(out_path),
        "output_url": f"/static/output/{out_filename}",
        "cover_url": cover_url,
        "duration": round(total_dur, 1),
        "has_audio": has_audio,
        "file_size": out_path.stat().st_size,
        "scene_count": n,
        "subtitle_count": len(norm_subs),
    }
