"""
Production Execution API - AI生产执行引擎接口

TASK-016.3B.2：AI生产执行引擎

提供生产任务管理、步骤执行、进度查询、自动修复等接口
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List, Dict, Any

from app.api.deps import get_current_user
from app.services.production_executor_agent import ProductionExecutorAgent
from app.services.timeline_builder import TimelineBuilder
from app.services.production_repair_agent import ProductionRepairAgent
from app.services.video_production_service import ProductionExecutionService

router = APIRouter(prefix="/production-execution", tags=["AI生产执行"])


# ==================== 生产任务管理 ====================

@router.post("/jobs/{job_id}/initialize")
async def initialize_job(job_id: int, current_user = Depends(get_current_user)):
    """初始化生产任务"""
    executor = ProductionExecutorAgent()
    try:
        result = executor.initialize_job(job_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        executor.close()


@router.post("/jobs/{job_id}/execute")
async def execute_job(job_id: int, current_user = Depends(get_current_user)):
    """执行生产任务"""
    executor = ProductionExecutorAgent()
    try:
        result = executor.execute_job(job_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        executor.close()


@router.get("/jobs/{job_id}/progress")
async def get_job_progress(job_id: int, current_user = Depends(get_current_user)):
    """获取任务进度"""
    executor = ProductionExecutorAgent()
    try:
        result = executor.get_job_progress(job_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=404, detail=result["error"])
    finally:
        executor.close()


@router.get("/jobs/{job_id}/steps")
async def get_job_steps(job_id: int, current_user = Depends(get_current_user)):
    """获取任务步骤列表"""
    executor = ProductionExecutorAgent()
    try:
        result = executor.get_job_progress(job_id)
        if result["success"]:
            return {
                "success": True,
                "job_id": job_id,
                "steps": result["steps"],
            }
        raise HTTPException(status_code=404, detail=result["error"])
    finally:
        executor.close()


@router.post("/jobs/{job_id}/steps/{sequence}/execute")
async def execute_step(job_id: int, sequence: int, current_user = Depends(get_current_user)):
    """执行单个步骤"""
    executor = ProductionExecutorAgent()
    try:
        result = executor.execute_step(job_id, sequence)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        executor.close()


@router.post("/jobs/{job_id}/steps/{sequence}/retry")
async def retry_step(job_id: int, sequence: int, current_user = Depends(get_current_user)):
    """重试失败步骤"""
    executor = ProductionExecutorAgent()
    try:
        result = executor.retry_failed_step(job_id, sequence)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        executor.close()


# ==================== Timeline管理 ====================

@router.get("/jobs/{job_id}/timeline")
async def get_timeline(job_id: int, current_user = Depends(get_current_user)):
    """获取Timeline JSON"""
    executor = ProductionExecutorAgent()
    try:
        result = executor.generate_timeline_json(job_id)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return {"success": True, "data": result}
    finally:
        executor.close()


@router.get("/jobs/{job_id}/timeline/ffmpeg")
async def get_timeline_ffmpeg(job_id: int, current_user = Depends(get_current_user)):
    """导出FFmpeg格式"""
    builder = TimelineBuilder()
    try:
        timeline = builder.build_phoenix_timeline(job_id)
        if "error" in timeline:
            raise HTTPException(status_code=400, detail=timeline["error"])
        ffmpeg_config = builder.export_for_ffmpeg(timeline)
        return {"success": True, "data": ffmpeg_config}
    finally:
        builder.close()


@router.get("/jobs/{job_id}/timeline/remotion")
async def get_timeline_remotion(job_id: int, current_user = Depends(get_current_user)):
    """导出Remotion格式"""
    builder = TimelineBuilder()
    try:
        timeline = builder.build_phoenix_timeline(job_id)
        if "error" in timeline:
            raise HTTPException(status_code=400, detail=timeline["error"])
        remotion_config = builder.export_for_remotion(timeline)
        return {"success": True, "data": remotion_config}
    finally:
        builder.close()


# ==================== 自动修复 ====================

@router.get("/jobs/{job_id}/inspect")
async def inspect_job(job_id: int, current_user = Depends(get_current_user)):
    """检查任务问题"""
    repair_agent = ProductionRepairAgent()
    try:
        result = repair_agent.inspect_job(job_id)
        return result
    finally:
        repair_agent.close()


@router.post("/jobs/{job_id}/auto-repair")
async def auto_repair(job_id: int, current_user = Depends(get_current_user)):
    """自动修复问题"""
    repair_agent = ProductionRepairAgent()
    try:
        result = repair_agent.auto_repair(job_id)
        return result
    finally:
        repair_agent.close()


# ==================== 生产任务CRUD ====================

@router.post("/jobs")
async def create_production_job(
    title: str,
    source_plan_id: int,
    target_platforms: List[str],
    creator_id: Optional[int] = None,
    product_id: Optional[int] = None,
    current_user = Depends(get_current_user),
):
    """创建生产任务"""
    service = ProductionExecutionService()
    try:
        job = service.create_production_job(
            user_id=current_user.id,
            title=title,
            source_plan_id=source_plan_id,
            creator_id=creator_id,
            product_id=product_id,
            target_platforms=target_platforms,
        )
        return {"success": True, "data": {"job_id": job.id, "status": job.status}}
    finally:
        service.close()


@router.get("/jobs/{job_id}")
async def get_job(job_id: int, current_user = Depends(get_current_user)):
    """获取生产任务详情"""
    service = ProductionExecutionService()
    try:
        job = service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="任务不存在")
        return {"success": True, "data": {
            "id": job.id,
            "title": job.title,
            "status": job.status,
            "total_duration": job.total_duration,
            "target_platforms": job.target_platforms,
            "creator_id": job.creator_id,
            "product_id": job.product_id,
            "progress": job.progress,
            "blocked_reasons": job.blocked_reasons,
        }}
    finally:
        service.close()


@router.get("/jobs")
async def list_jobs(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user = Depends(get_current_user),
):
    """获取生产任务列表"""
    service = ProductionExecutionService()
    try:
        query = service.db.query(service.model)
        if status:
            query = query.filter(service.model.status == status)
        query = query.filter(service.model.user_id == current_user.id)
        query = query.order_by(service.model.created_at.desc())
        
        total = query.count()
        jobs = query.offset((page - 1) * page_size).limit(page_size).all()
        
        return {"success": True, "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "jobs": [
                {
                    "id": job.id,
                    "title": job.title,
                    "status": job.status,
                    "total_duration": job.total_duration,
                    "target_platforms": job.target_platforms,
                    "progress": job.progress,
                }
                for job in jobs
            ],
        }}
    finally:
        service.close()


@router.put("/jobs/{job_id}")
async def update_job(
    job_id: int,
    status: Optional[str] = None,
    title: Optional[str] = None,
    current_user = Depends(get_current_user),
):
    """更新生产任务"""
    service = ProductionExecutionService()
    try:
        job = service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        if status:
            job = service.update_job_status(job_id, status)
        if title:
            job.title = title
            service.db.commit()
        
        return {"success": True, "data": {"job_id": job.id, "status": job.status}}
    finally:
        service.close()


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: int, current_user = Depends(get_current_user)):
    """删除生产任务"""
    service = ProductionExecutionService()
    try:
        job = service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        service.db.delete(job)
        service.db.commit()
        
        return {"success": True, "message": "删除成功"}
    finally:
        service.close()


# ==================== 阻塞任务管理 ====================

@router.get("/jobs/{job_id}/block-tasks")
async def get_block_tasks(job_id: int, current_user = Depends(get_current_user)):
    """获取阻塞任务"""
    service = ProductionExecutionService()
    try:
        block_service = service.__class__.__bases__[0]()
        if hasattr(service, 'check_material_gaps'):
            tasks = service.check_material_gaps(job_id)
        else:
            tasks = []
        
        return {"success": True, "data": [
            {
                "id": task.id,
                "block_type": task.block_type,
                "priority": task.priority,
                "status": task.status,
                "reason": task.reason,
                "suggested_action": task.suggested_action,
            }
            for task in tasks
        ]}
    finally:
        service.close()


@router.post("/block-tasks/{task_id}/resolve")
async def resolve_block_task(task_id: int, collection_task_id: Optional[int] = None, current_user = Depends(get_current_user)):
    """解决阻塞任务"""
    service = ProductionExecutionService()
    try:
        if hasattr(service, 'resolve_block_task'):
            task = service.resolve_block_task(task_id, collection_task_id)
            if not task:
                raise HTTPException(status_code=404, detail="任务不存在")
            return {"success": True, "data": {"task_id": task.id, "status": task.status}}
        raise HTTPException(status_code=500, detail="未实现此功能")
    finally:
        service.close()
