"""
渠道商（Tenant）模型

SaaS 模式核心：每个渠道商是一个独立租户，数据相互隔离。
总部管理员创建渠道商账号，设置使用期限。
"""

from sqlalchemy import Column, String, Integer, DateTime, Text, JSON
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.base_model import BaseModel


class Tenant(Base, BaseModel):
    """渠道商：SaaS 租户"""
    __tablename__ = "tenants"

    # 渠道商基本信息
    name = Column(String(200), nullable=False, comment="渠道商名称")
    code = Column(String(50), unique=True, index=True, nullable=False, comment="渠道商编码（唯一标识）")
    contact_name = Column(String(100), nullable=True, comment="联系人姓名")
    contact_phone = Column(String(20), nullable=True, comment="联系电话")

    # 登录凭证（总部管理员分配）
    account = Column(String(100), unique=True, index=True, nullable=False, comment="登录账号")
    password_hash = Column(String(255), nullable=False, comment="登录密码哈希")

    # 使用期限
    expires_at = Column(DateTime, nullable=True, comment="使用到期时间（null=永久）")
    status = Column(Integer, default=1, index=True, comment="状态：1=启用, 0=停用, -1=过期")

    # 配额
    max_users = Column(Integer, default=5, comment="最大用户数")
    max_video_projects = Column(Integer, default=50, comment="最大视频项目数")

    # 渠道商配置
    config = Column(JSON, nullable=True, comment="渠道商配置（平台权限、功能开关等）")
    # 例: {"platforms": ["douyin", "video_channel"], "features": ["publish", "growth_graph"]}

    # 关联
    users = relationship("User", back_populates="tenant")

    def is_active(self) -> bool:
        """检查渠道商是否可用"""
        if self.status != 1:
            return False
        if self.expires_at is not None:
            from datetime import datetime
            if datetime.utcnow() > self.expires_at:
                return False
        return True
