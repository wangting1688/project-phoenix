import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.config import settings
from app.api.deps import get_current_user
from app.models import User, Footage, FootageCategory
from app.schemas.footage import (
    FootageCategoryCreate,
    FootageCategoryResponse,
    FootageResponse,
    FootageUpdate,
)
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/footage", tags=["素材库"])

UPLOAD_DIR = os.path.join(settings.STORAGE_PATH, "footage")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/categories", response_model=ApiResponse[List[FootageCategoryResponse]])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cats = db.query(FootageCategory).filter(
        FootageCategory.user_id == current_user.id
    ).all()
    return ApiResponse(data=[FootageCategoryResponse.model_validate(c) for c in cats])


@router.post("/categories", response_model=ApiResponse[FootageCategoryResponse])
def create_category(
    cat_in: FootageCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cat = FootageCategory(
        user_id=current_user.id,
        name=cat_in.name,
        type=cat_in.type,
        icon=cat_in.icon,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return ApiResponse(data=FootageCategoryResponse.model_validate(cat))


@router.post("/upload", response_model=ApiResponse[FootageResponse])
async def upload_footage(
    file: UploadFile = File(...),
    category_id: int = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    allowed_types = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"}
    if file.content_type and file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="仅支持视频文件(mp4/mov/avi/webm)")

    ext = os.path.splitext(file.filename or "video.mp4")[1] or ".mp4"
    filename = f"{uuid.uuid4().hex}{ext}"
    user_dir = os.path.join(UPLOAD_DIR, str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)
    file_path = os.path.join(user_dir, filename)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    footage = Footage(
        user_id=current_user.id,
        category_id=category_id,
        filename=file.filename or filename,
        file_path=file_path,
        duration=0,
        file_size=len(content),
        resolution="1080x1920",
        status="ready",
    )
    db.add(footage)
    db.commit()
    db.refresh(footage)
    return ApiResponse(data=FootageResponse.model_validate(footage))


@router.get("/list", response_model=ApiResponse[dict])
def list_footages(
    category_id: int = Query(None),
    scene: str = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Footage).filter(Footage.user_id == current_user.id)
    if category_id:
        query = query.filter(Footage.category_id == category_id)
    if scene:
        query = query.filter(Footage.scene == scene)
    total = query.count()
    items = (
        query.order_by(Footage.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return ApiResponse(
        data={
            "items": [FootageResponse.model_validate(f) for f in items],
            "total": total,
            "page": page,
            "size": size,
        }
    )


@router.put("/{footage_id}", response_model=ApiResponse[FootageResponse])
def update_footage(
    footage_id: int,
    update_in: FootageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    footage = (
        db.query(Footage)
        .filter(Footage.id == footage_id, Footage.user_id == current_user.id)
        .first()
    )
    if not footage:
        raise HTTPException(status_code=404, detail="素材不存在")

    if update_in.category_id is not None:
        footage.category_id = update_in.category_id
    if update_in.scene is not None:
        footage.scene = update_in.scene
    if update_in.emotion is not None:
        footage.emotion = update_in.emotion
    if update_in.action is not None:
        footage.action = update_in.action
    if update_in.topics is not None:
        footage.topics = update_in.topics
    db.commit()
    db.refresh(footage)
    return ApiResponse(data=FootageResponse.model_validate(footage))


@router.delete("/{footage_id}", response_model=ApiResponse[dict])
def delete_footage(
    footage_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    footage = (
        db.query(Footage)
        .filter(Footage.id == footage_id, Footage.user_id == current_user.id)
        .first()
    )
    if not footage:
        raise HTTPException(status_code=404, detail="素材不存在")

    if os.path.exists(footage.file_path):
        os.remove(footage.file_path)
    db.delete(footage)
    db.commit()
    return ApiResponse(data={"deleted": True})


@router.get("/suggest-shots", response_model=ApiResponse[dict])
def get_suggest_shots(
    current_user: User = Depends(get_current_user),
):
    """获取推荐拍摄素材清单"""
    suggestions = {
        "life": [
            {"scene": "厨房", "action": "做饭", "emotion": "温暖"},
            {"scene": "客厅", "action": "喝水", "emotion": "平静"},
            {"scene": "户外", "action": "散步", "emotion": "轻松"},
            {"scene": "市场", "action": "买菜", "emotion": "生活"},
            {"scene": "书房", "action": "看书", "emotion": "思考"},
        ],
        "health": [
            {"scene": "公园", "action": "运动", "emotion": "活力"},
            {"scene": "厨房", "action": "做早餐", "emotion": "温暖"},
            {"scene": "卫生间", "action": "泡脚", "emotion": "放松"},
            {"scene": "茶室", "action": "喝茶", "emotion": "平静"},
        ],
        "emotion": [
            {"scene": "窗边", "action": "看窗外", "emotion": "思考"},
            {"scene": "沙发", "action": "微笑", "emotion": "温暖"},
            {"scene": "客厅", "action": "与家人聊天", "emotion": "温馨"},
        ],
        "work": [
            {"scene": "书房", "action": "学习", "emotion": "专注"},
            {"scene": "直播间", "action": "直播准备", "emotion": "专业"},
            {"scene": "办公室", "action": "产品整理", "emotion": "认真"},
        ],
    }
    return ApiResponse(data=suggestions)
