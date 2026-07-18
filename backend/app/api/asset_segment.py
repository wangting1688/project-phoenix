"""
素材片段 API

TASK-016.3A.5：AI素材片段化能力增强

提供素材片段管理、AI剪辑搜索、主播表现画像接口
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.api.deps import get_current_user
from app.services.asset_segment_service import AssetSegmentService

router = APIRouter(prefix="/asset-segments", tags=["素材片段管理"])


# ==================== 请求模型 ====================

class SegmentSearchRequest(BaseModel):
    """片段搜索请求"""
    segment_role: Optional[str] = None
    emotion: Optional[str] = None
    min_duration: float = 0
    max_duration: float = 60
    min_score: int = 0
    exclude_segment_ids: Optional[List[int]] = None
    limit: int = 10


class CreateSegmentsRequest(BaseModel):
    """创建片段请求"""
    asset_id: int


# ==================== 片段管理接口 ====================

@router.post("/")
async def create_segments(
    request: CreateSegmentsRequest,
    current_user = Depends(get_current_user)
):
    """为素材创建片段"""
    service = AssetSegmentService()
    try:
        segments = service.create_segments_for_asset(
            asset_id=request.asset_id,
            user_id=current_user.id,
        )
        return {
            "success": True,
            "message": f"成功创建 {len(segments)} 个片段",
            "data": {
                "asset_id": request.asset_id,
                "segments_count": len(segments),
                "segments": [
                    {
                        "id": s.id,
                        "segment_number": s.segment_number,
                        "segment_role": s.segment_role,
                        "emotion": s.emotion,
                        "duration": s.duration,
                        "quality_score": s.quality_score,
                    }
                    for s in segments
                ]
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        service.close()


@router.get("/{asset_id}")
async def get_segments_by_asset(
    asset_id: int,
    current_user = Depends(get_current_user)
):
    """获取素材的所有片段"""
    service = AssetSegmentService()
    try:
        from app.models import AssetSegment
        segments = service.db.query(AssetSegment).filter(
            AssetSegment.asset_id == asset_id,
            AssetSegment.user_id == current_user.id,
        ).order_by(AssetSegment.segment_number).all()
        
        return {
            "success": True,
            "data": {
                "asset_id": asset_id,
                "segments": [service._format_segment(s) for s in segments],
            }
        }
    finally:
        service.close()


@router.get("/{asset_id}/{segment_id}")
async def get_segment_detail(
    asset_id: int,
    segment_id: int,
    current_user = Depends(get_current_user)
):
    """获取片段详情"""
    service = AssetSegmentService()
    try:
        from app.models import AssetSegment
        segment = service.db.query(AssetSegment).filter(
            AssetSegment.id == segment_id,
            AssetSegment.asset_id == asset_id,
            AssetSegment.user_id == current_user.id,
        ).first()
        
        if not segment:
            raise HTTPException(status_code=404, detail="片段不存在")
        
        return {
            "success": True,
            "data": service._format_segment(segment),
        }
    finally:
        service.close()


# ==================== AI剪辑搜索接口 ====================

@router.post("/search")
async def search_segments_for_clip(
    request: SegmentSearchRequest,
    current_user = Depends(get_current_user)
):
    """
    AI剪辑搜索接口
    
    根据角色、情绪、时长等条件搜索可用片段
    
    示例请求：
    {
        "segment_role": "hook",
        "emotion": "疑问",
        "min_duration": 3,
        "max_duration": 6,
        "min_score": 80,
        "limit": 5
    }
    """
    service = AssetSegmentService()
    try:
        segments = service.search_for_clip(
            user_id=current_user.id,
            segment_role=request.segment_role,
            emotion=request.emotion,
            min_duration=request.min_duration,
            max_duration=request.max_duration,
            min_score=request.min_score,
            exclude_segment_ids=request.exclude_segment_ids,
            limit=request.limit,
        )
        
        return {
            "success": True,
            "data": {
                "total": len(segments),
                "segments": segments,
            }
        }
    finally:
        service.close()


# ==================== 主播表现画像接口 ====================

@router.get("/profile/{user_id}")
async def get_creator_profile(
    user_id: int,
    current_user = Depends(get_current_user)
):
    """获取主播表现画像"""
    service = AssetSegmentService()
    try:
        profile = service.get_creator_profile(user_id)
        
        if not profile:
            return {
                "success": True,
                "data": None,
                "message": "暂无表现画像，上传素材后自动生成",
            }
        
        return {
            "success": True,
            "data": {
                "user_id": profile.user_id,
                "best_emotion": profile.best_emotion,
                "best_scene": profile.best_scene,
                "best_segment_roles": profile.best_segment_roles,
                "emotion_scores": profile.emotion_scores,
                "scene_scores": profile.scene_scores,
                "overall_performance_score": profile.overall_performance_score,
                "analyzed_segments": profile.analyzed_segments,
                "total_usage_count": profile.total_usage_count,
                "last_updated_at": profile.last_updated_at.isoformat() if profile.last_updated_at else None,
            }
        }
    finally:
        service.close()


@router.post("/profile/{user_id}/refresh")
async def refresh_creator_profile(
    user_id: int,
    current_user = Depends(get_current_user)
):
    """刷新主播表现画像"""
    service = AssetSegmentService()
    try:
        profile = service.update_creator_profile(user_id)
        
        return {
            "success": True,
            "message": "表现画像已更新",
            "data": {
                "user_id": profile.user_id,
                "best_emotion": profile.best_emotion,
                "best_scene": profile.best_scene,
                "overall_performance_score": profile.overall_performance_score,
                "analyzed_segments": profile.analyzed_segments,
            }
        }
    finally:
        service.close()


# ==================== 统计接口 ====================

@router.get("/stats/{user_id}")
async def get_segment_stats(
    user_id: int,
    current_user = Depends(get_current_user)
):
    """获取用户片段统计"""
    service = AssetSegmentService()
    try:
        from app.models import AssetSegment
        segments = service.db.query(AssetSegment).filter(
            AssetSegment.user_id == user_id
        ).all()
        
        role_stats = {}
        emotion_stats = {}
        
        for seg in segments:
            role_stats[seg.segment_role] = role_stats.get(seg.segment_role, 0) + 1
            emotion_stats[seg.emotion] = emotion_stats.get(seg.emotion, 0) + 1
        
        avg_score = sum(s.quality_score for s in segments) / len(segments) if segments else 0
        avg_duration = sum(s.duration for s in segments) / len(segments) if segments else 0
        
        return {
            "success": True,
            "data": {
                "total_segments": len(segments),
                "avg_quality_score": round(avg_score, 1),
                "avg_duration": round(avg_duration, 1),
                "role_distribution": role_stats,
                "emotion_distribution": emotion_stats,
            }
        }
    finally:
        service.close()


# ==================== 批量操作接口 ====================

@router.post("/batch-create")
async def batch_create_segments(
    asset_ids: List[int],
    current_user = Depends(get_current_user)
):
    """批量为多个素材创建片段"""
    service = AssetSegmentService()
    try:
        results = []
        for asset_id in asset_ids:
            try:
                segments = service.create_segments_for_asset(
                    asset_id=asset_id,
                    user_id=current_user.id,
                )
                results.append({
                    "asset_id": asset_id,
                    "success": True,
                    "segments_count": len(segments),
                })
            except Exception as e:
                results.append({
                    "asset_id": asset_id,
                    "success": False,
                    "error": str(e),
                })
        
        success_count = sum(1 for r in results if r["success"])
        
        return {
            "success": True,
            "message": f"批量处理完成，成功 {success_count}/{len(asset_ids)}",
            "data": results,
        }
    finally:
        service.close()
