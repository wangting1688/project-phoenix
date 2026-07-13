from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta

from app.core.database import get_db
from app.core.security import create_access_token
from app.core.config import settings
from app.schemas import UserCreate, UserLogin, UserResponse, LoginResponse, CurrentUserResponse, ApiResponse
from app.services import user_service
from app.api.deps import get_current_user
from app.models import User

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=ApiResponse[LoginResponse])
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    db_user = user_service.get_user_by_phone(db, phone=user_in.phone)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="手机号已注册",
        )
    user = user_service.create_user(db, user_in=user_in)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return ApiResponse(
        data=LoginResponse(
            token=access_token,
            user=UserResponse.model_validate(user),
        )
    )


@router.post("/login", response_model=ApiResponse[LoginResponse])
def login(user_in: UserLogin, db: Session = Depends(get_db)):
    user = user_service.authenticate_user(db, phone=user_in.phone, password=user_in.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="手机号或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return ApiResponse(
        data=LoginResponse(
            token=access_token,
            user=UserResponse.model_validate(user),
        )
    )


@router.get("/me", response_model=ApiResponse[CurrentUserResponse])
def get_me(current_user: User = Depends(get_current_user)):
    return ApiResponse(
        data=CurrentUserResponse(
            id=current_user.id,
            nickname=current_user.nickname,
            avatar=current_user.avatar,
            content_profile={"style": "故事型", "category": "健康"},
        )
    )
