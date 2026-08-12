"""
视频渲染 P0 修复 - 单元测试

覆盖：
1. ToolRegistry.call_tool 错误返回检测（错误静默问题）
2. FFmpegTool render 操作参数协议（参数协议统一）
3. FFmpegTool 错误被正确识别为失败（错误静默问题）
4. 端到端渲染测试（实际生成视频）
"""

import os
import sys
import tempfile
import unittest
import subprocess

_backend_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _backend_root)

# 绕过 app.services.__init__ 的全量导入（依赖 sqlalchemy）
import importlib.util

def _load_module(name, rel_path):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(_backend_root, rel_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

tool_registry = _load_module(
    "app.services.tool_registry",
    "app/services/tool_registry.py")
ToolRegistry = tool_registry.ToolRegistry
BaseTool = tool_registry.BaseTool
ToolParameter = tool_registry.ToolParameter
ToolCategory = tool_registry.ToolCategory


class DummyErrorTool(BaseTool):
    """模拟用 return {"error": ...} 返回错误的工具"""
    NAME = "dummy_error_tool"
    DESCRIPTION = "测试用：返回 error dict 的工具"
    CATEGORY = ToolCategory.UTILITY
    PARAMETERS = [
        ToolParameter(name="should_fail", type="boolean", description="是否失败", required=False),
    ]

    def execute(self, **kwargs):
        if kwargs.get("should_fail", True):
            return {"error": "测试错误信息"}
        return {"result": "成功数据"}


class DummyExceptionTool(BaseTool):
    """模拟抛异常的工具"""
    NAME = "dummy_exception_tool"
    DESCRIPTION = "测试用：抛异常的工具"
    CATEGORY = ToolCategory.UTILITY
    PARAMETERS = []

    def execute(self, **kwargs):
        raise RuntimeError("测试异常")


class TestToolRegistryErrorDetection(unittest.TestCase):
    """测试 ToolRegistry.call_tool 能否正确识别工具返回的 error"""

    def setUp(self):
        self.registry = ToolRegistry()
        # 清理单例中可能存在的其他注册
        for name in list(self.registry._tools.keys()):
            self.registry.unregister(name)

    def test_return_error_dict_is_failure(self):
        """工具 return {"error": ...} 应被识别为失败"""
        tool = DummyErrorTool()
        tool.register()

        result = self.registry.call_tool("dummy_error_tool", should_fail=True)

        self.assertFalse(result["success"],
            "return {error: ...} 应被识别为 success=False")
        self.assertIn("error", result, "返回值应包含 error 字段")
        self.assertEqual(result["error"], "测试错误信息")
        self.assertIn("data", result, "返回值应保留原始 data")

    def test_return_success_dict_is_success(self):
        """工具返回不含 error 的 dict 应被识别为成功"""
        tool = DummyErrorTool()
        tool.register()

        result = self.registry.call_tool("dummy_error_tool", should_fail=False)

        self.assertTrue(result["success"],
            "返回不含 error 的 dict 应被识别为 success=True")
        self.assertEqual(result["data"]["result"], "成功数据")

    def test_exception_is_failure(self):
        """工具抛异常应被识别为失败（原有逻辑）"""
        tool = DummyExceptionTool()
        tool.register()

        result = self.registry.call_tool("dummy_exception_tool")

        self.assertFalse(result["success"], "抛异常应被识别为 success=False")
        self.assertIn("error", result)
        self.assertIn("测试异常", result["error"])

    def test_tool_not_found_is_failure(self):
        """工具不存在应返回失败"""
        result = self.registry.call_tool("nonexistent_tool")
        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])


class TestFFmpegToolRenderOperation(unittest.TestCase):
    """测试 FFmpegTool 的 render 操作"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix="ffmpeg_test_")
        # 生成 2 个测试视频片段
        cls.video1 = os.path.join(cls.tmpdir, "seg1.mp4")
        cls.video2 = os.path.join(cls.tmpdir, "seg2.mp4")
        cls.output = os.path.join(cls.tmpdir, "output.mp4")

        # 用 ffmpeg 生成 3 秒测试视频（纯色 + 静音）
        for path, color in [(cls.video1, "blue"), (cls.video2, "red")]:
            cmd = [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", f"color=c={color}:s=360x640:d=3",
                "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", path,
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if proc.returncode != 0:
                raise RuntimeError(f"测试视频生成失败: {proc.stderr}")

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def _get_ffmpeg_tool(self):
        external_tools = _load_module(
            "app.services.external_tools",
            "app/services/external_tools.py")
        return external_tools.FFmpegTool()

    def test_render_with_valid_segments(self):
        """render 操作：有效素材应成功生成输出视频"""
        tool = self._get_ffmpeg_tool()
        segments = [
            {"path": self.video1, "duration": 2},
            {"path": self.video2, "duration": 2},
        ]
        subtitles = [
            {"text": "测试字幕一", "start_sec": 0, "end_sec": 2},
            {"text": "测试字幕二", "start_sec": 2, "end_sec": 4},
        ]

        result = tool.execute(
            operation="render",
            segments=segments,
            subtitles=subtitles,
            output_path=self.output,
            width=360,
            height=640,
            fps=30,
        )

        self.assertNotIn("error", result,
            f"render 不应返回错误: {result.get('error', '')}")
        self.assertTrue(result.get("success"), "render 结果应包含 success=True")
        self.assertTrue(os.path.exists(self.output), "输出文件应存在")
        self.assertGreater(os.path.getsize(self.output), 1024,
            "输出文件应大于 1KB")
        self.assertEqual(result.get("segment_count"), 2)
        self.assertEqual(result.get("subtitle_count"), 2)

    def test_render_empty_segments_returns_error(self):
        """render 操作：空 segments 应返回错误"""
        tool = self._get_ffmpeg_tool()
        result = tool.execute(
            operation="render",
            segments=[],
            output_path=self.output,
        )
        self.assertIn("error", result, "空 segments 应返回 error")

    def test_render_no_output_path_returns_error(self):
        """render 操作：不传 output_path 应返回错误"""
        tool = self._get_ffmpeg_tool()
        result = tool.execute(
            operation="render",
            segments=[{"path": self.video1, "duration": 2}],
        )
        self.assertIn("error", result, "无 output_path 应返回 error")

    def test_render_all_invalid_paths_returns_error(self):
        """render 操作：所有素材路径都无效应返回错误"""
        tool = self._get_ffmpeg_tool()
        result = tool.execute(
            operation="render",
            segments=[{"path": "/nonexistent/video.mp4", "duration": 5}],
            output_path=self.output,
        )
        self.assertIn("error", result, "全部无效路径应返回 error")

    def test_render_without_subtitles(self):
        """render 操作：无字幕也能正常渲染"""
        tool = self._get_ffmpeg_tool()
        output_no_sub = os.path.join(self.tmpdir, "output_nosub.mp4")
        result = tool.execute(
            operation="render",
            segments=[{"path": self.video1, "duration": 2}],
            subtitles=[],
            output_path=output_no_sub,
            width=360,
            height=640,
        )
        self.assertNotIn("error", result)
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("subtitle_count"), 0)
        self.assertTrue(os.path.exists(output_no_sub))


    def test_render_mixed_resolutions_scaled_concat(self):
        """P0-11 回归：不同分辨率（横屏+竖屏）素材统一缩放后拼接，SAR 应一致"""
        tool = self._get_ffmpeg_tool()
        v_hd = os.path.join(self.tmpdir, "p011_hd_1920x1080.mp4")
        v_sd = os.path.join(self.tmpdir, "p011_sd_720x1280.mp4")
        out = os.path.join(self.tmpdir, "p011_scaled_1080x1920.mp4")

        # 生成横屏(1920x1080)和竖屏(720x1280)测试视频
        for path, size in [(v_hd, "1920x1080"), (v_sd, "720x1280")]:
            cmd = [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", f"color=c=green:s={size}:d=2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-an", path,
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            self.assertEqual(proc.returncode, 0,
                f"测试视频生成失败 {size}: {proc.stderr}")

        result = tool.execute(
            operation="render",
            segments=[
                {"path": v_hd, "duration": 1},
                {"path": v_sd, "duration": 1},
            ],
            output_path=out,
            width=1080,
            height=1920,
            fps=30,
        )

        self.assertNotIn("error", result,
            f"不同分辨率缩放拼接不应报错: {result.get('error', '')}")
        self.assertTrue(result.get("success"),
            "不同分辨率素材统一缩放后应能成功 concat")

        # 验证输出分辨率
        proc = subprocess.run(
            ["ffmpeg", "-i", out],
            capture_output=True, text=True, timeout=10
        )
        found_res = False
        for line in proc.stderr.split("\n"):
            if "Stream #" in line and "Video:" in line:
                if "1080x1920" in line:
                    found_res = True
                break
        self.assertTrue(found_res,
            f"输出分辨率应为 1080x1920，实际 ffmpeg 输出: {proc.stderr}")


class TestFFmpegToolViaRegistry(unittest.TestCase):
    """测试 FFmpegTool 通过 ToolRegistry 调用时错误能否正确传播"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix="ffmpeg_reg_test_")
        cls.video = os.path.join(cls.tmpdir, "test.mp4")
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "color=c=green:s=360x640:d=2",
            "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
            "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", cls.video,
        ]
        subprocess.run(cmd, capture_output=True, timeout=30)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        # 注册 FFmpegTool
        external_tools = _load_module(
            "app.services.external_tools",
            "app/services/external_tools.py")
        FFmpegTool = external_tools.FFmpegTool
        self.registry = ToolRegistry()
        # 清理
        for name in list(self.registry._tools.keys()):
            self.registry.unregister(name)
        FFmpegTool().register()

    def test_render_success_via_registry(self):
        """通过 registry 调用成功的 render 应返回 success=True"""
        output = os.path.join(self.tmpdir, "reg_success.mp4")
        result = self.registry.call_tool(
            "ffmpeg_process",
            operation="render",
            segments=[{"path": self.video, "duration": 1}],
            output_path=output,
            width=360,
            height=640,
        )
        self.assertTrue(result["success"],
            f"成功渲染应返回 success=True，实际: {result}")
        self.assertIn("data", result)
        self.assertTrue(result["data"].get("success"))

    def test_render_failure_via_registry(self):
        """通过 registry 调用失败的 render 应返回 success=False"""
        result = self.registry.call_tool(
            "ffmpeg_process",
            operation="render",
            segments=[],
            output_path="/tmp/should_not_exist.mp4",
        )
        self.assertFalse(result["success"],
            f"空 segments 应返回 success=False，实际: {result}")
        self.assertIn("error", result)
        self.assertIsInstance(result["error"], str)
        self.assertTrue(len(result["error"]) > 0)

    def test_trim_invalid_input_via_registry(self):
        """通过 registry 调用 trim 操作，输入文件不存在应返回失败"""
        result = self.registry.call_tool(
            "ffmpeg_process",
            operation="trim",
            input_path="/nonexistent/file.mp4",
            output_path="/tmp/out.mp4",
        )
        self.assertFalse(result["success"],
            f"无效输入应返回 success=False，实际: {result}")
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
