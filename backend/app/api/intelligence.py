from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User
from app.services.intelligence_service import intelligence_engine
from app.schemas.footage import (
    CreatorProfileResponse,
    CreatorProfileUpdate,
    RecommendationItem,
)
from app.schemas.common import ApiResponse
from datetime import datetime

router = APIRouter(prefix="/intelligence", tags=["内容智能引擎"])


@router.get("/recommendations", response_model=ApiResponse[List[RecommendationItem]])
def get_recommendations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取A-E五级推荐"""
    recs = intelligence_engine.get_recommendations(db, current_user.id)
    return ApiResponse(data=recs)


@router.get("/profile", response_model=ApiResponse[CreatorProfileResponse])
def get_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取主播画像"""
    profile = intelligence_engine.get_or_create_profile(db, current_user.id)
    return ApiResponse(data=CreatorProfileResponse.model_validate(profile))


@router.put("/profile", response_model=ApiResponse[CreatorProfileResponse])
def update_profile(
    update_in: CreatorProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新主播画像"""
    profile = intelligence_engine.get_or_create_profile(db, current_user.id)

    if update_in.age is not None:
        profile.age = update_in.age
    if update_in.gender is not None:
        profile.gender = update_in.gender
    if update_in.region is not None:
        profile.region = update_in.region
    if update_in.style is not None:
        profile.style = update_in.style
    if update_in.speech_speed is not None:
        profile.speech_speed = update_in.speech_speed
    if update_in.good_topics is not None:
        profile.good_topics = update_in.good_topics

    db.commit()
    db.refresh(profile)
    return ApiResponse(data=CreatorProfileResponse.model_validate(profile))


@router.get("/tags", response_model=ApiResponse[dict])
def get_content_tags(
    current_user: User = Depends(get_current_user),
):
    """获取内容标签体系"""
    tags = {
        "categories": [
            {"name": "健康知识", "sub_tags": ["睡眠", "肠道", "营养", "运动", "压力"]},
            {"name": "养生", "sub_tags": ["三伏天", "湿气", "泡脚", "茶饮", "节气"]},
            {"name": "情绪健康", "sub_tags": ["焦虑", "关系", "孤独", "女性成长"]},
            {"name": "家庭", "sub_tags": ["亲子", "婚姻", "婆媳", "家庭沟通"]},
            {"name": "生活", "sub_tags": ["生活方式", "时间管理", "自我提升"]},
            {"name": "美丽管理", "sub_tags": ["抗衰", "护肤", "身材管理"]},
            {"name": "美食", "sub_tags": ["养生餐", "早餐", "家常菜"]},
            {"name": "热点话题", "sub_tags": ["季节", "节日", "社会热点"]},
        ]
    }
    return ApiResponse(data=tags)
