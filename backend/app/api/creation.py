from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import threading

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, ContentProject, WorkflowTask, Video
from app.workflow.orchestrator import WorkflowOrchestrator
from app.services import tenant_service
from app.schemas import (
    ContentProjectCreate,
    ContentProjectResponse,
    TaskStatusResponse,
    TaskResultResponse,
    ScriptResponse,
    VideoResponse,
    ApiResponse,
)

router = APIRouter(prefix="/creation", tags=["创作中心"])


def _select_best_video(videos: list) -> Optional[Video]:
    """从项目的多个 Video 中选最优展示视频。

    MVP 收敛后, 视频统一由 VideoProducer 生成 (通常仅 1 条)。
    但需兼容历史可能存在的 VideoGenerationWorkflow 占位记录 (url=None),
    避免占位空壳覆盖真实成片。

    优先级:
      1. status in (rendered, completed) 且 url 存在 (可播放)
      2. 任一带 url 的
      3. created_at 最新的一条
    """
    if not videos:
        return None
    playable = [v for v in videos if v.status in ("rendered", "completed") and v.url]
    if playable:
        return max(playable, key=lambda v: v.created_at or 0)
    with_url = [v for v in videos if v.url]
    if with_url:
        return max(with_url, key=lambda v: v.created_at or 0)
    return max(videos, key=lambda v: v.created_at or 0)


@router.post("/projects", response_model=ApiResponse[dict])
def create_project(
    project_in: ContentProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        tenant_service.ensure_project_quota(db, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    project = ContentProject(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        source_type=project_in.source_type,
        topic=project_in.topic,
        category=project_in.category,
        status="processing",
        workflow_status="starting",
    )
    db.add(project)
    db.flush()

    task = WorkflowTask(
        project_id=project.id,
        tenant_id=current_user.tenant_id,
        task_type="full_creation",
        status="waiting",
        progress=0,
    )
    db.add(task)
    db.commit()
    db.refresh(project)
    db.refresh(task)

    def run_workflow_background():
        try:
            orchestrator = WorkflowOrchestrator(
                project.id,
                project_in.topic,
                platform=project_in.platform,
                persona=project_in.persona,
            )
            orchestrator.execute()
        except Exception as e:
            print(f"Workflow error: {e}")

    threading.Thread(target=run_workflow_background, daemon=True).start()

    return ApiResponse(
        data={
            "project_id": project.id,
            "task_id": task.id,
            "status": "processing",
        }
    )


def _compute_display_status(project: ContentProject, video: Optional[Video], task: Optional[WorkflowTask]) -> str:
    """
    计算用户可感知的统一展示状态：
    - draft: 草稿
    - processing: 生成中（AI创作流程进行中）
    - plan_ready: 方案已完成（AI文案/方案就绪，等待渲染视频）
    - rendering: 视频渲染中
    - video_ready: 视频已完成（可播放/下载）
    - failed: 失败
    """
    if project.status == "failed":
        return "failed"
    if project.status == "draft":
        return "draft"
    if project.status == "processing":
        return "processing"

    # 历史遗留状态归一：语义都是「文案/方案就绪、还没出片」，等价于 plan_ready。
    #   - "ready"：早期 creation_studio 链路（/creation-studio）写进去的，线上存量 7 条
    #   - "ai_plan_ready" / "planned"：更早的 Video.status 写法
    # 不归一的话，这些值会从最下面那句兜底 `return project.status` 漏给前端：
    # 前端 map 里没有这些键，卡片会原样显示英文 "ready"，且不匹配任何按钮分支
    # —— 用户看到的就是一个「只剩删除按钮」的作品卡。
    if project.status in ("ready", "ai_plan_ready", "planned"):
        if video and video.status in ("rendered", "completed") and video.url:
            return "video_ready"
        return "plan_ready"

    # completed 状态下细分
    if project.status == "completed":
        if video and video.status in ("rendered", "completed") and video.url:
            return "video_ready"
        # 视频还没渲染，或只是方案就绪
        return "plan_ready"
    # 其他未知状态兜底：有可播放视频就按成片展示，否则按「方案就绪」处理，
    # 不要把原始枚举直接透给前端（前端不认识，会退化成英文文案 + 无操作按钮）。
    if video and video.status in ("rendered", "completed") and video.url:
        return "video_ready"
    return "plan_ready"


@router.get("/projects", response_model=ApiResponse[dict])
def list_projects(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(ContentProject).filter(
        ContentProject.user_id == current_user.id,
        ContentProject.deleted_at.is_(None),
    )
    if current_user.tenant_id:
        query = query.filter(ContentProject.tenant_id == current_user.tenant_id)
    total = query.count()
    projects = (
        query.order_by(ContentProject.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    project_ids = [p.id for p in projects]
    videos = {}
    tasks = {}
    if project_ids:
        by_project: dict = {}
        for v in db.query(Video).filter(Video.project_id.in_(project_ids)).all():
            by_project.setdefault(v.project_id, []).append(v)
        for pid, vs in by_project.items():
            videos[pid] = _select_best_video(vs)
        for t in db.query(WorkflowTask).filter(
            WorkflowTask.project_id.in_(project_ids),
            WorkflowTask.task_type == "full_creation",
        ).all():
            tasks[t.project_id] = t
    return ApiResponse(
        data={
            "items": [
                {
                    **ContentProjectResponse.model_validate(p).model_dump(),
                    "video_url": v.url if (v := videos.get(p.id)) else None,
                    "video_duration": v.duration if (v := videos.get(p.id)) else None,
                    "video_status": v.status if (v := videos.get(p.id)) else None,
                    "cover_url": v.cover_url if (v := videos.get(p.id)) else None,
                    "display_status": _compute_display_status(
                        p, videos.get(p.id), tasks.get(p.id)
                    ),
                    "task_id": t.id if (t := tasks.get(p.id)) else None,
                    "error_message": t.error_message if (t := tasks.get(p.id)) else None,
                }
                for p in projects
            ],
            "total": total,
            "page": page,
            "size": size,
        }
    )


@router.delete("/projects/{project_id}", response_model=ApiResponse[dict])
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """软删除作品：设置 deleted_at 时间戳，不从数据库物理删除"""
    from datetime import datetime
    query = db.query(ContentProject).filter(
        ContentProject.id == project_id,
        ContentProject.user_id == current_user.id,
        ContentProject.deleted_at.is_(None),
    )
    if current_user.tenant_id:
        query = query.filter(ContentProject.tenant_id == current_user.tenant_id)
    project = query.first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    project.deleted_at = datetime.utcnow()
    db.commit()
    return ApiResponse(data={"success": True, "id": project_id})


@router.get("/projects/{project_id}", response_model=ApiResponse[ContentProjectResponse])
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(ContentProject).filter(
        ContentProject.id == project_id,
        ContentProject.user_id == current_user.id,
        ContentProject.deleted_at.is_(None),
    )
    if current_user.tenant_id:
        query = query.filter(ContentProject.tenant_id == current_user.tenant_id)
    project = query.first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    # 补全视频相关字段 (优先可播放视频, 避免历史占位记录覆盖真实成片)
    videos = db.query(Video).filter(Video.project_id == project_id).all()
    video = _select_best_video(videos)
    task = db.query(WorkflowTask).filter(
        WorkflowTask.project_id == project_id,
        WorkflowTask.task_type == "full_creation",
    ).first()
    data = ContentProjectResponse.model_validate(project).model_dump()
    if video:
        data["video_url"] = video.url
        data["video_duration"] = video.duration
        data["video_status"] = video.status
        data["cover_url"] = video.cover_url
    data["display_status"] = _compute_display_status(project, video, task)
    # 透出任务 id：结果页据此接入轮询（从作品页「查看进度」进来时没带 task_id）
    data["task_id"] = task.id if task else None
    if task:
        data["error_message"] = task.error_message
    return ApiResponse(data=data)


@router.get("/projects/{project_id}/scripts", response_model=ApiResponse[List[ScriptResponse]])
def get_project_scripts(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models import Script

    query = db.query(ContentProject).filter(
        ContentProject.id == project_id,
        ContentProject.user_id == current_user.id,
    )
    if current_user.tenant_id:
        query = query.filter(ContentProject.tenant_id == current_user.tenant_id)
    project = query.first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    scripts = db.query(Script).filter(Script.project_id == project_id).all()
    return ApiResponse(data=[ScriptResponse.model_validate(s) for s in scripts])


@router.patch("/scripts/{script_id}", response_model=ApiResponse[ScriptResponse])
def update_script_content(
    script_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新文案内容 (供前端编辑 AI 文案后保存)"""
    from app.models import Script, ContentProject

    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail="文案不存在")
    # 校验归属: 通过 project.user_id + tenant_id 双重确认
    query = db.query(ContentProject).filter(
        ContentProject.id == script.project_id,
        ContentProject.user_id == current_user.id,
    )
    if current_user.tenant_id:
        query = query.filter(ContentProject.tenant_id == current_user.tenant_id)
    project = query.first()
    if not project:
        raise HTTPException(status_code=403, detail="无权限")

    new_content = payload.get("content")
    if not isinstance(new_content, str) or not new_content.strip():
        raise HTTPException(status_code=400, detail="content 不能为空")

    script.content = new_content
    db.commit()
    db.refresh(script)
    return ApiResponse(data=ScriptResponse.model_validate(script))


@router.post("/scripts/{script_id}/mark-hot", response_model=ApiResponse[ScriptResponse])
def mark_script_hot(
    script_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """把一条文案标记为爆款，后续生成会参考它的风格/结构。"""
    from app.models import Script, ContentProject

    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail="文案不存在")
    query = db.query(ContentProject).filter(
        ContentProject.id == script.project_id,
        ContentProject.user_id == current_user.id,
    )
    if current_user.tenant_id:
        query = query.filter(ContentProject.tenant_id == current_user.tenant_id)
    if not query.first():
        raise HTTPException(status_code=403, detail="无权限")

    md = dict(script.meta or {})
    md["is_hot"] = True
    script.meta = md
    db.commit()
    db.refresh(script)
    return ApiResponse(data=ScriptResponse.model_validate(script))


@router.post("/projects/{project_id}/scripts/{script_id}/re-review", response_model=ApiResponse[dict])
def re_review_script(
    project_id: int,
    script_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用户修改文案后重新提交合规审核；通过则恢复任务为已完成，允许继续生成视频。"""
    from app.models import Script, ContentProject, Review, WorkflowTask
    from app.experts.ai_expert import AIExpertService

    script = db.query(Script).filter(Script.id == script_id).first()
    if not script or script.project_id != project_id:
        raise HTTPException(status_code=404, detail="文案不存在")
    query = db.query(ContentProject).filter(
        ContentProject.id == project_id,
        ContentProject.user_id == current_user.id,
        ContentProject.deleted_at.is_(None),
    )
    if current_user.tenant_id:
        query = query.filter(ContentProject.tenant_id == current_user.tenant_id)
    project = query.first()
    if not project:
        raise HTTPException(status_code=403, detail="无权限")

    new_content = payload.get("content")
    if isinstance(new_content, str) and new_content.strip():
        script.content = new_content.strip()

    ai_result = AIExpertService().compliance_expert(script.content)
    problems = ai_result.get("problems") or []

    review = db.query(Review).filter(Review.project_id == project_id).first()
    if review:
        review.risk_score = ai_result.get("risk_score")
        review.result = "pass" if ai_result.get("pass") else "fail"
    else:
        review = Review(
            project_id=project_id,
            original_score=script.score,
            risk_score=ai_result.get("risk_score"),
            result="pass" if ai_result.get("pass") else "fail",
        )
        db.add(review)
    db.commit()

    if not ai_result.get("pass"):
        msg = "合规审核未通过: " + "; ".join(str(x) for x in problems) if problems \
            else "合规审核未通过"
        raise HTTPException(status_code=400, detail=msg)

    task = db.query(WorkflowTask).filter(
        WorkflowTask.project_id == project_id,
        WorkflowTask.task_type == "full_creation",
    ).first()
    if task:
        task.status = "completed"
        task.progress = 100
        task.error_message = None
    project.status = "completed"
    project.workflow_status = "completed"
    db.commit()

    return ApiResponse(data={"pass": True, "problems": []})
