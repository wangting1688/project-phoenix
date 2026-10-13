"""pytest 全局配置。

三个作用：
1. 把 backend 根目录加入 sys.path，让测试能 import app.*（各测试文件原本
   各自 sys.path.insert，重复且容易漏）。
2. 确保 ffmpeg 可被找到：被测代码与测试都直接调用 "ffmpeg" 依赖 PATH，
   而开发机常把 ffmpeg 装在非标准目录（本项目是 D:/ffmpeg_bin，因为
   官方脚本用 shell=True 调 ffmpeg，中文路径会导致查找失败）。
   找不到时跳过依赖 ffmpeg 的测试，而不是让它们报错。
3. 把 DATABASE_URL 锁到进程私有的临时 sqlite 文件（见下方 TEST_DB_PATH）。
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# ── 测试数据库隔离 ────────────────────────────────────────────────────
# 为什么必须写在模块级、且在任何 app.* 被 import 之前：
#   app/core/config.py 在 import 的那一刻就执行 Settings()，DATABASE_URL 随之
#   固定，之后再改环境变量已经无效。而 conftest.py 是 pytest 最早加载的文件，
#   早于所有测试模块（以及它们 import 的 app.*），这是唯一能可靠生效的位置。
#
# 为什么必须隔离：
#   test_static_resource_security.py 会真实查询 videos / content_projects 表
#   （_check_output_ownership 对非 render_/h3_p 命名的文件走「按 url 反查」兜底）。
#   若连到开发库或生产库，轻则被现有数据干扰造成断言漂移，重则意外写入。
#   第三方显式设置的 DATABASE_URL 仍然被尊重，便于将来接入真实测试库。
TEST_DB_PATH: Optional[Path] = None
if not os.environ.get("DATABASE_URL"):
    # 文件名带 pid：每次 pytest 进程拿到全新空库，避免上一次运行的残留数据
    # 让「查不到记录 → 403」这类断言莫名失败。
    TEST_DB_PATH = Path(tempfile.gettempdir()) / f"phoenix_pytest_{os.getpid()}.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"


@pytest.fixture(scope="session", autouse=True)
def _cleanup_test_db():
    """整个测试会话结束后删掉临时库，避免临时目录堆积。"""
    yield
    if TEST_DB_PATH is not None:
        try:
            TEST_DB_PATH.unlink(missing_ok=True)
        except OSError:
            pass

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
