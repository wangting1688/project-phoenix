from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, WorkflowTask
from app.schemas import TaskStatusResponse, TaskResultResponse, ApiResponse, ScriptResponse, VideoResponse
from app.api.creation import _select_best_video

router = APIRouter(prefix="/tasks", tags=["任务"])

# 单条任务的经验耗时（秒）。GPU worker 串行执行，前面每多一个任务就多等这么久。
# 数据来自实测：带口型的整条链路约 8 分钟，纯文案/配音的约 1 分钟。
EST_SECONDS_WITH_LIPSYNC = 480
EST_SECONDS_PLAIN = 60


def _queue_info(db, task):
    """算出任务的排队位置与预计等待。

    口型推理在 GPU worker 侧串行（max_workers=1），并发提交只能排队。
    前端拿不到排队信息时，用户看到的是长时间不动的进度条，会以为卡死。

    位置按 id 升序（先提交先执行）：0 表示轮到自己了，>0 表示前面还有几个。
    """
    import json

    if task.status in ("completed", "failed"):
        return None, None, None

    pending = (
        db.query(WorkflowTask)
        .filter(WorkflowTask.status.in_(["waiting", "running"]))
        .order_by(WorkflowTask.id.asc())
        .all()
    )
    ids = [t.id for t in pending]
    if task.id not in ids:
        return None, len(ids), None
    position = ids.index(task.id)

    def _est(t):
        # result 里存着提交参数，据此判断是否走口型（耗时差近 8 倍）
        try:
            params = json.loads(t.result or "{}")
        except (ValueError, TypeError):
            params = {}
        base = (EST_SECONDS_WITH_LIPSYNC if params.get("with_lipsync")
                else EST_SECONDS_PLAIN)
        # 正在执行的任务按剩余进度折算。这对队列中每一条都要生效：
        # 只折算自己会把前面那条已跑到 60% 的任务仍按全额计算，
        # 导致排在后面的人看到的等待时间被明显高估。
        if t.status == "running":
            remain = max(0, 100 - (t.progress or 0)) / 100.0
            return int(base * remain)
        return base

    eta = sum(_est(t) for t in pending[:position + 1])
    return position, len(ids), eta


@router.get("/{task_id}", response_model=ApiResponse[TaskStatusResponse])
def get_task_status(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models import ContentProject

    task = db.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    project = db.query(ContentProject).filter(ContentProject.id == task.project_id).first()
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问")

    position, total, eta = _queue_info(db, task)
    return ApiResponse(
        data=TaskStatusResponse(
            task_id=task.id,
            status=task.status,
            progress=task.progress,
            current_step=project.workflow_status or task.task_type,
            error_message=task.error_message if task.status == "failed" else None,
            queue_position=position,
            queue_total=total,
            eta_seconds=eta,
        )
    )


@router.get("/{task_id}/result", response_model=ApiResponse[TaskResultResponse])
def get_task_result(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models import ContentProject, Script, Video

    task = db.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    project = db.query(ContentProject).filter(ContentProject.id == task.project_id).first()
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问")

    scripts = db.query(Script).filter(Script.project_id == project.id).all()
    videos = db.query(Video).filter(Video.project_id == project.id).all()
    best_video = _select_best_video(videos)

    return ApiResponse(
        data=TaskResultResponse(
            project_id=project.id,
            scripts=[ScriptResponse.model_validate(s) for s in scripts],
            video=VideoResponse.model_validate(best_video) if best_video else None,
        )
    )


@router.get("/{task_id}/scripts", response_model=ApiResponse[List[ScriptResponse]])
def get_task_scripts(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models import ContentProject, Script

    task = db.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    project = db.query(ContentProject).filter(ContentProject.id == task.project_id).first()
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问")

    scripts = db.query(Script).filter(Script.project_id == project.id).all()
    return ApiResponse(data=[ScriptResponse.model_validate(s) for s in scripts])
