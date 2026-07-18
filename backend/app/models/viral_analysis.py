from sqlalchemy import Column, Integer, String, Text, JSON, ForeignKey

from app.core.database import Base
from app.core.base_model import BaseModel


class ViralAnalysisSession(Base, BaseModel):
    """爆款分析会话表 - 追踪整个分析流程"""
    __tablename__ = "viral_analysis_sessions"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    video_url = Column(String(500), nullable=False)
    platform = Column(String(50), nullable=True)
    original_data = Column(JSON, nullable=True)
    analysis_result = Column(JSON, nullable=True)
    opportunity_id = Column(Integer, ForeignKey("content_opportunities.id"), nullable=True)
    status = Column(String(50), default="pending", index=True)
    creator_match_score = Column(Integer, default=0)

    def __repr__(self):
        return f"<ViralAnalysisSession(user_id={self.user_id}, status={self.status})>"


class ViralPattern(Base, BaseModel):
    """爆款规律表 - 记录成功模式，供AI学习"""
    __tablename__ = "viral_patterns"

    hook_type = Column(String(100), index=True)
    audience = Column(String(100), index=True)
    category = Column(String(100), index=True)
    conversion_level = Column(String(20), default="medium")
    pattern_description = Column(Text, nullable=True)
    examples_count = Column(Integer, default=0)
    success_rate = Column(Integer, default=0)
    tags = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<ViralPattern(hook_type={self.hook_type}, category={self.category})>"