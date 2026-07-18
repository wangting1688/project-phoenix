from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.api.deps import get_current_user
from app.services.viral_analysis_service import ViralAnalysisService

router = APIRouter(prefix="/viral-analysis", tags=["AI爆款逆向工程"])


class CreateAnalysisRequest(BaseModel):
    video_url: str


@router.post("/create")
async def create_analysis(
    request: CreateAnalysisRequest,
    current_user = Depends(get_current_user)
):
    """创建分析任务"""
    service = ViralAnalysisService()
    try:
        session = service.create_analysis_session(current_user.id, request.video_url)
        return {
            "success": True,
            "data": {
                "session_id": session.id,
                "video_url": session.video_url,
                "platform": session.platform,
                "status": session.status,
            }
        }
    finally:
        service.close()


@router.post("/{session_id}/analyze")
async def analyze_video(
    session_id: int,
    current_user = Depends(get_current_user)
):
    """执行视频分析"""
    service = ViralAnalysisService()
    try:
        result = service.analyze_video(session_id)
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        service.close()


@router.get("/{session_id}")
async def get_analysis_result(
    session_id: int,
    current_user = Depends(get_current_user)
):
    """获取分析结果"""
    service = ViralAnalysisService()
    try:
        result = service.get_analysis_result(session_id)
        if not result:
            raise HTTPException(status_code=404, detail="分析会话不存在")
        return {"success": True, "data": result}
    finally:
        service.close()


@router.post("/{session_id}/generate")
async def generate_opportunity(
    session_id: int,
    current_user = Depends(get_current_user)
):
    """生成原创方案（转化为Content Opportunity）"""
    service = ViralAnalysisService()
    try:
        result = service.generate_opportunity(session_id)
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        service.close()