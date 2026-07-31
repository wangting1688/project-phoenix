from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, Script, Footage, Video, ContentProject
from app.services.video_service import video_service
from app.services.video_renderer import render_video as do_render_video
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/video", tags=["视频生成"])


@router.post("/compose/{project_id}", response_model=ApiResponse[dict])
def compose_video(
    project_id: int,
    script_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """根据项目文案和素材生成视频合成方案"""
    project = (
        db.query(ContentProject)
        .filter(
            ContentProject.id == project_id,
            ContentProject.user_id == current_user.id,
        )
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 获取文案
    scripts = db.query(Script).filter(Script.project_id == project_id).all()
    if not scripts:
        raise HTTPException(status_code=400, detail="暂无文案，请先完成AI创作")

    if script_id:
        script = next((s for s in scripts if s.id == script_id), None)
        if not script:
            raise HTTPException(status_code=404, detail="文案不存在")
    else:
        script = scripts[0]

    # 获取素材
    footages = db.query(Footage).filter(Footage.user_id == current_user.id).all()
    if not footages:
        return ApiResponse(
            code=400,
            message="请先上传素材",
            data={"need_footage": True},
        )

    footage_list = [
        {
            "id": f.id,
            "file_path": f.file_path,
            "scene": f.scene,
            "emotion": f.emotion,
            "topics": f.topics,
        }
        for f in footages
    ]

    # 构建合成方案
    plan = video_service.build_composition_plan(
        script=script.content,
        footages=footage_list,
        voice_style="warm",
        emotion="calm",
    )

    # 评估质量
    quality = video_service.get_quality_score(plan)

    # 更新视频记录
    video = db.query(Video).filter(Video.project_id == project_id).first()
    if video:
        video.status = "planned"
    else:
        video = Video(
            project_id=project_id,
            script_id=script.id,
            duration=int(plan["total_duration"]),
            resolution="1080x1920",
            status="planned",
        )
        db.add(video)

    db.commit()

    return ApiResponse(
        data={
            "plan": plan,
            "quality": quality,
            "video_id": video.id if video else None,
            "script_type": script.type,
            "footage_count": len(footage_list),
        }
    )


class RenderRequest(BaseModel):
    plan: dict
    script_text: str = ""  # 用于 TTS 配音 (前端传当前选中的文案)
    with_tts: bool = True  # 是否启用 TTS 配音
    voice_profile_id: Optional[int] = None  # 用 user 声纹 (C1 接入, 训练完成后用 cloned voice)


@router.post("/render/{project_id}", response_model=ApiResponse[dict])
def render_final_video(
    project_id: int,
    body: RenderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """执行 ffmpeg 渲染, 烧录字幕, 可选 TTS 配音, 输出到 storage/output/"""
    from pathlib import Path
    project = (
        db.query(ContentProject)
        .filter(ContentProject.id == project_id, ContentProject.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    plan = body.plan
    if not plan or not plan.get("scene_plan"):
        raise HTTPException(status_code=400, detail="plan 为空, 请先生成视频方案")

    backend_root = Path(__file__).resolve().parent.parent.parent
    try:
        # 解析 voice_profile -> custom_speaker_id (active 状态才用)
        custom_speaker_id = None
        if body.voice_profile_id and body.with_tts:
            from app.models import UserVoiceProfile
            vp = db.query(UserVoiceProfile).filter(
                UserVoiceProfile.id == body.voice_profile_id,
                UserVoiceProfile.user_id == current_user.id,
                UserVoiceProfile.status == "active",
            ).first()
            if vp:
                custom_speaker_id = vp.custom_speaker_id

        result = do_render_video(
            plan=plan,
            project_id=project_id,
            user_id=current_user.id,
            storage_root=backend_root,
            tts_text=body.script_text if body.with_tts else None,
            custom_speaker_id=custom_speaker_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"渲染失败: {e}")

    # 更新 Video 记录 (用 url 字段存渲染输出, 不引入新字段)
    video = db.query(Video).filter(Video.project_id == project_id).first()
    if video:
        video.status = "rendered"
        video.duration = int(result["duration"])
        video.url = result["output_url"]
    else:
        video = Video(
            project_id=project_id,
            duration=int(result["duration"]),
            resolution=plan.get("output_format", {}).get("resolution", "1080x1920"),
            status="rendered",
            url=result["output_url"],
        )
        db.add(video)
    db.commit()
    db.refresh(video)

    return ApiResponse(
        data={
            "video_id": video.id,
            "output_url": result["output_url"],
            "duration": result["duration"],
            "has_audio": result["has_audio"],
            "file_size": result["file_size"],
            "scene_count": result["scene_count"],
            "subtitle_count": result["subtitle_count"],
        }
    )


@router.get("/plan/{project_id}", response_model=ApiResponse[dict])
def get_video_plan(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取视频合成方案"""
    project = (
        db.query(ContentProject)
        .filter(
            ContentProject.id == project_id,
            ContentProject.user_id == current_user.id,
        )
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    scripts = db.query(Script).filter(Script.project_id == project_id).all()
    if not scripts:
        raise HTTPException(status_code=400, detail="暂无文案")

    footages = db.query(Footage).filter(Footage.user_id == current_user.id).all()

    return ApiResponse(
        data={
            "scripts": [
                {
                    "id": s.id,
                    "type": s.type,
                    "content": s.content[:100] + "...",
                    "score": float(s.score) if s.score else None,
                }
                for s in scripts
            ],
            "footage_count": len(footages),
            "ready_to_compose": len(footages) > 0,
        }
    )
