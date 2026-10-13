# -*- coding: utf-8 -*-
"""CosyVoice2 合成执行体。

由 local_tts.synthesize_local 以子进程方式调用，运行在 CosyVoice2 自己的
Python 3.11 环境（依赖 hyperpyyaml/conformer/wetext/matcha 等，与本项目的
.venv_lipsync 隔离，避免 numpy 等版本互相顶掉）。

输入：文案与参考音频逐字稿从 stdin 读入，以 \x00SPLIT\x00 分隔，
      避免命令行长度限制与 Windows 下的引号转义问题。

两种运行模式
------------
- 一次性（默认）：合成一条即退出。
- 常驻（--serve）：加载模型后循环读取请求。CosyVoice2 的导入与权重加载
  合计约 8 秒，而一条 30 字文案的实际合成只要几秒 —— 一次性模式下每条
  配音都要重付这 8 秒。常驻模式把它摊薄到只在 worker 启动时付一次。
  协议按行传输 JSON，一行一个请求，一行一个响应，便于跨解释器调用。
"""
import argparse
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load_local_tts():
    """加载同目录的 local_tts（此处不能按包导入，app 包依赖 fastapi 等）。"""
    spec = importlib.util.spec_from_file_location("local_tts", HERE / "local_tts.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def serve():
    """常驻模式：加载模型后按行处理 JSON 请求，直到 stdin 关闭。

    每行请求形如 {"text":..., "ref_wav":..., "ref_text":..., "out":...,
    "target_cps":..., "max_tempo":...}，
    每行响应形如 PHXRESP {"ok":true,"out":...}。

    响应必须带 PHXRESP 前缀：local_tts 的诊断日志（合成进度、语速矫正等）
    也打在 stdout 上，不加标记的话调用方会把日志行当成响应去解析而失败。
    """
    import json

    tts = _load_local_tts()
    # 预热：把导入与权重加载的开销放在启动阶段，而不是第一条请求里
    tts._load_model()
    print("PHXRESP " + json.dumps({"ready": True}), flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception as e:
            print("PHXRESP " + json.dumps({"ok": False, "error": f"bad request: {e}"}), flush=True)
            continue
        try:
            ref_text = (req.get("ref_text") or "").strip()
            if not ref_text:
                # 与一次性模式同一条铁律：绝不用空文稿合成
                ref_text = tts.transcribe(req["ref_wav"])
            tts.TTS_MAX_TEMPO = float(req.get("max_tempo", 1.5))
            res = tts._synthesize_inproc(
                (req.get("text") or "").strip(), req["ref_wav"], ref_text,
                req["out"], target_cps=float(req.get("target_cps", 4.4)),
                variant=int(req.get("variant", 0) or 0))
            if res:
                print("PHXRESP " + json.dumps({"ok": True, "out": str(res)}), flush=True)
            else:
                print("PHXRESP " + json.dumps(
                    {"ok": False, "error": "synthesis returned nothing"}), flush=True)
        except Exception as e:
            import traceback
            traceback.print_exc(file=sys.stderr)
            print("PHXRESP " + json.dumps(
                {"ok": False, "error": f"{type(e).__name__}: {e}"}), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true",
                    help="常驻模式：模型只加载一次，循环处理请求")
    ap.add_argument("--ref-wav")
    ap.add_argument("--out")
    ap.add_argument("--target-cps", type=float, default=4.4)
    ap.add_argument("--max-tempo", type=float, default=1.5)
    a = ap.parse_args()

    if a.serve:
        serve()
        return
    if not a.ref_wav or not a.out:
        ap.error("--ref-wav 与 --out 在一次性模式下必填")

    # 按字节读并显式 utf-8 解码。若走 sys.stdin.read()，在中文 Windows 上
    # 默认编码是 GBK，文案会被解成乱码，模型照着乱码发音，产出无法辨识的语音。
    payload = sys.stdin.buffer.read().decode("utf-8", "replace")
    if "\x00SPLIT\x00" in payload:
        text, ref_text = payload.split("\x00SPLIT\x00", 1)
    else:
        text, ref_text = payload, ""
    text = text.strip()
    ref_text = ref_text.strip()

    tts = _load_local_tts()
    tts.TTS_MAX_TEMPO = a.max_tempo

    if not ref_text:
        # 没有逐字稿就用 ASR 转写。绝不猜测内容：音文错配会输出乱码。
        print("[runner] 未提供逐字稿，ASR 转写参考音频")
        ref_text = tts.transcribe(a.ref_wav)

    res = tts._synthesize_inproc(text, a.ref_wav, ref_text, a.out,
                                 target_cps=a.target_cps)
    if not res:
        print("[runner] 合成失败")
        sys.exit(1)
    print(f"[runner] OK -> {res}")


if __name__ == "__main__":
    main()
