from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, WorkflowTask
from app.schemas import TaskStatusResponse, TaskResultResponse, ApiResponse, ScriptResponse, VideoResponse

router = APIRouter(prefix="/tasks", tags=["任务"])


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

    return ApiResponse(
        data=TaskStatusResponse(
            task_id=task.id,
            status=task.status,
            progress=task.progress,
            current_step=project.workflow_status or task.task_type,
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

    return ApiResponse(
        data=TaskResultResponse(
            project_id=project.id,
            scripts=[ScriptResponse.model_validate(s) for s in scripts],
            video=VideoResponse.model_validate(videos[0]) if videos else None,
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
