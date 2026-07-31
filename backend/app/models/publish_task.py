from sqlalchemy import Column, String, Integer, Text, JSON, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.base_model import BaseModel


class PublishTask(Base, BaseModel):
    """发布任务：视频分发到各平台的任务管理"""
    __tablename__ = "publish_tasks"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    # 关联内容
    video_project_id = Column(Integer, ForeignKey("video_projects.id"), nullable=True)
    content_title = Column(String(200), nullable=False)
    content_description = Column(Text, nullable=True)

    # 发布目标
    platform_account_id = Column(Integer, ForeignKey("platform_accounts.id"), nullable=False)
    platform = Column(String(50), nullable=False, index=True)

    # 发布计划
    scheduled_at = Column(DateTime, nullable=True)  # 计划发布时间
    published_at = Column(DateTime, nullable=True)  # 实际发布时间

    # 任务状态
    status = Column(String(30), default="draft", index=True)
    # draft / pending / queued / publishing / published / failed / cancelled / collecting / reviewed

    # 发布内容
    video_url = Column(String(500), nullable=True)
    cover_url = Column(String(500), nullable=True)
    tags = Column(JSON, nullable=True)
    # ["健康", "养生", "青汁"]
    category = Column(String(50), nullable=True)

    # 平台返回信息
    platform_post_id = Column(String(200), nullable=True)
    platform_post_url = Column(String(500), nullable=True)
    publish_error = Column(Text, nullable=True)

    # 回流数据（发布后自动采集）
    metrics_collected_at = Column(DateTime, nullable=True)
    play_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    collect_count = Column(Integer, default=0)
    follower_gained = Column(Integer, default=0)
    completion_rate = Column(Float, nullable=True)  # 完播率
    ctr = Column(Float, nullable=True)  # 点击率

    # 增长分析结果
    growth_insight = Column(JSON, nullable=True)
    # {"attribution": "hook_pattern", "score": 8.5, "suggestion": "..."}

    # 是否已进入 Growth Graph
    processed_by_graph = Column(Integer, default=0)  # 0=未处理, 1=已处理

    # 人工审核
    review_status = Column(String(20), default="auto", nullable=True)
    # auto / pending / approved / rejected
    review_comment = Column(Text, nullable=True)

    platform_account = relationship("PlatformAccount", back_populates="publish_tasks")
    user = relationship("User", back_populates="publish_tasks")
