from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.base_model import BaseModel


class PromptTemplate(Base, BaseModel):
    __tablename__ = "prompt_templates"

    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(500))
    content = Column(Text, nullable=False)
    status = Column(String(20), default="active")
    version = Column(Integer, default=1)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<PromptTemplate(name={self.name}, version={self.version})>"
