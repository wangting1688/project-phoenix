from sqlalchemy import Column, String, Integer, Text, Boolean, ForeignKey

from app.core.database import Base
from app.core.base_model import BaseModel


class UserNotification(Base, BaseModel):
    __tablename__ = "notifications"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    type = Column(String(30), default="task", nullable=False, index=True)
    title = Column(String(120), nullable=False)
    content = Column(Text, nullable=True)
    link = Column(String(500), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
