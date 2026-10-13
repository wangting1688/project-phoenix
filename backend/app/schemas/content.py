from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class ContentProjectCreate(BaseModel):
    source_type: str = Field(..., description="recommend / viral_analysis / custom")
    topic: str
    category: Optional[str] = None
    platform: Optional[str] = "抖音"
    persona: Optional[str] = None


class ContentProjectResponse(BaseModel):
    id: int
    user_id: int
    source_type: str
    topic: Optional[str] = None
    category: Optional[str] = None
    status: str
    workflow_status: Optional[str] = None
    # 该项目的主创作任务 id。结果页靠它接入任务轮询 —— 否则从作品页
    # 「查看进度」跳进来时拿不到任务，进度条永远停在 0%。
    task_id: Optional[int] = None
    video_url: Optional[str] = None
    video_duration: Optional[int] = None
    video_status: Optional[str] = None
    cover_url: Optional[str] = None
    display_status: Optional[str] = None
    error_message: Optional[str] = None
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
    meta: Optional[dict] = None

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
    error_message: Optional[str] = None
    # 排队信息：GPU worker 串行执行（max_workers=1），并发提交会排队。
    # 不给反馈的话用户只能盯着不动的进度条，误以为卡死。
    queue_position: Optional[int] = None      # 0=正在执行，>0=前面还有几个
    queue_total: Optional[int] = None         # 当前未完成任务总数
    eta_seconds: Optional[int] = None         # 预计还需等待（秒）


class TaskResultResponse(BaseModel):
    project_id: int
    scripts: List[ScriptResponse] = []
    video: Optional[VideoResponse] = None
