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
import time
from pathlib import Path
from typing import Optional

FFMPEG = os.environ.get("FFMPEG_BIN", "ffmpeg")


def kill_process_tree(pid: int) -> None:
    """连根杀掉一棵进程树。

    口型流水线是「worker -> run_pipeline -> scripts.inference」三层，
    占显存的是最里层。只杀顶层会留下孤儿推理独占显卡（2026-08-22 事故）。
    psutil 不是本项目依赖，所以走系统命令：Windows 用 taskkill /T，
    其他平台杀进程组。
    """
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           capture_output=True, timeout=60)
        else:
            os.killpg(os.getpgid(pid), 9)
    except Exception as e:
        print(f"[lipsync] 终止进程树 {pid} 失败: {e}")


# 选择推理内核。默认 luogen：直接复用「罗根视频生成」已验证的四阶段流水线，
# 经用户目视确认效果达标（嘴部相对亮度 0.804 最接近真人 0.842，耗时约 8 分钟）。
# 回退顺序建议：luogen -> latentsync（本地自研）-> wav2lip（最老，画质天花板低）。
LIPSYNC_ENGINE = os.environ.get("LIPSYNC_ENGINE", "luogen").strip().lower()


class LipsyncEngine:
    """推理内核抽象。输入输出契约对所有实现一致。"""

    name = "base"
    # 该引擎要求输入视频的帧率；None 表示不关心（预处理层据此决定是否重采样）
    required_fps: Optional[int] = None
    # 该引擎建议的输入最大高度（预处理层限高用）
    max_input_height: int = 1280
    # 引擎自带完整预处理时置 True，链路层将原素材直接交给它，
    # 避免二次转码造成额外画质损失
    skip_preprocess: bool = False

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
# 参数组合来自「罗根视频生成」项目 4 轮调优后的锁定值（40 步 / guidance 1.5 / seed 1247）。
# 注意 guidance 用 1.5 而非 2.5：更高的 guidance 会加重嘴部塑料感。
LATENTSYNC_STEPS = int(os.environ.get("LATENTSYNC_STEPS", "40"))
LATENTSYNC_GUIDANCE = float(os.environ.get("LATENTSYNC_GUIDANCE", "1.5"))
LATENTSYNC_SEED = int(os.environ.get("LATENTSYNC_SEED", "1247"))
# DeepCache 跳层缓存能提速但损失嘴部细节，默认关闭
LATENTSYNC_DEEPCACHE = os.environ.get("LATENTSYNC_DEEPCACHE", "0").strip() == "1"
# 嘴部细节复原 + 口型动力学微调（见 lipsync_postprocess.py）。
# 这是解决"嘴部发黑发糊"的关键步骤，默认开启；出问题可置 0 快速回退。
LATENTSYNC_REFINE = os.environ.get("LATENTSYNC_REFINE", "1").strip() == "1"


class LatentSyncEngine(LipsyncEngine):
    name = "latentsync"
    # pipeline 内部按 video_fps 对齐 whisper 特征与视频帧，输入必须是 25fps
    required_fps = 25
    # 不要压到 720p 级。人脸裁剪尺寸随画面尺寸等比缩小，
    # 压到 1280 高会让嘴部可用像素砍半（实测嘴宽 210px -> 110px），
    # 这是"模糊"的主因。对照项目在 1080x2320 原生分辨率下输出，效果明显更好。
    # 2400 允许常见手机竖拍（1080x2336）原样通过，只挡住 4K 以上素材。
    max_input_height = int(os.environ.get("LATENTSYNC_MAX_H", "2400"))

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
                # 固定 seed：同素材同音频可复现，便于对比参数效果
                generator = torch.Generator(device="cuda").manual_seed(LATENTSYNC_SEED)
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
                    generator=generator,
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

            # 精修：把原素材的真实嘴部高频搬回生成帧，并补足张合幅度。
            # 失败不致命（降级交付未精修版本），因为推理结果本身已可用。
            final = tmp_out
            if LATENTSYNC_REFINE:
                try:
                    refined = self._refine(tmp_out, face_path, Path(td))
                    if refined and refined.exists() and refined.stat().st_size > 0:
                        final = refined
                except Exception as e:
                    print(f"[lipsync:latentsync] 精修失败，交付未精修版本: {e}")

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(final.read_bytes())
            return True

    def _refine(self, gen_video: Path, src_video: Path, workdir: Path) -> Optional[Path]:
        """嘴部细节复原 + 亮度校正 + 口型动力学微调，分块流式编码。"""
        import subprocess
        import cv2
        import numpy as np

        pp = _load_postprocess()

        def _probe(fp):
            cap = cv2.VideoCapture(str(fp))
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            return fps, n

        fps_gen, n_gen = _probe(gen_video)
        fps_src, n_src = _probe(src_video)
        print(f"[lipsync:latentsync] 精修 gen={n_gen}f@{fps_gen:.1f} src={n_src}f@{fps_src:.1f}")

        # 关键点缓存到工作目录：同素材重复生成可省约 25 秒
        lm_gen = pp.extract_landmarks(str(gen_video), str(workdir / "lm_gen.npy"), log=print)
        lm_src = pp.extract_landmarks(str(src_video), str(workdir / "lm_src.npy"), log=print)

        # 分块流式处理：全分辨率(1088x2336)下 546 帧一次驻留约 3.9GB，
        # pipeline 里同时存在多份副本会把物理内存吃光（实测被系统杀进程，
        # 无 traceback）。改为一次只处理 CHUNK 帧，边处理边写进编码器。
        cap = cv2.VideoCapture(str(gen_video))
        ok, probe_frame = cap.read()
        if not ok:
            cap.release()
            print("[lipsync:latentsync] 精修读不到帧，跳过")
            return None
        h, w = probe_frame.shape[:2]
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        out = workdir / "refined.mp4"
        proc = subprocess.Popen(
            [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
             "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}",
             "-r", f"{fps_gen}", "-i", "pipe:0",
             "-c:v", "libx264", "-preset", "slow", "-crf", "16",
             "-pix_fmt", "yuv420p", str(out)],
            stdin=subprocess.PIPE)

        CHUNK = max(16, int(os.environ.get("LATENTSYNC_REFINE_CHUNK", "48")))
        idx = 0
        done = 0
        try:
            while True:
                buf = []
                while len(buf) < CHUNK:
                    ok, fr = cap.read()
                    if not ok:
                        break
                    buf.append(fr)
                if not buf:
                    break
                lo, hi = idx, idx + len(buf)
                sub_gen = lm_gen[lo:hi]
                # 顺序有讲究：先补高频细节，再校亮度（低频增益，不削弱细节），
                # 最后做几何形变，避免形变把校正后的边界又拉开。
                quiet = lambda *a: None
                buf = pp.restore_mouth_detail(buf, str(src_video), sub_gen, lm_src,
                                              fps_gen, fps_src, log=quiet,
                                              frame_offset=lo)
                if getattr(pp, "TONE_CORRECT", False):
                    buf = pp.correct_mouth_tone(buf, str(src_video), sub_gen, lm_src,
                                                fps_gen, fps_src, log=quiet,
                                                frame_offset=lo)
                buf = pp.refine_lip_dynamics(buf, sub_gen, lm_src, log=quiet,
                                             width_ref=lm_gen)
                for fr in buf:
                    proc.stdin.write(np.ascontiguousarray(fr).tobytes())
                done += len(buf)
                idx = hi
                del buf
                print(f"[lipsync:latentsync] 精修 {done} 帧", flush=True)
        finally:
            cap.release()
            proc.stdin.close()
        if proc.wait() != 0:
            print("[lipsync:latentsync] 精修帧编码失败")
            return None

        # 精修输出无音轨，从推理产物把音频搬过来（视频流 copy，不二次转码）
        muxed = workdir / "refined_av.mp4"
        r = subprocess.run(
            [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
             "-i", str(out), "-i", str(gen_video),
             "-map", "0:v", "-map", "1:a?",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
             "-movflags", "+faststart", str(muxed)],
            capture_output=True, text=True)
        if r.returncode == 0 and muxed.exists() and muxed.stat().st_size > 0:
            return muxed
        print(f"[lipsync:latentsync] 精修混音失败: {r.stderr[-300:]}")
        return out


# ---------------------------------------------------------------------------
# Luogen：直接复用「罗根视频生成」已验证的四阶段流水线
# ---------------------------------------------------------------------------

LUOGEN_PIPELINE = os.environ.get(
    "LUOGEN_PIPELINE", r"D:/luogen_demo/pipeline")
LUOGEN_PY = os.environ.get(
    "LUOGEN_PY", r"D:/luogen_demo/latentsync_env/Scripts/python.exe")
# 单次推理上限。默认 3300 秒，必须小于线上 LIPSYNC_HTTP_TIMEOUT（3600）：
# 2026-08-22 事故里它是 7200，线上等满 1 小时放弃后本机仍在推理，
# 孤儿进程独占 18GB 显存，后续任务全部撞上"显存不足"。
# 宁可这边先失败并释放显卡，也不要留下没人来取结果的推理。
LUOGEN_TIMEOUT = int(os.environ.get("LUOGEN_TIMEOUT", "3300"))

class LuogenEngine(LipsyncEngine):
    """把罗根项目的 run_pipeline.py 当成外部推理服务调用。

    为什么不把算法再抄一遍：那套流水线（重叠滑窗推理 + 嘴部细节复原 +
    口型动力学微调 + 交付编码）已经经过多轮参数调优和定量验证，
    参数写死在它自己的代码里。复制过来会立刻产生两份实现，
    以后它那边调参我们这边就落后。直接调用可以始终吃到它的最新效果。

    它自带完整环境（独立 venv：torch 2.7.1 + diffusers 0.32.2 + decord），
    与本项目的 .venv_lipsync 互不干扰。

    注意：本引擎自己完成全部预处理（音频转 16k、探测 fps），
    所以链路层不要再做限高/转码，见 skip_preprocess。
    """

    name = "luogen"
    # 该流水线自行处理原始素材（含 HEVC/HDR），不需要链路层预处理
    skip_preprocess = True
    required_fps = None
    max_input_height = 4096

    @property
    def available(self) -> bool:
        need = [
            Path(LUOGEN_PIPELINE) / "run_pipeline.py",
            Path(LUOGEN_PIPELINE) / "postprocess.py",
            Path(LUOGEN_PY),
        ]
        for p in need:
            if not p.exists():
                print(f"[lipsync:luogen] 缺少依赖: {p}")
                return False
        return True

    def infer(self, face_path: Path, audio_path: Path, output_path: Path) -> bool:
        import subprocess
        import shutil
        import uuid

        pipeline_dir = Path(LUOGEN_PIPELINE)
        # 任务名唯一化，避免并发任务互相覆盖 work/ 与 output/
        name = f"phx_{uuid.uuid4().hex[:12]}"

        # 输入必须落在 ASCII 路径：流水线内部多处用 shell 调 ffmpeg，
        # 本项目根目录含中文会静默失败（坑#1）。
        staging = Path(tempfile.gettempdir()) / "phx_luogen" / name
        staging.mkdir(parents=True, exist_ok=True)
        src_video = staging / "face.mp4"
        src_audio = staging / "audio.wav"
        shutil.copyfile(face_path, src_video)
        shutil.copyfile(audio_path, src_audio)

        cmd = [
            LUOGEN_PY, "-u", "run_pipeline.py",
            "--video", str(src_video),
            "--audio", str(src_audio),
            "--name", name,
        ]
        env = os.environ.copy()
        env["PATH"] = str(Path(FFMPEG).parent) + os.pathsep + env.get("PATH", "")
        # 该 venv 自带依赖，清掉可能干扰的继承变量
        for k in ("PYTHONPATH", "PYTHONHOME"):
            env.pop(k, None)

        started = time.time()
        print(f"[lipsync:luogen] 调用外部流水线 name={name} timeout={LUOGEN_TIMEOUT}s")
        # 必须用 Popen 而非 subprocess.run：run 超时只杀直接子进程，
        # 而这条流水线会再 spawn 一个 scripts.inference 子进程，真正吃显存的是后者。
        # 事故现场就是父进程退出后孙进程继续占着 18GB 显卡跑了一小时。
        proc = subprocess.Popen(
            cmd, cwd=str(pipeline_dir), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace",
        )
        try:
            stdout, stderr = proc.communicate(timeout=LUOGEN_TIMEOUT)
        except subprocess.TimeoutExpired:
            print(f"[lipsync:luogen] 超时 {LUOGEN_TIMEOUT}s，终止流水线进程树")
            kill_process_tree(proc.pid)
            stdout, stderr = proc.communicate()
            stderr = (stderr or "") + f"\n[timeout] 超过 {LUOGEN_TIMEOUT}s 未完成"
        except BaseException:
            # 上层取消或进程被中断时同样不能留下占卡的推理
            kill_process_tree(proc.pid)
            raise
        produced = pipeline_dir / "output" / f"{name}.mp4"
        if not (produced.exists() and produced.stat().st_size > 0):
            tail = (stderr or stdout or "")[-1500:]
            print(f"[lipsync:luogen] 流水线未产出成片 rc={proc.returncode}\n{tail}")
            # 失败路径也要清理：work/ 下是无损帧与素材副本，单次可达数 GB，
            # 只在成功分支清会让磁盘随失败次数持续膨胀。
            shutil.rmtree(staging, ignore_errors=True)
            shutil.rmtree(pipeline_dir / "work" / name, ignore_errors=True)
            return False

        cost = time.time() - started
        # 记录耗时：这条流水线的成本随音频时长线性增长，日志里有实测值才能
        # 判断某次任务是正常慢还是异常慢（显存被抢占时会成倍变慢）。
        print(f"[lipsync:luogen] 完成 name={name} 耗时 {cost / 60:.1f} 分钟")
        if cost > LUOGEN_TIMEOUT * 0.8:
            print(f"[lipsync:luogen] 警告: 耗时已达超时上限的 "
                  f"{cost / LUOGEN_TIMEOUT * 100:.0f}%，"
                  "建议缩短素材时长或检查是否有其他程序占用显卡")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(produced.read_bytes())

        # 清理：成片已取回，中间产物体积很大（work/ 下有无损帧与原素材副本）
        for junk in (produced, pipeline_dir / "work" / name):
            try:
                if junk.is_dir():
                    shutil.rmtree(junk, ignore_errors=True)
                else:
                    junk.unlink()
            except Exception:
                pass
        shutil.rmtree(staging, ignore_errors=True)
        return True


_pp_mod = None


def _load_postprocess():
    """加载后处理模块，兼容 gpu_worker 按路径直加载的场景。"""
    global _pp_mod
    if _pp_mod is None:
        try:
            from app.services import lipsync_postprocess as _m
        except Exception:
            import importlib.util
            _p = Path(__file__).resolve().parent / "lipsync_postprocess.py"
            _spec = importlib.util.spec_from_file_location("lipsync_postprocess", _p)
            _m = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_m)
        _pp_mod = _m
    return _pp_mod


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------

_ENGINES = {
    Wav2LipEngine.name: Wav2LipEngine,
    LatentSyncEngine.name: LatentSyncEngine,
    LuogenEngine.name: LuogenEngine,
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
