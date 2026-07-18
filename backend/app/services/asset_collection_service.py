"""
素材采集服务

主播素材采集中心 - 告诉主播应该拍什么素材

核心逻辑：
1. 根据主播能力和内容方向，推荐需要采集的素材
2. 追踪采集进度
3. 让素材库越来越丰富，AI剪辑能力越来越强
"""

from typing import Dict, Any, List, Optional
from datetime import date, datetime
from app.core.database import SessionLocal
from app.models import (
    CreatorAsset,
    AssetCollectionTask,
    AssetCollectionPlan,
    AssetCategory,
    DailyAssetRecommendation,
    CreatorProfile,
)


class AssetCollectionService:
    """素材采集服务"""

    def __init__(self):
        self.db = SessionLocal()

    # ==================== 每日推荐 ====================

    def get_daily_recommendation(self, user_id: int, target_date: Optional[date] = None) -> Dict[str, Any]:
        """
        获取每日素材采集推荐
        
        根据主播当前素材库的缺口，生成推荐清单
        """
        if not target_date:
            target_date = date.today()

        # 检查是否已有今日推荐
        existing = self.db.query(DailyAssetRecommendation).filter(
            DailyAssetRecommendation.user_id == user_id,
            DailyAssetRecommendation.recommend_date == target_date,
        ).first()

        if existing:
            return self._format_daily_recommendation(existing)

        # 生成新的推荐
        recommendations = self._generate_recommendations(user_id)

        # 计算统计
        total_estimated = sum(r.get("estimated_minutes", 5) for r in recommendations)
        high_priority = len([r for r in recommendations if r.get("priority") == "high"])

        # 保存到数据库
        daily_rec = DailyAssetRecommendation(
            user_id=user_id,
            recommend_date=target_date,
            recommendations=recommendations,
            total_recommended=len(recommendations),
            high_priority_count=high_priority,
            total_estimated_time=total_estimated,
        )

        self.db.add(daily_rec)
        self.db.commit()
        self.db.refresh(daily_rec)

        return self._format_daily_recommendation(daily_rec)

    def _generate_recommendations(self, user_id: int) -> List[Dict[str, Any]]:
        """生成推荐列表"""
        recommendations = []
        
        # 获取主播已有素材
        existing_assets = self.db.query(CreatorAsset).filter(
            CreatorAsset.user_id == user_id
        ).all()

        existing_emotions = set()
        existing_scenes = set()
        for asset in existing_assets:
            if asset.emotion:
                existing_emotions.add(asset.emotion)
            if asset.scene:
                existing_scenes.add(asset.scene)

        # 获取主播能力画像
        profile = self.db.query(CreatorProfile).filter(
            CreatorProfile.user_id == user_id
        ).first()

        shooting_level = "基础"
        if profile and profile.shooting_profile:
            shooting_level = profile.shooting_profile.get("shooting_level", "基础")

        # 基础素材（必须）
        basic_materials = [
            {
                "rank": 1,
                "title": "正面讲话 30秒",
                "priority": "high",
                "reason": "最基础的口播素材，使用率最高",
                "estimated_minutes": 5,
                "tags": ["正面", "讲话", "自然"],
                "emotion": "自然",
                "scene": "室内",
                "shooting_guide": {
                    "scene": "室内/白墙背景",
                    "action": "正面坐姿讲话",
                    "emotion": "自然亲切",
                    "duration_min": 20,
                    "duration_max": 60,
                    "tips": [
                        "坐姿端正，肩膀放松",
                        "眼睛看向镜头",
                        "声音清晰，语速适中",
                        "背景干净，光线充足",
                    ],
                },
            },
            {
                "rank": 2,
                "title": "微笑点头 10秒",
                "priority": "high",
                "reason": "用于视频开头结尾，增加亲切感",
                "estimated_minutes": 3,
                "tags": ["微笑", "点头", "正面"],
                "emotion": "开心",
                "scene": "室内",
                "shooting_guide": {
                    "scene": "室内/干净背景",
                    "action": "微笑点头",
                    "emotion": "亲切友好",
                    "duration_min": 5,
                    "duration_max": 15,
                    "tips": [
                        "微笑自然，不要僵硬",
                        "轻轻点头1-2次",
                        "眼神温柔",
                    ],
                },
            },
            {
                "rank": 3,
                "title": "思考状态 10秒",
                "priority": "high",
                "reason": "用于提出问题、引出内容",
                "estimated_minutes": 3,
                "tags": ["思考", "认真", "正面"],
                "emotion": "思考",
                "scene": "室内",
                "shooting_guide": {
                    "scene": "室内",
                    "action": "思考状",
                    "emotion": "认真思考",
                    "duration_min": 5,
                    "duration_max": 15,
                    "tips": [
                        "稍微皱眉，眼神看向斜上方",
                        "可以用手托下巴",
                        "停顿2-3秒再开口",
                    ],
                },
            },
        ]

        # 进阶素材（中优先级）
        intermediate_materials = [
            {
                "rank": 4,
                "title": "喝水动作 5秒",
                "priority": "medium",
                "reason": "增加自然感，适合生活类内容",
                "estimated_minutes": 3,
                "tags": ["喝水", "生活", "自然"],
                "emotion": "自然",
                "scene": "室内",
                "shooting_guide": {
                    "scene": "室内/客厅",
                    "action": "喝水",
                    "emotion": "自然放松",
                    "duration_min": 3,
                    "duration_max": 10,
                    "tips": [
                        "拿杯子的动作自然",
                        "喝一小口即可",
                        "表情放松",
                    ],
                },
            },
            {
                "rank": 5,
                "title": "走路画面 10秒",
                "priority": "medium",
                "reason": "适合过渡和转场",
                "estimated_minutes": 5,
                "tags": ["走路", "户外", "运动"],
                "emotion": "自然",
                "scene": "户外",
                "shooting_guide": {
                    "scene": "户外/小区/公园",
                    "action": "走路",
                    "emotion": "悠闲自然",
                    "duration_min": 5,
                    "duration_max": 20,
                    "tips": [
                        "脚步自然，不要太快",
                        "可以从侧面拍",
                        "背景干净",
                    ],
                },
            },
        ]

        # 增强素材（低优先级）
        enhancement_materials = [
            {
                "rank": 6,
                "title": "厨房场景 15秒",
                "priority": "low",
                "reason": "适合饮食健康类内容",
                "estimated_minutes": 5,
                "tags": ["厨房", "做饭", "生活"],
                "emotion": "自然",
                "scene": "厨房",
                "shooting_guide": {
                    "scene": "厨房",
                    "action": "准备食材/做饭",
                    "emotion": "认真专注",
                    "duration_min": 10,
                    "duration_max": 30,
                    "tips": [
                        "动作自然",
                        "光线充足",
                        "厨房整洁",
                    ],
                },
            },
        ]

        # 根据主播等级选择推荐
        if shooting_level == "基础":
            recommendations = basic_materials
        elif shooting_level == "进阶":
            recommendations = basic_materials + intermediate_materials
        else:
            recommendations = basic_materials + intermediate_materials + enhancement_materials

        # 过滤掉已经有的素材（基于情绪和场景匹配）
        filtered = []
        for rec in recommendations:
            emotion = rec.get("emotion", "")
            scene = rec.get("scene", "")

            # 检查是否已有类似素材
            has_similar = False
            for asset in existing_assets:
                if asset.emotion == emotion and asset.scene == scene:
                    has_similar = True
                    break

            if not has_similar:
                filtered.append(rec)

        # 如果全部都有了，返回一些增强建议
        if not filtered:
            filtered = [
                {
                    "rank": 1,
                    "title": "🎉 基础素材已充足",
                    "priority": "high",
                    "reason": "你的素材库已经很棒了！可以尝试更多场景",
                    "estimated_minutes": 0,
                    "tags": [],
                    "emotion": "",
                    "scene": "",
                    "shooting_guide": {},
                },
            ]

        return filtered

    def _format_daily_recommendation(self, daily_rec: DailyAssetRecommendation) -> Dict[str, Any]:
        """格式化每日推荐"""
        return {
            "recommend_date": daily_rec.recommend_date.isoformat() if daily_rec.recommend_date else None,
            "recommendations": daily_rec.recommendations or [],
            "total_recommended": daily_rec.total_recommended,
            "high_priority_count": daily_rec.high_priority_count,
            "total_estimated_time": daily_rec.total_estimated_time,
        }

    # ==================== 采集任务管理 ====================

    def create_collection_task(
        self,
        user_id: int,
        title: str,
        asset_type: str = "video",
        asset_role: str = "creator",
        priority: str = "medium",
        description: Optional[str] = None,
        shooting_guide: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        scene: Optional[str] = None,
        emotion: Optional[str] = None,
        estimated_time: int = 5,
    ) -> AssetCollectionTask:
        """创建采集任务"""
        task = AssetCollectionTask(
            user_id=user_id,
            title=title,
            description=description,
            priority=priority,
            asset_type=asset_type,
            asset_role=asset_role,
            shooting_guide=shooting_guide,
            tags=tags,
            scene=scene,
            emotion=emotion,
            estimated_time=estimated_time,
            status="pending",
            progress=0,
        )

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        return task

    def get_user_tasks(
        self,
        user_id: int,
        status: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> List[AssetCollectionTask]:
        """获取用户的采集任务"""
        query = self.db.query(AssetCollectionTask).filter(
            AssetCollectionTask.user_id == user_id
        )

        if status:
            query = query.filter(AssetCollectionTask.status == status)
        if priority:
            query = query.filter(AssetCollectionTask.priority == priority)

        return query.order_by(
            AssetCollectionTask.priority.desc(),
            AssetCollectionTask.created_at.desc(),
        ).all()

    def update_task_status(
        self,
        task_id: int,
        status: str,
        uploaded_asset_id: Optional[int] = None,
    ) -> Optional[AssetCollectionTask]:
        """更新任务状态"""
        task = self.db.query(AssetCollectionTask).filter(
            AssetCollectionTask.id == task_id
        ).first()

        if not task:
            return None

        task.status = status

        if status == "completed":
            task.progress = 100
        elif status == "in_progress":
            task.progress = 50

        if uploaded_asset_id:
            task.uploaded_asset_id = uploaded_asset_id

        self.db.commit()
        self.db.refresh(task)

        return task

    # ==================== 素材库统计 ====================

    def get_asset_library_stats(self, user_id: int) -> Dict[str, Any]:
        """获取素材库统计"""
        assets = self.db.query(CreatorAsset).filter(
            CreatorAsset.user_id == user_id
        ).all()

        # 按类型统计
        by_role = {}
        for asset in assets:
            role = asset.asset_role or "creator"
            if role not in by_role:
                by_role[role] = 0
            by_role[role] += 1

        # 按场景统计
        by_scene = {}
        for asset in assets:
            scene = asset.scene or "未分类"
            if scene not in by_scene:
                by_scene[scene] = 0
            by_scene[scene] += 1

        # 按情绪统计
        by_emotion = {}
        for asset in assets:
            emotion = asset.emotion or "未分类"
            if emotion not in by_emotion:
                by_emotion[emotion] = 0
            by_emotion[emotion] += 1

        # 总时长
        total_duration = sum(asset.duration or 0 for asset in assets)

        # 采集任务完成情况
        tasks = self.db.query(AssetCollectionTask).filter(
            AssetCollectionTask.user_id == user_id
        ).all()
        completed_tasks = len([t for t in tasks if t.status == "completed"])

        return {
            "total_assets": len(assets),
            "total_duration": round(total_duration, 1),
            "by_role": by_role,
            "by_scene": by_scene,
            "by_emotion": by_emotion,
            "tasks_total": len(tasks),
            "tasks_completed": completed_tasks,
            "completion_rate": round(completed_tasks / len(tasks) * 100, 1) if tasks else 0,
        }

    # ==================== 素材分类体系 ====================

    def get_asset_categories(self, category_type: str = "creator") -> List[Dict[str, Any]]:
        """获取素材分类列表"""
        categories = self.db.query(AssetCategory).filter(
            AssetCategory.category_type == category_type
        ).order_by(AssetCategory.sort_order).all()

        return [
            {
                "id": cat.id,
                "name": cat.name,
                "description": cat.description,
                "shooting_tips": cat.shooting_tips,
                "recommended_duration": cat.recommended_duration,
                "is_required": cat.is_required,
            }
            for cat in categories
        ]

    def close(self):
        self.db.close()