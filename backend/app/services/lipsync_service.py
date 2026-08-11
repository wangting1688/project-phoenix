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
- 本地模式（LIPSYNC_REMOTE_SSH 为空）：本机需装 torch(+cuda/CPU)、opencv、librosa、face-alignment。
"""
import os
import sys
import shlex
import subprocess
from pathlib import Path
from typing import Optional, List

WAV2LIP_CHECKPOINT = "storage/models/wav2lip_gan.pth"
WAV2LIP_REPO_DIR = "storage/models/wav2lip"  # 官方仓库(git clone) 根目录，含 inference.py
WAV2LIP_PADS = [0, 10, 0, 0]
WAV2LIP_RESIZE_FACTOR = 1

# 远程 GPU 机器地址（留空=本地运行；形如 root@1.2.3.4 则通过 ssh 派发）
LIPSYNC_REMOTE_SSH = os.environ.get("LIPSYNC_REMOTE_SSH", "").strip()
FFMPEG = os.environ.get("FFMPEG_BIN", "ffmpeg")


class LipsyncService:
    """口型同步服务封装（真实 Wav2Lip）"""

    def __init__(self, storage_root: Path):
        self.storage_root = Path(storage_root)
        self.checkpoint = self.storage_root / WAV2LIP_CHECKPOINT
        self.repo_dir = self.storage_root / WAV2LIP_REPO_DIR

    # ------------------------------------------------------------------
    # 可用性检测
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """口型同步是否可用（模型 + 运行环境都有）"""
        if not self.checkpoint.exists():
            print(f"[lipsync] 缺少模型文件: {self.checkpoint}（请先运行 setup_lipsync_gpu.sh）")
            return False
        if LIPSYNC_REMOTE_SSH:
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
        # 本地模式：需要 torch / cv2 / librosa
        try:
            import torch  # noqa: F401
            import cv2  # noqa: F401
            import librosa  # noqa: F401
        except Exception as e:
            print(f"[lipsync] 本地缺少依赖(torch/cv2/librosa): {e}")
            return False
        return True

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
            if LIPSYNC_REMOTE_SSH:
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
        inference = self.repo_dir / "inference.py"
        if not inference.exists():
            print(f"[lipsync] 官方 inference.py 不存在: {inference}（请先运行 setup_lipsync_gpu.sh）")
            return False
        tmp = self.repo_dir / "temp"
        tmp.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable, str(inference),
            "--checkpoint_path", str(self.checkpoint),
            "--face", str(video_path),
            "--audio", str(audio_path),
            "--outfile", str(output_path),
            "--pads", *[str(p) for p in WAV2LIP_PADS],
            "--resize_factor", str(WAV2LIP_RESIZE_FACTOR),
            "--wav2lip_batch_size", "128",
            "--face_det_batch_size", "16",
        ]
        # 官方 inference.py 使用相对 temp/，故以仓库目录为 cwd
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=1800, cwd=str(self.repo_dir),
        )
        if proc.returncode != 0:
            print(f"[lipsync] 本地推理失败 rc={proc.returncode}: {proc.stderr[-600:]}")
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
