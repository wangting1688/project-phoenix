#!/usr/bin/env python3
"""
口型同步推理执行（已弃用）

历史版本里这里手写了一版 U-Net 风格的 "Wav2LipGenerator"，但它并非官方 Wav2Lip
的真实网络结构，与 wav2lip_gan.pth 不对应，导致口型对不上。

现统一改为：由 lipsync_service.py 直接调用官方 Wav2Lip 的 inference.py
（通过 setup_lipsync_gpu.sh 克隆到 storage/models/wav2lip/）。

本文件保留仅作说明，不再被任何代码调用。请勿恢复其中的手写网络。
"""
if __name__ == "__main__":
    raise SystemExit(
        "lipsync_runner.py 已弃用：请使用官方 Wav2Lip inference.py "
        "(storage/models/wav2lip/inference.py)，由 lipsync_service 调度。"
    )
