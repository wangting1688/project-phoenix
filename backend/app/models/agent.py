from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean

from app.core.database import Base
from app.core.base_model import BaseModel


class Agent(Base, BaseModel):
    __tablename__ = "agents"

    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    prompt_id = Column(Integer, ForeignKey("prompt_templates.id"), nullable=True)
    version = Column(Integer, default=1)
    enabled = Column(Boolean, default=True)
    priority = Column(Integer, default=100)
    category = Column(String(50), nullable=True)

    def __repr__(self):
        return f"<Agent(name={self.name}, version={self.version}, enabled={self.enabled})>"