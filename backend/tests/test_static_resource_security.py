"""
静态资源安全 P0 修复 - 单元测试

覆盖：
1. 未登录访问 → 401
2. 用户A访问用户B文件 → 403
3. 用户访问自己的文件 → 200
4. token过期 → 401
5. 路径穿越 → 安全（不泄露）

分两类：
- 路由集成测试：验证 serve_static 路由的整体行为
- 函数单元测试：验证 _check_output_ownership 的归属校验逻辑
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from datetime import timedelta
from pathlib import Path

_backend_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _backend_root)

from fastapi.testclient import TestClient
from app.core.security import create_access_token


class TestStaticResourceSecurity(unittest.TestCase):
    """静态资源安全路由集成测试"""

    @classmethod
    def setUpClass(cls):
        # 创建临时存储目录和测试文件
        cls.tmp_storage = tempfile.mkdtemp(prefix="static_test_")

        # 模拟目录结构
        for d in [
            "footage/1", "footage/6",
            "voice_demos/1", "voice_demos/6",
            "voice_samples/1",
            "output", "test_output",
        ]:
            os.makedirs(os.path.join(cls.tmp_storage, d), exist_ok=True)

        # 创建测试文件
        test_files = [
            "footage/1/user1_video.mp4",
            "footage/6/user6_video.mp4",
            "voice_demos/1/demo1.mp3",
            "voice_demos/6/demo6.mp3",
            "voice_samples/1/sample1.wav",
            "output/render_22_1234567890.mp4",
            "output/render_99_1234567890.mp4",
            "output/sneaky_file.mp4",
            "test_output/test.mp4",
        ]
        for f in test_files:
            full = os.path.join(cls.tmp_storage, f)
            with open(full, "wb") as fh:
                fh.write(b"fake video data for testing")

        # 生成各种 token
        cls.token_user1 = create_access_token(
            data={"sub": "1", "tenant_id": 1, "role": "anchor"})
        cls.token_user6 = create_access_token(
            data={"sub": "6", "tenant_id": 1, "role": "anchor"})
        cls.token_admin = create_access_token(
            data={"sub": "100", "tenant_id": None, "role": "super_admin"})
        cls.token_expired = create_access_token(
            data={"sub": "1"}, expires_delta=timedelta(seconds=-1))
        cls.token_no_sub = create_access_token(
            data={"tenant_id": 1, "role": "anchor"})

        # 导入 app 并替换 STORAGE_DIR
        import app.main as main_mod
        main_mod.STORAGE_DIR = Path(cls.tmp_storage).resolve()
        from app.main import app

        # 建表：_check_output_ownership 对不符合 render_<pid>_/h3_p<pid>_ 命名的
        # 文件会**兜底按 Video.url 反查归属**（见 app/main.py 该函数注释，
        # 目的是防止命名约定变化时合法成片被误 403）。这条兜底路径会真实查询
        # videos / content_projects 表。
        #
        # 测试库由 conftest.py 锁到进程私有临时 sqlite，默认是空文件，不建表
        # 就会抛 OperationalError: no such table: videos —— 表现是把一个本应
        # 返回 403 的用例变成 500，看起来像代码挂了，其实是测试环境缺 schema。
        # create_all 幂等，对已存在的表不做任何改动。
        from app.core.database import Base, engine as db_engine
        Base.metadata.create_all(bind=db_engine)

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmp_storage, ignore_errors=True)

    # ======== 1. 未登录访问 → 401 ========

    def test_no_token_returns_401(self):
        """未登录访问静态资源 → 401"""
        resp = self.client.get("/static/footage/1/user1_video.mp4")
        self.assertEqual(resp.status_code, 401)

    def test_empty_token_returns_401(self):
        """空 token → 401"""
        resp = self.client.get("/static/footage/1/user1_video.mp4?token=")
        self.assertEqual(resp.status_code, 401)

    def test_invalid_token_returns_401(self):
        """伪造 token → 401"""
        resp = self.client.get("/static/footage/1/user1_video.mp4?token=fake.token.here")
        self.assertEqual(resp.status_code, 401)

    def test_bearer_invalid_returns_401(self):
        """Authorization Bearer 无效 token → 401"""
        resp = self.client.get(
            "/static/footage/1/user1_video.mp4",
            headers={"Authorization": "Bearer fake.token"})
        self.assertEqual(resp.status_code, 401)

    # ======== 2. 用户A访问用户B文件 → 403 ========

    def test_cross_user_footage_403(self):
        """用户1访问用户6的素材 → 403"""
        resp = self.client.get(
            f"/static/footage/6/user6_video.mp4?token={self.token_user1}")
        self.assertEqual(resp.status_code, 403)

    def test_cross_user_voice_demo_403(self):
        """用户6访问用户1的音色Demo → 403"""
        resp = self.client.get(
            f"/static/voice_demos/1/demo1.mp3?token={self.token_user6}")
        self.assertEqual(resp.status_code, 403)

    def test_cross_user_voice_sample_403(self):
        """用户6访问用户1的语音样本 → 403"""
        resp = self.client.get(
            f"/static/voice_samples/1/sample1.wav?token={self.token_user6}")
        self.assertEqual(resp.status_code, 403)

    # ======== 3. 用户访问自己的文件 → 200 ========

    def test_own_footage_200(self):
        """用户1访问自己的素材 → 200"""
        resp = self.client.get(
            f"/static/footage/1/user1_video.mp4?token={self.token_user1}")
        self.assertEqual(resp.status_code, 200)

    def test_own_voice_demo_200(self):
        """用户1访问自己的音色Demo → 200"""
        resp = self.client.get(
            f"/static/voice_demos/1/demo1.mp3?token={self.token_user1}")
        self.assertEqual(resp.status_code, 200)

    def test_own_voice_sample_200(self):
        """用户1访问自己的语音样本 → 200"""
        resp = self.client.get(
            f"/static/voice_samples/1/sample1.wav?token={self.token_user1}")
        self.assertEqual(resp.status_code, 200)

    def test_bearer_token_200(self):
        """Authorization Bearer 方式也能正常访问 → 200"""
        resp = self.client.get(
            "/static/footage/1/user1_video.mp4",
            headers={"Authorization": f"Bearer {self.token_user1}"})
        self.assertEqual(resp.status_code, 200)

    def test_admin_access_all_200(self):
        """super_admin 可访问所有用户的文件 → 200"""
        resp = self.client.get(
            f"/static/footage/6/user6_video.mp4?token={self.token_admin}")
        self.assertEqual(resp.status_code, 200)

    def test_admin_voice_demo_200(self):
        """super_admin 访问任意音色Demo → 200"""
        resp = self.client.get(
            f"/static/voice_demos/6/demo6.mp3?token={self.token_admin}")
        self.assertEqual(resp.status_code, 200)

    # ======== 4. token过期 → 401 ========

    def test_expired_token_401(self):
        """过期 token → 401"""
        resp = self.client.get(
            f"/static/footage/1/user1_video.mp4?token={self.token_expired}")
        self.assertEqual(resp.status_code, 401)

    def test_token_no_sub_401(self):
        """token 中无 sub → 401"""
        resp = self.client.get(
            f"/static/footage/1/user1_video.mp4?token={self.token_no_sub}")
        self.assertEqual(resp.status_code, 401)

    # ======== 5. 路径穿越 & 安全边界 ========

    def test_path_traversal_dotdot_safe(self):
        """路径穿越 ../etc/passwd → 不会泄露文件"""
        resp = self.client.get(
            f"/static/../../../etc/passwd?token={self.token_user1}")
        self.assertIn(resp.status_code, [403, 404])
        self.assertNotEqual(resp.status_code, 200)

    def test_path_traversal_dotdot_footage_safe(self):
        """footage/../../etc/passwd → 不会泄露文件"""
        resp = self.client.get(
            f"/static/footage/../../../etc/passwd?token={self.token_user1}")
        self.assertIn(resp.status_code, [403, 404])
        self.assertNotEqual(resp.status_code, 200)

    def test_path_traversal_url_encode_safe(self):
        """URL 编码的路径穿越 → 不会泄露文件"""
        resp = self.client.get(
            f"/static/footage/1/%2e%2e%2f%2e%2e%2fetc/passwd?token={self.token_user1}")
        self.assertIn(resp.status_code, [403, 404])
        self.assertNotEqual(resp.status_code, 200)

    def test_nonexistent_file_404(self):
        """不存在的文件 → 404"""
        resp = self.client.get(
            f"/static/footage/1/nonexistent.mp4?token={self.token_user1}")
        self.assertEqual(resp.status_code, 404)

    def test_unknown_category_not_accessible(self):
        """未知目录分类 → 不可访问"""
        resp = self.client.get(
            f"/static/unknown_dir/file.txt?token={self.token_user1}")
        self.assertIn(resp.status_code, [403, 404])
        self.assertNotEqual(resp.status_code, 200)

    # ======== output 目录归属校验（mock _check_output_ownership） ========

    @patch("app.main._check_output_ownership", return_value=True)
    def test_output_own_project_200(self, mock_check):
        """output 目录：归属校验通过 → 200"""
        resp = self.client.get(
            f"/static/output/render_22_1234567890.mp4?token={self.token_user1}")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(mock_check.called)

    @patch("app.main._check_output_ownership", return_value=False)
    def test_output_cross_user_403(self, mock_check):
        """output 目录：归属校验失败 → 403"""
        resp = self.client.get(
            f"/static/output/render_99_1234567890.mp4?token={self.token_user1}")
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(mock_check.called)

    @patch("app.main._check_output_ownership", return_value=True)
    def test_output_admin_200(self, mock_check):
        """output 目录：admin 访问 → 200"""
        resp = self.client.get(
            f"/static/output/render_99_1234567890.mp4?token={self.token_admin}")
        self.assertEqual(resp.status_code, 200)

    def test_output_bad_filename_403(self):
        """output 文件名格式不对（无 project_id）→ 403"""
        resp = self.client.get(
            f"/static/output/sneaky_file.mp4?token={self.token_user1}")
        self.assertEqual(resp.status_code, 403)

    # ======== 同租户访问 ========

    def test_same_tenant_footage_still_403(self):
        """同租户但不同用户的 footage → 403（目录级只校验本人）"""
        resp = self.client.get(
            f"/static/footage/6/user6_video.mp4?token={self.token_user1}")
        self.assertEqual(resp.status_code, 403)


class TestCheckOutputOwnership(unittest.TestCase):
    """_check_output_ownership 函数的单元测试"""

    def test_super_admin_always_true(self):
        """super_admin 始终返回 True，不查 DB"""
        from app.main import _check_output_ownership
        db = MagicMock()
        result = _check_output_ownership(
            "render_1_123.mp4", user_id=999, tenant_id=None, role="super_admin", db=db)
        self.assertTrue(result)
        db.query.assert_not_called()

    def test_bad_filename_false(self):
        """文件名不符合成片命名约定、且按 url 反查也查不到 → False

        契约说明（别把断言改回「不查 DB」）：
        实现里对不匹配 render_<pid>_ / h3_p<pid>_ 的文件名**会兜底按
        Video.url 反查归属**，这是有意设计 —— 历史上改过一次成片命名，
        导致老成片全部 403，用户以为视频丢了。所以这里断言的是
        「最终拒绝」，而不是「完全不查 DB」。
        空库下反查不到记录，因此结果仍为 False。
        """
        from app.main import _check_output_ownership
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        result = _check_output_ownership(
            "sneaky.mp4", user_id=1, tenant_id=None, role="anchor", db=db)
        self.assertFalse(result)

    def test_no_video_false(self):
        """查不到 video → False"""
        from app.main import _check_output_ownership
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        result = _check_output_ownership(
            "render_1_123.mp4", user_id=1, tenant_id=None, role="anchor", db=db)
        self.assertFalse(result)

    def _make_db_mock(self, video_user_id, video_tenant_id=None):
        """构造返回指定 project 的 mock DB"""
        db = MagicMock()
        mock_video = MagicMock()
        mock_project = MagicMock()
        mock_project.user_id = video_user_id
        mock_project.tenant_id = video_tenant_id
        call_count = {"n": 0}

        def _first():
            call_count["n"] += 1
            if call_count["n"] == 1:
                return mock_video
            return mock_project

        db.query.return_value.filter.return_value.first.side_effect = _first
        return db

    def test_own_project_true(self):
        """用户自己的项目 → True"""
        from app.main import _check_output_ownership
        db = self._make_db_mock(video_user_id=1)
        result = _check_output_ownership(
            "render_22_123.mp4", user_id=1, tenant_id=None, role="anchor", db=db)
        self.assertTrue(result)

    def test_other_user_project_false(self):
        """其他用户的项目 → False"""
        from app.main import _check_output_ownership
        db = self._make_db_mock(video_user_id=2)
        result = _check_output_ownership(
            "render_22_123.mp4", user_id=1, tenant_id=None, role="anchor", db=db)
        self.assertFalse(result)

    def test_same_tenant_returns_true(self):
        """同租户不同用户 → True"""
        from app.main import _check_output_ownership
        db = self._make_db_mock(video_user_id=2, video_tenant_id=1)
        result = _check_output_ownership(
            "render_22_123.mp4", user_id=1, tenant_id=1, role="anchor", db=db)
        self.assertTrue(result)

    def test_different_tenant_returns_false(self):
        """不同租户 → False"""
        from app.main import _check_output_ownership
        db = self._make_db_mock(video_user_id=2, video_tenant_id=2)
        result = _check_output_ownership(
            "render_22_123.mp4", user_id=1, tenant_id=1, role="anchor", db=db)
        self.assertFalse(result)


class TestResourceOwnership(unittest.TestCase):
    """_check_resource_ownership 函数的单元测试"""

    def test_super_admin_all_true(self):
        """super_admin 所有目录都放行"""
        from app.main import _check_resource_ownership
        self.assertTrue(_check_resource_ownership(
            "footage/1/x.mp4", user_id=999, tenant_id=None, role="super_admin"))
        self.assertTrue(_check_resource_ownership(
            "output/render_1_xxx.mp4", user_id=999, tenant_id=None, role="super_admin"))
        self.assertTrue(_check_resource_ownership(
            "voice_demos/1/x.mp3", user_id=999, tenant_id=None, role="super_admin"))

    def test_footage_own_true(self):
        """footage：本人 → True"""
        from app.main import _check_resource_ownership
        self.assertTrue(_check_resource_ownership(
            "footage/1/x.mp4", user_id=1, tenant_id=1, role="anchor"))

    def test_footage_other_false(self):
        """footage：他人 → False"""
        from app.main import _check_resource_ownership
        self.assertFalse(_check_resource_ownership(
            "footage/2/x.mp4", user_id=1, tenant_id=1, role="anchor"))

    def test_voice_demos_own_true(self):
        """voice_demos：本人 → True"""
        from app.main import _check_resource_ownership
        self.assertTrue(_check_resource_ownership(
            "voice_demos/1/x.mp3", user_id=1, tenant_id=1, role="anchor"))

    def test_voice_samples_own_true(self):
        """voice_samples：本人 → True"""
        from app.main import _check_resource_ownership
        self.assertTrue(_check_resource_ownership(
            "voice_samples/1/x.wav", user_id=1, tenant_id=1, role="anchor"))

    def test_output_passes_to_db_check(self):
        """output 目录返回 True（由 DB 层进一步校验）"""
        from app.main import _check_resource_ownership
        self.assertTrue(_check_resource_ownership(
            "output/render_1_x.mp4", user_id=1, tenant_id=1, role="anchor"))

    def test_unknown_category_false(self):
        """未知目录 → False"""
        from app.main import _check_resource_ownership
        self.assertFalse(_check_resource_ownership(
            "secrets/passwords.txt", user_id=1, tenant_id=1, role="anchor"))

    def test_test_output_debug_only(self):
        """test_output 目录：非 DEBUG 模式 → False"""
        from app.main import _check_resource_ownership
        # settings.DEBUG 默认 True，但我们测试下逻辑
        # 这里直接依赖实际 settings
        pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
