from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from app.api.deps import get_current_user
from app.core.database import SessionLocal
from app.models import CreatorProfile, CreatorPreference

router = APIRouter(prefix="/creator-profile", tags=["主播画像"])


class ProfileUpdateRequest(BaseModel):
    age: Optional[int] = None
    gender: Optional[str] = None
    region: Optional[str] = None
    background: Optional[str] = None
    style: Optional[str] = None
    speech_speed: Optional[str] = None
    emotion_level: Optional[str] = None
    content_style: Optional[Dict[str, Any]] = None
    speaking_style: Optional[Dict[str, Any]] = None
    camera_style: Optional[str] = None
    editing_level: Optional[str] = None
    good_topics: Optional[List[str]] = None
    fan_age_range: Optional[str] = None
    fan_gender_ratio: Optional[str] = None
    fan_interests: Optional[List[str]] = None


class PreferenceUpdateRequest(BaseModel):
    category_weights: Optional[Dict[str, float]] = None
    style_weights: Optional[Dict[str, float]] = None
    score_weights: Optional[Dict[str, int]] = None
    preferred_tags: Optional[List[str]] = None
    avoided_tags: Optional[List[str]] = None


@router.get("")
async def get_creator_profile(current_user = Depends(get_current_user)):
    """获取主播画像"""
    db = SessionLocal()
    try:
        profile = db.query(CreatorProfile).filter(
            CreatorProfile.user_id == current_user.id
        ).first()

        if not profile:
            profile = CreatorProfile(user_id=current_user.id)
            db.add(profile)
            db.commit()
            db.refresh(profile)

        preference = db.query(CreatorPreference).filter(
            CreatorPreference.user_id == current_user.id
        ).first()

        return {
            "success": True,
            "data": {
                "profile": _format_profile(profile),
                "preference": _format_preference(preference) if preference else None,
            }
        }
    finally:
        db.close()


@router.put("")
async def update_creator_profile(
    request: ProfileUpdateRequest,
    current_user = Depends(get_current_user)
):
    """更新主播画像"""
    db = SessionLocal()
    try:
        profile = db.query(CreatorProfile).filter(
            CreatorProfile.user_id == current_user.id
        ).first()

        if not profile:
            profile = CreatorProfile(user_id=current_user.id)
            db.add(profile)

        if request.age is not None:
            profile.age = request.age
        if request.gender is not None:
            profile.gender = request.gender
        if request.region is not None:
            profile.region = request.region
        if request.background is not None:
            profile.background = request.background
        if request.style is not None:
            profile.style = request.style
        if request.speech_speed is not None:
            profile.speech_speed = request.speech_speed
        if request.emotion_level is not None:
            profile.emotion_level = request.emotion_level
        if request.content_style is not None:
            profile.content_style = request.content_style
        if request.speaking_style is not None:
            profile.speaking_style = request.speaking_style
        if request.camera_style is not None:
            profile.camera_style = request.camera_style
        if request.editing_level is not None:
            profile.editing_level = request.editing_level
        if request.good_topics is not None:
            profile.good_topics = request.good_topics
        if request.fan_age_range is not None:
            profile.fan_age_range = request.fan_age_range
        if request.fan_gender_ratio is not None:
            profile.fan_gender_ratio = request.fan_gender_ratio
        if request.fan_interests is not None:
            profile.fan_interests = request.fan_interests

        db.commit()
        db.refresh(profile)

        return {"success": True, "data": _format_profile(profile)}
    finally:
        db.close()


@router.get("/preference")
async def get_creator_preference(current_user = Depends(get_current_user)):
    """获取主播推荐偏好"""
    db = SessionLocal()
    try:
        preference = db.query(CreatorPreference).filter(
            CreatorPreference.user_id == current_user.id
        ).first()

        return {
            "success": True,
            "data": _format_preference(preference) if preference else None
        }
    finally:
        db.close()


@router.put("/preference")
async def update_creator_preference(
    request: PreferenceUpdateRequest,
    current_user = Depends(get_current_user)
):
    """更新主播推荐偏好"""
    db = SessionLocal()
    try:
        preference = db.query(CreatorPreference).filter(
            CreatorPreference.user_id == current_user.id
        ).first()

        if not preference:
            preference = CreatorPreference(user_id=current_user.id)
            db.add(preference)

        if request.category_weights is not None:
            preference.category_weights = request.category_weights
        if request.style_weights is not None:
            preference.style_weights = request.style_weights
        if request.score_weights is not None:
            preference.score_weights = request.score_weights
        if request.preferred_tags is not None:
            preference.preferred_tags = request.preferred_tags
        if request.avoided_tags is not None:
            preference.avoided_tags = request.avoided_tags

        db.commit()
        db.refresh(preference)

        return {"success": True, "data": _format_preference(preference)}
    finally:
        db.close()


@router.post("/diagnose")
async def diagnose_account(current_user = Depends(get_current_user)):
    """AI账号诊断 - 生成主播画像分析"""
    db = SessionLocal()
    try:
        profile = db.query(CreatorProfile).filter(
            CreatorProfile.user_id == current_user.id
        ).first()

        if not profile:
            profile = CreatorProfile(user_id=current_user.id)
            db.add(profile)
            db.commit()
            db.refresh(profile)

        diagnosis = _generate_mock_diagnosis(profile)

        return {"success": True, "data": diagnosis}
    finally:
        db.close()


def _format_profile(profile: CreatorProfile) -> Dict[str, Any]:
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "age": profile.age,
        "gender": profile.gender,
        "region": profile.region,
        "background": profile.background,
        "style": profile.style,
        "speech_speed": profile.speech_speed,
        "emotion_level": profile.emotion_level,
        "content_style": profile.content_style,
        "speaking_style": profile.speaking_style,
        "camera_style": profile.camera_style,
        "editing_level": profile.editing_level,
        "good_topics": profile.good_topics or [],
        "category_distribution": profile.category_distribution or {},
        "fan_age_range": profile.fan_age_range,
        "fan_gender_ratio": profile.fan_gender_ratio,
        "fan_interests": profile.fan_interests or [],
        "audience_profile": profile.audience_profile or {},
        "account_type": profile.account_type,
        "growth_stage": profile.growth_stage,
        "overall_score": float(profile.overall_score) if profile.overall_score else 0,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
    }


def _format_preference(preference: CreatorPreference) -> Dict[str, Any]:
    return {
        "id": preference.id,
        "user_id": preference.user_id,
        "category_weights": preference.category_weights or {},
        "style_weights": preference.style_weights or {},
        "score_weights": preference.score_weights or {},
        "preferred_tags": preference.preferred_tags or [],
        "avoided_tags": preference.avoided_tags or [],
        "updated_at": preference.updated_at.isoformat() if preference.updated_at else None,
    }


def _generate_mock_diagnosis(profile: CreatorProfile) -> Dict[str, Any]:
    return {
        "account_type": "咨询型" if profile.account_type == "consultation" else "涨粉型",
        "growth_stage": "新手期",
        "overall_score": 72,
        "strengths": [
            "内容方向明确，专注健康领域",
            "有稳定的内容产出",
            "粉丝互动基础不错",
        ],
        "improvements": [
            "建议增加更多情感共鸣元素",
            "可以优化开头钩子设计",
            "建议丰富内容形式",
        ],
        "content_style": {
            "primary_style": "知识科普型",
            "tone": "专业",
            "pace": "中等",
        },
        "category_distribution": {
            "健康知识": 52,
            "养生保健": 28,
            "情感心理": 15,
            "其他": 5,
        },
        "audience_insights": {
            "primary_age": "35-55岁",
            "primary_gender": "女性为主",
            "top_interests": ["睡眠健康", "日常养生", "情绪管理"],
        },
        "recommendations": [
            "建议重点发展睡眠健康内容，咨询潜力最高",
            "可以尝试加入更多真实案例故事",
            "建议优化视频标题和封面设计",
        ],
    }