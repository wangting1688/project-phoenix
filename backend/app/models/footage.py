from sqlalchemy import Column, String, Integer, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.base_model import BaseModel


class FootageCategory(Base, BaseModel):
    """素材分类表"""
    __tablename__ = "footage_categories"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    name = Column(String(100), nullable=False)
    type = Column(String(50), default="life")  # life/health/emotion/work
    icon = Column(String(200), nullable=True)

    footages = relationship("Footage", back_populates="category", cascade="all, delete-orphan")


class Footage(Base, BaseModel):
    """真人素材表"""
    __tablename__ = "footages"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    category_id = Column(Integer, ForeignKey("footage_categories.id"), index=True, nullable=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    thumbnail = Column(String(500), nullable=True)
    duration = Column(Integer, default=0)  # 秒
    resolution = Column(String(50), nullable=True)
    file_size = Column(Integer, default=0)  # 字节

    # AI分析标签
    scene = Column(String(100), nullable=True)  # 厨房/卧室/客厅...
    emotion = Column(String(100), nullable=True)  # 温暖/思考/微笑...
    action = Column(String(100), nullable=True)  # 做饭/喝水/散步...
    topics = Column(JSON, nullable=True)  # ["家庭","健康","生活"]

    status = Column(String(50), default="ready", index=True)  # ready/analyzing/error

    category = relationship("FootageCategory", back_populates="footages")

    # ===== 素材来源 =====
    # user_upload: 用户上传（默认）
    # system_demo: 系统演示素材
    # ai_generated: AI 生成素材
    # partner_provided: 合作方提供素材
    source_type = Column(String(30), default="user_upload", server_default="user_upload", index=True, nullable=False)
    source_ref = Column(String(128), nullable=True, index=True)
