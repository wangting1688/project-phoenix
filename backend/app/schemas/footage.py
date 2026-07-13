from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class FootageCategoryCreate(BaseModel):
    name: str = Field(..., max_length=100)
    type: str = Field("life", description="life/health/emotion/work")
    icon: Optional[str] = None


class FootageCategoryResponse(BaseModel):
    id: int
    user_id: int
    name: str
    type: str
    icon: Optional[str] = None

    class Config:
        from_attributes = True


class FootageUploadResponse(BaseModel):
    id: int
    filename: str
    file_path: str
    duration: int
    status: str

    class Config:
        from_attributes = True


class FootageResponse(BaseModel):
    id: int
    category_id: Optional[int] = None
    filename: str
    thumbnail: Optional[str] = None
    duration: int
    scene: Optional[str] = None
    emotion: Optional[str] = None
    action: Optional[str] = None
    topics: Optional[list] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class FootageUpdate(BaseModel):
    category_id: Optional[int] = None
    scene: Optional[str] = None
    emotion: Optional[str] = None
    action: Optional[str] = None
    topics: Optional[List[str]] = None


class CreatorProfileResponse(BaseModel):
    id: int
    style: Optional[str] = None
    speech_speed: Optional[str] = None
    good_topics: Optional[list] = None
    fan_age_range: Optional[str] = None
    overall_score: Optional[float] = None

    class Config:
        from_attributes = True


class CreatorProfileUpdate(BaseModel):
    age: Optional[int] = None
    gender: Optional[str] = None
    region: Optional[str] = None
    style: Optional[str] = None
    speech_speed: Optional[str] = None
    good_topics: Optional[List[str]] = None


class RecommendationItem(BaseModel):
    level: str  # A/B/C/D/E
    title: str
    category: str
    reason: str
    score: float
    topic: str


class RecommendationResponse(BaseModel):
    items: List[RecommendationItem]
    updated_at: str
