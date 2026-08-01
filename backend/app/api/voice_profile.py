"""
声纹档案 API
- POST   /api/v1/voice-profiles          上传样本 + 创建档案
- GET    /api/v1/voice-profiles          列表
- GET    /api/v1/voice-profiles/{id}     详情
- POST   /api/v1/voice-profiles/{id}/train  触发训练 (C2)
- POST   /api/v1/voice-profiles/{id}/test   试听合成
- DELETE /api/v1/voice-profiles/{id}     软删
"""
import os
import tempfile
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, UserVoiceProfile
from app.services.voice_clone import (
    upload_sample,
    list_profiles,
    delete_profile,
    test_synthesize,
    train_voice,
)
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/voice-profiles", tags=["声纹档案"])


def _to_dict(p: UserVoiceProfile) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "custom_speaker_id": p.custom_speaker_id,
        "icl_speaker_id": p.icl_speaker_id,
        "status": p.status,
        "volc_status": p.volc_status,
        "available_training_times": p.available_training_times,
        "sample_duration": p.sample_duration,
        "language": p.language,
        "reference_text": p.reference_text,
        "demo_text": p.demo_text,
        "demo_audio_url": (f"/static/voice_demos/{p.user_id}/{Path(p.demo_audio_path).name}"
                  if p.demo_audio_path else None),
        "error_message": p.error_message,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.post("", response_model=ApiResponse[dict])
async def upload_voice_sample(
    file: UploadFile = File(...),
    name: str = Form(...),
    demo_text: str = Form("你好, 这是我的专属声音测试。"),
    language: int = Form(0),
    reference_text: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传音频样本, 创建声纹档案"""
    file_bytes = await file.read()
    try:
        profile = upload_sample(
            db=db,
            user_id=current_user.id,
            file_bytes=file_bytes,
            filename=file.filename or "sample.mp3",
            name=name,
            demo_text=demo_text,
            language=language,
            reference_text=reference_text,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ApiResponse(data=_to_dict(profile))


@router.get("", response_model=ApiResponse[list])
def list_voice_profiles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出我的声纹"""
    profiles = list_profiles(db, current_user.id)
    return ApiResponse(data=[_to_dict(p) for p in profiles])


@router.get("/{profile_id}", response_model=ApiResponse[dict])
def get_voice_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = db.query(UserVoiceProfile).filter(
        UserVoiceProfile.id == profile_id,
        UserVoiceProfile.user_id == current_user.id,
        UserVoiceProfile.status != "deleted",
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="声纹不存在")
    return ApiResponse(data=_to_dict(p))


@router.post("/{profile_id}/train", response_model=ApiResponse[dict])
def trigger_train(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """触发/重训练 (C2 阶段实接火山)"""
    try:
        profile = train_voice(db, profile_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ApiResponse(data=_to_dict(profile))


@router.post("/{profile_id}/test", response_model=ApiResponse[dict])
def test_voice_synthesis(
    profile_id: int,
    text: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """试听合成 (生成临时 mp3 路径)"""
    try:
        out_path = test_synthesize(db, profile_id, current_user.id, text or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"合成失败: {e}")

    # 暴露 URL: /static/voice_demos/{user_id}/{filename}
    storage_root = Path(__file__).resolve().parent.parent.parent / "storage"
    rel = out_path.relative_to(storage_root)
    return ApiResponse(data={
        "audio_url": f"/static/{rel.as_posix()}",
        "duration_hint": out_path.stat().st_size,
    })


@router.delete("/{profile_id}", response_model=ApiResponse[dict])
def delete_voice_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = delete_profile(db, profile_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="声纹不存在")
    return ApiResponse(data={"profile_id": profile_id, "status": "deleted"})
