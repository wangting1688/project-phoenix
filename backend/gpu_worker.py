"""
本机口型 GPU Worker（方案A 派发端点）
- 监听 127.0.0.1:18080（仅本机/反向隧道可达，不暴露公网）
- 接收 live 服务器 POST 的 face 视频 + audio 音频，调用本地推理引擎，返回口型对齐视频
- 推理内核由 LIPSYNC_ENGINE 选择（wav2lip / latentsync / luogen，见 app/services/lipsync_engines.py）
- 另提供 /tts 端点：CosyVoice2 本地音色克隆，替代付费的火山 TTS
- 用 .venv_lipsync 运行（含 torch+cu128 / cv2 / librosa / ffmpeg）
启动： .venv_lipsync/Scripts/python.exe gpu_worker.py
"""
import os, sys, io, tempfile, importlib.util, asyncio, traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import JSONResponse, Response

# 日志里全是中文诊断信息。stdout 被重定向到文件时，Windows 会退回 ANSI 编码
# (简中 GBK)，print 中文即抛 UnicodeEncodeError 并让整个请求 500。
# 不依赖启动脚本是否设了 PYTHONIOENCODING，在进程内自行兜底。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BACKEND = Path(__file__).resolve().parent           # backend/
# 重要：ffmpeg 必须放在 ASCII 路径下。
# 官方 inference.py 用 subprocess.call('ffmpeg ...', shell=True) 调 ffmpeg，
# 而项目目录含中文（D:/汪挺/...），cmd.exe 扫描 PATH 时遇到非 ASCII 条目会失效，
# 导致"ffmpeg 不是内部或外部命令"、推理 exit 0 却不产出文件 → /sync 返回错误/空视频。
# 解决方案：把 ffmpeg.exe 复制到 ASCII 目录 D:/ffmpeg_bin 并加入 PATH。
FF = Path(r"D:/ffmpeg_bin")
if not (FF / "ffmpeg.exe").exists():
    # 兜底：首次部署若 ASCII 复制缺失，退回项目内 ffmpeg 目录
    FF = BACKEND / "storage/models/ffmpeg"
os.environ["PATH"] = str(FF) + os.pathsep + os.environ.get("PATH", "")
os.environ["FFMPEG_BIN"] = str(FF / "ffmpeg.exe")

# 本 worker 直跑本机推理：清掉远程派发变量，否则会把任务又转发出去形成回环
os.environ.pop("LIPSYNC_REMOTE_HTTP", None)
os.environ.pop("LIPSYNC_REMOTE_SSH", None)

# 直接加载 lipsync_service（绕开 app/__init__ 的 fastapi 依赖）
spec = importlib.util.spec_from_file_location(
    "lipsync_service", BACKEND / "app/services/lipsync_service.py"
)
_lm = importlib.util.module_from_spec(spec); spec.loader.exec_module(_lm)
LipsyncService = _lm.LipsyncService

svc = LipsyncService(BACKEND)

# 本地 TTS（CosyVoice2）。同样按路径加载，绕开 app/__init__ 依赖。
_tts_spec = importlib.util.spec_from_file_location(
    "local_tts", BACKEND / "app/services/local_tts.py")
_tts = importlib.util.module_from_spec(_tts_spec)
try:
    _tts_spec.loader.exec_module(_tts)
except Exception as e:
    print(f">>> local_tts 加载失败: {e}")
    _tts = None

app = FastAPI()
# Wav2Lip 推理是同步阻塞且耗时（转码+检测+生成可达数分钟），
# 放线程池执行，避免阻塞 uvicorn 事件循环导致 /health 探活超时
# （live 端任务开始前会探活 worker，探活失败会直接跳过口型 → 成片用原素材 → 嘴型对不上）
_sync_pool = ThreadPoolExecutor(max_workers=1)
# TTS 独立线程池：合成不该被口型任务阻塞，两者显存占用差距很大
_tts_pool = ThreadPoolExecutor(max_workers=1)
# 素材检测：与口型同池串行。检测本身只有几秒，但和推理抢显存不划算。
_inspect_pool = ThreadPoolExecutor(max_workers=1)

# face_alignment 首次加载约 30s，加载后常驻复用（与 /tts 的模型常驻同思路）
_fa = None


def _get_face_aligner():
    """按需加载并复用 face_alignment。返回 None 表示环境不支持。"""
    global _fa
    if _fa is not None:
        return _fa
    # 同 lipsync_postprocess：torch 2.11 会用 inductor 编译检测网络，
    # 而本 venv 无 triton（Windows 无稳定 wheel）→ TritonMissing，故走 eager。
    os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")
    os.environ.setdefault("TORCH_COMPILE_DISABLE", "1")
    try:
        import torch
        import face_alignment
        try:
            lt = face_alignment.LandmarksType.TWO_D
        except AttributeError:
            lt = face_alignment.LandmarksType._2D
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        _fa = face_alignment.FaceAlignment(lt, flip_input=False, device=dev)
        print(f"[inspect] face_alignment 已加载 device={dev}")
        return _fa
    except Exception as e:
        print(f"[inspect] face_alignment 加载失败: {e}")
        return None


def _measure_face_ratio(video_path: Path):
    """人脸宽度占画面宽度的比例（抽样帧取中位数）。

    口型链路会把人脸裁剪缩放到 512 做推理，脸太小则嘴部有效像素不足，
    放大贴回就会模糊——这个比例是判断「素材能否出清晰口型」的关键指标。

    返回 (ratio, detected_frames, sampled_frames)；ratio 为 None 表示无法检测。
    """
    fa = _get_face_aligner()
    if fa is None:
        return None, 0, 0
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None, 0, 0
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = float(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        if width <= 0:
            return None, 0, 0

        # 每 2 秒取一帧、最多 10 帧：足够稳，且不会让请求拖到分钟级
        step = max(int(fps * 2), 1)
        positions = [i * step for i in range(10)]
        if total > 0:
            positions = [p for p in positions if p < total] or [0]

        ratios = []
        sampled = 0
        for pos in positions:
            cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
            ok, frame = cap.read()
            if not ok:
                break
            sampled += 1
            # 缩放到长边 640 再检测：关键点精度足够，速度快数倍
            h, w = frame.shape[:2]
            scale = 640.0 / max(h, w) if max(h, w) > 640 else 1.0
            small = cv2.resize(frame, None, fx=scale, fy=scale,
                               interpolation=cv2.INTER_AREA) if scale != 1.0 else frame
            preds = fa.get_landmarks(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
            if not preds:
                continue
            # 多人时取最大脸，对应口型链路实际会选中的主体
            best = 0.0
            for lm in preds:
                xs = lm[:, 0]
                fw = (float(xs.max()) - float(xs.min())) / scale
                best = max(best, fw / width)
            if best > 0:
                ratios.append(best)
        if not ratios:
            return 0.0, 0, sampled
        ratios.sort()
        return round(float(np.median(ratios)), 3), len(ratios), sampled
    finally:
        cap.release()


@app.get("/health")
def health():
    cuda = False
    gpu = "N/A"
    try:
        import torch
        cuda = torch.cuda.is_available()
        if cuda:
            gpu = torch.cuda.get_device_name(0)
    except Exception:
        pass
    tts_ok = False
    if _tts is not None:
        # 只检查模型目录是否就位，不在探活里真加载（5.4GB 权重会拖垮探活）
        tts_ok = Path(_tts.COSY_MODEL).exists()
    return {"status": "ok", "lipsync_available": svc.available,
            "engine": svc.engine.name,
            "tts_available": tts_ok,
            "inspect_available": True,
            "cuda": cuda, "gpu": gpu}

@app.post("/inspect")
async def inspect(video: UploadFile = File(...)):
    """统计素材人脸占比，供上传环节的拍摄质量检测补齐这一项。

    亮度在线上用 ffmpeg 就能测（app/services/footage_quality.py），
    但人脸检测需要模型：生产机没有 cv2，本机 cv2 5.0 headless 也没有
    CascadeClassifier，唯一可用的 face_alignment 在本 worker 常驻，故放这里。
    """
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / (video.filename or "in.mp4")
        src.write_bytes(await video.read())
        loop = asyncio.get_event_loop()
        try:
            ratio, detected, sampled = await loop.run_in_executor(
                _inspect_pool, _measure_face_ratio, src)
        except Exception as e:
            traceback.print_exc()
            return JSONResponse({"error": "inspect failed", "detail": str(e)},
                                status_code=500)
        print(f"[inspect] face_ratio={ratio} detected={detected}/{sampled}")
        return {"face_ratio": ratio, "detected_frames": detected,
                "sampled_frames": sampled}


@app.post("/sync")
async def sync(face: UploadFile = File(...), audio: UploadFile = File(...)):
    if not svc.available:
        return JSONResponse({"error": "lipsync unavailable (check model/torch)"},
                            status_code=503)
    with tempfile.TemporaryDirectory() as td:
        vid = Path(td) / "face.mp4"
        aud = Path(td) / "audio.mp3"
        out = Path(td) / "out.mp4"
        vid.write_bytes(await face.read())
        aud.write_bytes(await audio.read())
        loop = asyncio.get_running_loop()
        err = {}

        def _run():
            # 把异常文本带回调用方，否则 worker 侧的真实原因只留在本机控制台
            try:
                return svc.sync_video(vid, aud, out)
            except Exception as e:
                err["detail"] = f"{type(e).__name__}: {e}"
                traceback.print_exc()
                return None

        res = await loop.run_in_executor(_sync_pool, _run)
        if res and Path(res).exists() and Path(res).stat().st_size > 0:
            # 在临时目录销毁前把视频读进内存，避免流式读取时文件已被删
            data = Path(res).read_bytes()
            return Response(content=data, media_type="video/mp4",
                            headers={"Content-Disposition": "attachment; filename=lipsync.mp4"})
    # 必须用 JSONResponse 显式给状态码：`return dict, 500` 会被序列化成
    # JSON 数组并返回 200，调用方会把错误响应当视频落盘（29 字节的假成片）
    return JSONResponse({"error": "sync failed", "engine": svc.engine.name,
                         "detail": err.get("detail", "")}, status_code=500)

@app.post("/tts")
async def tts(text: str = Form(...), ref_text: str = Form(""),
              ref_wav: UploadFile = File(...)):
    """CosyVoice2 zero-shot 克隆合成，返回 mp3。

    ref_text 为空时用 whisper 转写参考音频——绝不猜测文稿内容，
    音文错配会让模型输出无法辨识的声音。
    """
    if _tts is None:
        return JSONResponse({"error": "local_tts unavailable"}, status_code=503)
    with tempfile.TemporaryDirectory() as td:
        ref = Path(td) / "ref.wav"
        out = Path(td) / "out.mp3"
        raw = await ref_wav.read()
        ref.write_bytes(raw)
        rt = (ref_text or "").strip()
        err = {}
        # 请求指纹：ref 音频的 md5 与两段文本的开头。
        # 排查配音乱码时靠它区分「音文错配」和「传输层编码损坏」两种原因。
        import hashlib
        print(
            f"[tts] req ref_wav={len(raw)}B md5={hashlib.md5(raw).hexdigest()[:12]} "
            f"text={text[:24]!r} ref_text={rt[:24]!r}"
        )

        def _run():
            nonlocal rt
            try:
                if not rt:
                    # 逐字稿必须由这里生成：生产机没有 whisper，
                    # 在上游转写会静默失败并留下空文稿，而空文稿会让
                    # zero-shot 按错误音素映射发音，产出整段乱码。
                    print("[tts] 未提供逐字稿，ASR 转写参考音频")
                    rt = _tts.transcribe(ref)
                    if not rt.strip():
                        err["detail"] = "参考音频转写为空，无法克隆"
                        return None
                res = _tts.synthesize_local(text, ref, rt, out)
                if not res:
                    return None
                # 质量门禁：回读不可辨识就不返回，避免乱码进到成片
                ok, ratio, got = _tts.verify_intelligibility(res, text)
                if not ok:
                    err["detail"] = (f"合成音频回读不可辨识(相似度 {ratio*100:.1f}%)，"
                                     f"多为参考音频与逐字稿不匹配")
                    return None
                return res
            except Exception as e:
                err["detail"] = f"{type(e).__name__}: {e}"
                traceback.print_exc()
                return None

        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(_tts_pool, _run)
        if res and Path(res).exists() and Path(res).stat().st_size > 0:
            data = Path(res).read_bytes()
            return Response(content=data, media_type="audio/mpeg",
                            headers={"Content-Disposition": "attachment; filename=tts.mp3"})
    return JSONResponse({"error": "tts failed", "detail": err.get("detail", "")},
                        status_code=500)


@app.on_event("startup")
async def _warmup():
    """后台预热 CosyVoice2。

    首个请求要加载 5.4GB 权重（约 3 分钟），期间调用方容易先超时而失败。
    启动即在后台加载，让第一个真实任务直接命中已就绪的模型。
    口型模型不在这里预热：它占近 20GB 显存，且 luogen 引擎是子进程模式。
    """
    if _tts is None:
        return

    def _go():
        # 合成跑在 CosyVoice2 自己的解释器（子进程）里，模型随子进程结束而释放，
        # 所以这里不做"预加载常驻"——那对子进程模式无效。
        # 只做一次依赖自检，把环境问题在启动阶段就暴露出来，
        # 而不是等第一个真实任务失败才发现。
        try:
            import subprocess
            r = subprocess.run(
                [_tts.COSY_PY, "-c",
                 "import sys;"
                 f"sys.path.insert(0, r'{_tts.COSY_DIR}/third_party/Matcha-TTS');"
                 f"sys.path.insert(0, r'{_tts.COSY_DIR}');"
                 "from cosyvoice.cli.cosyvoice import CosyVoice2;"
                 "print('ok')"],
                capture_output=True, text=True, timeout=180)
            if "ok" in (r.stdout or ""):
                print("[warmup] CosyVoice2 依赖自检通过")
            else:
                print(f"[warmup] CosyVoice2 依赖自检失败: "
                      f"{(r.stderr or r.stdout or '')[-300:]}")
        except Exception as e:
            print(f"[warmup] CosyVoice2 自检异常: {e}")

    asyncio.get_running_loop().run_in_executor(_tts_pool, _go)


if __name__ == "__main__":
    import uvicorn
    print(">>> starting GPU worker on 127.0.0.1:18080 "
          "(engine=%s, lipsync=%s, tts=%s)"
          % (svc.engine.name, svc.available,
             _tts is not None and Path(_tts.COSY_MODEL).exists()))
    uvicorn.run(app, host="127.0.0.1", port=18080, log_level="info")
