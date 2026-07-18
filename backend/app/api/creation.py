from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
import threading

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, ContentProject, WorkflowTask
from app.workflow.orchestrator import WorkflowOrchestrator
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


@router.post("/projects", response_model=ApiResponse[dict])
def create_project(
    project_in: ContentProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = ContentProject(
        user_id=current_user.id,
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
            orchestrator = WorkflowOrchestrator(project.id, project_in.topic)
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


@router.get("/projects", response_model=ApiResponse[dict])
def list_projects(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(ContentProject).filter(ContentProject.user_id == current_user.id)
    total = query.count()
    projects = (
        query.order_by(ContentProject.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return ApiResponse(
        data={
            "items": [ContentProjectResponse.model_validate(p) for p in projects],
            "total": total,
            "page": page,
            "size": size,
        }
    )


@router.get("/projects/{project_id}", response_model=ApiResponse[ContentProjectResponse])
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = (
        db.query(ContentProject)
        .filter(
            ContentProject.id == project_id,
            ContentProject.user_id == current_user.id,
        )
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return ApiResponse(data=ContentProjectResponse.model_validate(project))


@router.get("/projects/{project_id}/scripts", response_model=ApiResponse[List[ScriptResponse]])
def get_project_scripts(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models import Script

    project = (
        db.query(ContentProject)
        .filter(
            ContentProject.id == project_id,
            ContentProject.user_id == current_user.id,
        )
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    scripts = db.query(Script).filter(Script.project_id == project_id).all()
    return ApiResponse(data=[ScriptResponse.model_validate(s) for s in scripts])
