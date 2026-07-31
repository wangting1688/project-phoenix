from sqlalchemy import Column, String, Integer, Text, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.base_model import BaseModel


class PlatformAccount(Base, BaseModel):
    """平台账号画像：管理各平台账号信息和授权"""
    __tablename__ = "platform_accounts"

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    # 平台信息
    platform = Column(String(50), nullable=False, index=True)
    # douyin / video_channel / xiaohongshu / kuaishou / bilibili

    account_name = Column(String(200), nullable=False)
    account_id = Column(String(200), nullable=True)
    account_url = Column(String(500), nullable=True)

    # 授权信息（加密存储）
    auth_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)

    # 账号状态
    status = Column(String(20), default="active", index=True)
    # active / expired / disabled / error

    # 粉丝画像（自动采集）
    follower_count = Column(Integer, default=0)
    follower_gender_ratio = Column(JSON, nullable=True)  # {"male": 0.3, "female": 0.7}
    follower_age_distribution = Column(JSON, nullable=True)  # {"18-24": 0.2, "25-34": 0.5}
    follower_region_top = Column(JSON, nullable=True)  # ["广东", "浙江", "江苏"]

    # 内容风格画像
    content_style = Column(String(50), nullable=True)
    # 故事型 / 知识型 / 测评型 / 搞笑型 / 剧情型
    avg_video_duration = Column(Integer, nullable=True)  # 平均视频时长（秒）
    best_publish_time = Column(JSON, nullable=True)  # ["07:00", "12:00", "19:00"]

    # 最近表现
    last_7d_plays = Column(Integer, default=0)
    last_7d_likes = Column(Integer, default=0)
    last_7d_comments = Column(Integer, default=0)
    last_7d_shares = Column(Integer, default=0)
    avg_completion_rate = Column(Integer, nullable=True)  # 平均完播率（百分比）

    # 平台策略配置
    strategy_config = Column(JSON, nullable=True)
    # {"auto_publish": true, "best_tags": ["健康", "养生"], "hook_style": "冲突开场"}

    # 数据同步时间
    last_sync_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="platform_accounts")
    publish_tasks = relationship("PublishTask", back_populates="platform_account")
