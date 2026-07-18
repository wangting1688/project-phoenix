from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.api.deps import get_current_user
from app.services.creation_studio_service import CreationStudioService

router = APIRouter(prefix="/creation-studio", tags=["AI创作工作台"])


class CreateSessionRequest(BaseModel):
    source_type: str
    opportunity_id: Optional[int] = None
    topic: Optional[str] = None


class ConfigureRequest(BaseModel):
    session_id: int
    style: str
    duration: int
    tone: str


class GenerateRequest(BaseModel):
    session_id: int


@router.get("/templates")
async def get_templates(current_user = Depends(get_current_user)):
    """获取创作模板（风格、语气、时长选项）"""
    service = CreationStudioService()
    try:
        return {
            "success": True,
            "data": {
                "styles": service.get_style_templates(),
                "tones": service.get_tone_options(),
                "durations": service.get_duration_options(),
            }
        }
    finally:
        service.close()


@router.post("/sessions")
async def create_session(
    request: CreateSessionRequest,
    current_user = Depends(get_current_user)
):
    """创建创作会话"""
    service = CreationStudioService()
    try:
        session = service.create_session(
            user_id=current_user.id,
            source_type=request.source_type,
            opportunity_id=request.opportunity_id,
            topic=request.topic,
        )
        return {
            "success": True,
            "data": {
                "session_id": session.id,
                "status": session.status,
                "current_step": session.current_step,
            }
        }
    finally:
        service.close()


@router.post("/configure")
async def configure_session(
    request: ConfigureRequest,
    current_user = Depends(get_current_user)
):
    """配置创作参数"""
    service = CreationStudioService()
    try:
        session = service.configure_session(
            session_id=request.session_id,
            style=request.style,
            duration=request.duration,
            tone=request.tone,
        )
        return {
            "success": True,
            "data": {
                "session_id": session.id,
                "config": session.config,
                "current_step": session.current_step,
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        service.close()


@router.post("/generate")
async def generate_content(
    request: GenerateRequest,
    current_user = Depends(get_current_user)
):
    """生成内容（Planning + Script + Review）"""
    service = CreationStudioService()
    try:
        result = service.generate_content(request.session_id)
        return {
            "success": True,
            "data": result
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        service.close()


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: int,
    current_user = Depends(get_current_user)
):
    """获取创作会话状态和结果"""
    service = CreationStudioService()
    try:
        result = service.get_session_result(session_id)
        if not result:
            raise HTTPException(status_code=404, detail="创作会话不存在")
        return {"success": True, "data": result}
    finally:
        service.close()


@router.get("/sessions")
async def list_sessions(current_user = Depends(get_current_user)):
    """获取用户活跃创作会话"""
    service = CreationStudioService()
    try:
        sessions = service.get_user_active_sessions(current_user.id)
        return {
            "success": True,
            "data": [
                {
                    "id": s.id,
                    "source_type": s.source_type,
                    "status": s.status,
                    "current_step": s.current_step,
                    "config": s.config,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in sessions
            ]
        }
    finally:
        service.close()