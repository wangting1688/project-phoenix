from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, Script, Footage, Video, ContentProject
from app.services.video_service import video_service
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
