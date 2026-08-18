# -*- coding: utf-8 -*-
"""CosyVoice2 合成执行体。

由 local_tts.synthesize_local 以子进程方式调用，运行在 CosyVoice2 自己的
Python 3.11 环境（依赖 hyperpyyaml/conformer/wetext/matcha 等，与本项目的
.venv_lipsync 隔离，避免 numpy 等版本互相顶掉）。

输入：文案与参考音频逐字稿从 stdin 读入，以 \x00SPLIT\x00 分隔，
      避免命令行长度限制与 Windows 下的引号转义问题。
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref-wav", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--target-cps", type=float, default=4.4)
    ap.add_argument("--max-tempo", type=float, default=1.5)
    a = ap.parse_args()

    payload = sys.stdin.read()
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
