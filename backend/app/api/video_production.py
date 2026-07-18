"""
视频生产执行编排层 API

TASK-016.3B.0：AI视频生产执行编排层

提供生产任务管理、时间线操作、版本管理、素材匹配等接口
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.api.deps import get_current_user
from app.services.video_production_service import (
    ProductionExecutionService,
    VideoEditorAgent,
    ProductionBlockService,
)

router = APIRouter(prefix="/video-production", tags=["AI视频生产"])


# ==================== 生产任务管理 ====================

@router.post("/jobs")
async def create_production_job(
    title: str,
    source_plan_id: int = None,
    video_project_id: int = None,
    creator_id: int = None,
    product_id: int = None,
    target_platforms: Optional[List[str]] = Query(None),
    job_type: str = "short_video",
    current_user = Depends(get_current_user),
):
    """创建视频生产任务"""
    service = ProductionExecutionService()
    try:
        job = service.create_production_job(
            user_id=current_user.id,
            title=title,
            source_plan_id=source_plan_id,
            video_project_id=video_project_id,
            creator_id=creator_id,
            product_id=product_id,
            target_platforms=target_platforms,
            job_type=job_type,
        )
        return {
            "success": True,
            "data": {
                "job_id": job.id,
                "title": job.title,
                "status": job.status,
                "created_at": job.created_at.isoformat() if job.created_at else None,
            },
        }
    finally:
        service.close()


@router.get("/jobs")
async def get_production_jobs(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user = Depends(get_current_user),
):
    """获取生产任务列表"""
    service = ProductionExecutionService()
    try:
        from app.models.video_production import VideoProductionJob

        query = service.db.query(VideoProductionJob).filter(
            VideoProductionJob.user_id == current_user.id
        )

        if status:
            query = query.filter(VideoProductionJob.status == status)

        query = query.order_by(VideoProductionJob.created_at.desc())
        total = query.count()
        jobs = query.offset((page - 1) * page_size).limit(page_size).all()

        return {
            "success": True,
            "data": {
                "jobs": [
                    {
                        "id": j.id,
                        "title": j.title,
                        "status": j.status,
                        "progress": j.progress,
                        "total_duration": j.total_duration,
                        "variant_count": j.variant_count,
                        "blocked_reasons": j.blocked_reasons,
                        "created_at": j.created_at.isoformat() if j.created_at else None,
                    }
                    for j in jobs
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
    finally:
        service.close()


@router.get("/jobs/{job_id}")
async def get_production_job(
    job_id: int,
    current_user = Depends(get_current_user),
):
    """获取生产任务详情"""
    service = ProductionExecutionService()
    try:
        job = service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="任务不存在")
        if job.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")

        return {
            "success": True,
            "data": {
                "id": job.id,
                "title": job.title,
                "job_type": job.job_type,
                "status": job.status,
                "progress": job.progress,
                "source_plan_id": job.source_plan_id,
                "video_project_id": job.video_project_id,
                "creator_id": job.creator_id,
                "product_id": job.product_id,
                "target_platforms": job.target_platforms,
                "total_duration": job.total_duration,
                "estimated_duration": job.estimated_duration,
                "variant_count": job.variant_count,
                "timeline_generated": job.timeline_generated,
                "material_matched": job.material_matched,
                "subtitle_ready": job.subtitle_ready,
                "bgm_ready": job.bgm_ready,
                "cover_ready": job.cover_ready,
                "rendering_done": job.rendering_done,
                "blocked_reasons": job.blocked_reasons,
                "created_at": job.created_at.isoformat() if job.created_at else None,
            },
        }
    finally:
        service.close()


@router.put("/jobs/{job_id}/status")
async def update_job_status(
    job_id: int,
    status: str,
    current_user = Depends(get_current_user),
):
    """更新任务状态"""
    service = ProductionExecutionService()
    try:
        job = service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="任务不存在")
        if job.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")

        job = service.update_job_status(job_id, status)
        return {
            "success": True,
            "data": {"job_id": job.id, "status": job.status},
        }
    finally:
        service.close()


# ==================== 时间线管理 ====================

@router.post("/jobs/{job_id}/timeline")
async def generate_timeline(
    job_id: int,
    current_user = Depends(get_current_user),
):
    """从导演方案生成时间线"""
    service = ProductionExecutionService()
    try:
        job = service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="任务不存在")
        if job.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")

        result = service.generate_timeline_from_plan(job_id)
        return {
            "success": result["success"],
            "message": "时间线生成成功" if result["success"] else result["error"],
            "data": result,
        }
    finally:
        service.close()


@router.get("/jobs/{job_id}/timeline")
async def get_job_timeline(
    job_id: int,
    current_user = Depends(get_current_user),
):
    """获取任务时间线"""
    service = ProductionExecutionService()
    try:
        from app.models.video_production import VideoTimeline

        job = service.get_job(job_id)
        if not job or job.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")

        timelines = service.db.query(VideoTimeline).filter(
            VideoTimeline.production_job_id == job_id
        ).order_by(VideoTimeline.sequence).all()

        return {
            "success": True,
            "data": [
                {
                    "id": t.id,
                    "sequence": t.sequence,
                    "start_time": t.start_time,
                    "end_time": t.end_time,
                    "duration": round(t.end_time - t.start_time, 1),
                    "layer": t.layer,
                    "content_type": t.content_type,
                    "source_type": t.source_type,
                    "source_id": t.source_id,
                    "role": t.role,
                    "segment_type": t.segment_type,
                    "status": t.status,
                    "material_found": t.material_found,
                    "material_duration": t.material_duration,
                    "material_gap": t.material_gap,
                    "effect_config": t.effect_config,
                    "transition_config": t.transition_config,
                    "subtitle_config": t.subtitle_config,
                    "audio_config": t.audio_config,
                }
                for t in timelines
            ],
        }
    finally:
        service.close()


# ==================== AI剪辑执行Agent ====================

@router.post("/jobs/{job_id}/match-materials")
async def match_materials(
    job_id: int,
    current_user = Depends(get_current_user),
):
    """为任务匹配素材"""
    agent = VideoEditorAgent()
    try:
        from app.models.video_production import VideoProductionJob

        job = agent.db.query(VideoProductionJob).filter(VideoProductionJob.id == job_id).first()
        if not job or job.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")

        result = agent.match_materials_for_job(job_id)
        return {
            "success": result["success"],
            "message": f"素材匹配完成，{result['matched_count']}/{result['total_timelines']}段匹配成功" if result["success"] else f"素材匹配失败，缺少{result['missing_count']}段素材",
            "data": result,
        }
    finally:
        agent.close()


@router.post("/jobs/{job_id}/clip-project")
async def generate_clip_project(
    job_id: int,
    current_user = Depends(get_current_user),
):
    """生成剪辑工程"""
    agent = VideoEditorAgent()
    try:
        from app.models.video_production import VideoProductionJob

        job = agent.db.query(VideoProductionJob).filter(VideoProductionJob.id == job_id).first()
        if not job or job.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")

        result = agent.generate_clip_project(job_id)
        return {
            "success": result["success"],
            "message": "剪辑工程生成成功" if result["success"] else result["error"],
            "data": result,
        }
    finally:
        agent.close()


# ==================== 版本管理 ====================

@router.post("/jobs/{job_id}/variants")
async def generate_variants(
    job_id: int,
    platforms: Optional[List[str]] = Query(None),
    current_user = Depends(get_current_user),
):
    """生成多平台版本"""
    service = ProductionExecutionService()
    try:
        job = service.get_job(job_id)
        if not job or job.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")

        result = service.generate_variants(job_id, platforms)
        return {
            "success": result["success"],
            "message": f"生成{result['variant_count']}个平台版本" if result["success"] else result["error"],
            "data": result,
        }
    finally:
        service.close()


@router.get("/jobs/{job_id}/variants")
async def get_job_variants(
    job_id: int,
    current_user = Depends(get_current_user),
):
    """获取任务版本列表"""
    service = ProductionExecutionService()
    try:
        from app.models.video_production import VideoVariant

        job = service.get_job(job_id)
        if not job or job.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")

        variants = service.db.query(VideoVariant).filter(
            VideoVariant.production_job_id == job_id
        ).all()

        return {
            "success": True,
            "data": [
                {
                    "id": v.id,
                    "platform": v.platform,
                    "strategy": v.strategy,
                    "target_duration": v.target_duration,
                    "actual_duration": v.actual_duration,
                    "status": v.status,
                    "director_score": v.director_score,
                    "variant_config": v.variant_config,
                    "output_video_url": v.output_video_url,
                }
                for v in variants
            ],
        }
    finally:
        service.close()


# ==================== 生产阻塞管理 ====================

@router.post("/jobs/{job_id}/check-blocks")
async def check_block_tasks(
    job_id: int,
    current_user = Depends(get_current_user),
):
    """检查素材缺口并创建阻塞任务"""
    block_service = ProductionBlockService()
    try:
        from app.models.video_production import VideoProductionJob

        job = block_service.db.query(VideoProductionJob).filter(VideoProductionJob.id == job_id).first()
        if not job or job.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")

        tasks = block_service.check_material_gaps(job_id)
        return {
            "success": True,
            "data": {
                "block_count": len(tasks),
                "tasks": [
                    {
                        "id": t.id,
                        "block_type": t.block_type,
                        "priority": t.priority,
                        "status": t.status,
                        "required_content_type": t.required_content_type,
                        "required_duration": t.required_duration,
                        "gap_duration": t.gap_duration,
                        "reason": t.reason,
                        "suggested_action": t.suggested_action,
                    }
                    for t in tasks
                ],
            },
        }
    finally:
        block_service.close()


@router.get("/block-tasks")
async def get_block_tasks(
    status: Optional[str] = "pending",
    current_user = Depends(get_current_user),
):
    """获取阻塞任务列表"""
    block_service = ProductionBlockService()
    try:
        from app.models.video_production import ProductionBlockTask, VideoProductionJob

        query = block_service.db.query(ProductionBlockTask).join(
            VideoProductionJob,
            VideoProductionJob.id == ProductionBlockTask.production_job_id,
        ).filter(VideoProductionJob.user_id == current_user.id)

        if status:
            query = query.filter(ProductionBlockTask.status == status)

        tasks = query.all()

        return {
            "success": True,
            "data": [
                {
                    "id": t.id,
                    "production_job_id": t.production_job_id,
                    "block_type": t.block_type,
                    "priority": t.priority,
                    "status": t.status,
                    "required_content_type": t.required_content_type,
                    "required_duration": t.required_duration,
                    "gap_duration": t.gap_duration,
                    "target_role": t.target_role,
                    "target_emotion": t.target_emotion,
                    "reason": t.reason,
                    "suggested_action": t.suggested_action,
                }
                for t in tasks
            ],
        }
    finally:
        block_service.close()


@router.put("/block-tasks/{task_id}/resolve")
async def resolve_block_task(
    task_id: int,
    collection_task_id: int = None,
    current_user = Depends(get_current_user),
):
    """解决阻塞任务"""
    block_service = ProductionBlockService()
    try:
        from app.models.video_production import ProductionBlockTask, VideoProductionJob

        task = block_service.db.query(ProductionBlockTask).join(
            VideoProductionJob,
            VideoProductionJob.id == ProductionBlockTask.production_job_id,
        ).filter(
            ProductionBlockTask.id == task_id,
            VideoProductionJob.user_id == current_user.id,
        ).first()

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        resolved = block_service.resolve_block_task(task_id, collection_task_id)
        return {
            "success": True,
            "data": {"task_id": resolved.id, "status": resolved.status},
        }
    finally:
        block_service.close()


# ==================== 统计接口 ====================

@router.get("/stats")
async def get_production_stats(
    current_user = Depends(get_current_user),
):
    """获取生产统计"""
    service = ProductionExecutionService()
    try:
        from app.models.video_production import VideoProductionJob, VideoVariant

        total_jobs = service.db.query(VideoProductionJob).filter(
            VideoProductionJob.user_id == current_user.id
        ).count()

        completed_jobs = service.db.query(VideoProductionJob).filter(
            VideoProductionJob.user_id == current_user.id,
            VideoProductionJob.status == "completed",
        ).count()

        blocked_jobs = service.db.query(VideoProductionJob).filter(
            VideoProductionJob.user_id == current_user.id,
            VideoProductionJob.status == "blocked",
        ).count()

        total_variants = service.db.query(VideoVariant).join(
            VideoProductionJob,
            VideoProductionJob.id == VideoVariant.production_job_id,
        ).filter(VideoProductionJob.user_id == current_user.id).count()

        return {
            "success": True,
            "data": {
                "total_jobs": total_jobs,
                "completed_jobs": completed_jobs,
                "blocked_jobs": blocked_jobs,
                "total_variants": total_variants,
                "completion_rate": round(completed_jobs / max(total_jobs, 1) * 100, 1),
            },
        }
    finally:
        service.close()
