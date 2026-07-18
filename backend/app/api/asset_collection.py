"""
素材采集中心 API

主播素材采集中心 - 告诉主播应该拍什么素材
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.api.deps import get_current_user
from app.services.asset_collection_service import AssetCollectionService

router = APIRouter(prefix="/asset-collection", tags=["素材采集中心"])


# ==================== 请求模型 ====================

class CreateTaskRequest(BaseModel):
    """创建采集任务请求"""
    title: str
    asset_type: str = "video"
    asset_role: str = "creator"
    priority: str = "medium"
    description: Optional[str] = None
    shooting_guide: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    scene: Optional[str] = None
    emotion: Optional[str] = None
    estimated_time: int = 5


class UpdateTaskStatusRequest(BaseModel):
    """更新任务状态请求"""
    status: str
    uploaded_asset_id: Optional[int] = None


# ==================== 每日推荐接口 ====================

@router.get("/daily")
async def get_daily_recommendation(
    current_user = Depends(get_current_user)
):
    """
    获取每日素材采集推荐
    
    根据主播当前素材库的缺口，智能推荐需要采集的素材
    按优先级排序，告诉主播今天应该拍什么
    """
    service = AssetCollectionService()
    try:
        result = service.get_daily_recommendation(current_user.id)
        return {
            "success": True,
            "data": result,
        }
    finally:
        service.close()


# ==================== 采集任务接口 ====================

@router.post("/tasks")
async def create_collection_task(
    request: CreateTaskRequest,
    current_user = Depends(get_current_user)
):
    """创建素材采集任务"""
    service = AssetCollectionService()
    try:
        task = service.create_collection_task(
            user_id=current_user.id,
            title=request.title,
            asset_type=request.asset_type,
            asset_role=request.asset_role,
            priority=request.priority,
            description=request.description,
            shooting_guide=request.shooting_guide,
            tags=request.tags,
            scene=request.scene,
            emotion=request.emotion,
            estimated_time=request.estimated_time,
        )
        return {
            "success": True,
            "data": {
                "task_id": task.id,
                "title": task.title,
                "priority": task.priority,
                "status": task.status,
            }
        }
    finally:
        service.close()


@router.get("/tasks")
async def get_collection_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    current_user = Depends(get_current_user)
):
    """获取用户的采集任务列表"""
    service = AssetCollectionService()
    try:
        tasks = service.get_user_tasks(current_user.id, status, priority)
        return {
            "success": True,
            "data": [
                {
                    "task_id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "priority": task.priority,
                    "asset_type": task.asset_type,
                    "asset_role": task.asset_role,
                    "shooting_guide": task.shooting_guide,
                    "tags": task.tags,
                    "scene": task.scene,
                    "emotion": task.emotion,
                    "status": task.status,
                    "progress": task.progress,
                    "estimated_time": task.estimated_time,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                }
                for task in tasks
            ]
        }
    finally:
        service.close()


@router.post("/tasks/{task_id}/status")
async def update_task_status(
    task_id: int,
    request: UpdateTaskStatusRequest,
    current_user = Depends(get_current_user)
):
    """更新采集任务状态"""
    service = AssetCollectionService()
    try:
        task = service.update_task_status(
            task_id=task_id,
            status=request.status,
            uploaded_asset_id=request.uploaded_asset_id,
        )
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        return {
            "success": True,
            "data": {
                "task_id": task.id,
                "status": task.status,
                "progress": task.progress,
            }
        }
    finally:
        service.close()


# ==================== 素材库统计接口 ====================

@router.get("/stats")
async def get_asset_library_stats(
    current_user = Depends(get_current_user)
):
    """获取素材库统计信息"""
    service = AssetCollectionService()
    try:
        stats = service.get_asset_library_stats(current_user.id)
        return {
            "success": True,
            "data": stats,
        }
    finally:
        service.close()


# ==================== 素材分类接口 ====================

@router.get("/categories")
async def get_asset_categories(
    type: str = "creator",
    current_user = Depends(get_current_user)
):
    """获取素材分类列表"""
    service = AssetCollectionService()
    try:
        categories = service.get_asset_categories(type)
        return {
            "success": True,
            "data": categories,
        }
    finally:
        service.close()
