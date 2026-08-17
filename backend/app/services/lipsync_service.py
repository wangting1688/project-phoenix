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

        # 兼容 HEVC/HDR/rotate 素材：OpenCV(cv2) 读不了 h265/10bit/HDR 视频，
        # 会读出 0 帧导致 Wav2Lip 静默失败（成片降级用原素材 = 嘴型与音频完全对不上）。
        # 先用 ffmpeg 转码为 h264 8bit（默认 autorotate 应用旋转），再喂给 inference。
        transcoded = tmp / f"face_in_{os.getpid()}.mp4"
        # 限制高度≤1280(720p 级)：超大分辨率素材(如手机 2336 高)人脸检测极慢/易卡，
        # 720p 级在速度和口型精度间平衡最佳；并只截取到 TTS 音频时长附近
        max_h = engine.max_input_height
        tc_cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", str(video_path),
                  "-vf", f"scale=-2:min({max_h}\\,ih)"]
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
        tc_cmd += ["-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
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
            with urllib.request.urlopen(req, timeout=1800) as r:
                data = r.read()
            if data[:1] == b"{":  # 远程返回了错误 JSON
                print(f"[lipsync] 远程 HTTP 返回错误: {data[:200]}")
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
