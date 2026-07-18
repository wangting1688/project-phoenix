from sqlalchemy import Column, Integer, String, Text, JSON, ForeignKey

from app.core.database import Base
from app.core.base_model import BaseModel


class CreatorAction(Base, BaseModel):
    __tablename__ = "creator_actions"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    action_type = Column(String(50), index=True, nullable=False)
    target_id = Column(Integer, nullable=True)
    target_type = Column(String(50), nullable=True)
    extra_data = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<CreatorAction(user_id={self.user_id}, action_type={self.action_type})>"


class ContentMetrics(Base, BaseModel):
    __tablename__ = "content_metrics"

    video_id = Column(Integer, ForeignKey("videos.id"), index=True, nullable=False)
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    favorites = Column(Integer, default=0)
    private_messages = Column(Integer, default=0)
    orders = Column(Integer, default=0)

    def __repr__(self):
        return f"<ContentMetrics(video_id={self.video_id}, views={self.views})>"