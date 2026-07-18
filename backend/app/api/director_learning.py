"""
AI导演学习记忆层 API

TASK-016.3A.8：AI导演学习记忆层 V2

提供效果分析、经验库、策略画像、复盘等接口
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.api.deps import get_current_user
from app.services.director_learning_service import DirectorLearningService

router = APIRouter(prefix="/director-learning", tags=["AI导演学习"])


# ==================== 视频与发布记录 ====================

@router.get("/videos/{video_id}")
async def get_video_master(
    video_id: int,
    current_user = Depends(get_current_user)
):
    """获取视频本体详情"""
    from app.models import VideoMasterContent
    service = DirectorLearningService()
    try:
        video = service.db.query(VideoMasterContent).filter(
            VideoMasterContent.id == video_id
        ).first()
        if not video:
            raise HTTPException(status_code=404, detail="视频不存在")
        if video.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")
        return {
            "success": True,
            "data": {
                "id": video.id,
                "title": video.title,
                "template_type": video.template_type,
                "duration": video.duration,
                "director_score": video.director_score,
                "predicted_completion_rate": video.predicted_completion_rate,
                "predicted_conversion_rate": video.predicted_conversion_rate,
                "actual_performance": video.actual_performance,
                "status": video.status,
            },
        }
    finally:
        service.close()


@router.get("/videos/{video_id}/platform-scores")
async def get_platform_scores(
    video_id: int,
    current_user = Depends(get_current_user)
):
    """获取视频各平台效果评分"""
    from app.models import VideoMasterContent, PlatformPerformanceScore
    service = DirectorLearningService()
    try:
        video = service.db.query(VideoMasterContent).filter(VideoMasterContent.id == video_id).first()
        if not video or video.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")

        scores = service.db.query(PlatformPerformanceScore).filter(
            PlatformPerformanceScore.video_id == video_id
        ).all()

        return {
            "success": True,
            "data": [
                {
                    "platform": s.platform,
                    "overall_score": s.overall_score,
                    "traffic_score": s.traffic_score,
                    "engagement_score": s.engagement_score,
                    "conversion_score": s.conversion_score,
                    "customer_value_score": s.customer_value_score,
                    "score_breakdown": s.score_breakdown,
                    "platform_specific": s.platform_specific,
                }
                for s in scores
            ],
        }
    finally:
        service.close()


# ==================== 导演复盘Agent ====================

@router.post("/videos/{video_id}/review")
async def run_director_review(
    video_id: int,
    current_user = Depends(get_current_user)
):
    """
    运行导演复盘Agent

    分析视频表现，与预测对比，更新经验库和策略画像
    """
    from app.models import VideoMasterContent
    service = DirectorLearningService()
    try:
        video = service.db.query(VideoMasterContent).filter(VideoMasterContent.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="视频不存在")
        if video.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")

        result = service.run_review(video_id)
        return {
            "success": result.get("success", False),
            "message": f"复盘完成，生成{result.get('new_memories', 0)}条新经验" if result.get("success") else result.get("error"),
            "data": result,
        }
    finally:
        service.close()


# ==================== 导演评分 V3 ====================

@router.post("/calculate-score")
async def calculate_director_score(
    plan_id: int,
    target_platform: str = "wechat_video",
    current_user = Depends(get_current_user)
):
    """
    计算导演评分 V3

    内容质量40% + 主播适配20% + 平台匹配20% + 历史经验20%
    """
    from app.models import VideoEditPlan, VideoEditSegment
    service = DirectorLearningService()
    try:
        plan = service.db.query(VideoEditPlan).filter(VideoEditPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="方案不存在")
        if plan.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")

        segments = service.db.query(VideoEditSegment).filter(
            VideoEditSegment.edit_plan_id == plan_id
        ).order_by(VideoEditSegment.sequence).all()

        score, breakdown, reasons = service.calculate_director_score_v3(
            plan, segments, target_platform, current_user.id
        )

        return {
            "success": True,
            "data": {
                "plan_id": plan_id,
                "target_platform": target_platform,
                "director_score": score,
                "score_breakdown": breakdown,
                "score_reasons": reasons,
            },
        }
    finally:
        service.close()


# ==================== 导演经验库 ====================

@router.get("/memories")
async def get_learning_memories(
    memory_type: Optional[str] = None,
    min_confidence: float = 0.0,
    limit: int = 50,
    current_user = Depends(get_current_user)
):
    """获取导演经验库"""
    service = DirectorLearningService()
    try:
        memories = service.get_memories(
            user_id=current_user.id,
            memory_type=memory_type,
            min_confidence=min_confidence,
            limit=limit,
        )
        return {
            "success": True,
            "data": [
                {
                    "id": m.id,
                    "memory_type": m.memory_type,
                    "condition": m.condition,
                    "recommendation": m.recommendation,
                    "confidence_score": m.confidence_score,
                    "usage_count": m.usage_count,
                    "success_count": m.success_count,
                    "source_data_points": m.source_data_points,
                    "is_verified": m.is_verified,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in memories
            ],
        }
    finally:
        service.close()


# ==================== 主播策略画像 ====================

@router.get("/creator-strategy")
async def get_creator_strategy(
    current_user = Depends(get_current_user)
):
    """获取主播策略画像"""
    service = DirectorLearningService()
    try:
        profile = service.get_creator_strategy_profile(current_user.id)
        if not profile:
            return {
                "success": True,
                "data": None,
                "message": "暂无策略画像，发布视频后自动生成",
            }
        return {
            "success": True,
            "data": {
                "best_content_type": profile.best_content_type,
                "best_content_types": profile.best_content_types,
                "best_hook_style": profile.best_hook_style,
                "best_camera_style": profile.best_camera_style,
                "best_duration_range": profile.best_duration_range,
                "best_conversion_style": profile.best_conversion_style,
                "weak_styles": profile.weak_styles,
                "platform_performance": profile.platform_performance,
                "strategy_recommendation": profile.strategy_recommendation,
                "analyzed_videos": profile.analyzed_videos,
                "last_updated": profile.last_updated.isoformat() if profile.last_updated else None,
            },
        }
    finally:
        service.close()


# ==================== 平台策略画像 ====================

@router.get("/platform-strategies")
async def get_platform_strategies(
    current_user = Depends(get_current_user)
):
    """获取所有平台策略画像"""
    service = DirectorLearningService()
    try:
        profiles = service.get_platform_strategy_profiles(current_user.id)
        return {
            "success": True,
            "data": [
                {
                    "platform": p.platform,
                    "platform_role": p.platform_role,
                    "best_content_types": p.best_content_types,
                    "best_duration_range": p.best_duration_range,
                    "best_publish_times": p.best_publish_times,
                    "avg_views": p.avg_views,
                    "avg_completion_rate": p.avg_completion_rate,
                    "avg_conversion_rate": p.avg_conversion_rate,
                    "total_published": p.total_published,
                    "weight_config": p.weight_config,
                }
                for p in profiles
            ],
        }
    finally:
        service.close()


# ==================== Phoenix商业权重说明 ====================

@router.get("/weights/phoenix-commercial")
async def get_phoenix_commercial_weights(
    current_user = Depends(get_current_user)
):
    """获取Phoenix默认商业评分权重说明"""
    service = DirectorLearningService()
    try:
        return {
            "success": True,
            "data": {
                "description": "Phoenix私域电商导向的商业评分权重",
                "weights": {
                    "gmv": {"name": "成交金额 GMV", "weight": "35%"},
                    "consultation": {"name": "有效咨询人数", "weight": "25%"},
                    "conversion_rate": {"name": "成交转化率", "weight": "15%"},
                    "retention": {"name": "用户停留", "weight": "10%"},
                    "engagement": {"name": "互动", "weight": "10%"},
                    "views": {"name": "播放", "weight": "5%"},
                },
                "philosophy": "目标不是培养网红，而是培养会卖货的主播",
                "core_platforms": {
                    "wechat_video": "私域成交主阵地（高权重）",
                    "douyin": "流量增长主阵地",
                    "xiaohongshu": "内容资产沉淀（长尾搜索价值）",
                },
            },
        }
    finally:
        service.close()


# ==================== 统计接口 ====================

@router.get("/stats")
async def get_learning_stats(
    current_user = Depends(get_current_user)
):
    """获取学习层统计"""
    service = DirectorLearningService()
    try:
        from app.models import (
            VideoMasterContent,
            VideoPublishRecord,
            DirectorLearningMemory,
        )

        total_videos = service.db.query(VideoMasterContent).filter(
            VideoMasterContent.user_id == current_user.id
        ).count()

        total_publish = service.db.query(VideoPublishRecord).filter(
            VideoPublishRecord.user_id == current_user.id
        ).count()

        total_memories = service.db.query(DirectorLearningMemory).filter(
            DirectorLearningMemory.user_id == current_user.id,
            DirectorLearningMemory.is_active == True,
        ).count()

        verified_memories = service.db.query(DirectorLearningMemory).filter(
            DirectorLearningMemory.user_id == current_user.id,
            DirectorLearningMemory.is_verified == True,
        ).count()

        # 按类型统计经验
        type_stats = {}
        memory_types = ["template_success", "platform_success", "creator_success", "hook_success"]
        for mt in memory_types:
            count = service.db.query(DirectorLearningMemory).filter(
                DirectorLearningMemory.user_id == current_user.id,
                DirectorLearningMemory.memory_type == mt,
                DirectorLearningMemory.is_active == True,
            ).count()
            type_stats[mt] = count

        return {
            "success": True,
            "data": {
                "total_videos": total_videos,
                "total_publish_records": total_publish,
                "total_memories": total_memories,
                "verified_memories": verified_memories,
                "memory_type_stats": type_stats,
                "learning_progress": min(round(total_memories / 50 * 100, 1), 100),  # 50条经验达到成熟
            },
        }
    finally:
        service.close()
