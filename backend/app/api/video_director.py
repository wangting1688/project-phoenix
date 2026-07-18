"""
AI导演编排层 API

TASK-016.3A.6：AI剪辑素材编排层

提供剪辑计划生成、查看、素材不足检测等接口
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any

from app.api.deps import get_current_user
from app.core.database import get_db
from app.services.video_director_service import VideoDirectorService
from app.services.director_enhancement_service import DirectorEnhancementService

router = APIRouter(prefix="/video-director", tags=["AI导演编排"])


# ==================== 请求模型 ====================

class GeneratePlanRequest(BaseModel):
    """生成剪辑计划请求"""
    script_content: str
    script_id: Optional[int] = None
    video_project_id: Optional[int] = None
    target_duration: int = 30
    strategy: str = "standard"
    # standard / story / product / knowledge


class UpdatePlanStatusRequest(BaseModel):
    """更新计划状态"""
    status: str
    # draft / reviewed / approved / editing / completed


# ==================== 核心接口 ====================

@router.post("/generate-plan")
async def generate_edit_plan(
    request: GeneratePlanRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    AI导演生成剪辑方案

    输入文案，自动生成完整剪辑计划：
    - TASK-016.3A.7: 自动匹配爆款模板
    - 分析文案结构
    - 匹配素材片段
    - 检测素材不足
    - TASK-016.3A.7: 计算导演评分
    - TASK-016.3A.7: 自动生成补拍任务（闭环）
    - 预测完播率/转化率
    """
    service = VideoDirectorService(db=db)
    try:
        plan = service.generate_edit_plan(
            user_id=current_user.id,
            script_content=request.script_content,
            script_id=request.script_id,
            video_project_id=request.video_project_id,
            target_duration=request.target_duration,
            strategy=request.strategy,
        )
        return {
            "success": True,
            "message": f"剪辑方案已生成（{plan.matched_shots}/{plan.total_shots}镜头已匹配）",
            "data": service.format_plan(plan),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        service.close()


@router.get("/plans")
async def get_plans(
    status: Optional[str] = None,
    current_user = Depends(get_current_user)
):
    """获取剪辑计划列表"""
    service = VideoDirectorService()
    try:
        plans = service.get_user_plans(current_user.id, status)
        return {
            "success": True,
            "data": [service.format_plan(p) for p in plans],
        }
    finally:
        service.close()


@router.get("/plans/{plan_id}")
async def get_plan_detail(
    plan_id: int,
    current_user = Depends(get_current_user)
):
    """获取剪辑计划详情"""
    service = VideoDirectorService()
    try:
        plan = service.get_edit_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="剪辑计划不存在")
        if plan.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")
        return {
            "success": True,
            "data": service.format_plan(plan),
        }
    finally:
        service.close()


@router.put("/plans/{plan_id}/status")
async def update_plan_status(
    plan_id: int,
    request: UpdatePlanStatusRequest,
    current_user = Depends(get_current_user)
):
    """更新剪辑计划状态"""
    service = VideoDirectorService()
    try:
        plan = service.get_edit_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="剪辑计划不存在")
        plan.status = request.status
        service.db.commit()
        return {
            "success": True,
            "data": {"plan_id": plan.id, "status": plan.status},
        }
    finally:
        service.close()


# ==================== 素材不足检测 ====================

@router.get("/plans/{plan_id}/shooting-suggestions")
async def get_shooting_suggestions(
    plan_id: int,
    current_user = Depends(get_current_user)
):
    """获取补拍建议"""
    service = VideoDirectorService()
    try:
        plan = service.get_edit_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="剪辑计划不存在")
        if plan.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")
        return {
            "success": True,
            "data": {
                "plan_id": plan.id,
                "title": plan.title,
                "match_status": plan.match_status,
                "total_shots": plan.total_shots,
                "matched_shots": plan.matched_shots,
                "missing_shots": plan.missing_shots,
                "shooting_suggestions": plan.shooting_suggestions or [],
            },
        }
    finally:
        service.close()


# ==================== 商业价值评分 ====================

@router.post("/update-commercial-scores")
async def update_commercial_scores(
    current_user = Depends(get_current_user)
):
    """批量更新素材片段的商业价值评分"""
    service = VideoDirectorService()
    try:
        updated = service.update_commercial_value_scores(current_user.id)
        return {
            "success": True,
            "message": f"已更新 {updated} 个片段的商业价值评分",
            "data": {"updated_count": updated},
        }
    finally:
        service.close()


# ==================== 统计接口 ====================

@router.get("/stats")
async def get_director_stats(
    current_user = Depends(get_current_user)
):
    """获取导演编排统计"""
    service = VideoDirectorService()
    try:
        plans = service.get_user_plans(current_user.id)
        total_plans = len(plans)
        matched_plans = len([p for p in plans if p.match_status == "matched"])
        partial_plans = len([p for p in plans if p.match_status == "partial"])
        total_shots = sum(p.total_shots for p in plans)
        total_matched = sum(p.matched_shots for p in plans)
        total_missing = sum(p.missing_shots for p in plans)

        avg_completion = 0
        avg_conversion = 0
        if plans:
            avg_completion = round(sum(p.predicted_completion_rate for p in plans) / len(plans), 2)
            avg_conversion = round(sum(p.predicted_conversion_rate for p in plans) / len(plans), 3)

        return {
            "success": True,
            "data": {
                "total_plans": total_plans,
                "matched_plans": matched_plans,
                "partial_plans": partial_plans,
                "total_shots": total_shots,
                "matched_shots": total_matched,
                "missing_shots": total_missing,
                "match_rate": round(total_matched / total_shots * 100, 1) if total_shots > 0 else 0,
                "avg_predicted_completion": avg_completion,
                "avg_predicted_conversion": avg_conversion,
            },
        }
    finally:
        service.close()


# ==================== TASK-016.3A.7: 爆款模板管理 ====================

@router.get("/templates")
async def get_templates(
    template_type: Optional[str] = None,
    industry: Optional[str] = None,
    current_user = Depends(get_current_user)
):
    """获取爆款模板列表"""
    service = DirectorEnhancementService()
    try:
        templates = service.get_templates(template_type, industry)
        return {
            "success": True,
            "data": [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "template_type": t.template_type,
                    "industry": t.industry,
                    "content_type": t.content_type,
                    "structure": t.structure,
                    "best_for": t.best_for,
                    "target_audience": t.target_audience,
                    "conversion_rate": t.conversion_rate,
                    "completion_rate": t.completion_rate,
                    "template_score": t.template_score,
                    "usage_count": t.usage_count,
                    "is_preset": t.is_preset,
                }
                for t in templates
            ],
        }
    finally:
        service.close()


@router.get("/templates/{template_id}")
async def get_template_detail(
    template_id: int,
    current_user = Depends(get_current_user)
):
    """获取模板详情"""
    service = DirectorEnhancementService()
    try:
        template = service.get_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="模板不存在")
        return {
            "success": True,
            "data": {
                "id": template.id,
                "name": template.name,
                "description": template.description,
                "template_type": template.template_type,
                "industry": template.industry,
                "content_type": template.content_type,
                "structure": template.structure,
                "best_for": template.best_for,
                "target_audience": template.target_audience,
                "conversion_rate": template.conversion_rate,
                "completion_rate": template.completion_rate,
                "template_score": template.template_score,
                "usage_count": template.usage_count,
                "is_preset": template.is_preset,
            },
        }
    finally:
        service.close()


@router.post("/match-template")
async def match_template(
    script_content: str,
    target_duration: int = 30,
    current_user = Depends(get_current_user)
):
    """预览文案匹配的最佳模板"""
    service = DirectorEnhancementService()
    try:
        template = service.match_best_template(script_content, target_duration)
        if not template:
            return {
                "success": True,
                "data": None,
                "message": "未找到匹配模板",
            }
        return {
            "success": True,
            "data": {
                "id": template.id,
                "name": template.name,
                "description": template.description,
                "template_type": template.template_type,
                "structure": template.structure,
                "best_for": template.best_for,
                "conversion_rate": template.conversion_rate,
                "completion_rate": template.completion_rate,
                "template_score": template.template_score,
            },
        }
    finally:
        service.close()


# ==================== TASK-016.3A.7: 补拍闭环 ====================

@router.get("/plans/{plan_id}/shooting-tasks")
async def get_shooting_tasks_status(
    plan_id: int,
    current_user = Depends(get_current_user)
):
    """获取补拍任务状态（闭环检查）"""
    service = DirectorEnhancementService()
    try:
        result = service.check_shooting_tasks_completed(plan_id)
        return {
            "success": True,
            "data": result,
        }
    finally:
        service.close()


@router.post("/plans/{plan_id}/regenerate")
async def regenerate_plan(
    plan_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    补拍完成后重新生成方案

    闭环：补拍完成 → 重新分析素材 → 重新匹配 → 更新方案
    """
    director_service = VideoDirectorService(db=db)
    try:
        old_plan = director_service.get_edit_plan(plan_id)
        if not old_plan:
            raise HTTPException(status_code=404, detail="剪辑计划不存在")
        if old_plan.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")

        # 复用同一 db (director_service 内部同 session), 消除 request 内嵌套 session
        task_status = director_service.enhancement.check_shooting_tasks_completed(plan_id)

        if not task_status.get("can_regenerate"):
            return {
                "success": False,
                "message": "补拍任务尚未完成，无法重新生成",
                "data": task_status,
            }

        # 使用原文案重新生成
        new_plan = director_service.generate_edit_plan(
            user_id=current_user.id,
            script_content=old_plan.script_content,
            script_id=old_plan.script_id,
            video_project_id=old_plan.video_project_id,
            target_duration=old_plan.total_duration,
            strategy=old_plan.editing_strategy,
        )

        return {
            "success": True,
            "message": f"方案已重新生成（{new_plan.matched_shots}/{new_plan.total_shots}镜头已匹配，评分{new_plan.director_score}）",
            "data": director_service.format_plan(new_plan),
        }
    finally:
        director_service.close()
