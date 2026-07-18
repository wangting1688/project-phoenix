"""
AI拍摄助手 API

帮助普通主播用最低成本完成素材采集
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from app.api.deps import get_current_user
from app.services.shooting_assistant_service import ShootingAssistantService

router = APIRouter(prefix="/shooting-assistant", tags=["AI拍摄助手"])


# ==================== 请求模型 ====================

class UpdateProfileRequest(BaseModel):
    """更新拍摄能力画像请求"""
    shooting_level: str
    available_scenes: List[str]
    camera_skill: str
    editing_skill: str
    available_time: str
    recommended_mode: str


class GeneratePlanRequest(BaseModel):
    """生成拍摄方案请求"""
    project_id: int
    script_content: str


# ==================== 能力评估接口 ====================

@router.get("/profile")
async def get_shooting_profile(current_user = Depends(get_current_user)):
    """
    获取主播拍摄能力画像
    
    根据主播已有信息，评估其拍摄能力，返回能力画像和推荐模式
    """
    service = ShootingAssistantService()
    try:
        profile = service.evaluate_shooting_profile(current_user.id)
        return {
            "success": True,
            "data": profile,
        }
    finally:
        service.close()


@router.post("/profile")
async def update_shooting_profile(
    request: UpdateProfileRequest,
    current_user = Depends(get_current_user)
):
    """更新主播拍摄能力画像"""
    service = ShootingAssistantService()
    try:
        profile_data = {
            "shooting_level": request.shooting_level,
            "available_scenes": request.available_scenes,
            "camera_skill": request.camera_skill,
            "editing_skill": request.editing_skill,
            "available_time": request.available_time,
            "recommended_mode": request.recommended_mode,
        }
        profile = service.update_shooting_profile(current_user.id, profile_data)
        return {
            "success": True,
            "data": profile,
        }
    finally:
        service.close()


# ==================== 拍摄方案接口 ====================

@router.post("/plan")
async def generate_shooting_plan(
    request: GeneratePlanRequest,
    current_user = Depends(get_current_user)
):
    """
    生成拍摄方案
    
    根据主播能力和文案内容，生成适合她的最低成本拍摄方案
    
    返回：
    - 推荐模式（基础/进阶/高级）
    - 必须拍的镜头清单
    - 可选增强的镜头清单
    - 素材需求清单
    - 预计拍摄时间
    """
    service = ShootingAssistantService()
    try:
        plan = service.generate_shooting_plan(
            user_id=current_user.id,
            project_id=request.project_id,
            script_content=request.script_content,
        )
        return {
            "success": True,
            "data": plan,
        }
    finally:
        service.close()


@router.post("/plan/{project_id}/assets")
async def match_assets_for_plan(
    project_id: int,
    current_user = Depends(get_current_user)
):
    """
    根据拍摄方案匹配已有素材
    
    返回：
    - 已匹配的素材列表
    - 缺少的素材列表（需要拍摄）
    """
    service = ShootingAssistantService()
    try:
        # 获取项目的分镜
        from app.services.video_production_service import VideoProductionService
        
        production_service = VideoProductionService()
        shots = production_service.get_project_shots(project_id)
        production_service.close()

        # 生成需求清单
        requirements = []
        for shot in shots:
            if shot.status != "deleted":
                req_type = "creator" if shot.shot_type == "口播" else "b_roll"
                requirements.append({
                    "type": req_type,
                    "role": shot.shot_type,
                    "emotion": shot.action,
                    "scene": shot.background,
                    "duration": shot.end_time - shot.start_time,
                })

        # 匹配素材
        result = service.match_assets(current_user.id, requirements)
        
        return {
            "success": True,
            "data": result,
        }
    finally:
        service.close()


# ==================== 模式说明接口 ====================

@router.get("/modes")
async def get_shooting_modes():
    """获取拍摄模式说明"""
    modes = {
        "basic": {
            "name": "基础模式",
            "description": "单人口播模式 - 一个固定机位，一个干净背景",
            "suitable_for": "大部分主播（70-80%）",
            "requirements": [
                "1个固定机位",
                "1个干净背景（白墙/书房）",
                "手机拍摄即可",
            ],
            "estimated_time": "10分钟",
            "enhancement": "靠字幕、BGM、图片提升质量",
        },
        "intermediate": {
            "name": "进阶模式",
            "description": "可以增加生活场景素材",
            "suitable_for": "约20%主播",
            "requirements": [
                "有多个可用场景",
                "如：客厅、厨房、户外",
            ],
            "estimated_time": "20-30分钟",
            "enhancement": "增加生活场景画面",
        },
        "advanced": {
            "name": "高级模式",
            "description": "支持多场景切换、故事叙述",
            "suitable_for": "少量主播",
            "requirements": [
                "有丰富拍摄经验",
                "能驾驭多场景",
                "有后期能力",
            ],
            "estimated_time": "30-60分钟",
            "enhancement": "vlog风格、故事叙述",
        },
    }

    return {
        "success": True,
        "data": modes,
    }