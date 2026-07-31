from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime


class PlatformAccountBase(BaseModel):
    platform: str = Field(..., description="平台类型: douyin/video_channel/xiaohongshu/kuaishou/bilibili")
    account_name: str = Field(..., description="账号名称")
    account_id: Optional[str] = None
    account_url: Optional[str] = None
    content_style: Optional[str] = None
    strategy_config: Optional[Dict[str, Any]] = None


class PlatformAccountCreate(PlatformAccountBase):
    auth_token: Optional[str] = None
    refresh_token: Optional[str] = None


class PlatformAccountUpdate(BaseModel):
    account_name: Optional[str] = None
    account_url: Optional[str] = None
    content_style: Optional[str] = None
    strategy_config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class PlatformAccountResponse(PlatformAccountBase):
    id: int
    user_id: int
    status: str
    follower_count: int
    content_style: Optional[str]
    avg_video_duration: Optional[int]
    last_7d_plays: int
    last_7d_likes: int
    last_sync_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PlatformAccountListResponse(BaseModel):
    items: List[PlatformAccountResponse]
    total: int
