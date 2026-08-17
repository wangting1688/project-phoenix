"""
口型同步服务 —— 真实 Wav2Lip 封装

设计原则（关键教训）：
- 口型同步必须调用官方 Wav2Lip 的 inference.py + 官方 wav2lip_gan.pth。
  二者训练时严格对应，自己实现网络结构必然导致口型对不上。
- 官方仓库通过 setup_lipsync_gpu.sh 克隆到 storage/models/wav2lip/（含 inference.py /
  models.py / audio.py / hparams.py / face_detection/）。
- 官方 inference.py 内部自带人脸检测（face_alignment），无需我们再做 Haar 预筛。

部署模式：
- 远程模式（LIPSYNC_REMOTE_SSH=user@host）：口型同步派发到 GPU 机器执行。
  本机（CPU 生产后端）只负责 scp 传文件 + ssh 调用，不依赖本机 torch/cuda，
  也避免在本机 CPU 上跑极慢的推理。
- 本地模式（LIPSYNC_REMOTE_SSH 为空）：在本机跑推理，依赖由所选引擎决定。

推理内核可插拔（见 lipsync_engines.py）：
- 本模块只负责链路（远程派发、素材预处理、失败降级），与具体模型无关；
- 具体模型由 LIPSYNC_ENGINE 环境变量选择（wav2lip / latentsync），
  便于低成本 A/B 对比而不改动链路代码。
"""
import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, List

WAV2LIP_CHECKPOINT = "storage/models/wav2lip_gan.pth"
WAV2LIP_REPO_DIR = "storage/models/wav2lip"  # 官方仓库(git clone) 根目录，含 inference.py

# 远程 GPU 机器地址（留空=本地运行；形如 root@1.2.3.4 则通过 ssh 派发）
LIPSYNC_REMOTE_SSH = os.environ.get("LIPSYNC_REMOTE_SSH", "").strip()
# 远程口型 HTTP 服务地址（方案A：本机 GPU worker 经反向 SSH 隧道暴露到 live:18080）
# 形如 http://127.0.0.1:18080 则通过 HTTP 派发，优先级高于 SSH 远程
LIPSYNC_REMOTE_HTTP = os.environ.get("LIPSYNC_REMOTE_HTTP", "").strip()
FFMPEG = os.environ.get("FFMPEG_BIN", "ffmpeg")
# 远程 HTTP 推理超时（秒）。扩散引擎(LatentSync)单条 20 秒视频约需 9~10 分钟，
# 且首条含模型加载，故给足余量；纯 CPU/网络异常靠 worker 侧自身超时兜底。
LIPSYNC_HTTP_TIMEOUT = int(os.environ.get("LIPSYNC_HTTP_TIMEOUT", "3600"))
# 影调提升（抬暗部）。素材偏暗时开启可显著改善"发黑"观感，置 0 关闭。
LIPSYNC_GRADE = os.environ.get("LIPSYNC_GRADE", "1").strip() == "1"


def _probe_source(fp, ffmpeg_bin) -> dict:
    """探测素材分辨率与是否 HDR（用 ffmpeg -i，无需 ffprobe）。"""
    info = {}
    try:
        r = subprocess.run([ffmpeg_bin, "-i", str(fp)],
                           capture_output=True, text=True, timeout=30)
        err = r.stderr
        m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", err, re.S)
        if m:
            w, h = int(m.group(1)), int(m.group(2))
            # 旋转信息有两种写法：老版 metadata 的 "rotate: 90"，
            # 新版 ffmpeg 的 "Display Matrix: rotation of -90.00 degrees"。
            # 只认前者会漏判手机竖拍素材，导致按横向高度做缩放判断。
            deg = None
            rot = re.search(r"rotate\s*:\s*(-?\d+)", err)
            if rot:
                deg = int(rot.group(1))
            else:
                dm = re.search(r"rotation of\s*(-?[\d.]+)\s*degrees", err)
                if dm:
                    deg = int(round(float(dm.group(1))))
            if deg is not None and abs(deg) % 180 == 90:
                w, h = h, w
            info["rotation"] = deg or 0
            info["width"], info["height"] = w, h
        # HLG / PQ / bt2020 都需要色调映射后才能当 SDR 用
        info["hdr"] = bool(re.search(r"arib-std-b67|smpte2084|bt2020", err))
    except Exception as e:
        print(f"[lipsync] 素材探测失败: {e}")
    return info


def _looks_like_mp4(data: bytes, content_type: str = "") -> bool:
    """判定响应体是否为真实 mp4。

    历史事故：worker 失败时返回 JSON，调用方仅检查首字节 '{'，
    而 FastAPI 把 (dict, 500) 序列化成 JSON 数组 '[...]' 且状态码 200，
    于是错误响应被写成 .mp4（29 字节），直到渲染阶段才报 "matches no streams"。
    """
    if len(data) < 32:
        return False
    if content_type and "json" in content_type.lower():
        return False
    if data[:1] in (b"{", b"["):
        return False
    # ISO BMFF: 前 4 字节为 box size，紧随其后是 'ftyp'
    return data[4:8] == b"ftyp"


_engines_mod = None


def _load_engines():
    """导入引擎层。

    正常后端进程走包导入；gpu_worker.py 为绕开 app/__init__ 的依赖用
    importlib 直接按路径加载本文件，此时 app 包不在 sys.path，需按路径兜底。
    """
    global _engines_mod
    if _engines_mod is None:
        try:
            from app.services import lipsync_engines as _m
        except Exception:
            import importlib.util
            _p = Path(__file__).resolve().parent / "lipsync_engines.py"
            _spec = importlib.util.spec_from_file_location("lipsync_engines", _p)
            _m = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_m)
        _engines_mod = _m
    return _engines_mod


class LipsyncService:
    """口型同步服务封装（链路层，推理内核可插拔）"""

    def __init__(self, storage_root: Path, engine: Optional[str] = None):
        self.storage_root = Path(storage_root)
        self.checkpoint = self.storage_root / WAV2LIP_CHECKPOINT
        self.repo_dir = self.storage_root / WAV2LIP_REPO_DIR
        self._engine_name = engine

    @property
    def engine(self):
        """当前推理引擎（进程内单例，模型只加载一次）"""
        return _load_engines().get_engine(self.storage_root, self._engine_name)

    # ------------------------------------------------------------------
    # 可用性检测
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """口型同步是否可用（模型 + 运行环境都有）"""
        if LIPSYNC_REMOTE_HTTP:
            # HTTP 远程模式：探活远程 worker 的 /health
            try:
                import urllib.request
                with urllib.request.urlopen(
                    LIPSYNC_REMOTE_HTTP.rstrip("/") + "/health", timeout=10
                ) as r:
                    if r.status == 200:
                        return True
            except Exception as e:
                print(f"[lipsync] 远程 HTTP 口型服务不可用: {e}")
            return False
        if LIPSYNC_REMOTE_SSH:
            if not self.checkpoint.exists():
                print(f"[lipsync] 缺少模型文件: {self.checkpoint}（请先运行 setup_lipsync_gpu.sh）")
                return False
            # 远程模式：检查远程是否有 checkpoint + inference.py + torch
            try:
                cmd = (
                    f"test -f {shlex.quote(str(self.checkpoint))} "
                    f"&& test -f {shlex.quote(str(self.repo_dir / 'inference.py'))} "
                    f"&& python3 -c 'import torch'"
                )
                r = subprocess.run(
                    ["ssh", LIPSYNC_REMOTE_SSH, cmd],
                    capture_output=True, text=True, timeout=25,
                )
                if r.returncode != 0:
                    print("[lipsync] 远程 GPU 机器不可用（checkpoint/inference.py/torch 缺失）")
                    return False
                return True
            except Exception as e:
                print(f"[lipsync] 远程可用性检查失败: {e}")
                return False
        # 本地模式：资产与依赖由所选推理引擎自行判定
        return self.engine.available

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def sync_video(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Optional[Path] = None,
    ) -> Optional[Path]:
        """
        对单个视频片段做口型同步，返回输出路径；失败返回 None。
        失败降级由调用方处理（用原素材）。
        """
        if not self.available:
            return None
        video_path = Path(video_path)
        audio_path = Path(audio_path)
        if not video_path.exists():
            print(f"[lipsync] 视频不存在: {video_path}")
            return None
        if not audio_path.exists():
            print(f"[lipsync] 音频不存在: {audio_path}")
            return None
        if output_path is None:
            output_path = video_path.parent / f"{video_path.stem}_lipsync.mp4"
        output_path = Path(output_path)

        try:
            if LIPSYNC_REMOTE_HTTP:
                ok = self._run_remote_http(video_path, audio_path, output_path)
            elif LIPSYNC_REMOTE_SSH:
                ok = self._run_remote(video_path, audio_path, output_path)
            else:
                ok = self._run_local(video_path, audio_path, output_path)
            if ok and output_path.exists() and output_path.stat().st_size > 0:
                return output_path
        except Exception as e:
            print(f"[lipsync] 执行异常: {e}")

        return None

    # ------------------------------------------------------------------
    # 本地执行（官方 inference.py）
    # ------------------------------------------------------------------

    def _run_local(self, video_path: Path, audio_path: Path, output_path: Path) -> bool:
        engine = self.engine
        if not engine.available:
            print(f"[lipsync] 引擎 {engine.name} 不可用")
            return False
        # 预处理产物必须落在 ASCII 路径：cv2 与 shell=True 的 ffmpeg 调用
        # 在 Windows 中文路径下会静默失败（坑#1）。项目根目录含中文，故用系统临时目录。
        tmp = Path(tempfile.gettempdir()) / "phx_lipsync"
        tmp.mkdir(parents=True, exist_ok=True)

        # 自带预处理的引擎（如 luogen 外部流水线）直接吃原素材：
        # 它内部会做音频规范化与探测，我们再转一遍只会多一次有损压缩。
        if getattr(engine, "skip_preprocess", False):
            print(f"[lipsync] 引擎={engine.name} 自带预处理，直接使用原素材")
            try:
                ok = engine.infer(video_path, audio_path, output_path)
            except Exception as e:
                print(f"[lipsync] 引擎 {engine.name} 推理异常: {e}")
                return False
            if not ok:
                return False
            if not (output_path.exists() and output_path.stat().st_size > 0):
                print(f"[lipsync] 引擎 {engine.name} 未产出有效文件")
                return False
            return True

        # 兼容 HEVC/HDR/rotate 素材：OpenCV(cv2) 读不了 h265/10bit/HDR 视频，
        # 会读出 0 帧导致推理静默失败（成片降级用原素材 = 嘴型与音频完全对不上）。
        # 先用 ffmpeg 转码为 h264 8bit（默认 autorotate 应用旋转），再喂给引擎。
        transcoded = tmp / f"face_in_{os.getpid()}.mp4"
        meta = _probe_source(video_path, FFMPEG)
        vf = []

        # HDR/HLG 素材必须做色调映射再转 SDR。
        # 这条素材是 bt2020nc + arib-std-b67(HLG)，若直接按 SDR 解码，
        # 画面整体发灰发暗（实测平均亮度 L 从 214.9 掉到 192.9），
        # 表现就是用户反馈的"发黑发暗"。tonemap=hable 保留高光细节。
        if meta.get("hdr"):
            vf.append("zscale=t=linear:npl=100,tonemap=hable,"
                      "zscale=t=bt709:m=bt709:r=tv")
            print("[lipsync] 检测到 HDR/HLG 素材，已启用色调映射")

        # 限高：过去写死 1280，把 2336 高的手机素材压掉 45% 像素，
        # 人脸裁剪随之变小，扩散模型可用的嘴部像素被砍掉一半 —— 这是
        # "模糊"的主因，而非模型能力。改为跟随引擎声明的上限，
        # 且只在确实超限时才缩放（不放大小素材）。
        max_h = engine.max_input_height
        src_h = meta.get("height") or 0
        if src_h and src_h > max_h:
            vf.append(f"scale=-2:{max_h}")
            print(f"[lipsync] 素材高度 {src_h} > {max_h}，缩放至 {max_h}")
        elif src_h:
            print(f"[lipsync] 素材高度 {src_h} 未超限，保持原分辨率")

        # 影调提升：抬暗部 + 略提饱和。
        # 与效果达标的对照项目逐帧比对后发现，我们素材的暗部被压得更死
        # （暗部 p5=66 vs 对照 85，皮肤亮度 169.6 vs 239.7）——这是拍摄光线
        # 差异，不是算法问题，但观感就是"整体发暗"。这里把影调拉到与对照
        # 相当的水平（p5≈92 / p95≈245，不过曝）。
        # 放在推理前做，模型才会基于提亮后的画面重绘嘴部；只做后处理会导致
        # 生成区与周围影调不一致。
        if LIPSYNC_GRADE:
            vf.append("eq=gamma=1.15:saturation=1.05,"
                      "curves=all='0/0.04 0.5/0.52 1/0.96'")
            print("[lipsync] 已启用影调提升（抬暗部）")

        vf.append("format=yuv420p")
        tc_cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", str(video_path),
                  "-vf", ",".join(vf)]
        # 部分引擎（LatentSync）按固定 video_fps 对齐 whisper 特征与视频帧，
        # 输入帧率不符会导致口型整体偏移，故在此统一重采样
        if engine.required_fps:
            tc_cmd += ["-r", str(engine.required_fps)]
        try:
            r = subprocess.run([FFMPEG, "-i", str(audio_path)],
                               capture_output=True, text=True, timeout=30)
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", r.stderr)
            if m:
                hh, mm, ss = (float(x) for x in m.groups())
                tc_cmd += ["-t", str(min(hh * 3600 + mm * 60 + ss + 2, 60))]
        except Exception:
            pass
        # crf 16 + preset slow：预处理产物是推理输入，也是细节复原的纹理供体，
        # 这一步的压缩损失会一路带到成片，不能省码率
        tc_cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "16",
                   "-pix_fmt", "yuv420p",
                   "-c:a", "aac", str(transcoded)]
        tc = subprocess.run(
            tc_cmd, capture_output=True, text=True, timeout=900,
        )
        if tc.returncode == 0 and transcoded.exists() and transcoded.stat().st_size > 0:
            video_path = transcoded
        else:
            print(f"[lipsync] 输入转码失败，将尝试直接用原始文件: {tc.stderr[-200:]}")

        print(f"[lipsync] 引擎={engine.name} 输入={video_path.name}")
        try:
            ok = engine.infer(video_path, audio_path, output_path)
        except Exception as e:
            print(f"[lipsync] 引擎 {engine.name} 推理异常: {e}")
            return False
        # 不能只信返回值：历史上 Wav2Lip 的 inference.py 失败也 exit 0（坑#6）
        if not ok:
            return False
        if not (output_path.exists() and output_path.stat().st_size > 0):
            print(f"[lipsync] 引擎 {engine.name} 未产出有效文件: {output_path}")
            return False
        return True

    # ------------------------------------------------------------------
    # 远程执行（GPU 机器）
    # ------------------------------------------------------------------

    def _run_remote(self, video_path: Path, audio_path: Path, output_path: Path) -> bool:
        remote = LIPSYNC_REMOTE_SSH
        remote_tmp = f"/tmp/wav2lip_{os.getpid()}"
        remote_face = f"{remote_tmp}/face.mp4"
        remote_audio = f"{remote_tmp}/audio.mp3"
        remote_out = f"{remote_tmp}/out.mp4"

        # 1) 建远程临时目录
        r = subprocess.run(
            ["ssh", remote, f"mkdir -p {remote_tmp}"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            print(f"[lipsync] 远程建目录失败: {r.stderr[-200:]}"); return False

        # 2) 传视频 + 音频到远程
        for local, remote_path in [(video_path, remote_face), (audio_path, remote_audio)]:
            r = subprocess.run(
                ["scp", "-q", "-o", "StrictHostKeyChecking=no", str(local), f"{remote}:{remote_path}"],
                capture_output=True, text=True, timeout=180,
            )
            if r.returncode != 0:
                print(f"[lipsync] scp 失败: {r.stderr[-200:]}"); return False

        # 3) 远程执行官方 inference（cwd=远程仓库根）
        remote_inference = str(Path(WAV2LIP_REPO_DIR) / "inference.py")
        remote_checkpoint = str(WAV2LIP_CHECKPOINT)
        remote_repo = str(WAV2LIP_REPO_DIR)
        cmd = (
            f"cd {shlex.quote(remote_repo)} && mkdir -p temp && "
            f"python3 {shlex.quote(remote_inference)} "
            f"--checkpoint_path {shlex.quote(remote_checkpoint)} "
            f"--face {shlex.quote(remote_face)} "
            f"--audio {shlex.quote(remote_audio)} "
            f"--outfile {shlex.quote(remote_out)} "
            f"--pads {' '.join(str(p) for p in WAV2LIP_PADS)} "
            f"--resize_factor {WAV2LIP_RESIZE_FACTOR} "
            f"--wav2lip_batch_size 128 --face_det_batch_size 16"
        )
        proc = subprocess.run(
            ["ssh", remote, cmd], capture_output=True, text=True, timeout=1800,
        )
        if proc.returncode != 0:
            print(f"[lipsync] 远程推理失败 rc={proc.returncode}: {proc.stderr[-600:]}")
            subprocess.run(["ssh", remote, f"rm -rf {remote_tmp}"], capture_output=True, text=True, timeout=30)
            return False

        # 4) 取回结果
        r = subprocess.run(
            ["scp", "-q", "-o", "StrictHostKeyChecking=no", f"{remote}:{remote_out}", str(output_path)],
            capture_output=True, text=True, timeout=180,
        )
        if r.returncode != 0:
            print(f"[lipsync] 取回结果失败: {r.stderr[-200:]}"); return False

        subprocess.run(["ssh", remote, f"rm -rf {remote_tmp}"], capture_output=True, text=True, timeout=30)
        return True

    # ------------------------------------------------------------------
    # 远程执行（HTTP：本机 GPU worker，经反向隧道暴露）
    # ------------------------------------------------------------------

    def _run_remote_http(self, video_path: Path, audio_path: Path, output_path: Path) -> bool:
        import urllib.error
        import urllib.request
        import uuid
        base = LIPSYNC_REMOTE_HTTP.rstrip("/")
        url = base + "/sync"
        boundary = "----phx_lipsync_%s" % uuid.uuid4().hex

        def _field(name: str, filename: str, data: bytes, ctype: str) -> bytes:
            head = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                f"Content-Type: {ctype}\r\n\r\n"
            ).encode()
            return head + data + b"\r\n"

        try:
            body = b"".join([
                _field("face", "face.mp4", open(video_path, "rb").read(), "video/mp4"),
                _field("audio", "audio.mp3", open(audio_path, "rb").read(), "audio/mpeg"),
            ]) + f"--{boundary}--\r\n".encode()
        except Exception as e:
            print(f"[lipsync] 读取本地文件失败: {e}")
            return False

        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        try:
            try:
                with urllib.request.urlopen(req, timeout=LIPSYNC_HTTP_TIMEOUT) as r:
                    data = r.read()
                    ctype = r.headers.get("Content-Type", "")
            except urllib.error.HTTPError as e:
                # worker 用 4xx/5xx 表达失败，body 里带 detail
                print(f"[lipsync] 远程 HTTP {e.code}: {e.read()[:300]}")
                return False

            if not _looks_like_mp4(data, ctype):
                # 关键：不能把错误响应写成 .mp4，否则「假成片」会一路流到渲染阶段
                print(f"[lipsync] 远程 HTTP 未返回视频(ctype={ctype!r}): {data[:200]}")
                return False

            with open(output_path, "wb") as f:
                f.write(data)
            return True
        except Exception as e:
            print(f"[lipsync] 远程 HTTP 推理失败: {e}")
            return False

    # ------------------------------------------------------------------
    # 批量处理：对多段素材分别做口型同步
    # ------------------------------------------------------------------

    def batch_sync(
        self,
        video_segments: List[dict],
        audio_path: Path,
    ) -> List[dict]:
        """
        对多段素材批量做口型同步。
        每段独立调用真实 Wav2Lip；某段失败则保留原素材（由调用方降级）。
        官方 inference.py 内部自带人脸检测，无需本服务再做预筛。
        """
        if not self.available:
            return video_segments

        result_segments = []
        for seg in video_segments:
            seg_path = seg.get("path")
            if not seg_path:
                result_segments.append(seg)
                continue
            out = self.sync_video(Path(seg_path), audio_path)
            if out:
                new_seg = dict(seg)
                new_seg["path"] = str(out)
                new_seg["_lipsync"] = True
                result_segments.append(new_seg)
            else:
                result_segments.append(seg)

        return result_segments


# ---------------------------------------------------------------------------
# 单例工厂
# ---------------------------------------------------------------------------

_lipsync_instance: Optional[LipsyncService] = None


def get_lipsync_service(storage_root: Optional[Path] = None) -> LipsyncService:
    """获取全局 LipsyncService 单例"""
    global _lipsync_instance
    if _lipsync_instance is None:
        from pathlib import Path as _Path
        if storage_root is None:
            storage_root = _Path(__file__).resolve().parent.parent.parent
        _lipsync_instance = LipsyncService(storage_root)
    return _lipsync_instance
