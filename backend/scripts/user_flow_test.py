"""
MVP 真实主播流程集成测试 (后端 API 链路, 模拟前端 user_flow_test 的调用)

主播A: 输入主题 -> 生成3文案 -> 选1 -> 选声音 -> 选素材 -> 生成 -> 轮询 -> 作品页

通过 FastAPI TestClient 以真实 HTTP 路径驱动, 复刻 frontend 的接口调用链:
  POST /api/v1/creation/projects        (createProject)
  GET  /api/v1/creation/projects/{id}/scripts   (getProjectScripts)
  GET  /api/v1/voice-profiles          (getVoiceProfiles)
  GET  /api/v1/footage/list             (listFootages)
  POST /api/v1/video/generate/{id}      (generateVideo)
  GET  /api/v1/tasks/{id}               (getTaskStatus 轮询)
  GET  /api/v1/creation/projects/{id}   (getProject 作品详情)
  GET  /api/v1/creation/projects        (listProjects 作品列表)

不修改任何核心代码, 仅用临时 SQLite + 托管 venv 依赖进行验证。
"""
import os
import sys
import time
import json
import subprocess
from pathlib import Path

# 必须在 import app 之前设置环境
os.environ["DATABASE_URL"] = "sqlite:////tmp/phoenix_userflow_test.db"
os.environ["DEBUG"] = "true"          # 开发模式 -> TTS 允许 macOS say fallback
os.environ.setdefault("AI_PROVIDER", "mock")  # 默认 mock, 文案生成走本地桩

BACKEND = Path("/Users/mac/Desktop/Project Phoenix/backend")
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient
from fastapi import Depends
from sqlalchemy.orm import Session
from app.core.database import Base, engine, SessionLocal
from app.models import (
    User, UserVoiceProfile, Footage,
    Script, Video, WorkflowTask, ContentProject,
)
import app.main as main_mod

# 抑制 sqlalchemy 引擎的 echo 日志 (避免淹没测试结果)
import logging as _logging
_logging.getLogger("sqlalchemy.engine").setLevel(_logging.WARNING)
_logging.getLogger("sqlalchemy.engine.Engine").setLevel(_logging.WARNING)
_logging.getLogger("sqlalchemy.orm").setLevel(_logging.WARNING)
from app.core.database import engine as _eng
_eng.echo = False

# ---------- 准备临时 DB + 测试素材 ----------
DB_PATH = Path("/tmp/phoenix_userflow_test.db")
if DB_PATH.exists():
    DB_PATH.unlink()
Base.metadata.create_all(bind=engine)

storage_root = BACKEND
footage_dir = storage_root / "storage" / "footage"
footage_dir.mkdir(parents=True, exist_ok=True)
footage_file = footage_dir / "test_footage.mp4"
# 生成 3 秒 1080x1920 测试素材 (无音频, 渲染时由 TTS 配音 mux)
subprocess.run(
    ["ffmpeg", "-y", "-loglevel", "error",
     "-f", "lavfi", "-i", "color=c=teal:s=1080x1920:d=3",
     "-pix_fmt", "yuv420p", str(footage_file)],
    check=True,
)

# ---------- 种子数据 ----------
db = SessionLocal()
db.query(Video).delete()
db.query(Script).delete()
db.query(WorkflowTask).delete()
db.query(Footage).delete()
db.query(UserVoiceProfile).delete()
db.query(ContentProject).delete()
db.query(User).delete()
db.commit()

anchor = User(
    id=1, phone="13800000000", nickname="主播A",
    password_hash="seed", tenant_id=None, role="anchor", status=1,
)
db.add(anchor)
db.flush()
voice = UserVoiceProfile(
    id=1, user_id=1, name="主播A默认声音", status="active",
    custom_speaker_id=None, language=0,
    sample_path="storage/voice_demos/seed_sample.mp3",
)
db.add(voice)
db.flush()
foot = Footage(
    id=1, user_id=1, filename="test_footage.mp4",
    file_path=f"storage/footage/test_footage.mp4",
    duration=3, status="ready", scene="客厅", emotion="微笑",
    topics=["健康", "生活"],
)
db.add(foot)
db.commit()
db.close()

# ---------- 覆盖鉴权依赖 (复用请求内的 db 会话, 使 current_user 保持 attached) ----------
app = main_mod.app
from app.api.deps import get_current_user
from app.core.database import get_db

def _override_current_user(db: Session = Depends(get_db)):
    return db.query(User).filter(User.id == 1).first()

app.dependency_overrides[get_current_user] = _override_current_user

client = TestClient(app, raise_server_exceptions=False)
BASE = "/api/v1"

results = []   # (name, ok, detail)
def record(name, ok, detail=""):
    results.append((name, ok, detail))
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name}" + (f" :: {detail}" if detail else ""))

TOPIC = "夏季健康饮食注意事项"

# 1) 创建项目 (选题) ------------------------------------------------
t0 = time.time()
r = client.post(f"{BASE}/creation/projects", json={
    "source_type": "custom", "topic": TOPIC, "category": "健康养生",
})
dt = round(time.time() - t0, 2)
if r.status_code == 200:
    data = r.json()["data"]
    project_id = data["project_id"]
    fc_task_id = data["task_id"]
    record("1.创建项目/返回task_id", True,
           f"project_id={project_id} full_creation_task_id={fc_task_id} status={data['status']} ({dt}s)")
else:
    record("1.创建项目/返回task_id", False, f"status={r.status_code} {r.text[:200]}")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    raise SystemExit(1)

# 2) 轮询生成 3 个文案方案 ------------------------------------------
scripts = []
deadline = time.time() + 40
while time.time() < deadline:
    r = client.get(f"{BASE}/creation/projects/{project_id}/scripts")
    if r.status_code == 200:
        scripts = r.json()["data"]
        if len(scripts) >= 1:
            break
    time.sleep(1.5)
if len(scripts) == 3:
    types = [s.get("type") for s in scripts]
    record("2.生成3个文案方案", True, f"count=3 types={types}")
elif len(scripts) > 0:
    record("2.生成3个文案方案", False, f"只生成 {len(scripts)} 个: {[s.get('type') for s in scripts]}")
else:
    record("2.生成3个文案方案", False, "未在40s内生成任何文案")

selected_script = scripts[0] if scripts else None

# 2b) full_creation 任务完成 (仅做文案/方案编排, MVP 阶段不再生成视频)
fc_done = False
deadline = time.time() + 60
while time.time() < deadline:
    r = client.get(f"{BASE}/tasks/{fc_task_id}")
    if r.status_code == 200:
        st = r.json()["data"]["status"]
        if st in ("completed", "failed"):
            fc_done = (st == "completed")
            record("2b.full_creation编排任务", fc_done,
                   f"status={st} progress={r.json()['data']['progress']}")
            break
    time.sleep(1.5)
if not fc_done:
    record("2b.full_creation编排任务", False, "超时未完成")

# 2c) 收敛验证: orchestrator 不应再创建占位 Video (MVP 唯一生产入口 = VideoProducer)
_vdb = SessionLocal()
_vcount = _vdb.query(Video).filter(Video.project_id == project_id).count()
_vdb.close()
record("2c.收敛/orchestrator未建Video", _vcount == 0,
       f"project 下 Video 数={_vcount} (期望 0, 占位记录已移除)")

# 3) 声音列表 (选声音) ----------------------------------------------
r = client.get(f"{BASE}/voice-profiles")
if r.status_code == 200 and r.json()["data"]:
    vps = r.json()["data"]
    active = [v for v in vps if v["status"] == "active"]
    record("3.声音列表/可选active", len(active) > 0,
           f"总数={len(vps)} active={[v['id'] for v in active]}")
    voice_id = active[0]["id"] if active else None
else:
    record("3.声音列表/可选active", False, f"status={r.status_code} {r.text[:120]}")
    voice_id = None

# 4) 素材列表 (选素材) ----------------------------------------------
# 注: footage.list 存在与本次收敛无关的既有序列化 bug (topics JSON 串 vs list),
#     这里如实记录该发现, 并回退到已 seed 的 footage_id 以验证视频生产链路收敛。
r = client.get(f"{BASE}/footage/list", params={"page": 1, "size": 20})
if r.status_code == 200:
    items = r.json()["data"]["items"]
    record("4.素材列表/可选", len(items) > 0,
           f"count={len(items)} ids={[f['id'] for f in items]}")
    footage_id = items[0]["id"] if items else 1
else:
    # 既有 bug: FootageResponse.topics 期望 list, 但 DB 存的是 JSON 字符串 -> 500
    record("4.素材列表/可选", False,
           f"既有序列化 bug (footage.list) status={r.status_code}: {r.text[:160]}")
    footage_id = 1  # 回退: 使用已 seed 的素材继续验证视频链路

# 5) 生成视频 (一键生成) --------------------------------------------
if selected_script and voice_id and footage_id:
    t0 = time.time()
    r = client.post(f"{BASE}/video/generate/{project_id}", json={
        "script_id": selected_script["id"],
        "voice_profile_id": voice_id,
        "footage_id": footage_id,
        "with_lipsync": True,
    })
    dt = round(time.time() - t0, 2)
    if r.status_code == 200:
        vp_task_id = r.json()["data"]["task_id"]
        record("5.生成视频/返回task_id", True,
               f"video_production_task_id={vp_task_id} status={r.json()['data']['status']} ({dt}s)")
    else:
        record("5.生成视频/返回task_id", False, f"status={r.status_code} {r.text[:200]}")
        vp_task_id = None
else:
    record("5.生成视频/返回task_id", False, "前置步骤缺失, 无法生成")
    vp_task_id = None

# 6) 轮询任务状态 (实时进度) ----------------------------------------
task_history = []
if vp_task_id:
    deadline = time.time() + 120
    final = None
    while time.time() < deadline:
        r = client.get(f"{BASE}/tasks/{vp_task_id}")
        if r.status_code == 200:
            d = r.json()["data"]
            task_history.append((d["status"], d["progress"]))
            if d["status"] in ("completed", "failed"):
                final = d
                break
        time.sleep(2)
    if final and final["status"] == "completed":
        record("6.任务轮询/最终完成", True, f"progress={final['progress']} 历史={task_history}")
    elif final and final["status"] == "failed":
        record("6.任务轮询/最终完成", False, f"failed reason={final.get('error_message')} 历史={task_history}")
    else:
        record("6.任务轮询/最终完成", False, f"超时 历史={task_history}")
else:
    record("6.任务轮询/最终完成", False, "无 task_id")

# 6b) 收敛验证: 仅 VideoProducer 创建了 1 条真实 Video (P0 双链路问题应已消除)
if vp_task_id:
    _vdb = SessionLocal()
    vs = _vdb.query(Video).filter(Video.project_id == project_id).all()
    _vdb.close()
    real = [v for v in vs if v.url]
    _ok = (len(vs) == 1 and len(real) == 1)
    record("6b.收敛/仅1条真实Video", _ok,
           f"Video总数={len(vs)} 有url的={len(real)} status={[v.status for v in vs]}")

# 7) 作品详情 (跳转作品页) ------------------------------------------
r = client.get(f"{BASE}/creation/projects/{project_id}")
if r.status_code == 200:
    pj = r.json()["data"]
    video_url = pj.get("video_url")
    disp = pj.get("display_status")
    has_file = bool(video_url) and (storage_root / "storage" / video_url.replace("/static/", "", 1)).exists()
    record("7.作品详情/视频可访问", bool(video_url) and has_file,
           f"display_status={disp} video_url={video_url} file_exists={has_file}")
else:
    record("7.作品详情/视频可访问", False, f"status={r.status_code}")
    video_url = None

# 7b) 作品列表 display_status
r = client.get(f"{BASE}/creation/projects", params={"page": 1, "size": 20})
if r.status_code == 200:
    items = r.json()["data"]["items"]
    mine = [x for x in items if x["id"] == project_id]
    if mine:
        record("7b.作品列表状态", mine[0].get("display_status") == "video_ready",
               f"display_status={mine[0].get('display_status')} video_url_set={bool(mine[0].get('video_url'))}")
    else:
        record("7b.作品列表状态", False, "作品未出现在列表")

# 8) 文件可播放 (ffmpeg 解码) --------------------------------------
playable = False
if video_url:
    fpath = storage_root / "storage" / video_url.replace("/static/", "", 1)
    if fpath.exists():
        rc = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(fpath), "-f", "null", "-"],
            capture_output=True, text=True,
        )
        playable = (rc.returncode == 0)
        # 提取流信息
        info = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", str(fpath)],
            capture_output=True, text=True,
        ).stderr
        streams = [l.strip() for l in info.splitlines() if "Stream" in l]
        record("8.视频文件可播放", playable,
               f"decode_errors={'none' if playable else rc.stderr[:200]!r} streams={streams}")
    else:
        record("8.视频文件可播放", False, "文件不存在")
else:
    record("8.视频文件可播放", False, "无 video_url")

# ---------- 汇总 ----------
total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
print("\n==================== SUMMARY ====================")
print(f"PASS {passed}/{total}")
print(f"project_id={project_id}  selected_script_type={selected_script['type'] if selected_script else None}")
print(f"voice_id={voice_id} footage_id={footage_id} full_creation_task={fc_task_id} video_task={vp_task_id}")
print(f"video_url={video_url} playable={playable}")

# 清理临时产物 (保留脚本本身)
try:
    footage_file.unlink(missing_ok=True)
    for f in (storage_root / "storage" / "output").glob("render_*.mp4"):
        f.unlink(missing_ok=True)
    for f in (storage_root / "storage" / "output").glob("render_*_cover.jpg"):
        f.unlink(missing_ok=True)
    for f in (storage_root / "storage" / "output").glob("tts_*.mp3"):
        f.unlink(missing_ok=True)
    for f in (storage_root / "storage" / "output").glob("tts_*.aiff"):
        f.unlink(missing_ok=True)
except Exception as e:
    print("cleanup warn:", e)

# 写出结构化结果供报告使用
out = {
    "pass": passed, "total": total,
    "project_id": project_id,
    "selected_script_type": selected_script["type"] if selected_script else None,
    "voice_id": voice_id, "footage_id": footage_id,
    "full_creation_task_id": fc_task_id, "video_task_id": vp_task_id,
    "video_url": video_url, "playable": playable,
    "results": [{"name": n, "ok": ok, "detail": d} for n, ok, d in results],
}
with open("/tmp/user_flow_result.json", "w") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print("RESULT_JSON=/tmp/user_flow_result.json")
