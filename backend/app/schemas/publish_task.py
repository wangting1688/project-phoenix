from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime


class PublishTaskBase(BaseModel):
    content_title: str = Field(..., description="内容标题")
    content_description: Optional[str] = None
    platform_account_id: int
    platform: str = Field(..., description="平台类型")
    scheduled_at: Optional[datetime] = None
    tags: Optional[List[str]] = None
    category: Optional[str] = None
    video_url: Optional[str] = None
    cover_url: Optional[str] = None


class PublishTaskCreate(PublishTaskBase):
    video_project_id: Optional[int] = None


class PublishTaskUpdate(BaseModel):
    content_title: Optional[str] = None
    content_description: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None
    review_status: Optional[str] = None
    review_comment: Optional[str] = None


class PublishTaskMetrics(BaseModel):
    play_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    collect_count: int = 0
    follower_gained: int = 0
    completion_rate: Optional[float] = None
    ctr: Optional[float] = None


class PublishTaskResponse(PublishTaskBase):
    id: int
    user_id: int
    video_project_id: Optional[int]
    status: str
    published_at: Optional[datetime]
    platform_post_id: Optional[str]
    platform_post_url: Optional[str]
    publish_error: Optional[str]
    metrics_collected_at: Optional[datetime]
    play_count: int
    like_count: int
    comment_count: int
    share_count: int
    collect_count: int
    follower_gained: int
    completion_rate: Optional[float]
    ctr: Optional[float]
    growth_insight: Optional[Dict[str, Any]]
    processed_by_graph: int
    review_status: Optional[str]
    review_comment: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PublishTaskListResponse(BaseModel):
    items: List[PublishTaskResponse]
    total: int
