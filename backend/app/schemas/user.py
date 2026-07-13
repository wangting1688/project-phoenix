from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    phone: str = Field(..., max_length=20)
    nickname: Optional[str] = None
    avatar: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=100)


class UserLogin(BaseModel):
    phone: str
    password: str


class UserUpdate(BaseModel):
    nickname: Optional[str] = None
    avatar: Optional[str] = None


class UserResponse(UserBase):
    id: int
    role: str
    status: int
    created_at: datetime

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    token: str
    user: UserResponse


class CurrentUserResponse(BaseModel):
    id: int
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    content_profile: Optional[dict] = None
