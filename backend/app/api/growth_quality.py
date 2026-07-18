"""
Growth Quality API - 增长质量检测接口

TASK-016.3B.3：增长质量控制层

提供增长质量检测、评分、建议修改等接口
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List, Dict, Any

from app.api.deps import get_current_user
from app.services.growth_quality_agent import GrowthQualityAgent

router = APIRouter(prefix="/growth-quality", tags=["增长质量检测"])


# ==================== 增长质量检测 ====================

@router.post("/jobs/{job_id}/assess")
async def assess_growth_quality(job_id: int, current_user = Depends(get_current_user)):
    """评估增长质量"""
    agent = GrowthQualityAgent()
    try:
        result = agent.assess_growth_quality(job_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        agent.close()


@router.post("/jobs/{job_id}/suggest-revision")
async def suggest_revision(job_id: int, current_user = Depends(get_current_user)):
    """生成修改建议"""
    agent = GrowthQualityAgent()
    try:
        result = agent.suggest_revision(job_id)
        if result["success"]:
            return result
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        agent.close()


# ==================== 评分详情 ====================

@router.get("/jobs/{job_id}/hook-score")
async def get_hook_score(job_id: int, current_user = Depends(get_current_user)):
    """获取Hook评分"""
    agent = GrowthQualityAgent()
    try:
        result = agent.assess_growth_quality(job_id)
        if result["success"]:
            return {
                "success": True,
                "hook_score": result["details"]["hook_score"],
                "retention_prediction": result["details"]["retention_prediction"],
            }
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        agent.close()


@router.get("/jobs/{job_id}/emotion-curve")
async def get_emotion_curve(job_id: int, current_user = Depends(get_current_user)):
    """获取情绪曲线分析"""
    agent = GrowthQualityAgent()
    try:
        result = agent.assess_growth_quality(job_id)
        if result["success"]:
            return {
                "success": True,
                "emotion_curve": result["details"]["emotion_curve"],
            }
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        agent.close()


@router.get("/jobs/{job_id}/risks")
async def get_risks(job_id: int, current_user = Depends(get_current_user)):
    """获取风险检测结果"""
    agent = GrowthQualityAgent()
    try:
        result = agent.assess_growth_quality(job_id)
        if result["success"]:
            return {
                "success": True,
                "risks": result["details"]["risks"],
            }
        raise HTTPException(status_code=400, detail=result["error"])
    finally:
        agent.close()


# ==================== 阶段配置 ====================

@router.get("/stage-config")
async def get_stage_config(current_user = Depends(get_current_user)):
    """获取当前阶段配置"""
    return {
        "success": True,
        "current_stage": "growth",
        "stage_weights": {
            "growth": {"play": 40, "completion": 25, "engagement": 20, "follow": 15},
            "private_domain": {"comment": 30, "message": 30, "profile": 20, "contact": 20},
            "conversion": {"gmv": 35, "consultation": 25, "conversion": 15, "retention": 25},
        },
        "growth_rules": [
            "禁止开头直接介绍产品",
            "禁止价格刺激",
            "禁止'买3送1'",
            "禁止强功效暗示",
            "禁止硬广口播",
        ],
        "content_structure": ["用户兴趣", "情绪价值", "知识价值", "主播人格", "自然关注"],
    }


# ==================== 质量阈值 ====================

@router.get("/thresholds")
async def get_thresholds(current_user = Depends(get_current_user)):
    """获取质量阈值"""
    agent = GrowthQualityAgent()
    return {
        "success": True,
        "min_growth_score": agent.MIN_GROWTH_SCORE,
        "hook_threshold": 70,
        "high_retention_threshold": 85,
        "commercial_position_threshold": 0.3,
    }
