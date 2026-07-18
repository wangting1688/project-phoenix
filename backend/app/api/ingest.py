"""
数据采集接口

阶段五 · Iteration-1
- POST /ingest/videos           登记一条视频到某平台
- POST /ingest/daily            上报一次日快照（手工渠道）
- GET  /ingest/videos/{id}/snapshots  查询快照历史
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.services.ingest_service import IngestService


router = APIRouter(prefix="/ingest", tags=["数据采集"])


# ==================== 请求模型 ====================

class RegisterVideoRequest(BaseModel):
    platform: str = Field(..., description="douyin/wechat_video/xiaohongshu/kuaishou/bilibili")
    title: str
    publish_url: Optional[str] = None
    publish_time: Optional[datetime] = None
    video_master_id: Optional[int] = None
    script_content: Optional[str] = None
    duration: Optional[int] = None


class DailySnapshotRequest(BaseModel):
    publish_record_id: int
    mode: Literal["manual", "browser", "official_api"] = "manual"
    source_client: Optional[str] = None
    snapshot_date: Optional[str] = Field(default=None, description="YYYY-MM-DD，默认今天")
    payload: Dict[str, Any] = Field(..., description="views/likes/comments/favorites/shares 至少一项")


# ==================== 接口 ====================

@router.post("/videos")
def register_video(req: RegisterVideoRequest, current_user=Depends(get_current_user)):
    service = IngestService()
    try:
        record = service.register_video(
            user_id=current_user.id,
            platform=req.platform,
            title=req.title,
            publish_url=req.publish_url,
            publish_time=req.publish_time,
            video_master_id=req.video_master_id,
            script_content=req.script_content,
            duration=req.duration,
        )
        return {
            "success": True,
            "data": {
                "publish_record_id": record.id,
                "video_master_id": record.video_id,
                "platform": record.platform,
                "publish_url": record.publish_url,
                "publish_status": record.publish_status,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        service.close()


@router.post("/daily")
def report_daily(req: DailySnapshotRequest, current_user=Depends(get_current_user)):
    service = IngestService()
    try:
        snapshot = service.record_daily_snapshot(
            user_id=current_user.id,
            publish_record_id=req.publish_record_id,
            payload=req.payload,
            source_mode=req.mode,
            source_client=req.source_client,
            snapshot_date=req.snapshot_date,
        )
        return {
            "success": True,
            "data": {
                "snapshot_id": snapshot.id,
                "publish_record_id": snapshot.publish_record_id,
                "snapshot_date": snapshot.snapshot_date,
                "source_mode": snapshot.source_mode,
                "views": snapshot.views,
                "likes": snapshot.likes,
                "comments": snapshot.comments,
                "favorites": snapshot.favorites,
                "shares": snapshot.shares,
                "private_message_count": snapshot.private_message_count,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        service.close()


@router.get("/videos/{publish_record_id}/snapshots")
def list_snapshots(
    publish_record_id: int,
    limit: int = 30,
    current_user=Depends(get_current_user),
):
    service = IngestService()
    try:
        snapshots = service.list_snapshots(
            user_id=current_user.id,
            publish_record_id=publish_record_id,
            limit=limit,
        )
        return {
            "success": True,
            "data": [
                {
                    "id": s.id,
                    "snapshot_date": s.snapshot_date,
                    "source_mode": s.source_mode,
                    "views": s.views,
                    "likes": s.likes,
                    "comments": s.comments,
                    "favorites": s.favorites,
                    "shares": s.shares,
                    "private_message_count": s.private_message_count,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in snapshots
            ],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        service.close()
