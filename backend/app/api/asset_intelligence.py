"""
AI素材智能分析管理 API

让AI看懂每一个主播素材
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.api.deps import get_current_user
from app.services.asset_analysis_service import AssetAnalysisService
from app.services.asset_search_service import AssetSearchService
from app.services.asset_scoring_service import AssetScoringService

router = APIRouter(prefix="/asset-intelligence", tags=["AI素材智能分析"])


# ==================== 请求模型 ====================

class BatchAnalyzeRequest(BaseModel):
    """批量分析请求"""
    asset_ids: Optional[List[int]] = None


class SearchRequest(BaseModel):
    """搜索请求"""
    query: Optional[str] = None
    scene_type: Optional[str] = None
    emotion: Optional[str] = None
    style: Optional[str] = None
    topics: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    min_score: int = 0
    asset_role: Optional[str] = None
    limit: int = 20


class SmartRecommendRequest(BaseModel):
    """智能推荐请求"""
    script_content: str
    shot_type: Optional[str] = None


class FindSegmentsRequest(BaseModel):
    """查找片段请求"""
    requirements: List[Dict[str, Any]]


# ==================== 分析接口 ====================

@router.post("/analyze/{asset_id}")
async def analyze_asset(
    asset_id: int,
    current_user = Depends(get_current_user)
):
    """
    分析单个素材
    
    对素材进行AI分析，生成智能标签和评分
    """
    service = AssetAnalysisService()
    try:
        intelligence = service.analyze_asset(asset_id)
        return {
            "success": True,
            "data": {
                "asset_id": intelligence.asset_id,
                "status": intelligence.analysis_status,
                "overall_score": intelligence.overall_score,
                "analysis_result": intelligence.analysis_result,
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
    finally:
        service.close()


@router.post("/analyze/batch")
async def batch_analyze(
    request: BatchAnalyzeRequest,
    current_user = Depends(get_current_user)
):
    """批量分析素材"""
    service = AssetAnalysisService()
    try:
        result = service.batch_analyze(current_user.id, request.asset_ids)
        return {
            "success": True,
            "data": result,
        }
    finally:
        service.close()


@router.get("/result/{asset_id}")
async def get_analysis_result(
    asset_id: int,
    current_user = Depends(get_current_user)
):
    """获取素材分析结果"""
    service = AssetAnalysisService()
    try:
        intelligence = service.get_analysis_result(asset_id)
        if not intelligence:
            raise HTTPException(status_code=404, detail="分析结果不存在")
        
        return {
            "success": True,
            "data": {
                "asset_id": intelligence.asset_id,
                "status": intelligence.analysis_status,
                "duration": intelligence.duration,
                "overall_score": intelligence.overall_score,
                "quality_score": intelligence.quality_score,
                "face_visibility": intelligence.face_visibility,
                "face_score": intelligence.face_score,
                "eye_contact": intelligence.eye_contact,
                "emotion_primary": intelligence.emotion_primary,
                "emotion_secondary": intelligence.emotion_secondary,
                "emotion_score": intelligence.emotion_score,
                "scene_type": intelligence.scene_type,
                "scene_score": intelligence.scene_score,
                "background_cleanliness": intelligence.background_cleanliness,
                "speech_detected": intelligence.speech_detected,
                "speech_score": intelligence.speech_score,
                "voice_tone": intelligence.voice_tone,
                "style": intelligence.style,
                "topics": intelligence.topics,
                "tags": intelligence.tags,
                "segments": intelligence.segments,
                "analysis_result": intelligence.analysis_result,
                "usage_count": intelligence.usage_count,
            }
        }
    finally:
        service.close()


# ==================== 搜索接口 ====================

@router.post("/search")
async def search_assets(
    request: SearchRequest,
    current_user = Depends(get_current_user)
):
    """
    搜索素材
    
    支持按场景、情绪、风格、主题、标签等条件搜索
    """
    service = AssetSearchService()
    try:
        results = service.search(
            user_id=current_user.id,
            query=request.query,
            scene_type=request.scene_type,
            emotion=request.emotion,
            style=request.style,
            topics=request.topics,
            tags=request.tags,
            min_score=request.min_score,
            asset_role=request.asset_role,
            limit=request.limit,
        )
        return {
            "success": True,
            "data": results,
            "total": len(results),
        }
    finally:
        service.close()


@router.post("/smart-recommend")
async def smart_recommend(
    request: SmartRecommendRequest,
    current_user = Depends(get_current_user)
):
    """
    基于文案智能推荐素材
    
    分析文案内容，自动推断需要的素材类型并推荐
    """
    service = AssetSearchService()
    try:
        results = service.smart_recommend(
            user_id=current_user.id,
            script_content=request.script_content,
            shot_type=request.shot_type,
        )
        return {
            "success": True,
            "data": results,
            "total": len(results),
        }
    finally:
        service.close()


@router.post("/find-segments")
async def find_best_segments(
    request: FindSegmentsRequest,
    current_user = Depends(get_current_user)
):
    """
    为剪辑需求寻找最佳片段
    
    根据分镜需求，找到最适合的素材片段
    """
    service = AssetSearchService()
    try:
        results = service.find_best_segments(
            user_id=current_user.id,
            requirements=request.requirements,
        )
        return {
            "success": True,
            "data": results,
        }
    finally:
        service.close()


# ==================== 评分接口 ====================

@router.get("/score/{asset_id}")
async def get_asset_score(
    asset_id: int,
    current_user = Depends(get_current_user)
):
    """
    获取素材评分详情
    
    返回五个维度的详细评分分解
    """
    from app.core.database import SessionLocal
    from app.models import AssetIntelligence

    db = SessionLocal()
    try:
        intelligence = db.query(AssetIntelligence).filter(
            AssetIntelligence.asset_id == asset_id,
            AssetIntelligence.user_id == current_user.id,
        ).first()

        if not intelligence:
            raise HTTPException(status_code=404, detail="分析结果不存在")

        scoring_service = AssetScoringService()
        breakdown = scoring_service.get_score_breakdown(intelligence)

        return {
            "success": True,
            "data": breakdown,
        }
    finally:
        db.close()


# ==================== 统计接口 ====================

@router.get("/stats")
async def get_intelligence_stats(
    current_user = Depends(get_current_user)
):
    """获取素材智能分析统计"""
    from app.core.database import SessionLocal
    from app.models import AssetIntelligence, CreatorAsset

    db = SessionLocal()
    try:
        # 总素材数
        total_assets = db.query(CreatorAsset).filter(
            CreatorAsset.user_id == current_user.id
        ).count()

        # 已分析素材数
        analyzed = db.query(AssetIntelligence).filter(
            AssetIntelligence.user_id == current_user.id,
            AssetIntelligence.analysis_status == "completed",
        ).count()

        # 平均评分
        avg_score = db.query(AssetIntelligence).filter(
            AssetIntelligence.user_id == current_user.id,
            AssetIntelligence.analysis_status == "completed",
        ).all()

        avg = sum(i.overall_score for i in avg_score) / len(avg_score) if avg_score else 0

        # 高分素材数
        high_score = len([i for i in avg_score if i.overall_score >= 80])

        return {
            "success": True,
            "data": {
                "total_assets": total_assets,
                "analyzed_count": analyzed,
                "pending_count": total_assets - analyzed,
                "average_score": round(avg, 1),
                "high_score_count": high_score,
                "analysis_rate": round(analyzed / total_assets * 100, 1) if total_assets else 0,
            }
        }
    finally:
        db.close()
