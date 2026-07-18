from sqlalchemy import Column, Integer, String, Text, Float

from app.core.database import Base
from app.core.base_model import BaseModel


class ContentOpportunity(Base, BaseModel):
    """内容机会表 - AI内容中心核心"""
    __tablename__ = "content_opportunities"

    title = Column(String(500), nullable=False)
    category = Column(String(100), index=True, nullable=False)
    subcategory = Column(String(100), nullable=True)
    opening = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    pain_point = Column(Text, nullable=True)
    recommend_reason = Column(Text, nullable=True)
    trend_score = Column(Integer, default=50)
    consult_score = Column(Integer, default=50)
    creator_match = Column(Integer, default=50)
    original_score = Column(Integer, default=50)
    final_score = Column(Float, default=50.0)
    status = Column(String(20), default="active", index=True)
    source = Column(String(50), nullable=True)
    source_url = Column(String(500), nullable=True)

    def __repr__(self):
        return f"<ContentOpportunity(title={self.title[:30]}, final_score={self.final_score})>"