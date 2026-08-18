"""pytest 全局配置。

两个作用：
1. 把 backend 根目录加入 sys.path，让测试能 import app.*（各测试文件原本
   各自 sys.path.insert，重复且容易漏）。
2. 确保 ffmpeg 可被找到：被测代码与测试都直接调用 "ffmpeg" 依赖 PATH，
   而开发机常把 ffmpeg 装在非标准目录（本项目是 D:/ffmpeg_bin，因为
   官方脚本用 shell=True 调 ffmpeg，中文路径会导致查找失败）。
   找不到时跳过依赖 ffmpeg 的测试，而不是让它们报错。
"""
import os
import shutil
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# ffmpeg 的常见位置：环境变量优先，其次本项目约定的 ASCII 目录，最后系统路径
_FFMPEG_CANDIDATES = [
    os.environ.get("FFMPEG_DIR"),
    r"D:\ffmpeg_bin",
    "/usr/local/bin",
    "/usr/bin",
]


def _ensure_ffmpeg_on_path():
    if shutil.which("ffmpeg"):
        return True
    for d in _FFMPEG_CANDIDATES:
        if not d:
            continue
        exe = Path(d) / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        if exe.is_file():
            os.environ["PATH"] = str(Path(d)) + os.pathsep + os.environ.get("PATH", "")
            return True
    return False


HAS_FFMPEG = _ensure_ffmpeg_on_path()


def pytest_collection_modifyitems(config, items):
    """没有 ffmpeg 时跳过相关测试，避免把环境缺失误报成代码失败。"""
    if HAS_FFMPEG:
        return
    skip = pytest.mark.skip(reason="ffmpeg 不可用，跳过依赖 ffmpeg 的测试")
    for item in items:
        if "render_p0" in item.nodeid or "ffmpeg" in item.nodeid.lower():
            item.add_marker(skip)
