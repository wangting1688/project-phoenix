"""
Scheduler API - 定时任务管理接口

TASK-017.4：自动复盘触发控制
"""

from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.models import User
from app.services.scheduler_service import get_growth_scheduler

router = APIRouter(prefix="/scheduler", tags=["定时任务"])


@router.post("/start")
def start_scheduler(current_user: User = Depends(get_current_user)):
    """启动增长定时调度器"""
    scheduler = get_growth_scheduler()
    scheduler.start()
    return {"success": True, "message": "调度器已启动", "status": scheduler.status()}


@router.post("/stop")
def stop_scheduler(current_user: User = Depends(get_current_user)):
    """停止增长定时调度器"""
    scheduler = get_growth_scheduler()
    scheduler.stop()
    return {"success": True, "message": "调度器已停止", "status": scheduler.status()}


@router.get("/status")
def get_scheduler_status(current_user: User = Depends(get_current_user)):
    """获取调度器状态"""
    scheduler = get_growth_scheduler()
    return {"success": True, "data": scheduler.status()}
