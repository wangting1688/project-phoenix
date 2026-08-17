"""
本机口型 GPU Worker（方案A 派发端点）
- 监听 127.0.0.1:18080（仅本机/反向隧道可达，不暴露公网）
- 接收 live 服务器 POST 的 face 视频 + audio 音频，调用本地推理引擎，返回口型对齐视频
- 推理内核由 LIPSYNC_ENGINE 选择（wav2lip / latentsync，见 app/services/lipsync_engines.py）
- 用 .venv_lipsync 运行（含 torch+cu128 / cv2 / librosa / ffmpeg）
启动： .venv_lipsync/Scripts/python.exe gpu_worker.py
"""
import os, sys, io, tempfile, importlib.util, asyncio, traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse, Response

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
app = FastAPI()
# Wav2Lip 推理是同步阻塞且耗时（转码+检测+生成可达数分钟），
# 放线程池执行，避免阻塞 uvicorn 事件循环导致 /health 探活超时
# （live 端任务开始前会探活 worker，探活失败会直接跳过口型 → 成片用原素材 → 嘴型对不上）
_sync_pool = ThreadPoolExecutor(max_workers=1)

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
    return {"status": "ok", "lipsync_available": svc.available,
            "engine": svc.engine.name,
            "cuda": cuda, "gpu": gpu}

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

if __name__ == "__main__":
    import uvicorn
    print(">>> starting lipsync GPU worker on 127.0.0.1:18080 "
          "(engine=%s, lipsync_available=%s)" % (svc.engine.name, svc.available))
    uvicorn.run(app, host="127.0.0.1", port=18080, log_level="info")
