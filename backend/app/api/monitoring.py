from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, desc
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from datetime import datetime, timedelta

from app.core.database import get_db
from app.api.deps import get_current_super_admin
from app.models import User
from app.models.ai_task import AITask
from app.models.content import WorkflowTask, ContentProject

router = APIRouter(prefix="/admin/monitoring", tags=["监控"])


@router.get("/overview")
def get_monitoring_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> Dict[str, Any]:
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)

    ai_stats = _get_ai_task_stats(db, today_start)
    workflow_stats = _get_workflow_stats(db, today_start)
    project_stats = _get_project_stats(db, today_start)

    return {
        "timestamp": now.isoformat(),
        "ai_tasks": ai_stats,
        "workflow_tasks": workflow_stats,
        "projects": project_stats,
    }


@router.get("/ai-tasks")
def get_ai_task_monitoring(
    status: str = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> Dict[str, Any]:
    query = db.query(AITask)
    if status:
        query = query.filter(AITask.status == status)
    
    total = query.count()
    tasks = query.order_by(desc(AITask.updated_at)).offset(offset).limit(limit).all()

    status_counts = dict(
        db.query(AITask.status, func.count(AITask.id))
        .group_by(AITask.status).all()
    )

    return {
        "total": total,
        "status_breakdown": status_counts,
        "tasks": [
            {
                "id": t.id,
                "workflow": t.workflow,
                "agent": t.agent,
                "model": t.model,
                "status": t.status,
                "tokens_input": t.tokens_input,
                "tokens_output": t.tokens_output,
                "cost": t.cost,
                "duration": t.duration,
                "retry_count": t.retry_count,
                "error_message": t.error_message,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in tasks
        ],
    }


@router.get("/workflow-tasks")
def get_workflow_monitoring(
    status: str = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> Dict[str, Any]:
    query = db.query(WorkflowTask)
    if status:
        query = query.filter(WorkflowTask.status == status)

    total = query.count()
    tasks = query.order_by(desc(WorkflowTask.updated_at)).offset(offset).limit(limit).all()

    status_counts = dict(
        db.query(WorkflowTask.status, func.count(WorkflowTask.id))
        .group_by(WorkflowTask.status).all()
    )

    return {
        "total": total,
        "status_breakdown": status_counts,
        "tasks": [
            {
                "id": t.id,
                "project_id": t.project_id,
                "task_type": t.task_type,
                "status": t.status,
                "progress": t.progress,
                "error_message": t.error_message,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in tasks
        ],
    }


@router.get("/failed-tasks")
def get_failed_tasks(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> Dict[str, Any]:
    failed_workflow = (
        db.query(WorkflowTask)
        .filter(WorkflowTask.status == "failed")
        .order_by(desc(WorkflowTask.updated_at))
        .limit(limit)
        .all()
    )

    failed_ai = (
        db.query(AITask)
        .filter(AITask.status == "failed")
        .order_by(desc(AITask.updated_at))
        .limit(limit)
        .all()
    )

    return {
        "failed_workflow_tasks": [
            {
                "id": t.id,
                "project_id": t.project_id,
                "task_type": t.task_type,
                "error": t.error_message,
                "failed_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in failed_workflow
        ],
        "failed_ai_tasks": [
            {
                "id": t.id,
                "agent": t.agent,
                "workflow": t.workflow,
                "error": t.error_message,
                "failed_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in failed_ai
        ],
    }


def _get_ai_task_stats(db: Session, today_start: datetime) -> Dict[str, Any]:
    total = db.query(AITask).count()
    today_count = db.query(AITask).filter(AITask.created_at >= today_start).count()
    
    status_counts = dict(
        db.query(AITask.status, func.count(AITask.id))
        .group_by(AITask.status).all()
    )

    running_count = status_counts.get("running", 0)
    failed_count = status_counts.get("failed", 0)
    completed_count = status_counts.get("completed", 0)

    total_today_with_result = completed_count + failed_count
    failure_rate = round(failed_count / total_today_with_result * 100, 2) if total_today_with_result > 0 else 0

    avg_duration = db.query(func.avg(AITask.duration)).filter(
        AITask.status == "completed",
        AITask.duration > 0,
    ).scalar() or 0

    total_cost = db.query(func.sum(AITask.cost)).scalar() or 0

    return {
        "total": total,
        "today_new": today_count,
        "status": status_counts,
        "running": running_count,
        "failure_rate_pct": failure_rate,
        "avg_duration_sec": round(avg_duration, 2),
        "total_cost": round(total_cost, 4),
    }


def _get_workflow_stats(db: Session, today_start: datetime) -> Dict[str, Any]:
    total = db.query(WorkflowTask).count()
    today_count = db.query(WorkflowTask).filter(
        WorkflowTask.created_at >= today_start
    ).count()

    status_counts = dict(
        db.query(WorkflowTask.status, func.count(WorkflowTask.id))
        .group_by(WorkflowTask.status).all()
    )

    failed = status_counts.get("failed", 0)
    completed = status_counts.get("completed", 0)
    total_with_result = failed + completed
    failure_rate = round(failed / total_with_result * 100, 2) if total_with_result > 0 else 0

    return {
        "total": total,
        "today_new": today_count,
        "status": status_counts,
        "failure_rate_pct": failure_rate,
    }


def _get_project_stats(db: Session, today_start: datetime) -> Dict[str, Any]:
    total = db.query(ContentProject).count()
    today_count = db.query(ContentProject).filter(
        ContentProject.created_at >= today_start
    ).count()

    status_counts = dict(
        db.query(ContentProject.status, func.count(ContentProject.id))
        .group_by(ContentProject.status).all()
    )

    return {
        "total": total,
        "today_new": today_count,
        "status": status_counts,
    }
