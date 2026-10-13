from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, JSON, DECIMAL
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.base_model import BaseModel


class User(Base, BaseModel):
    __tablename__ = "users"

    # SaaS 租户关联
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True, comment="所属用户账号（null=总部管理员）")

    username = Column(String(50), unique=True, index=True, nullable=True)
    phone = Column(String(20), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    nickname = Column(String(100), nullable=True)
    avatar = Column(String(500), nullable=True)
    # 微信登录：openid 唯一，未绑定手机号前 phone 可为空
    openid = Column(String(64), unique=True, index=True, nullable=True)
    unionid = Column(String(64), index=True, nullable=True)
    wechat_nickname = Column(String(100), nullable=True)
    wechat_avatar = Column(String(500), nullable=True)
    # role: super_admin=总部管理员, tenant_admin=用户管理员, anchor=主播
    role = Column(String(20), default="anchor", index=True)
    status = Column(Integer, default=1, index=True)

    # 关联
    tenant = relationship("Tenant", back_populates="users")
    projects = relationship("ContentProject", back_populates="user")
    memory = relationship("UserMemory", back_populates="user")
    platform_accounts = relationship("PlatformAccount", back_populates="user")
    publish_tasks = relationship("PublishTask", back_populates="user")
