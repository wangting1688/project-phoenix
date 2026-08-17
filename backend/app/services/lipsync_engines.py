"""
口型同步推理引擎层（可插拔）

设计意图
--------
`lipsync_service.LipsyncService` 负责「链路」：远程派发（HTTP/SSH）、素材预处理
（HEVC/10bit 转码、限高、按 TTS 时长截取）、失败降级。这些逻辑与具体模型无关，
是踩过多轮坑换来的，不应随换模型而重写。

本模块只负责「推理内核」：给定一段已预处理好的人脸视频 + 一段音频，产出口型对齐
的视频。不同实现（Wav2Lip / LatentSync / 未来的商业 API）在此并列，通过
环境变量 LIPSYNC_ENGINE 选择，从而支持低成本 A/B 对比而不必改动链路代码。

已知引擎
--------
- wav2lip   ：官方 inference.py + wav2lip_gan.pth。96x96 贴片，快但嘴部模糊，
              是画质天花板（见交接文档坑#13）。当前的历史生产内核。
- latentsync：LatentSync 1.6（Apache 2.0），512x512 人脸区域扩散重绘，中文拟合好，
              约需 18~20GB 显存。质量显著优于 wav2lip，代价是推理慢约一个数量级。

新增引擎只需继承 LipsyncEngine 并在 _ENGINES 注册，链路层无需改动。
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

FFMPEG = os.environ.get("FFMPEG_BIN", "ffmpeg")

# 选择推理内核：wav2lip（默认，保持历史行为）/ latentsync
LIPSYNC_ENGINE = os.environ.get("LIPSYNC_ENGINE", "wav2lip").strip().lower()


class LipsyncEngine:
    """推理内核抽象。输入输出契约对所有实现一致。"""

    name = "base"
    # 该引擎要求输入视频的帧率；None 表示不关心（预处理层据此决定是否重采样）
    required_fps: Optional[int] = None
    # 该引擎建议的输入最大高度（预处理层限高用）
    max_input_height: int = 1280

    def __init__(self, storage_root: Path):
        self.storage_root = Path(storage_root)

    @property
    def available(self) -> bool:
        raise NotImplementedError

    def infer(self, face_path: Path, audio_path: Path, output_path: Path) -> bool:
        """对 face_path 做口型同步写入 output_path。成功返回 True。

        注意：调用方只信任「返回 True 且输出文件存在且非空」，因为历史上
        Wav2Lip 的 inference.py 失败也会 exit 0（坑#6）。
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Wav2Lip：官方 inference.py 子进程
# ---------------------------------------------------------------------------

WAV2LIP_CHECKPOINT = "storage/models/wav2lip_gan.pth"
WAV2LIP_REPO_DIR = "storage/models/wav2lip"
WAV2LIP_PADS = [0, 10, 0, 0]
WAV2LIP_RESIZE_FACTOR = 1


class Wav2LipEngine(LipsyncEngine):
    name = "wav2lip"
    required_fps = None
    max_input_height = 1280

    def __init__(self, storage_root: Path):
        super().__init__(storage_root)
        self.checkpoint = self.storage_root / WAV2LIP_CHECKPOINT
        self.repo_dir = self.storage_root / WAV2LIP_REPO_DIR

    @property
    def available(self) -> bool:
        if not self.checkpoint.exists():
            print(f"[lipsync:wav2lip] 缺少模型文件: {self.checkpoint}")
            return False
        if not (self.repo_dir / "inference.py").exists():
            print(f"[lipsync:wav2lip] 缺少 inference.py: {self.repo_dir}")
            return False
        try:
            import torch  # noqa: F401
            import cv2  # noqa: F401
            import librosa  # noqa: F401
        except Exception as e:
            print(f"[lipsync:wav2lip] 缺少依赖(torch/cv2/librosa): {e}")
            return False
        return True

    def infer(self, face_path: Path, audio_path: Path, output_path: Path) -> bool:
        cmd = [
            sys.executable, str(self.repo_dir / "inference.py"),
            "--checkpoint_path", str(self.checkpoint),
            "--face", str(face_path),
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
            print(f"[lipsync:wav2lip] 推理失败 rc={proc.returncode}: {proc.stderr[-600:]}")
            return False
        return True


# ---------------------------------------------------------------------------
# LatentSync 1.6：进程内 diffusion pipeline
# ---------------------------------------------------------------------------

LATENTSYNC_ROOT = "storage/models/latentsync"
# 默认沿用已实测验证过的 demo 参数（40 步 / guidance 2.5 = 高画质版）。
# 想换速度可用环境变量下调，但请重新目视验证画质后再上线。
LATENTSYNC_STEPS = int(os.environ.get("LATENTSYNC_STEPS", "40"))
LATENTSYNC_GUIDANCE = float(os.environ.get("LATENTSYNC_GUIDANCE", "2.5"))
# DeepCache 跳层缓存能提速但损失嘴部细节，默认关闭
LATENTSYNC_DEEPCACHE = os.environ.get("LATENTSYNC_DEEPCACHE", "0").strip() == "1"


class LatentSyncEngine(LipsyncEngine):
    name = "latentsync"
    # pipeline 内部按 video_fps 对齐 whisper 特征与视频帧，输入必须是 25fps
    required_fps = 25
    max_input_height = 1280

    def __init__(self, storage_root: Path):
        super().__init__(storage_root)
        self.root = self.storage_root / LATENTSYNC_ROOT
        self.pkg = self.root / "latentsync"
        self._pipeline = None

    @property
    def available(self) -> bool:
        required = [
            self.root / "latentsync_unet.pt",
            self.root / "whisper/tiny.pt",
            self.root / "vae/config.json",
            self.pkg / "configs/unet/stage2_512.yaml",
            self.pkg / "utils/mask.png",
            self.root / "auxiliary/models/buffalo_l",
        ]
        for p in required:
            if not p.exists():
                print(f"[lipsync:latentsync] 缺少资产: {p}")
                return False
        try:
            import torch
            import diffusers  # noqa: F401
            import omegaconf  # noqa: F401
            import onnxruntime  # noqa: F401
        except Exception as e:
            print(f"[lipsync:latentsync] 缺少依赖: {e}")
            return False
        if not torch.cuda.is_available():
            # 512 扩散模型在 CPU 上不具备可用性（单条视频需数小时）
            print("[lipsync:latentsync] CUDA 不可用，拒绝在 CPU 上运行扩散模型")
            return False
        return True

    def _build_pipeline(self):
        """首次调用时加载模型并常驻（约 20GB 显存，避免每条任务重复加载）。"""
        import torch
        from omegaconf import OmegaConf
        from diffusers import AutoencoderKL, DDIMScheduler

        # LatentSync 包不是 pip 安装的，需把模型根目录加入 sys.path
        root_str = str(self.root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)

        from latentsync.models.unet import UNet3DConditionModel
        from latentsync.pipelines.lipsync_pipeline import LipsyncPipeline
        from latentsync.whisper.audio2feature import Audio2Feature

        config = OmegaConf.load(str(self.pkg / "configs/unet/stage2_512.yaml"))
        # sm_80+ 才用 fp16；5090 (sm_120) 满足
        is_fp16 = torch.cuda.get_device_capability()[0] > 7
        self._dtype = torch.float16 if is_fp16 else torch.float32
        self._resolution = config.data.resolution
        self._num_frames = config.data.num_frames

        print(f"[lipsync:latentsync] 加载模型 dtype={self._dtype} gpu={torch.cuda.get_device_name(0)}")
        scheduler = DDIMScheduler.from_pretrained(str(self.pkg / "configs"))
        audio_encoder = Audio2Feature(
            model_path=str(self.root / "whisper/tiny.pt"),
            device="cuda",
            num_frames=config.data.num_frames,
            audio_feat_length=config.data.audio_feat_length,
        )
        vae = AutoencoderKL.from_pretrained(str(self.root / "vae"), torch_dtype=self._dtype)
        vae.config.scaling_factor = 0.18215
        vae.config.shift_factor = 0
        unet, _ = UNet3DConditionModel.from_pretrained(
            OmegaConf.to_container(config.model),
            str(self.root / "latentsync_unet.pt"),
            device="cpu",
        )
        unet = unet.to(dtype=self._dtype)

        pipeline = LipsyncPipeline(
            vae=vae, audio_encoder=audio_encoder, unet=unet, scheduler=scheduler,
        ).to("cuda")

        if LATENTSYNC_DEEPCACHE:
            from DeepCache import DeepCacheSDHelper
            helper = DeepCacheSDHelper(pipe=pipeline)
            helper.set_params(cache_interval=3, cache_branch_id=0)
            helper.enable()
            print("[lipsync:latentsync] DeepCache 已启用（提速但损失嘴部细节）")

        print("[lipsync:latentsync] 模型加载完成，常驻显存")
        return pipeline

    def _ascii_mask_path(self) -> str:
        """把 mask.png 落到 ASCII 路径。

        pipeline 内部用 cv2.imread 读 mask，而 cv2 在 Windows 下读不了非 ASCII
        路径（静默返回 None → cvtColor 报 !_src.empty()）。项目根目录含中文，
        故复制一份到系统临时目录复用。
        """
        cached = Path(tempfile.gettempdir()) / "phx_latentsync_mask.png"
        src = self.pkg / "utils/mask.png"
        if not cached.exists() or cached.stat().st_size != src.stat().st_size:
            cached.write_bytes(src.read_bytes())
        return str(cached)

    def infer(self, face_path: Path, audio_path: Path, output_path: Path) -> bool:
        import torch

        # pipeline 内部用 shell 调 ffmpeg 做 check_ffmpeg_installed 与最终 mux，
        # 必须保证 PATH 里有 ASCII 路径的 ffmpeg（坑#1）
        ff_dir = str(Path(FFMPEG).parent)
        if ff_dir and ff_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ff_dir + os.pathsep + os.environ.get("PATH", "")

        if self._pipeline is None:
            self._pipeline = self._build_pipeline()

        mask_path = self._ascii_mask_path()

        # 输出路径不能含非 ASCII：pipeline 最终 mux 用 shell=True 拼命令，
        # 中文路径在 cmd.exe 下会失败。故先写到 ASCII 临时目录再搬回。
        with tempfile.TemporaryDirectory(prefix="phx_ls_") as td:
            tmp_out = Path(td) / "out.mp4"
            tmp_dir = Path(td) / "work"
            try:
                self._pipeline(
                    video_path=str(face_path),
                    audio_path=str(audio_path),
                    video_out_path=str(tmp_out),
                    num_frames=self._num_frames,
                    num_inference_steps=LATENTSYNC_STEPS,
                    guidance_scale=LATENTSYNC_GUIDANCE,
                    weight_dtype=self._dtype,
                    width=self._resolution,
                    height=self._resolution,
                    mask_image_path=mask_path,
                    temp_dir=str(tmp_dir),
                )
            except Exception as e:
                print(f"[lipsync:latentsync] 推理异常: {e}")
                return False
            finally:
                # 扩散模型显存占用高，单条结束后释放缓存，降低并发任务 OOM 概率
                try:
                    torch.cuda.empty_cache()
                except Exception:
                    pass

            if not (tmp_out.exists() and tmp_out.stat().st_size > 0):
                print("[lipsync:latentsync] 推理未产出有效文件")
                return False
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(tmp_out.read_bytes())
            return True


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------

_ENGINES = {
    Wav2LipEngine.name: Wav2LipEngine,
    LatentSyncEngine.name: LatentSyncEngine,
}

_engine_cache = {}


def get_engine(storage_root: Path, name: Optional[str] = None) -> LipsyncEngine:
    """按名字取推理引擎（进程内单例，保证模型只加载一次）。

    未知名字回退到 wav2lip，避免配置写错导致口型功能整体不可用。
    """
    key = (name or LIPSYNC_ENGINE).strip().lower()
    if key not in _ENGINES:
        print(f"[lipsync] 未知引擎 {key!r}，回退 wav2lip。可选: {sorted(_ENGINES)}")
        key = Wav2LipEngine.name
    cache_key = (str(storage_root), key)
    if cache_key not in _engine_cache:
        _engine_cache[cache_key] = _ENGINES[key](Path(storage_root))
    return _engine_cache[cache_key]
