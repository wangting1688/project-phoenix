#!/usr/bin/env bash
#
# setup_lipsync_gpu.sh —— 在 GPU 机器上搭建真实 Wav2Lip 口型同步环境
#
# 用法（在 GPU 机器上，且已位于 backend 仓库根目录，或传 REPO_ROOT）：
#   sudo bash setup_lipsync_gpu.sh
#   REPO_ROOT=/path/to/backend sudo -E bash setup_lipsync_gpu.sh
#
# 前置：Ubuntu 20.04/22.04 + NVIDIA 驱动 + CUDA 11.8 已装好（nvidia-smi 可用）。
#
# 脚本会：
#   1. 装系统依赖 ffmpeg / git / python3.10 / venv
#   2. 建 venv 并装 torch(CUDA11.8) + opencv + librosa + face-alignment + scipy + numpy + tqdm
#   3. git clone 官方 Wav2Lip 到 storage/models/wav2lip/
#   4. 下载 wav2lip_gan.pth 检查点
#   5. 自检 import torch / 官方 inference.py 存在
#
# 注意：生产(CPU)后端通过环境变量 LIPSYNC_REMOTE_SSH=user@gpu-host 把口型同步派发到本机，
#       在本机 .env / systemd 里设置即可（本脚本不负责那一步）。
#
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$REPO_ROOT"
echo ">>> REPO_ROOT=$REPO_ROOT"

VENV="${REPO_ROOT}/.venv_lipsync"
STORAGE_MODELS="${REPO_ROOT}/storage/models"
WAV2LIP_DIR="${STORAGE_MODELS}/wav2lip"
CHECKPOINT="${STORAGE_MODELS}/wav2lip_gan.pth"

# 1) 系统依赖
export DEBIAN_FRONTEND=noninteractive
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y ffmpeg git python3.10 python3.10-venv python3.10-dev build-essential
fi

# 2) venv + python 依赖
python3.10 -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install --upgrade pip
# CUDA 11.8 版 torch（与常见 GPU 驱动兼容；如为 CUDA 12.x 请改 cu121）
pip install torch==2.1.2+cu118 --index-url https://download.pytorch.org/whl/cu118
pip install opencv-python-headless librosa scipy face-alignment numpy tqdm gdown

# 3) 克隆官方 Wav2Lip（含 inference.py / models.py / audio.py / hparams.py / face_detection/）
mkdir -p "$STORAGE_MODELS"
if [ ! -d "$WAV2LIP_DIR/.git" ]; then
  git clone https://github.com/Rudrabha/Wav2Lip.git "$WAV2LIP_DIR"
fi
mkdir -p "$WAV2LIP_DIR/temp"

# 4) 下载检查点 wav2lip_gan.pth（官方 Google Drive）
if [ ! -f "$CHECKPOINT" ]; then
  echo ">>> 下载 wav2lip_gan.pth ..."
  gdown "1epOCtfTzOawCdNhtWlStDBpoUS3-hhLd" -O "$CHECKPOINT"
fi

# 5) 自检
echo ">>> 自检 ..."
python - <<'PY'
import os, sys
root = os.environ["REPO_ROOT"]
ckpt = os.path.join(root, "storage/models/wav2lip_gan.pth")
inf = os.path.join(root, "storage/models/wav2lip/inference.py")
import torch
print("torch", torch.__version__, "cuda available:", torch.cuda.is_available())
assert os.path.exists(ckpt), f"checkpoint 缺失: {ckpt}"
assert os.path.exists(inf), f"inference.py 缺失: {inf}"
print("OK: Wav2Lip 环境就绪")
PY

echo ">>> 完成。GPU 机器地址请配置到生产后端的 LIPSYNC_REMOTE_SSH=user@gpu-host"
