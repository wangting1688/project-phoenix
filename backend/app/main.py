from fastapi import FastAPI, Request, HTTPException, status
from typing import Optional, Tuple
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path

from app.core.config import settings
from app.api import api_router
from app.core.security import decode_token

_DEFAULT_SECRET_KEY = "phoenix-secret-key-change-in-production"
if not settings.DEBUG and settings.SECRET_KEY == _DEFAULT_SECRET_KEY:
    raise RuntimeError(
        "生产环境必须修改 SECRET_KEY！请在 .env 或环境变量中设置强随机密钥。"
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

    if category in ("footage", "voice_demos", "voice_samples"):
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

    # 从文件名提取 project_id
    import re as _re
    m = _re.match(r"render_(\d+)_", filename)
    if not m:
        return False
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
    # 1. 提取并校验 token
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

    # 2. 路径穿越防护
    full_path = (STORAGE_DIR / file_path).resolve()
    if not str(full_path).startswith(str(STORAGE_DIR) + "/"):
        raise HTTPException(status_code=403, detail="Forbidden")
    if not full_path.is_file():
        raise HTTPException(status_code=404, detail="Not found")

    # 3. 目录级归属校验
    if not _check_resource_ownership(file_path, user_id, tenant_id, role):
        raise HTTPException(status_code=403, detail="Forbidden")

    # 4. output 目录需要 DB 级 project 归属校验
    parts = file_path.split("/", 1)
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

    return FileResponse(full_path)


@app.on_event("startup")
def cleanup_stuck_tasks():
    from app.core.database import SessionLocal
    from app.models.content import WorkflowTask, ContentProject

    db = SessionLocal()
    try:
        stuck_tasks = db.query(WorkflowTask).filter(
            WorkflowTask.status.in_(["waiting", "running"])
        ).all()
        if stuck_tasks:
            project_ids = [t.project_id for t in stuck_tasks]
            for task in stuck_tasks:
                task.status = "failed"
                task.error_message = "服务重启导致任务中断，请重新创建"
            if project_ids:
                db.query(ContentProject).filter(
                    ContentProject.id.in_(project_ids),
                    ContentProject.status == "processing",
                ).update(
                    {"status": "failed", "workflow_status": "interrupted"},
                    synchronize_session=False,
                )
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
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
