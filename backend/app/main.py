import os
from fastapi import Depends, FastAPI, Request, HTTPException, status
from typing import Optional, Tuple
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path

from app.core.config import settings
from app.api import api_router
from app.core.security import decode_token, sign_media_path, verify_media_signature
from app.api.deps import get_current_user

_DEFAULT_SECRET_KEY = "phoenix-secret-key-change-in-production"
if not settings.DEBUG and settings.SECRET_KEY == _DEFAULT_SECRET_KEY:
    raise RuntimeError(
        "生产环境必须修改 SECRET_KEY！请在 .env 或环境变量中设置强随机密钥。"
    )

if not settings.DEBUG and settings.CORS_ORIGINS.strip() == "*":
    raise RuntimeError(
        "生产环境 CORS_ORIGINS 不能为 *！请在 .env 中设置具体前端域名，"
        "如 CORS_ORIGINS=https://phoenix.example.com"
    )

if not settings.DEBUG and settings.DATABASE_URL.startswith("sqlite"):
    import warnings
    _warn_lines = [
        "=" * 70,
        "WARNING: 生产环境仍在使用 SQLite！",
        "SQLite 不支持高并发写入，用户量上来后会出现 database is locked 错误。",
        "请切换到 MySQL 或 PostgreSQL，修改 DATABASE_URL 配置。",
        "=" * 70,
    ]
    warnings.warn("\\n".join(_warn_lines), stacklevel=2)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI短视频操作系统 - Project Phoenix",
)

_cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

STORAGE_DIR = Path("storage").resolve()


def _extract_token(request: Request) -> Optional[str]:
    """从请求中提取 token：优先 query token，其次 Authorization Bearer"""
    token = request.query_params.get("token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    return token if token else None


def _get_user_from_token(token: str) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """
    解析 token 并返回 (user_id, tenant_id, role)
    失败返回 (None, None, None)
    """
    payload = decode_token(token)
    if not payload:
        return None, None, None
    sub = payload.get("sub")
    if not sub:
        return None, None, None
    # 兼容 tenant:{id} 格式
    if isinstance(sub, str) and sub.startswith("tenant:"):
        return None, None, None
    user_id = int(sub)
    tenant_id = payload.get("tenant_id")
    role = payload.get("role")
    if tenant_id is not None:
        tenant_id = int(tenant_id)
    return user_id, tenant_id, role


def _check_resource_ownership(
    file_path: str, user_id: int, tenant_id: Optional[int], role: Optional[str]
) -> bool:
    """
    校验资源归属：用户只能访问自己的或同租户的资源
    super_admin 可访问所有

    目录规则:
    - footage/{user_id}/...       → user_id 匹配
    - voice_demos/{user_id}/...   → user_id 匹配
    - voice_samples/{user_id}/... → user_id 匹配
    - output/render_{project_id}_... → 需查 DB (由调用方处理，这里放行到 output 层)
    - test_output/...             → 仅 DEBUG 模式允许
    """
    # super_admin 全部放行
    if role == "super_admin":
        return True

    parts = file_path.split("/", 2)
    if len(parts) < 2:
        return False

    category = parts[0]

    if category == "test_output":
        from app.core.config import settings
        return settings.DEBUG

    if category in ("footage", "voice_demos", "voice_samples",
                    "anchor_portraits", "anchor_scenes"):
        # 第二段是 user_id
        owner_id_str = parts[1]
        try:
            owner_id = int(owner_id_str)
        except (ValueError, TypeError):
            return False
        # 本人或同租户
        if owner_id == user_id:
            return True
        if tenant_id:
            # 同租户校验需要查 DB，这里先放行到 DB 层检查
            # 对于简单目录级校验，先只校验本人，同租户由 output 等复杂路径处理
            return False
        return False

    if category == "output":
        # output 目录文件名包含 project_id，需要 DB 查询归属
        # 这里先放行，在路由层做 DB 校验
        return True

    # 未知目录，拒绝访问（防止新增目录被绕过）
    return False


def _check_output_ownership(
    filename: str, user_id: int, tenant_id: Optional[int], role: Optional[str], db
) -> bool:
    """
    校验 output 目录下文件的归属（基于 project_id）
    文件名格式: render_{project_id}_{timestamp}.mp4
    """
    if role == "super_admin":
        return True

    # 从文件名提取 project_id。
    # 兼容两种成片命名：旧渲染 render_<pid>_*.mp4；
    # H3 图生视频 h3_p<pid>_<ts>.mp4（video_producer._run_h3 产出）。
    import re as _re
    m = _re.match(r"render_(\d+)_", filename) or _re.match(r"h3_p(\d+)_", filename)
    if not m:
        # 兜底：直接按 Video.url 反查归属，避免命名约定变化再次 403
        from app.models.content import Video as _V, ContentProject as _CP
        v = db.query(_V).filter(_V.url == f"/static/output/{filename}").first()
        if not v:
            return False
        proj = db.query(_CP).filter(_CP.id == v.project_id).first()
        if not proj:
            return False
        if proj.user_id == user_id:
            return True
        return bool(tenant_id and proj.tenant_id == tenant_id)
    project_id = int(m.group(1))

    from app.models.content import ContentProject, Video
    video = db.query(Video).filter(
        Video.project_id == project_id
    ).first()
    if not video:
        return False
    project = db.query(ContentProject).filter(
        ContentProject.id == project_id
    ).first()
    if not project:
        return False

    if project.user_id == user_id:
        return True
    if tenant_id and project.tenant_id == tenant_id:
        return True
    return False


@app.get("/static/{file_path:path}", include_in_schema=False)
async def serve_static(file_path: str, request: Request):
    # 1. 优先用短时签名 URL（media/sign 下发，签名里绑定 path+过期时间）
    expires = request.query_params.get("expires")
    sig = request.query_params.get("sig")
    signed_ok = bool(expires and sig) and verify_media_signature(file_path, expires, sig)
    if not signed_ok:
        # 兼容旧链接：仍允许 Bearer / query token 访问
        token = _extract_token(request)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
            )
        user_id, tenant_id, role = _get_user_from_token(token)
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    else:
        # 签名由鉴权后的 media/sign 接口签发，这里不再重复校验归属
        user_id, tenant_id, role = None, None, None

    # 2. 路径穿越防护
    # 用 Path 关系判断而不是字符串前缀拼 "/"：后者在 Windows 上恒为 False
    # （分隔符是 \），导致本地跑测试时所有静态资源都被误判成路径穿越。
    # is_relative_to 同时避免 /storage 与 /storage_evil 这类前缀误匹配。
    full_path = (STORAGE_DIR / file_path).resolve()
    try:
        inside = full_path.is_relative_to(STORAGE_DIR)
    except AttributeError:      # Python < 3.9
        inside = str(full_path).startswith(str(STORAGE_DIR) + os.sep)
    if not inside or full_path == STORAGE_DIR:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not full_path.is_file():
        raise HTTPException(status_code=404, detail="Not found")

    # 3. 目录级归属校验（签名 URL 已由签发接口校验过归属）
    if not signed_ok:
        if not _check_resource_ownership(file_path, user_id, tenant_id, role):
            raise HTTPException(status_code=403, detail="Forbidden")

    # 4. output 目录需要 DB 级 project 归属校验
    parts = file_path.split("/", 1)
    if parts[0] == "output" and not signed_ok:
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            filename = parts[1] if len(parts) > 1 else ""
            if not _check_output_ownership(
                filename, user_id, tenant_id, role, db
            ):
                raise HTTPException(status_code=403, detail="Forbidden")
        finally:
            db.close()

    return FileResponse(
        full_path,
        headers={"Cache-Control": "private, max-age=3600"} if signed_ok else None,
    )


@app.get("/api/v1/media/sign", include_in_schema=False)
def sign_media(
    path: str,
    current_user = Depends(get_current_user),
):
    """为当前用户可访问的 storage 文件签发短时签名 URL。"""
    if not path:
        raise HTTPException(status_code=400, detail="path 不能为空")

    full_path = (STORAGE_DIR / path).resolve()
    try:
        inside = full_path.is_relative_to(STORAGE_DIR)
    except AttributeError:
        inside = str(full_path).startswith(str(STORAGE_DIR) + os.sep)
    if not inside or full_path == STORAGE_DIR:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not full_path.is_file():
        raise HTTPException(status_code=404, detail="Not found")

    user_id = current_user.id
    tenant_id = getattr(current_user, "tenant_id", None)
    role = getattr(current_user, "role", None)

    if not _check_resource_ownership(path, user_id, tenant_id, role):
        raise HTTPException(status_code=403, detail="Forbidden")

    parts = path.split("/", 1)
    if parts[0] == "output":
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            filename = parts[1] if len(parts) > 1 else ""
            if not _check_output_ownership(
                filename, user_id, tenant_id, role, db
            ):
                raise HTTPException(status_code=403, detail="Forbidden")
        finally:
            db.close()

    return {"url": sign_media_path(path)}


@app.on_event("startup")
def cleanup_stuck_tasks():
    from app.core.database import SessionLocal
    from app.models.content import WorkflowTask, ContentProject
    from app.models.ai_task import AITask
    from app.models.notification import UserNotification

    db = SessionLocal()
    try:
        # 注意：任务用 daemon 线程执行，进程退出即消失，没有任何恢复机制，
        # 所以启动时必须把残留的 waiting/running 标记掉，否则前端会一直转圈。
        # ⚠️ 本钩子在每个 uvicorn worker 启动时都会执行（线上 --workers 2）。
        # 这不会误杀正常任务（只在启动瞬间跑一次），但意味着部署必然打断在跑
        # 的任务 —— 故 update.sh 在重启前会先检查是否有任务在执行。
        stuck_workflow = db.query(WorkflowTask).filter(
            WorkflowTask.status.in_(["waiting", "running"])
        ).all()
        if stuck_workflow:
            project_ids = [t.project_id for t in stuck_workflow]
            for task in stuck_workflow:
                # 记下中断时的阶段：排查「任务为什么没出片」时，
                # 知道它死在配音还是口型阶段能省掉大量翻日志的时间。
                stage = f"（中断于 {task.status}，进度 {task.progress or 0}%）"
                task.status = "failed"
                task.error_message = f"服务重启导致任务中断{stage}，请重新创建"
                print(f"[startup] 中断任务 id={task.id} project={task.project_id} "
                      f"progress={task.progress or 0}%")
                project = db.query(ContentProject).filter(
                    ContentProject.id == task.project_id
                ).first()
                if project and project.user_id:
                    db.add(UserNotification(
                        user_id=project.user_id,
                        type="task",
                        title="任务因服务重启中断",
                        content=f"任务 {task.id} 因服务重启中断（进度 {task.progress or 0}%），请重新生成。",
                        link=f"/result?project_id={task.project_id}",
                    ))
            if project_ids:
                db.query(ContentProject).filter(
                    ContentProject.id.in_(project_ids),
                    ContentProject.status == "processing",
                ).update(
                    {"status": "failed", "workflow_status": "interrupted"},
                    synchronize_session=False,
                )
            db.commit()

        stuck_ai = db.query(AITask).filter(
            AITask.status.in_(["pending", "running"])
        ).all()
        if stuck_ai:
            for task in stuck_ai:
                task.status = "failed"
                task.error_message = "服务重启导致任务中断"
            db.commit()
    finally:
        db.close()


@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }


@app.get("/health")
def health_check():
    import time
    from pathlib import Path
    from sqlalchemy import text

    checks = {}
    overall_status = "healthy"

    db_ok = False
    db_error = None
    db_start = time.time()
    try:
        from app.core.database import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        db_error = str(e)
        overall_status = "degraded"
    checks["database"] = {
        "status": "ok" if db_ok else "fail",
        "response_time_ms": round((time.time() - db_start) * 1000, 2),
        "error": db_error,
    }

    storage_ok = False
    storage_error = None
    storage_path = str(Path(settings.STORAGE_PATH).resolve())
    try:
        test_file = Path(settings.STORAGE_PATH) / ".health_write_test"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("ok")
        test_file.unlink()
        storage_ok = True
    except Exception as e:
        storage_error = str(e)
        overall_status = "degraded"
    checks["storage"] = {
        "status": "ok" if storage_ok else "fail",
        "path": storage_path,
        "error": storage_error,
    }

    return {
        "status": overall_status,
        "version": settings.APP_VERSION,
        "timestamp": time.time(),
        "checks": checks,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
