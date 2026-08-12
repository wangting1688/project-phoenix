"""
创作流程状态语义 P0 修复 - 单元测试

覆盖：
1. AI方案完成状态测试 (ai_plan_ready)
2. 无视频状态测试 (url=null 不显示已完成)
3. rendered 状态测试 (真正视频完成)
"""

import os
import sys
import unittest

_backend_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _backend_root)


def is_video_completed(video_status: str, video_url) -> bool:
    """判定视频是否真正完成（rendered + 有url）"""
    return video_status == "rendered" and bool(video_url)


def get_display_status(project_status: str, video_status,
                       video_url) -> str:
    """
    根据 project.status + video.status + video.url
    推导前端应展示的状态文案
    """
    if project_status == "processing":
        return "生成中"
    if project_status == "failed":
        return "失败"
    if project_status == "draft":
        return "草稿"
    if project_status == "completed":
        if video_status == "rendered" and video_url:
            return "已完成"
        return "待渲染"
    return project_status


class TestVideoWorkflowStatus(unittest.TestCase):
    """VideoGenerationWorkflow 创建 Video 时的初始状态"""

    def test_initial_status_is_ai_plan_ready(self):
        """VideoGenerationWorkflow 创建的 Video 初始状态应为 ai_plan_ready，而非 generated"""
        workflow_path = os.path.join(
            _backend_root, "app/workflow/video_workflow.py")
        with open(workflow_path, "r") as f:
            content = f.read()

        self.assertIn(
            'status="ai_plan_ready"', content,
            "video_workflow.py 中 Video 初始状态应为 ai_plan_ready")
        self.assertNotIn(
            'status="generated"', content,
            "video_workflow.py 中不应再有 status='generated'")

    def test_ai_plan_ready_semantic(self):
        """ai_plan_ready 语义：AI方案就绪，url应为空，非最终视频完成"""
        self.assertFalse(
            is_video_completed("ai_plan_ready", None),
            "ai_plan_ready + url=None 不应算视频完成")
        self.assertFalse(
            is_video_completed("ai_plan_ready", "http://example.com/x.mp4"),
            "ai_plan_ready 即使有 url 也不算视频完成（状态语义不对）")

    def test_rendered_status_semantic(self):
        """rendered 状态才是真正的视频完成，必须有 url"""
        self.assertTrue(
            is_video_completed("rendered", "https://example.com/out.mp4"),
            "rendered + 有 url 应算视频完成")
        self.assertFalse(
            is_video_completed("rendered", None),
            "rendered + url=None 不应算视频完成（保护）")

    def test_video_model_default_is_not_generated(self):
        """Video 模型默认值不是 generated（避免混淆）"""
        model_path = os.path.join(
            _backend_root, "app/models/content.py")
        with open(model_path, "r") as f:
            content = f.read()

        self.assertIn('status = Column(String(50), default="generating"', content,
            "Video 模型默认 status 应为 generating，与 ai_plan_ready/generated 区分")


class TestVideoUrlNullProtection(unittest.TestCase):
    """video.url = null 时的保护逻辑"""

    def test_url_null_not_completed(self):
        """url=null 时，即使 status 是 rendered 也不算完成（保护逻辑）"""
        self.assertFalse(
            is_video_completed("rendered", None),
            "url=None 时不应算视频完成")

    def test_url_empty_not_completed(self):
        """url 为空字符串时也不算完成"""
        self.assertFalse(
            is_video_completed("rendered", ""),
            "url='' 时不应算视频完成")

    def test_ai_plan_ready_not_completed(self):
        """ai_plan_ready 状态绝对不算视频完成"""
        self.assertFalse(
            is_video_completed("ai_plan_ready", None),
            "ai_plan_ready 状态不应算视频完成")
        self.assertFalse(
            is_video_completed("ai_plan_ready", "http://example.com/x.mp4"),
            "ai_plan_ready 即使有 url 也不算视频完成")

    def test_planned_not_completed(self):
        """planned（合成方案已生成）也不算视频完成"""
        self.assertFalse(
            is_video_completed("planned", None),
            "planned 状态不应算视频完成")

    def test_rendered_with_url_is_completed(self):
        """rendered + 有 url 才是真正完成"""
        self.assertTrue(
            is_video_completed("rendered", "https://cdn.com/out.mp4"),
            "rendered + 有 url 应算视频完成")


class TestStatusSemanticMatrix(unittest.TestCase):
    """状态语义矩阵测试 - 确保各状态含义清晰不混淆"""

    def test_completed_with_rendered_video(self):
        """project=completed + video=rendered + 有url → 已完成"""
        self.assertEqual(
            get_display_status("completed", "rendered", "/path/to/video.mp4"),
            "已完成")

    def test_completed_ai_plan_ready_no_url(self):
        """project=completed + video=ai_plan_ready + 无url → 待渲染"""
        self.assertEqual(
            get_display_status("completed", "ai_plan_ready", None),
            "待渲染")

    def test_completed_planned_no_url(self):
        """project=completed + video=planned + 无url → 待渲染"""
        self.assertEqual(
            get_display_status("completed", "planned", None),
            "待渲染")

    def test_completed_rendered_null_url(self):
        """project=completed + video=rendered + url=null → 待渲染（保护）"""
        self.assertEqual(
            get_display_status("completed", "rendered", None),
            "待渲染",
            "url=null 时即使 status=rendered 也应显示待渲染，不能显示已完成")

    def test_processing_stays_processing(self):
        """processing 状态不受视频影响"""
        self.assertEqual(
            get_display_status("processing", None, None),
            "生成中")

    def test_no_video_record_pending_render(self):
        """project=completed 但无 video 记录 → 待渲染"""
        self.assertEqual(
            get_display_status("completed", None, None),
            "待渲染")

    def test_draft_stays_draft(self):
        """draft 状态不变"""
        self.assertEqual(
            get_display_status("draft", None, None),
            "草稿")

    def test_failed_stays_failed(self):
        """failed 状态不变"""
        self.assertEqual(
            get_display_status("failed", None, None),
            "失败")


if __name__ == "__main__":
    unittest.main(verbosity=2)
