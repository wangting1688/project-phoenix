"""
主播 AI 素材表 (creator_assets)

历史遗留说明：该表已存在于生产库并被多处业务代码 (asset_analysis_service /
asset_collection_service / asset_segment_service / asset_intelligence API) 通过
`from app.models import CreatorAsset` 引用，但此前一直缺少 ORM 定义，只依赖
`Base.metadata.create_all` 兜底建表。本文件把字段完全对齐生产库现状，作为唯一来源。
"""

from sqlalchemy import Column, String, Integer, Float, ForeignKey, JSON

from app.core.database import Base
from app.core.base_model import BaseModel


class CreatorAsset(Base, BaseModel):
    __tablename__ = "creator_assets"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    name = Column(String(200), nullable=False)
    type = Column(String(50), index=True, nullable=False)
    url = Column(String(500), nullable=False)

    file_size = Column(Integer, nullable=True)
    duration = Column(Float, nullable=True)
    tags = Column(JSON, nullable=True)

    # AI 分析标签
    scene = Column(String(100), nullable=True)
    emotion = Column(String(50), nullable=True)
    ai_tags = Column(JSON, nullable=True)

    thumbnail_url = Column(String(500), nullable=True)
    usage_count = Column(Integer, nullable=True)
    last_used_at = Column(String(50), nullable=True)

    asset_role = Column(String(50), index=True, nullable=True)
