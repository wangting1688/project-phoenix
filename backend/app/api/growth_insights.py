"""
Growth Attribution API - 增长归因与实验接口

TASK-016.3B.5.1/2/3：增长归因层 + 实验记忆 + 用户认知层
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List, Dict, Any

from app.api.deps import get_current_user
from app.services.growth_attribution_service import GrowthAttributionService
from app.services.experiment_service import ExperimentService
from app.services.audience_memory_service import AudienceMemoryService

router = APIRouter(prefix="/growth-insights", tags=["增长洞察"])


# ==================== 增长归因 ====================

@router.post("/videos/{video_id}/attribution")
async def calculate_attribution(
    video_id: int,
    publish_record_id: Optional[int] = None,
    current_user = Depends(get_current_user),
):
    """计算增长归因"""
    service = GrowthAttributionService()
    try:
        result = service.calculate_attribution(video_id, publish_record_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        service.close()


@router.get("/videos/{video_id}/attribution")
async def get_attribution(video_id: int, current_user = Depends(get_current_user)):
    """获取增长归因记录"""
    from app.core.database import SessionLocal
    from app.models.video_production import GrowthAttributionRecord

    db = SessionLocal()
    try:
        records = db.query(GrowthAttributionRecord).filter(
            GrowthAttributionRecord.video_id == video_id
        ).order_by(GrowthAttributionRecord.created_at.desc()).all()

        return {
            "success": True,
            "data": [
                {
                    "id": r.id,
                    "platform": r.platform,
                    "overall_outcome": r.overall_outcome,
                    "success_factors": r.success_factors,
                    "failure_factors": r.failure_factors,
                    "total_contribution": r.total_contribution,
                    "confidence_score": r.confidence_score,
                    "created_at": str(r.created_at),
                }
                for r in records
            ],
        }
    finally:
        db.close()


# ==================== 实验服务 ====================

@router.post("/experiments")
async def create_experiment(
    experiment_type: str,
    variable: str,
    variant_a: Dict[str, Any],
    variant_b: Dict[str, Any],
    current_user = Depends(get_current_user),
):
    """创建实验"""
    service = ExperimentService()
    try:
        result = service.create_experiment(experiment_type, variable, variant_a, variant_b)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        service.close()


@router.post("/experiments/{experiment_id}/record-result")
async def record_experiment_result(
    experiment_id: int,
    video_a_id: int,
    video_b_id: int,
    current_user = Depends(get_current_user),
):
    """记录实验结果"""
    service = ExperimentService()
    try:
        result = service.record_experiment_result(experiment_id, video_a_id, video_b_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        service.close()


@router.get("/experiments/{experiment_type}")
async def get_experiments_by_type(experiment_type: str, current_user = Depends(get_current_user)):
    """按类型查询实验"""
    service = ExperimentService()
    try:
        experiments = service.get_experiment_by_type(experiment_type)
        return {"success": True, "data": experiments}
    finally:
        service.close()


@router.post("/videos/{video_id}/suggest-experiment")
async def suggest_experiment(video_id: int, current_user = Depends(get_current_user)):
    """建议下一步实验"""
    service = ExperimentService()
    try:
        result = service.suggest_experiment(video_id)
        return result
    finally:
        service.close()


# ==================== 用户认知 ====================

@router.post("/audience/analyze")
async def analyze_audience(
    platform: Optional[str] = None,
    current_user = Depends(get_current_user),
):
    """分析用户群体"""
    service = AudienceMemoryService()
    try:
        result = service.analyze_audience(current_user.id, platform)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        service.close()


@router.get("/audience/{audience_segment}")
async def get_audience_memory(audience_segment: str, current_user = Depends(get_current_user)):
    """获取用户认知记忆"""
    service = AudienceMemoryService()
    try:
        memories = service.get_audience_memory(audience_segment)
        return {"success": True, "data": memories}
    finally:
        service.close()


@router.get("/audience/{audience_segment}/topics")
async def suggest_topics(audience_segment: str, current_user = Depends(get_current_user)):
    """基于用户认知推荐选题"""
    service = AudienceMemoryService()
    try:
        topics = service.suggest_topics(audience_segment)
        return {"success": True, "topics": topics}
    finally:
        service.close()


# ==================== 综合洞察 ====================

@router.get("/overview")
async def get_growth_insights_overview(current_user = Depends(get_current_user)):
    """获取增长洞察概览"""
    from app.core.database import SessionLocal
    from app.models.video_production import (
        GrowthAttributionRecord,
        GrowthExperimentMemory,
        AudienceGrowthMemory,
        GrowthDecisionMemory,
        GrowthFailureMemory,
    )

    db = SessionLocal()
    try:
        attribution_count = db.query(GrowthAttributionRecord).filter(
            GrowthAttributionRecord.user_id == current_user.id
        ).count()
        experiment_count = db.query(GrowthExperimentMemory).filter(
            GrowthExperimentMemory.user_id == current_user.id
        ).count()
        audience_count = db.query(AudienceGrowthMemory).filter(
            AudienceGrowthMemory.user_id == current_user.id
        ).count()
        decision_count = db.query(GrowthDecisionMemory).filter(
            GrowthDecisionMemory.user_id == current_user.id
        ).count()
        failure_count = db.query(GrowthFailureMemory).filter(
            GrowthFailureMemory.user_id == current_user.id
        ).count()

        return {
            "success": True,
            "overview": {
                "attribution_records": attribution_count,
                "experiments": experiment_count,
                "audience_memories": audience_count,
                "decision_memories": decision_count,
                "failure_memories": failure_count,
            },
        }
    finally:
        db.close()
