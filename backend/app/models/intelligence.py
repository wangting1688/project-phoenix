from sqlalchemy import Column, String, Integer, Text, ForeignKey, JSON, DECIMAL
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.base_model import BaseModel


class CreatorProfile(Base, BaseModel):
    """主播画像表 - 内容智能引擎核心"""
    __tablename__ = "creator_profiles"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    region = Column(String(100), nullable=True)
    background = Column(Text, nullable=True)

    # 表达风格
    style = Column(String(100), nullable=True)  # 温暖陪伴型/专业科普型...
    speech_speed = Column(String(50), default="medium")  # slow/medium/fast
    emotion_level = Column(String(50), default="medium")  # low/medium/high

    # 擅长领域
    good_topics = Column(JSON, nullable=True)  # ["睡眠","女性健康","养生"]

    # 粉丝画像
    fan_age_range = Column(String(50), nullable=True)
    fan_gender_ratio = Column(String(50), nullable=True)  # "70%女,30%男"
    fan_interests = Column(JSON, nullable=True)

    # AI学习记忆
    content_preferences = Column(JSON, nullable=True)
    style_preferences = Column(JSON, nullable=True)

    # 评分
    overall_score = Column(DECIMAL(5, 2), default=50.0)


class ContentTopic(Base, BaseModel):
    """内容主题库"""
    __tablename__ = "content_topics"

    title = Column(String(500), nullable=False)
    category = Column(String(100), index=True, nullable=False)
    sub_tags = Column(JSON, nullable=True)  # ["睡眠","压力","女性"]
    pain_point = Column(Text, nullable=True)
    consultation_score = Column(Integer, default=50)  # 咨询潜力 0-100
    trend_score = Column(Integer, default=50)  # 热点指数 0-100
    status = Column(String(50), default="active", index=True)


class SuccessCase(Base, BaseModel):
    """成功案例库"""
    __tablename__ = "success_cases"

    topic = Column(String(500), nullable=False)
    creator_style = Column(String(100), nullable=True)  # 主播类型
    structure = Column(Text, nullable=True)  # 爆款结构
    opening = Column(Text, nullable=True)  # 开头
    emotion = Column(String(100), nullable=True)
    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    consultation_count = Column(Integer, default=0)
    tags = Column(JSON, nullable=True)


class RecommendationLog(Base, BaseModel):
    """推荐记录表"""
    __tablename__ = "recommendation_logs"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    topic_id = Column(Integer, ForeignKey("content_topics.id"), nullable=True)
    level = Column(String(10), nullable=False)  # A/B/C/D/E
    score = Column(DECIMAL(5, 2), default=0)
    reason = Column(Text, nullable=True)
    selected = Column(Integer, default=0)  # 是否被选中 0/1
