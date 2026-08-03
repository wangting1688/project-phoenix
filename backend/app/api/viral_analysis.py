from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from pydantic import BaseModel
from typing import Optional

from app.api.deps import get_current_user
from app.services.viral_analysis_service import ViralAnalysisService

router = APIRouter(prefix="/viral-analysis", tags=["AI爆款逆向工程"])


class VideoInfoInput(BaseModel):
    """用户手动录入的真实视频信息"""
    title: str
    duration: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    share_count: Optional[int] = None
    collect_count: Optional[int] = None


class CreateAnalysisRequest(BaseModel):
    video_url: str
    video_info: Optional[VideoInfoInput] = None


@router.post("/create")
async def create_analysis(
    request: CreateAnalysisRequest,
    current_user = Depends(get_current_user)
):
    """创建分析任务"""
    service = ViralAnalysisService()
    try:
        session = service.create_analysis_session(
            current_user.id,
            request.video_url,
            video_info=request.video_info.model_dump() if request.video_info else None,
        )
        return {
            "success": True,
            "data": {
                "session_id": session.id,
                "video_url": session.video_url,
                "platform": session.platform,
                "status": session.status,
                "data_source": (session.original_data or {}).get("data_source", "mock"),
            }
        }
    finally:
        service.close()


@router.post("/{session_id}/analyze")
def analyze_video(
    session_id: int,
    current_user = Depends(get_current_user)
):
    """执行视频分析"""
    service = ViralAnalysisService()
    try:
        result = service.analyze_video(session_id)
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
def generate_opportunity(
    session_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """生成原创方案（转化为Content Opportunity）"""
    service = ViralAnalysisService(db=db)
    try:
        result = service.generate_opportunity(session_id)
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        service.close()