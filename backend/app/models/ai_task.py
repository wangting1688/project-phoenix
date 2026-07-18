from sqlalchemy import Column, Integer, String, Text, Float, JSON, ForeignKey

from app.core.database import Base
from app.core.base_model import BaseModel


class AITask(Base, BaseModel):
    __tablename__ = "ai_tasks"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    project_id = Column(Integer, index=True)
    workflow = Column(String(50), index=True)
    agent = Column(String(50), index=True)
    model = Column(String(50), nullable=True)
    status = Column(String(20), default="pending", index=True)
    input = Column(JSON)
    output = Column(JSON)
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    duration = Column(Float, default=0.0)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    def __repr__(self):
        return f"<AITask(project_id={self.project_id}, agent={self.agent}, status={self.status})>"