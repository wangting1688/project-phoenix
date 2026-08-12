"""
MVP 生产链路冒烟测试 (Task 1.6)
验证 video_producer 修复后的链路是否可以启动：
  1) 接口检查: create_task 创建 WorkflowTask / 返回 task_id / 启动后台线程
  2) 文案生成: AIExpertService.script_expert 被调用 + Script 保存
  3) TTS: 开发模式 fallback (macOS say) 生成音频 + 任务状态更新
  4) 渲染: ffmpeg 执行 + 输出 MP4 存在
不依赖真实 LLM API key（外部 AI 调用以测试桩代替，仅验证集成点）。
"""
import os
import sys
import json
import time
import shutil
import subprocess
import tempfile
import pathlib
import logging
import threading
from unittest import mock

BACKEND = "/Users/mac/Desktop/Project Phoenix/backend"
sys.path.insert(0, BACKEND)

# ---- 隔离环境：临时 sqlite + 开发模式(DEBUG=True 允许 TTS fallback) ----
TMP = tempfile.mkdtemp(prefix="phoenix_smoke_")
DB_PATH = os.path.join(TMP, "smoke.db")
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["DEBUG"] = "true"
os.environ.pop("VOLC_TTS_API_KEY", None)
os.environ.pop("VOLC_TTS_BASE_URL", None)

import app.core.database as dbmod
from app.core.database import Base, SessionLocal, engine
from app.core.config import settings
settings.DEBUG = True  # 强制开发模式
settings.VOLC_TTS_API_KEY = None
settings.VOLC_TTS_BASE_URL = None

import app.models  # noqa: F401  (注册所有模型)
Base.metadata.create_all(engine)

from app.models.content import ContentProject, WorkflowTask, Script, Video
from app.models.footage import Footage
from app.services.video_producer import VideoProducer
from app.services.voice_clone import synthesize as vc_synthesize

logging.basicConfig(level=logging.INFO)
LOG_RECORDS = []
class _RecHandler(logging.Handler):
    def emit(self, record):
        LOG_RECORDS.append(record)
for _name in ("app.services.video_producer", "app.services.voice_clone"):
    logging.getLogger(_name).addHandler(_RecHandler())

RESULTS = {"steps": [], "ok": True, "notes": []}
def step(name, passed, detail=""):
    RESULTS["steps"].append({"name": name, "passed": bool(passed), "detail": detail})
    if not passed:
        RESULTS["ok"] = False
    print(f"[{'PASS' if passed else 'FAIL'}] {name}  {detail}")

def make_fixture(path: str):
    # 生成 6s 1080x1920 测试视频
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", "color=c=teal:s=1080x1920:d=6",
         "-pix_fmt", "yuv420p", path],
        check=True, capture_output=True, text=True,
    )

TOPIC = "春季健康饮食建议"
STUB_SCRIPT = ("春季养生应注意饮食调理。多吃新鲜蔬菜水果对身体很有好处。"
               "早睡早起能提升免疫力。适量运动有助于保持活力。")

def main():
    db = SessionLocal()
    try:
        # ---- 种子数据 ----
        proj = ContentProject(user_id=1, topic=TOPIC, status="draft",
                              workflow_status="draft")
        db.add(proj)
        db.flush()

        fixture = os.path.join(TMP, "test_footage.mp4")
        make_fixture(fixture)
        footage = Footage(user_id=1, filename="test_footage.mp4",
                          file_path=fixture, status="ready")
        db.add(footage)
        db.commit()
        db.refresh(footage)
        project_id = proj.id
        footage_id = footage.id
        step("种子数据: ContentProject + Footage 已创建",
             bool(project_id and footage_id),
             f"project_id={project_id} footage_id={footage_id}")
    finally:
        db.close()

    # ---- 桩: AIExpertService.script_expert (仅验证集成点, 不依赖真实 LLM) ----
    call_log = {}
    def fake_script_expert(self, topic, planning):
        call_log["called"] = True
        call_log["topic"] = topic
        call_log["planning"] = planning
        assert topic == TOPIC, f"script_expert 收到的 topic 不符: {topic!r}"
        return {"story_version": STUB_SCRIPT, "score": {"total": 88}}

    with mock.patch("app.experts.ai_expert.AIExpertService.script_expert",
                    fake_script_expert):
        # ===== 1. 接口检查: create_task =====
        captured = {}
        class _FakeThread(threading.Thread):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                captured["target"] = k.get("target")
            def start(self):
                captured["started"] = True  # 不真正起线程, 稍后前台手动跑

        with mock.patch("threading.Thread", _FakeThread):
            t0 = time.time()
            task_id = VideoProducer.create_task(
                project_id=project_id, user_id=1, script_id=0,
                voice_profile_id=0, footage_id=footage_id, with_lipsync=True,
            )
            create_dt = time.time() - t0

        db = SessionLocal()
        try:
            task = db.query(WorkflowTask).filter(
                WorkflowTask.id == task_id).first()
            created_ok = task is not None and task.status == "waiting"
            params = json.loads(task.result) if task and task.result else {}
            step("接口检查: create_task 返回 task_id",
                 isinstance(task_id, int) and task_id > 0, f"task_id={task_id}")
            step("接口检查: WorkflowTask 已创建(status=waiting)",
                 created_ok,
                 f"status={task.status if task else None} result={params}")
            step("接口检查: 已启动后台线程",
                 bool(captured.get("started") and callable(captured.get("target"))),
                 "threading.Thread.start 被调用")
        finally:
            db.close()

        # ===== 2~4. 前台运行后台任务体(完整链路) =====
        try:
            captured["target"]()  # 即 _run(): producer.run(task_id)
            run_ok = True
            run_err = ""
        except Exception as e:
            run_ok = False
            run_err = f"{type(e).__name__}: {e}"
        step("完整链路 run() 未抛异常", run_ok, run_err)

        db = SessionLocal()
        try:
            task = db.query(WorkflowTask).filter(
                WorkflowTask.id == task_id).first()
            script = db.query(Script).filter(
                Script.project_id == project_id).order_by(
                Script.id.desc()).first()
            video = db.query(Video).filter(
                Video.project_id == project_id).first()

            # 2. 文案生成
            step("文案生成: AIExpertService.script_expert 被调用",
                 bool(call_log.get("called")),
                 f"topic={call_log.get('topic')!r}")
            step("文案生成: Script 成功保存",
                 script is not None and (script.content or "").strip() != "",
                 f"script_id={script.id if script else None} "
                 f"len={len(script.content) if script else 0}")

            # 3. TTS
            out_dir = pathlib.Path(BACKEND) / "storage" / "output"
            tts_files = sorted(out_dir.glob("tts_*.mp3")) if out_dir.exists() else []
            tts_ok = any(f.exists() and f.stat().st_size > 0 for f in tts_files)
            tts_path = next((str(f) for f in tts_files
                             if f.exists() and f.stat().st_size > 0), None)
            step("TTS: 开发模式生成音频文件(fallback)",
                 tts_ok, f"file={tts_path} "
                 f"size={pathlib.Path(tts_path).stat().st_size if tts_path else 0}")

            # 4. 渲染
            renders = sorted(out_dir.glob("render_*.mp4")) if out_dir.exists() else []
            render_ok = any(f.exists() and f.stat().st_size > 1024 for f in renders)
            render_path = next((str(f) for f in renders
                                if f.exists() and f.stat().st_size > 1024), None)
            step("渲染: ffmpeg 输出 MP4 存在且可播放(>1KB)",
                 render_ok, f"file={render_path} "
                 f"size={pathlib.Path(render_path).stat().st_size if render_path else 0}")

            # 状态更新
            step("任务状态: completed + progress=100",
                 task.status == "completed" and task.progress == 100,
                 f"status={task.status} progress={task.progress} "
                 f"error={task.error_message}")
            step("Video 记录已写入", video is not None,
                 f"url={video.url if video else None} "
                 f"duration={video.duration if video else None}")

            # 日志规范(P1-4)
            log_hits = [r for r in LOG_RECORDS
                        if str(task_id) in r.getMessage()]
            step("日志: 使用 logging(含 task_id/步骤/状态)",
                 len(log_hits) >= 3,
                 f"命中日志条数={len(log_hits)} "
                 f"示例={log_hits[0].getMessage()[:80] if log_hits else ''}")
        finally:
            db.close()

    # ===== P1-3 生产模式: 未配火山必须显式报错(不静默) =====
    settings.DEBUG = False
    proj_prod = SessionLocal()
    try:
        dummy = pathlib.Path(TMP) / "prod_tts.mp3"
        try:
            vc_synthesize(db=proj_prod, custom_speaker_id=None,
                          text="生产环境测试", output_path=dummy)
            prod_raised = False
            prod_msg = "未抛异常(不符合预期)"
        except RuntimeError as e:
            prod_raised = True
            prod_msg = str(e)
        except Exception as e:
            prod_raised = False
            prod_msg = f"抛了非 RuntimeError: {type(e).__name__}: {e}"
        finally:
            settings.DEBUG = True
        step("生产模式: 未配火山显式报错(不静默降级)",
             prod_raised and "生产环境" in prod_msg, prod_msg)
    finally:
        proj_prod.close()

    # 清理测试产物(避免污染仓库)
    try:
        out_dir = pathlib.Path(BACKEND) / "storage" / "output"
        if out_dir.exists():
            for f in out_dir.glob("tts_*.mp3"):
                f.unlink(missing_ok=True)
            for f in out_dir.glob("render_*.mp4"):
                f.unlink(missing_ok=True)
            for f in out_dir.glob("render_*_cover.jpg"):
                f.unlink(missing_ok=True)
    except Exception:
        pass
    shutil.rmtree(TMP, ignore_errors=True)

    print("\n=== SMOKE TEST SUMMARY ===")
    print(json.dumps({"ok": RESULTS["ok"], "steps": RESULTS["steps"]},
                     ensure_ascii=False, indent=2))
    return RESULTS

if __name__ == "__main__":
    main()
