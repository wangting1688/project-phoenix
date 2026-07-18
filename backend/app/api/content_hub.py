from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.services.recommendation_engine import RecommendationEngine

router = APIRouter(prefix="/content-hub", tags=["AI内容中心"])


class RefreshRequest(BaseModel):
    category: str


@router.get("/recommendations")
async def get_recommendations(
    category: Optional[str] = None,
    count: int = 5,
    current_user = Depends(get_current_user)
):
    """获取AI内容推荐
    
    category:
    - A: 最近最火
    - B: 咨询潜力最高
    - C: 最适合你的
    - D: 新趋势
    - E: 历史爆款
    - 不传: 返回所有分类
    """
    engine = RecommendationEngine(current_user.id)
    try:
        if category:
            result = engine.get_recommendations_by_category(category, count)
        else:
            result = engine.get_all_categories(count)
        return {"success": True, "data": result}
    finally:
        engine.close()


@router.get("/today")
async def get_today_recommendations(
    current_user = Depends(get_current_user)
):
    """今日推荐 - 首页主入口"""
    engine = RecommendationEngine(current_user.id)
    try:
        result = engine.get_all_categories(5)
        return {"success": True, "data": result}
    finally:
        engine.close()


@router.post("/refresh")
async def refresh_recommendations(
    request: RefreshRequest,
    current_user = Depends(get_current_user)
):
    """换一批 - 重新推荐"""
    engine = RecommendationEngine(current_user.id)
    try:
        result = engine.get_recommendations_by_category(
            request.category, 
            count=5
        )
        return {"success": True, "data": result}
    finally:
        engine.close()


@router.get("/weights")
async def get_recommendation_weights(
    current_user = Depends(get_current_user)
):
    """获取当前推荐权重配置"""
    engine = RecommendationEngine(current_user.id)
    try:
        result = engine.get_weight_info()
        return {"success": True, "data": result}
    finally:
        engine.close()