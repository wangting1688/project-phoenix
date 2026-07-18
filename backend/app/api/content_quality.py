"""
AI内容质量控制 API

提供内容审核、优化、结果查询接口
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from app.api.deps import get_current_user
from app.services.content_quality_service import ContentQualityService

router = APIRouter(prefix="/quality", tags=["AI内容质量控制"])


class ReviewRequest(BaseModel):
    """审核请求"""
    content_type: str  # opportunity / script / video
    content_id: int
    content_text: str


class OptimizeRequest(BaseModel):
    """优化请求"""
    content_type: str
    content_id: int
    content_text: str


@router.post("/review")
async def review_content(
    request: ReviewRequest,
    current_user = Depends(get_current_user)
):
    """
    对内容进行全面审核

    四大维度审核：
    1. 健康合规 - 确保不涉及医疗违规
    2. 营销自然度 - 确保不像硬广告
    3. 爆款质量 - 检查开头、节奏、互动
    4. 咨询转化 - 检查自然引导私信
    """
    service = ContentQualityService()
    try:
        review = service.review_content(
            user_id=current_user.id,
            content_type=request.content_type,
            content_id=request.content_id,
            content_text=request.content_text,
        )
        return {
            "success": True,
            "data": service._format_review_result(review),
        }
    finally:
        service.close()


@router.get("/review/{review_id}")
async def get_review(
    review_id: int,
    current_user = Depends(get_current_user)
):
    """获取审核结果"""
    service = ContentQualityService()
    try:
        result = service.get_review_result(review_id)
        if not result:
            raise HTTPException(status_code=404, detail="审核记录不存在")
        return {"success": True, "data": result}
    finally:
        service.close()


@router.get("/content/{content_type}/{content_id}")
async def get_content_review(
    content_type: str,
    content_id: int,
    current_user = Depends(get_current_user)
):
    """根据内容获取最新审核结果"""
    service = ContentQualityService()
    try:
        result = service.get_review_by_content(content_type, content_id)
        if not result:
            raise HTTPException(status_code=404, detail="未找到该内容的审核记录")
        return {"success": True, "data": result}
    finally:
        service.close()


@router.post("/optimize")
async def optimize_content(
    request: OptimizeRequest,
    current_user = Depends(get_current_user)
):
    """
    基于审核结果优化内容

    自动应用修复建议，返回优化后的内容
    """
    service = ContentQualityService()
    try:
        result = service.optimize_content(
            content_type=request.content_type,
            content_id=request.content_id,
            content_text=request.content_text,
        )
        return {"success": True, "data": result}
    finally:
        service.close()


@router.post("/quick-check")
async def quick_check(
    request: ReviewRequest,
    current_user = Depends(get_current_user)
):
    """
    快速健康检查

    只检查健康合规和营销自然度，适合快速预审
    """
    from app.services.quality_agents import (
        HealthComplianceAgent,
        MarketingRiskAgent,
    )

    health_agent = HealthComplianceAgent()
    marketing_agent = MarketingRiskAgent()

    health_result = health_agent.analyze(request.content_text)
    marketing_result = marketing_agent.analyze(request.content_text)

    is_safe = (
        health_result["score"] >= 80 and
        marketing_result["score"] >= 80
    )

    return {
        "success": True,
        "data": {
            "is_safe": is_safe,
            "health_score": health_result["score"],
            "marketing_score": marketing_result["score"],
            "issues": health_result.get("issues", []) + marketing_result.get("hard_sells", []),
            "suggestions": health_result.get("suggestions", []) + marketing_result.get("suggestions", []),
        },
    }