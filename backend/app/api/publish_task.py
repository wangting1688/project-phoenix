from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, PublishTask, PlatformAccount
from app.schemas import (
    ApiResponse,
    PublishTaskCreate,
    PublishTaskUpdate,
    PublishTaskResponse,
    PublishTaskListResponse,
    PublishTaskMetrics,
)
from app.services.publish_auto_collector import PublishAutoCollector
from app.services.publish_auto_review import PublishAutoReview

router = APIRouter(prefix="/publish-tasks", tags=["发布任务"])


@router.post("", response_model=ApiResponse[PublishTaskResponse])
def create_task(
    data: PublishTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建发布任务"""
    # 校验平台账号归属
    account = db.query(PlatformAccount).filter(
        PlatformAccount.id == data.platform_account_id,
        PlatformAccount.user_id == current_user.id,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="平台账号不存在或无权限")

    task = PublishTask(
        user_id=current_user.id,
        video_project_id=data.video_project_id,
        content_title=data.content_title,
        content_description=data.content_description,
        platform_account_id=data.platform_account_id,
        platform=data.platform,
        scheduled_at=data.scheduled_at,
        tags=data.tags,
        category=data.category,
        video_url=data.video_url,
        cover_url=data.cover_url,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return ApiResponse(data=PublishTaskResponse.model_validate(task))


@router.get("", response_model=ApiResponse[PublishTaskListResponse])
def list_tasks(
    status: str = None,
    platform: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取发布任务列表"""
    query = db.query(PublishTask).filter(PublishTask.user_id == current_user.id)
    if status:
        query = query.filter(PublishTask.status == status)
    if platform:
        query = query.filter(PublishTask.platform == platform)
    tasks = query.order_by(PublishTask.created_at.desc()).all()
    return ApiResponse(
        data=PublishTaskListResponse(
            items=[PublishTaskResponse.model_validate(t) for t in tasks],
            total=len(tasks),
        )
    )


@router.get("/{task_id}", response_model=ApiResponse[PublishTaskResponse])
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取发布任务详情"""
    task = db.query(PublishTask).filter(
        PublishTask.id == task_id,
        PublishTask.user_id == current_user.id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ApiResponse(data=PublishTaskResponse.model_validate(task))


@router.put("/{task_id}", response_model=ApiResponse[PublishTaskResponse])
def update_task(
    task_id: int,
    data: PublishTaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新发布任务"""
    task = db.query(PublishTask).filter(
        PublishTask.id == task_id,
        PublishTask.user_id == current_user.id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    return ApiResponse(data=PublishTaskResponse.model_validate(task))


@router.delete("/{task_id}", response_model=ApiResponse[dict])
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除发布任务"""
    task = db.query(PublishTask).filter(
        PublishTask.id == task_id,
        PublishTask.user_id == current_user.id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    db.delete(task)
    db.commit()
    return ApiResponse(data={"deleted": True})


@router.post("/{task_id}/publish", response_model=ApiResponse[PublishTaskResponse])
def trigger_publish(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """触发发布（模拟）"""
    task = db.query(PublishTask).filter(
        PublishTask.id == task_id,
        PublishTask.user_id == current_user.id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status not in ["draft", "pending", "failed"]:
        raise HTTPException(status_code=400, detail="当前状态不可发布")

    task.status = "published"
    task.published_at = datetime.utcnow()
    task.platform_post_id = f"mock_{task.platform}_{task.id}"
    task.platform_post_url = f"https://{task.platform}.com/p/{task.platform_post_id}"

    db.commit()
    db.refresh(task)
    return ApiResponse(data=PublishTaskResponse.model_validate(task))


@router.post("/{task_id}/collect-metrics", response_model=ApiResponse[PublishTaskResponse])
def collect_metrics(
    task_id: int,
    metrics: PublishTaskMetrics,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动录入或更新回流数据"""
    task = db.query(PublishTask).filter(
        PublishTask.id == task_id,
        PublishTask.user_id == current_user.id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    task.play_count = metrics.play_count
    task.like_count = metrics.like_count
    task.comment_count = metrics.comment_count
    task.share_count = metrics.share_count
    task.collect_count = metrics.collect_count
    task.follower_gained = metrics.follower_gained
    task.completion_rate = metrics.completion_rate
    task.ctr = metrics.ctr
    task.metrics_collected_at = datetime.utcnow()
    task.status = "collecting"

    db.commit()
    db.refresh(task)
    return ApiResponse(data=PublishTaskResponse.model_validate(task))


@router.post("/{task_id}/auto-collect", response_model=ApiResponse[dict])
def auto_collect(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """自动采集平台数据（模拟）"""
    task = db.query(PublishTask).filter(
        PublishTask.id == task_id,
        PublishTask.user_id == current_user.id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    collector = PublishAutoCollector(db)
    result = collector.collect_metrics(task_id)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "采集失败"))

    return ApiResponse(data=result)


@router.post("/{task_id}/auto-review", response_model=ApiResponse[dict])
def auto_review(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """自动复盘：分析数据并写入 Growth Graph"""
    task = db.query(PublishTask).filter(
        PublishTask.id == task_id,
        PublishTask.user_id == current_user.id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    reviewer = PublishAutoReview(db)
    result = reviewer.review_task(task_id)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "复盘失败"))

    return ApiResponse(data=result)


@router.post("/{task_id}/full-pipeline", response_model=ApiResponse[dict])
def full_pipeline(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """完整闭环：采集数据 → 自动复盘 → 更新 Growth Graph"""
    task = db.query(PublishTask).filter(
        PublishTask.id == task_id,
        PublishTask.user_id == current_user.id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # Step 1: 自动采集
    collector = PublishAutoCollector(db)
    collect_result = collector.collect_metrics(task_id)
    if not collect_result.get("success"):
        raise HTTPException(status_code=400, detail=collect_result.get("error", "采集失败"))

    # Step 2: 自动复盘
    reviewer = PublishAutoReview(db)
    review_result = reviewer.review_task(task_id)
    if not review_result.get("success"):
        raise HTTPException(status_code=400, detail=review_result.get("error", "复盘失败"))

    return ApiResponse(data={
        "task_id": task_id,
        "collect": collect_result,
        "review": review_result,
        "message": "完整闭环执行成功：采集 → 复盘 → Growth Graph 已更新",
    })
