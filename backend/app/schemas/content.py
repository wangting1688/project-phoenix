from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class ContentProjectCreate(BaseModel):
    source_type: str = Field(..., description="recommend / viral_analysis / custom")
    topic: str
    category: Optional[str] = None


class ContentProjectResponse(BaseModel):
    id: int
    user_id: int
    source_type: str
    topic: Optional[str] = None
    category: Optional[str] = None
    status: str
    workflow_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScriptResponse(BaseModel):
    id: int
    project_id: int
    type: str
    content: str
    version: int
    score: Optional[Decimal] = None

    class Config:
        from_attributes = True


class VideoResponse(BaseModel):
    id: int
    project_id: int
    url: Optional[str] = None
    cover_url: Optional[str] = None
    duration: Optional[int] = None
    status: str

    class Config:
        from_attributes = True


class TaskStatusResponse(BaseModel):
    task_id: int
    status: str
    progress: int
    current_step: Optional[str] = None


class TaskResultResponse(BaseModel):
    project_id: int
    scripts: List[ScriptResponse] = []
    video: Optional[VideoResponse] = None
