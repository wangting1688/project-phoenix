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


# 朗读示例文本: 覆盖常用声韵 + 长度适中 (火山建议 10-30 秒)
# 用户照读, 参考文本自动准确, 规避 WER 校验失败
SAMPLE_SCRIPTS = [
    {
        "id": "daily",
        "title": "日常口语",
        "text": "大家好，今天天气真不错。我准备做点好吃的，再泡杯茶，享受这难得的悠闲时光。"
                "平时总是忙忙碌碌，其实偶尔慢下来，听听音乐，读几页书，也是一种很好的放松方式。",
    },
    {
        "id": "health",
        "title": "健康科普",
        "text": "很多朋友问我，秋天应该怎么养护脾胃。其实方法很简单，第一是三餐规律，"
                "第二是少吃生冷，第三是饭后适当活动。坚持一段时间，你会明显感觉到变化。",
    },
    {
        "id": "story",
        "title": "叙述表达",
        "text": "记得小时候，每到夏天的傍晚，院子里就摆满了竹椅和小板凳。"
                "大人们坐在一起聊天，孩子们追着萤火虫跑，那种热闹又安静的感觉，现在想起来还是很温暖。",
    },
]


@router.get("/sample-scripts", response_model=ApiResponse[list])
def get_sample_scripts():
    """朗读示例文本 (用户照读录音, 参考文本自动准确)"""
    return ApiResponse(data=SAMPLE_SCRIPTS)


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
