"""素材拍摄质量检测（上传环节前置把关）。

为什么需要：口型同步的效果上限由素材本身决定，不是模型能补的。
实测对照——效果好的参照素材皮肤亮度 239.7、暗部 p5=85，我们用户素材只有
169.6 / p5=66，扩散模型在暗部缺乏可用像素，成片就会「发黑发暗」。
与其等 8 分钟渲染完才发现废片，不如在上传时就告诉用户重拍。

实现约束（重要）：
- 生产机没有 ffprobe，也没有 cv2/numpy，只有一个 static ffmpeg。
  因此亮度指标全部用 ffmpeg 的 signalstats 滤镜取，不引入新依赖。
- 人脸占比需要检测器。生产机没有 cv2，本机的 cv2 5.0 是 headless 版、
  没有 CascadeClassifier（注意 external_tools.py 里那段 Haar 代码实际已失效）。
  故人脸占比经反向隧道派发到 GPU worker 的 /inspect（face_alignment 常驻），
  worker 不可达时按 None 返回「未检测」，不阻断上传、也不伪造数据。
"""
import json
import os
import re
import shutil
import subprocess
import uuid
from typing import Dict, List, Optional

# 抽样帧数：均匀取样即可反映整体光线，取太多会拖慢上传响应
SAMPLE_FPS = "fps=1/2"
# ⚠️ format=yuv420p 不可省：10-bit 素材（手机 HDR 常见 yuv420p10le）下
# signalstats 按位深输出，YAVG 会是 0~1023，实测同一段素材 708 vs 178，
# 不归一化就会把偏暗的 HDR 素材误判成「过曝」。
# 实测归一化到 8bit 与走 zscale+tonemap 的结果只差 0.2，故不引入 zscale 依赖。
PIX_NORMALIZE = "format=yuv420p"
# 取样窗口。10-bit HDR 素材解码很贵：实测同一素材 20s 窗口耗时 12.4s，
# 8s 窗口只要 5.1s，而均值几乎一样（177.5 vs 177.1）。
SAMPLE_SECONDS = 8

# 阈值依据实测标定（参照素材 YAVG 约 200+，问题素材 <120 明显偏暗）
BRIGHTNESS_MIN = 110.0      # 低于此值判定过暗，口型区域会发黑
BRIGHTNESS_LOW = 140.0      # 低于此值给出提示但不算失败
BRIGHTNESS_MAX = 245.0      # 高于此值判定过曝，嘴部细节被洗掉
# 人脸占画面宽度比例：LatentSync 把人脸裁剪缩放到 512 推理，
# 脸太小则嘴部有效像素不足，放大贴回就会模糊
FACE_RATIO_MIN = 0.12
# 人脸检测派发到 GPU worker（与口型/TTS 共用同一条反向隧道）
INSPECT_HTTP_TIMEOUT = int(os.environ.get("INSPECT_HTTP_TIMEOUT", "300"))
# worker 探活超时。反向隧道断开时 POST /inspect 会一直挂到 INSPECT_HTTP_TIMEOUT，
# 上传请求随之卡两分钟以上，浏览器早已断连（nginx 记 499，用户看到「上传失败」，
# 而文件其实已落盘）。先用极短超时探 /health，不通就跳过人脸检测。
INSPECT_PROBE_TIMEOUT = float(os.environ.get("INSPECT_PROBE_TIMEOUT", "3"))
# 派发给 worker 的探测片段时长。6s 够抽 4 帧，与整片结果差异 <0.01
PROBE_CLIP_SECONDS = int(os.environ.get("PROBE_CLIP_SECONDS", "6"))


def _ffmpeg() -> Optional[str]:
    """定位 ffmpeg，兼容 systemd 下 PATH 不含 /usr/local/bin 的情况。"""
    env = os.environ.get("FFMPEG_BIN")
    if env and os.path.isfile(env):
        return env
    for p in (shutil.which("ffmpeg"), "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"):
        if p and os.path.isfile(p):
            return p
    return None


def measure_brightness(file_path: str) -> Dict[str, Optional[float]]:
    """用 signalstats 抽样统计亮度（Y 通道 0~255）。

    返回 avg / min / max；取不到时全为 None（调用方据此跳过判定）。
    """
    ff = _ffmpeg()
    if not ff or not os.path.exists(file_path):
        return {"avg": None, "min": None, "max": None}

    cmd = [ff, "-hide_banner", "-t", str(SAMPLE_SECONDS), "-i", file_path,
           "-vf", (f"{SAMPLE_FPS},{PIX_NORMALIZE},signalstats,"
                   "metadata=print:key=lavfi.signalstats.YAVG"),
           "-f", "null", "-"]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           universal_newlines=True, timeout=120)
    except Exception:
        return {"avg": None, "min": None, "max": None}

    vals: List[float] = []
    for m in re.finditer(r"lavfi\.signalstats\.YAVG=([0-9.]+)", r.stderr or ""):
        try:
            vals.append(float(m.group(1)))
        except ValueError:
            continue
    if not vals:
        return {"avg": None, "min": None, "max": None}
    return {
        "avg": round(sum(vals) / len(vals), 1),
        "min": round(min(vals), 1),
        "max": round(max(vals), 1),
    }


def _worker_base() -> Optional[str]:
    """取 GPU worker 地址。与 local_tts 同源配置，环境变量优先再回落 Settings。"""
    v = os.environ.get("TTS_REMOTE_HTTP")
    if v:
        return v.rstrip("/")
    try:
        from app.core.config import settings
        v = getattr(settings, "TTS_REMOTE_HTTP", None)
        return v.rstrip("/") if v else None
    except Exception:
        return None


def _make_probe_clip(file_path: str) -> Optional[str]:
    """截取用于人脸检测的短片段，失败则返回 None（调用方回退传原片）。

    ⚠️ 必须用 -c copy 流拷贝，不要重编码。实测 43MB 的 10-bit HDR 素材：
      重编码到 640 宽 → 20s（CPU 解 10bit 很贵），整体请求 34s
      流拷贝 6s 片段  → 0.03s，整体请求 2.2s
    人脸占比是比例值，不随分辨率变化；6s 与整片实测 0.559 vs 0.562。
    """
    ff = _ffmpeg()
    if not ff:
        return None
    import tempfile
    fd, tmp = tempfile.mkstemp(prefix="phx_probe_", suffix=".mp4")
    os.close(fd)
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error",
           "-t", str(PROBE_CLIP_SECONDS), "-i", file_path,
           "-c", "copy", "-an", tmp]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            return tmp
    except Exception:
        pass
    try:
        os.unlink(tmp)
    except OSError:
        pass
    return None


def _worker_alive(base: str) -> bool:
    """短超时探 worker /health。隧道断开时 TCP 连接会挂住，
    这里用秒级超时快速判死，避免拖垮上传响应。"""
    import urllib.request

    try:
        with urllib.request.urlopen(base + "/health",
                                    timeout=INSPECT_PROBE_TIMEOUT) as r:
            return r.status == 200
    except Exception:
        return False


def measure_face_ratio(file_path: str) -> Optional[float]:
    """人脸宽度占画面宽度的比例，派发到 GPU worker 的 /inspect 计算。

    不在本进程做检测：生产机没有 cv2，且 face_alignment 首次加载约 30s，
    而 worker 侧模型本来就常驻。worker 不可达时返回 None（语义是「未检测」，
    不是「不合格」），调用方据此跳过这项判定。
    """
    import urllib.error
    import urllib.request

    base = _worker_base()
    if not base or not os.path.exists(file_path):
        return None

    # 隧道断了就别再抽片段、传大文件了，直接判「未检测」
    if not _worker_alive(base):
        print("[footage] GPU worker 不可达，跳过人脸检测")
        return None

    # 整片经反向隧道回传太慢（实测 43MB 素材耗时 22s），先抽一小段再传。
    # 检测本来只看抽样帧，前若干秒足够代表人物出镜情况。
    clip = _make_probe_clip(file_path)
    boundary = "----phx_inspect_%s" % uuid.uuid4().hex
    try:
        with open(clip or file_path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None
    finally:
        if clip:
            try:
                os.unlink(clip)
            except OSError:
                pass

    head = (f"--{boundary}\r\nContent-Disposition: form-data; "
            f'name="video"; filename="{os.path.basename(file_path)}"\r\n'
            "Content-Type: video/mp4\r\n\r\n").encode()
    body = head + raw + b"\r\n" + f"--{boundary}--\r\n".encode()

    req = urllib.request.Request(base + "/inspect", data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        with urllib.request.urlopen(req, timeout=INSPECT_HTTP_TIMEOUT) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        print(f"[footage] 人脸检测 HTTP {e.code}: {e.read()[:200]}")
        return None
    except Exception as e:
        print(f"[footage] 人脸检测不可用: {e}")
        return None

    ratio = data.get("face_ratio")
    if ratio is None:
        return None
    try:
        return float(ratio)
    except (TypeError, ValueError):
        return None


def inspect_footage(file_path: str) -> Dict:
    """综合检测，产出可直接展示给用户的拍摄建议。

    只做提示，不拦截上传：素材可能用于非口型用途（如 B-roll 插入），
    由用户自己决定是否重拍。
    """
    brightness = measure_brightness(file_path)
    face_ratio = measure_face_ratio(file_path)

    warnings: List[str] = []
    level = "good"

    avg = brightness.get("avg")
    if avg is not None:
        if avg < BRIGHTNESS_MIN:
            level = "poor"
            warnings.append(
                f"画面偏暗（亮度 {avg}，建议 {int(BRIGHTNESS_LOW)} 以上）。"
                "口型合成会出现嘴部发黑发暗，建议正面补光后重拍。")
        elif avg < BRIGHTNESS_LOW:
            level = "fair" if level == "good" else level
            warnings.append(
                f"光线略暗（亮度 {avg}）。可用时，但正面补光后口型会更清晰。")
        elif avg > BRIGHTNESS_MAX:
            level = "fair" if level == "good" else level
            warnings.append(
                f"画面接近过曝（亮度 {avg}），嘴部细节可能丢失，建议降低补光强度。")

    # 没有人脸 = 根本做不了口型，但素材本身可能是合格的空镜（B-roll），
    # 所以不算 poor，而是单独标记 suitable_for_lipsync=False。
    has_face = None
    if face_ratio is not None:
        has_face = face_ratio > 0.0
        if not has_face:
            level = "fair" if level == "good" else level
            warnings.append("未检测到清晰正脸，无法用于口型视频（作为空镜素材可用）。")
        elif face_ratio < FACE_RATIO_MIN:
            level = "poor"
            warnings.append(
                f"人脸偏小（占画面宽度 {int(face_ratio * 100)}%，"
                f"建议 {int(FACE_RATIO_MIN * 100)}% 以上）。"
                "人脸太小会让口型区域模糊，建议靠近镜头重拍。")

    return {
        "level": level,
        "brightness": brightness,
        "face_ratio": face_ratio,
        "has_face": has_face,
        "warnings": warnings,
        # 未检测到人脸时直接判不可用；has_face 为 None 表示未检测，不做否定
        "suitable_for_lipsync": level != "poor" and has_face is not False,
    }
