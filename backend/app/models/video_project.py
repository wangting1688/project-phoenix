"""
视频项目相关孤儿表：video_projects / content_versions / video_shots

历史遗留说明：这三张表存在于生产库，并被 service / api 通过
`from app.models import VideoProject / ContentVersion / VideoShot` 引用，但此前一直缺少
ORM 定义。本文件把字段完全对齐生产库现状，作为唯一来源。
"""

from sqlalchemy import Column, String, Integer, Float, Text, ForeignKey, JSON

from app.core.database import Base
from app.core.base_model import BaseModel


class VideoProject(Base, BaseModel):
    __tablename__ = "video_projects"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    session_id = Column(Integer, ForeignKey("creation_sessions.id"), index=True, nullable=True)
    title = Column(String(200), nullable=False)
    script_id = Column(Integer, ForeignKey("content_versions.id"), nullable=True)

    duration = Column(Integer, nullable=True)
    style = Column(String(50), nullable=True)
    aspect_ratio = Column(String(20), nullable=True)
    assets = Column(JSON, nullable=True)

    status = Column(String(50), index=True, nullable=True)
    output_url = Column(String(500), nullable=True)
    cover_url = Column(String(500), nullable=True)
    subtitle_url = Column(String(500), nullable=True)
    publish_platforms = Column(JSON, nullable=True)
    published_at = Column(String(50), nullable=True)


class ContentVersion(Base, BaseModel):
    __tablename__ = "content_versions"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    session_id = Column(Integer, ForeignKey("creation_sessions.id"), index=True, nullable=True)

    version_number = Column(Integer, nullable=True)
    content_type = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)

    quality_score = Column(Integer, nullable=True)
    health_score = Column(Integer, nullable=True)
    marketing_score = Column(Integer, nullable=True)
    viral_score = Column(Integer, nullable=True)

    changes = Column(JSON, nullable=True)
    change_reason = Column(String(200), nullable=True)
    created_by = Column(String(50), nullable=True)
    is_final = Column(Integer, nullable=True)


class VideoShot(Base, BaseModel):
    __tablename__ = "video_shots"

    project_id = Column(Integer, ForeignKey("video_projects.id"), index=True, nullable=False)
    shot_number = Column(Integer, nullable=True)
    shot_type = Column(String(50), nullable=False)

    start_time = Column(Float, nullable=True)
    end_time = Column(Float, nullable=True)

    description = Column(Text, nullable=True)
    script_content = Column(Text, nullable=True)
    action = Column(String(200), nullable=True)
    camera_angle = Column(String(50), nullable=True)
    background = Column(String(100), nullable=True)
    recommended_assets = Column(JSON, nullable=True)

    status = Column(String(50), nullable=True)
