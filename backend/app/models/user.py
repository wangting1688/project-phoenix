from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, JSON, DECIMAL
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.base_model import BaseModel


class User(Base, BaseModel):
    __tablename__ = "users"

    username = Column(String(50), unique=True, index=True, nullable=True)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    nickname = Column(String(100), nullable=True)
    avatar = Column(String(500), nullable=True)
    role = Column(String(20), default="anchor", index=True)
    status = Column(Integer, default=1, index=True)

    projects = relationship("ContentProject", back_populates="user")
    memory = relationship("UserMemory", back_populates="user")
