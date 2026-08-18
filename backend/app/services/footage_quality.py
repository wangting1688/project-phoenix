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
  唯一可用的 face_alignment 在 GPU worker 侧，太重不适合放进上传请求，
  故本模块只做亮度把关，人脸占比留给 worker 侧异步补充（见 measure_face_ratio）。
"""
import os
import re
import shutil
import subprocess
from typing import Dict, List, Optional

# 抽样帧数：均匀取样即可反映整体光线，取太多会拖慢上传响应
SAMPLE_FPS = "fps=1/2"
# ⚠️ format=yuv420p 不可省：10-bit 素材（手机 HDR 常见 yuv420p10le）下
# signalstats 按位深输出，YAVG 会是 0~1023，实测同一段素材 708 vs 178，
# 不归一化就会把偏暗的 HDR 素材误判成「过曝」。
# 实测归一化到 8bit 与走 zscale+tonemap 的结果只差 0.2，故不引入 zscale 依赖。
PIX_NORMALIZE = "format=yuv420p"
SAMPLE_SECONDS = 20

# 阈值依据实测标定（参照素材 YAVG 约 200+，问题素材 <120 明显偏暗）
BRIGHTNESS_MIN = 110.0      # 低于此值判定过暗，口型区域会发黑
BRIGHTNESS_LOW = 140.0      # 低于此值给出提示但不算失败
BRIGHTNESS_MAX = 245.0      # 高于此值判定过曝，嘴部细节被洗掉
# 人脸占画面宽度比例：LatentSync 把人脸裁剪缩放到 512 推理，
# 脸太小则嘴部有效像素不足，放大贴回就会模糊
FACE_RATIO_MIN = 0.12


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


def measure_face_ratio(file_path: str) -> Optional[float]:
    """人脸宽度占画面宽度的比例；无可用检测器时返回 None（表示「未检测」）。

    刻意不在这里引入人脸检测：上传接口需要秒级返回，而唯一可用的
    face_alignment 要加载模型（首次约 30s）。真正的人脸占比由 GPU worker
    在口型任务开始时统计，那里模型本来就是常驻的。
    """
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

    if face_ratio is not None:
        if face_ratio <= 0.0:
            level = "fair" if level == "good" else level
            warnings.append("未检测到清晰正脸，若用于口型视频请确保人物正面出镜。")
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
        "warnings": warnings,
        "suitable_for_lipsync": level != "poor",
    }
