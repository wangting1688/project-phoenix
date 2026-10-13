from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, Script, Footage, Video, ContentProject
from app.services.video_service import video_service
from app.services.video_renderer import render_video as do_render_video
from app.services.video_producer import VideoProducer
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
    with_lipsync: bool = True  # 是否启用人脸口型同步（默认开启）
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

    # 更新 Video 记录
    video = db.query(Video).filter(Video.project_id == project_id).first()
    if video:
        video.status = "rendered"
        video.duration = int(result["duration"])
        video.url = result["output_url"]
        video.cover_url = result.get("cover_url")
    else:
        video = Video(
            project_id=project_id,
            duration=int(result["duration"]),
            resolution=plan.get("output_format", {}).get("resolution", "1080x1920"),
            status="rendered",
            url=result["output_url"],
            cover_url=result.get("cover_url"),
        )
        db.add(video)
    db.commit()
    db.refresh(video)

    return ApiResponse(
        data={
            "video_id": video.id,
            "output_url": result["output_url"],
            "cover_url": result.get("cover_url"),
            "duration": result["duration"],
            "has_audio": result["has_audio"],
            "file_size": result["file_size"],
            "scene_count": result["scene_count"],
            "subtitle_count": result["subtitle_count"],
        }
    )


class GenerateVideoRequest(BaseModel):
    script_id: Optional[int] = None
    voice_profile_id: Optional[int] = None
    footage_id: Optional[int] = None
    with_lipsync: bool = True
    # H3 照片生成讲解画面（新主链路）：给人像照片+场景即可，无需实拍素材
    person_image: Optional[str] = None
    scene: str = "lecture"            # park_walk/lecture/teahouse/street_walk 或英文描述
    anchor_image: Optional[str] = None
    hair_hint: str = ""
    width: Optional[int] = None
    height: Optional[int] = None
    seed: int = 400000


def _assert_h3_ready() -> None:
    """提交前探一次 GPU worker，不可用就立刻返回可读原因。

    以前这个检查只在真正开跑时才做（H3VideoEngine.available()），后果是用户
    点下「生成视频」后要等十几分钟才看到一个 "ComfyUI(8188) 未运行" 的失败——
    中间那段等待完全没有产出（线上任务 60 即如此）。
    探针失败时给一次重试机会：隧道抖动不该把用户挡在门外；
    仍然不通就明确说明，让用户稍后再点，而不是白等。
    """
    import os
    import time as _time

    base = os.environ.get("H3_REMOTE_HTTP", "").strip()
    if not base:
        return  # 本地直连模式，交给引擎自己的 health 判断

    import requests

    url = base.rstrip("/") + "/h3/health"
    last = ""
    for attempt in (1, 2):
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                body = r.json() or {}
                if body.get("comfyui"):
                    return
                last = "画面生成服务（ComfyUI）未就绪"
            else:
                last = f"画面生成服务返回异常（{r.status_code}）"
        except requests.exceptions.Timeout:
            last = "画面生成服务响应超时"
        except requests.exceptions.ConnectionError:
            # 别把 ConnectionError/HTTPConnectionPool 这种原文糊给用户
            last = "连接不上画面生成服务"
        except Exception:
            last = "画面生成服务探测异常"
        if attempt == 1:
            _time.sleep(3)
    raise HTTPException(
        status_code=503,
        detail=f"视频生成服务暂时不可用（{last}），请稍等 1 分钟后重试。",
    )


@router.post("/generate/{project_id}", response_model=ApiResponse[dict])
def generate_video(
    project_id: int,
    body: GenerateVideoRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    一键生成视频（异步任务）。

    完整流程：文案 → TTS配音 → 口型同步 → 视频渲染 → 输出成片
    返回 task_id，通过 /tasks/{task_id} 轮询进度。
    """
    # 必须同时排除已软删除的作品。漏掉 deleted_at 的后果不是报错而是"白跑"：
    # 2026-08-24 任务 37 就在一个 8-20 已删除的项目上跑完了全流程并标记成功，
    # 但作品列表与详情接口都会过滤掉已删除项目，用户等了十几分钟、显卡跑了一轮，
    # 最后在页面上找不到成片，也没有任何解释。
    project = (
        db.query(ContentProject)
        .filter(
            ContentProject.id == project_id,
            ContentProject.user_id == current_user.id,
            ContentProject.deleted_at.is_(None),
        )
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或已删除")

    # 先确认 GPU 侧可服务，再落任务。这个检查必须放在最前面（在建任务之前）：
    # 否则用户等十几分钟才拿到一个 "ComfyUI(8188) 未运行" 的失败。
    _assert_h3_ready()

    task_id = VideoProducer.create_task(
        project_id=project_id,
        user_id=current_user.id,
        script_id=body.script_id,
        voice_profile_id=body.voice_profile_id,
        footage_id=body.footage_id,
        with_lipsync=body.with_lipsync,
        person_image=body.person_image,
        scene=body.scene,
        anchor_image=body.anchor_image,
        hair_hint=body.hair_hint,
        width=body.width,
        height=body.height,
        seed=body.seed,
    )

    return ApiResponse(data={"task_id": task_id, "status": "running"})


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
