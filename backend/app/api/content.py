from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User
from app.schemas import ApiResponse

router = APIRouter(prefix="/content", tags=["内容推荐"])


@router.get("/recommendations", response_model=ApiResponse[List[dict]])
def get_recommendations(
    category: str = Query(None),
    current_user: User = Depends(get_current_user),
):
    recommendations = [
        {
            "level": "A",
            "title": "睡眠成为近期热门话题",
            "reason": "45岁女性对睡眠质量的关注增长明显，你过去情绪类视频咨询率较高",
            "topic": "睡眠不好怎么办",
        },
        {
            "level": "B",
            "title": "肠道健康咨询潜力高",
            "reason": "最近肠道健康相关内容转化率提升，适合你的受众群体",
            "topic": "肠胃不好怎么调理",
        },
        {
            "level": "C",
            "title": "更年期话题容易涨粉",
            "reason": "更年期相关内容互动率高，适合建立专家人设",
            "topic": "更年期怎么调理",
        },
        {
            "level": "D",
            "title": "三伏天养生最新热点",
            "reason": "现在正值三伏天，养生话题搜索量激增",
            "topic": "三伏天怎么养生",
        },
        {
            "level": "E",
            "title": "你的历史高表现内容",
            "reason": "你之前发布的气血不足视频咨询率最高，可以再创作类似主题",
            "topic": "气血不足怎么补",
        },
    ]
    return ApiResponse(data=recommendations)


@router.get("/categories", response_model=ApiResponse[List[str]])
def get_categories(current_user: User = Depends(get_current_user)):
    categories = [
        "健康知识",
        "养生",
        "情绪健康",
        "家庭关系",
        "生活方式",
        "美丽管理",
        "美食",
        "热点话题",
    ]
    return ApiResponse(data=categories)
