"""
Growth Review API - 增长复盘记忆层 API

TASK-016.3B.4：AI Growth Review Memory

提供增长复盘报告、主播适配评分、三版本策略等接口
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List, Dict, Any

from app.api.deps import get_current_user
from app.services.growth_quality_agent_v2 import GrowthQualityAgentV2
from app.services.creator_fit_scorer import CreatorFitScorer
from app.services.three_version_service import ThreeVersionProductionService
from app.services.production_repair_agent import ProductionRepairAgent

router = APIRouter(prefix="/growth-review", tags=["增长复盘"])


# ==================== 增长质量评估V2 ====================

@router.post("/plans/{plan_id}/assess-v2")
async def assess_growth_quality_v2(plan_id: int, version_type: str = "growth", current_user = Depends(get_current_user)):
    """增长质量评估V2"""
    agent = GrowthQualityAgentV2()
    try:
        result = agent.assess_growth_quality_v2(plan_id, version_type)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        agent.close()


@router.post("/plans/{plan_id}/generate-report")
async def generate_review_report(plan_id: int, version_type: str = "growth", current_user = Depends(get_current_user)):
    """生成增长复盘报告"""
    agent = GrowthQualityAgentV2()
    try:
        result = agent.generate_growth_review_report(plan_id, version_type)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        agent.close()


# ==================== 商业压力指数 ====================

@router.get("/plans/{plan_id}/commercial-pressure")
async def get_commercial_pressure(plan_id: int, current_user = Depends(get_current_user)):
    """获取商业压力指数"""
    agent = GrowthQualityAgentV2()
    try:
        result = agent.assess_growth_quality_v2(plan_id, "growth")
        if result["success"]:
            return {
                "success": True,
                "commercial_pressure": result["details"]["commercial_pressure"],
            }
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        agent.close()


# ==================== 主播适配评分 ====================

@router.get("/plans/{plan_id}/creator-fit")
async def get_creator_fit(plan_id: int, current_user = Depends(get_current_user)):
    """获取主播适配评分"""
    scorer = CreatorFitScorer()
    try:
        result = scorer.score_creator_fit(plan_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        scorer.close()


# ==================== 有机增长指数 ====================

@router.get("/plans/{plan_id}/organic-growth-score")
async def get_organic_growth_score(plan_id: int, current_user = Depends(get_current_user)):
    """获取有机增长指数"""
    agent = GrowthQualityAgentV2()
    try:
        result = agent.assess_growth_quality_v2(plan_id, "growth")
        if result["success"]:
            return {
                "success": True,
                "organic_growth_score": result["organic_growth_score"],
                "hook_score": result["details"]["hook"]["score"],
                "retention_score": result["details"]["retention"]["score"],
                "emotion_score": result["details"]["emotion"]["avg_match_score"],
                "follow_reason_score": result["details"]["follow_reasons"]["avg_strength"],
                "platform_fit_score": result["details"]["platform_fit"]["score"],
            }
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        agent.close()


# ==================== 三版本策略 ====================

@router.post("/jobs/{job_id}/three-versions")
async def create_three_versions(job_id: int, current_user = Depends(get_current_user)):
    """创建三版本"""
    service = ThreeVersionProductionService()
    try:
        result = service.create_three_versions(job_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        service.close()


@router.get("/jobs/{job_id}/versions")
async def list_versions(job_id: int, current_user = Depends(get_current_user)):
    """列出所有版本"""
    service = ThreeVersionProductionService()
    try:
        versions = service.list_versions(job_id)
        return {"success": True, "data": versions}
    finally:
        service.close()


@router.post("/versions/{version_id}/assess")
async def assess_version(version_id: int, current_user = Depends(get_current_user)):
    """评估单个版本"""
    service = ThreeVersionProductionService()
    try:
        result = service.assess_version(version_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        service.close()


# ==================== 导演反馈闭环 ====================

@router.post("/jobs/{job_id}/suggest-versions")
async def suggest_three_versions(job_id: int, current_user = Depends(get_current_user)):
    """建议三版本策略"""
    repair_agent = ProductionRepairAgent()
    try:
        result = repair_agent.suggest_three_versions(job_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        repair_agent.close()


@router.get("/plans/{plan_id}/review-reports")
async def list_review_reports(plan_id: int, current_user = Depends(get_current_user)):
    """列出历史复盘报告"""
    from app.core.database import SessionLocal
    from app.models.video_production import GrowthReviewReport

    db = SessionLocal()
    try:
        reports = db.query(GrowthReviewReport).filter(
            GrowthReviewReport.video_plan_id == plan_id
        ).order_by(GrowthReviewReport.created_at.desc()).all()

        return {
            "success": True,
            "data": [
                {
                    "id": r.id,
                    "stage": r.stage,
                    "overall_score": r.overall_score,
                    "passed": r.passed,
                    "review_count": r.review_count,
                    "organic_growth_score": r.organic_growth_score,
                    "commercial_pressure_index": r.commercial_pressure_index,
                    "creator_fit_score": r.creator_fit_score,
                    "problems": r.problems,
                    "director_actions": r.director_actions,
                    "suggestions": r.suggestions,
                    "created_at": str(r.created_at),
                }
                for r in reports
            ],
        }
    finally:
        db.close()


# ==================== 自然增长洞察 ====================

@router.post("/insights")
async def create_insight(
    insight_type: str,
    platform: str,
    conclusion: str,
    conditions: Optional[Dict[str, Any]] = None,
    observation: Optional[Dict[str, Any]] = None,
    confidence_score: float = 0.5,
    plan_id: Optional[int] = None,
    publish_record_id: Optional[int] = None,
    product_category: Optional[str] = None,
    creator_id: Optional[int] = None,
    current_user = Depends(get_current_user),
):
    """创建自然增长洞察"""
    from app.core.database import SessionLocal
    from app.models.video_production import OrganicGrowthInsight

    db = SessionLocal()
    try:
        insight = OrganicGrowthInsight(
            user_id=current_user.id,
            video_plan_id=plan_id,
            publish_record_id=publish_record_id,
            insight_type=insight_type,
            platform=platform,
            product_category=product_category,
            creator_id=creator_id,
            conditions=conditions,
            observation=observation,
            conclusion=conclusion,
            confidence_score=confidence_score,
        )
        db.add(insight)
        db.commit()
        db.refresh(insight)
        return {
            "success": True,
            "insight_id": insight.id,
        }
    finally:
        db.close()


@router.get("/insights")
async def list_insights(
    platform: Optional[str] = None,
    product_category: Optional[str] = None,
    creator_id: Optional[int] = None,
    limit: int = 50,
    current_user = Depends(get_current_user),
):
    """列出自然增长洞察"""
    from app.core.database import SessionLocal
    from app.models.video_production import OrganicGrowthInsight

    db = SessionLocal()
    try:
        query = db.query(OrganicGrowthInsight)
        if platform:
            query = query.filter(OrganicGrowthInsight.platform == platform)
        if product_category:
            query = query.filter(OrganicGrowthInsight.product_category == product_category)
        if creator_id:
            query = query.filter(OrganicGrowthInsight.creator_id == creator_id)

        insights = query.order_by(OrganicGrowthInsight.created_at.desc()).limit(limit).all()

        return {
            "success": True,
            "data": [
                {
                    "id": i.id,
                    "insight_type": i.insight_type,
                    "platform": i.platform,
                    "product_category": i.product_category,
                    "creator_id": i.creator_id,
                    "conclusion": i.conclusion,
                    "confidence_score": i.confidence_score,
                    "usage_count": i.usage_count,
                    "created_at": str(i.created_at),
                }
                for i in insights
            ],
        }
    finally:
        db.close()
