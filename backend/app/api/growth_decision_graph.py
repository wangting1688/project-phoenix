"""
Growth Decision Graph API - 增长决策知识图谱接口

TASK-016.3B.5：AI Growth Decision Graph

提供表现分析、规律发现、导演学习、决策记忆查询等接口
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List, Dict, Any

from app.api.deps import get_current_user
from app.services.performance_analyst_agent import PerformanceAnalystAgent
from app.services.growth_scientist_agent import GrowthScientistAgent
from app.services.director_learning_agent import DirectorLearningAgent

router = APIRouter(prefix="/growth-decision", tags=["增长决策知识图谱"])


# ==================== Performance Analyst ====================

@router.get("/videos/{video_id}/analyze")
async def analyze_video_performance(video_id: int, current_user = Depends(get_current_user)):
    """分析视频表现"""
    agent = PerformanceAnalystAgent()
    try:
        result = agent.analyze_video_performance(video_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        agent.close()


@router.get("/videos/{video_id}/compare-prediction")
async def compare_prediction(video_id: int, current_user = Depends(get_current_user)):
    """对比预测与实际表现"""
    agent = PerformanceAnalystAgent()
    try:
        result = agent.compare_with_prediction(video_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        agent.close()


# ==================== Growth Scientist ====================

@router.post("/discover-patterns")
async def discover_patterns(time_range_days: int = 90, current_user = Depends(get_current_user)):
    """发现增长规律"""
    agent = GrowthScientistAgent()
    try:
        result = agent.discover_patterns(current_user.id, time_range_days)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        agent.close()


@router.post("/analyze-failures")
async def analyze_failures(time_range_days: int = 90, current_user = Depends(get_current_user)):
    """分析失败经验"""
    agent = GrowthScientistAgent()
    try:
        result = agent.analyze_failures(current_user.id, time_range_days)
        return result
    finally:
        agent.close()


# ==================== Director Learning ====================

@router.post("/plans/{plan_id}/optimize")
async def optimize_director_plan(
    plan_id: int,
    video_id: Optional[int] = None,
    current_user = Depends(get_current_user),
):
    """优化导演方案"""
    agent = DirectorLearningAgent()
    try:
        result = agent.optimize_director_plan(plan_id, video_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        agent.close()


@router.get("/plans/{plan_id}/guidance")
async def get_director_guidance(plan_id: int, current_user = Depends(get_current_user)):
    """获取导演指导（生产前）"""
    agent = DirectorLearningAgent()
    try:
        result = agent.get_director_guidance(plan_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        agent.close()


# ==================== Growth Decision Memory ====================

@router.get("/decision-memories")
async def list_decision_memories(
    platform: Optional[str] = None,
    product_category: Optional[str] = None,
    content_type: Optional[str] = None,
    limit: int = 50,
    current_user = Depends(get_current_user),
):
    """查询增长决策记忆"""
    from app.core.database import SessionLocal
    from app.models.video_production import GrowthDecisionMemory

    db = SessionLocal()
    try:
        query = db.query(GrowthDecisionMemory).filter(
            GrowthDecisionMemory.user_id == current_user.id
        )
        if platform:
            query = query.filter(GrowthDecisionMemory.platform == platform)
        if product_category:
            query = query.filter(GrowthDecisionMemory.product_category == product_category)
        if content_type:
            query = query.filter(GrowthDecisionMemory.content_type == content_type)

        memories = query.order_by(GrowthDecisionMemory.confidence_score.desc()).limit(limit).all()

        return {
            "success": True,
            "data": [
                {
                    "id": m.id,
                    "content_type": m.content_type,
                    "opening_pattern": m.opening_pattern,
                    "platform": m.platform,
                    "product_category": m.product_category,
                    "topic": m.topic,
                    "commercial_stage": m.commercial_stage,
                    "business_stage": m.business_stage,
                    "conclusion": m.conclusion,
                    "confidence_score": m.confidence_score,
                    "success_count": m.success_count,
                    "total_count": m.total_count,
                    "usage_count": m.usage_count,
                }
                for m in memories
            ],
        }
    finally:
        db.close()


# ==================== Growth Failure Memory ====================

@router.get("/failure-memories")
async def list_failure_memories(
    platform: Optional[str] = None,
    failure_type: Optional[str] = None,
    limit: int = 50,
    current_user = Depends(get_current_user),
):
    """查询失败经验记忆"""
    from app.core.database import SessionLocal
    from app.models.video_production import GrowthFailureMemory

    db = SessionLocal()
    try:
        query = db.query(GrowthFailureMemory).filter(
            GrowthFailureMemory.user_id == current_user.id
        )
        if platform:
            query = query.filter(GrowthFailureMemory.platform == platform)
        if failure_type:
            query = query.filter(GrowthFailureMemory.failure_type == failure_type)

        memories = query.order_by(GrowthFailureMemory.occurrence_count.desc()).limit(limit).all()

        return {
            "success": True,
            "data": [
                {
                    "id": m.id,
                    "failure_type": m.failure_type,
                    "failure_pattern": m.failure_pattern,
                    "platform": m.platform,
                    "product_category": m.product_category,
                    "creator_type": m.creator_type,
                    "business_stage": m.business_stage,
                    "lesson": m.lesson,
                    "avoid_actions": m.avoid_actions,
                    "recommended_actions": m.recommended_actions,
                    "occurrence_count": m.occurrence_count,
                    "confidence_score": m.confidence_score,
                }
                for m in memories
            ],
        }
    finally:
        db.close()
