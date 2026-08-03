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

# 中文字体 (macOS 自带, 部署到 Linux 时换 Noto Sans CJK 路径)
_FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/wqy-microhei/wqy-microhei.ttc",
]


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
    """移除 drawtext 不支持的字符, 单引号/冒号/反斜杠等需要转义"""
    # drawtext 中 text='xxx' 单引号包裹, 内部单引号会破坏语法
    return text.replace("\\", " ").replace("'", " ").replace(":", "：").replace("\n", " ")


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
    # 输出固定走 storage/output/ (与 main.py 的 StaticFiles mount="/static" 对应)
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

    n = len(valid_scenes)
    # 每个输入先 scale 到目标分辨率, 再 concat (素材原始尺寸可能不一致)
    scale_chain = ""
    concat_inputs = ""
    for i in range(n):
        scale_chain += f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setpts=PTS-STARTPTS[v{i}];"
        concat_inputs += f"[v{i}]"
    scale_chain = scale_chain.rstrip(";")
    concat_filter = scale_chain + ";" + f"{concat_inputs}concat=n={n}:v=1:a=0[cv]"

    # 2) 构造字幕 drawtext 链 (链式 , 串联, 最后一个输出到 [outv])
    drawtext_chain: List[str] = []
    for sub in subtitles:
        s = float(sub.get("start_sec") or 0)
        e = float(sub.get("end_sec") or s + 2)
        if e <= s:
            e = s + 2
        text = sub.get("text") or ""
        if not text.strip():
            continue
        drawtext_chain.append(_drawtext_filter(text, s, e, font))

    if drawtext_chain:
        # concat 输出 [cv] 是 labeled, 用 ; 重新拉链: [cv]drawtext1,drawtext2,...[outv]
        vf_arg = concat_filter + ";" + "[cv]" + ",".join(drawtext_chain) + "[outv]"
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
        audio_filter = (
            f"[{audio_idx}:a]atrim=0:{total_dur},asetpts=PTS-STARTPTS,"
            f"apad=whole_len={int(total_dur * 24000)}[aout]"
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
    cmd += [
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        "-s", resolution,
    ]
    if has_audio and tts_audio_path and Path(tts_audio_path).exists():
        cmd += ["-c:a", "aac", "-b:a", "128k", "-shortest"]
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

    # 6) 用 ffprobe 拿真实时长
    total_dur = sum(s["_duration"] for s in valid_scenes)
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(out_path)],
            capture_output=True, text=True, timeout=10,
        )
        if probe.returncode == 0 and probe.stdout.strip():
            total_dur = float(probe.stdout.strip())
    except Exception:
        pass

    return {
        "output_path": str(out_path),
        "output_url": f"/static/output/{out_filename}",
        "duration": round(total_dur, 1),
        "has_audio": has_audio,
        "file_size": out_path.stat().st_size,
        "scene_count": n,
        "subtitle_count": len(drawtext_chain),
    }
