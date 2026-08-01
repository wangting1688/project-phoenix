"""
用户 Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TenantCreate(BaseModel):
    """创建用户"""
    name: str = Field(..., max_length=200, description="用户名称")
    code: Optional[str] = Field(default=None, max_length=50, description="用户编码 (留空则按新增顺序自动生成)")
    account: str = Field(..., max_length=100, description="登录账号")
    password: str = Field(..., min_length=6, max_length=100, description="登录密码")
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    expires_at: Optional[datetime] = None
    max_users: int = Field(default=5, ge=1, le=1000)
    max_video_projects: int = Field(default=50, ge=1, le=10000)
    config: Optional[dict] = None


class TenantUpdate(BaseModel):
    """更新用户"""
    name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    expires_at: Optional[datetime] = None
    max_users: Optional[int] = None
    max_video_projects: Optional[int] = None
    config: Optional[dict] = None
    status: Optional[int] = Field(default=None, ge=-1, le=1)


class TenantResponse(BaseModel):
    """用户响应"""
    id: int
    name: str
    code: str
    account: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    expires_at: Optional[datetime] = None
    status: int
    max_users: int
    max_video_projects: int
    config: Optional[dict] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TenantListResponse(BaseModel):
    items: list[TenantResponse]
    total: int


# ========== 用户登录 ==========
class TenantLogin(BaseModel):
    """用户登录"""
    account: str
    password: str


class TenantLoginResponse(BaseModel):
    """用户登录响应"""
    token: str
    tenant: TenantResponse


# ========== 子账号管理 ==========
class TenantUserCreate(BaseModel):
    """创建子账号"""
    phone: str = Field(..., max_length=20)
    password: str = Field(..., min_length=6, max_length=100)
    nickname: Optional[str] = None
    role: str = Field(default="anchor", description="anchor=主播, tenant_admin=用户管理员")
