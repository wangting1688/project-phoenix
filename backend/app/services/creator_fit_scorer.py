"""
Creator Fit Score - 主播适配评分服务

TASK-016.3B.4：AI Growth Review Memory

核心职责：
1. 评估内容结构与主播画像的匹配度
2. 不同主播匹配不同的内容类型
3. 避免"爆款结构对但主播演不出来"的问题
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.video_edit_plan import VideoEditPlan, VideoEditSegment
from app.models.intelligence import CreatorProfile
from app.models.asset_segment import CreatorPerformanceProfile
from app.models.video_performance import CreatorStrategyProfile
from app.models.user import User


class CreatorFitScorer:
    """主播适配评分器"""

    CONTENT_CREATOR_FIT = {
        "story": {
            "preferred_ages": [40, 60],
            "preferred_styles": ["experienced", "mature", "warm"],
            "preferred_genders": ["female"],
            "score": 90,
        },
        "experience": {
            "preferred_ages": [35, 60],
            "preferred_styles": ["experienced", "mature", "trustworthy"],
            "score": 88,
        },
        "emotion": {
            "preferred_ages": [30, 60],
            "preferred_styles": ["emotional", "warm", "caring"],
            "score": 85,
        },
        "knowledge": {
            "preferred_ages": [25, 50],
            "preferred_styles": ["professional", "expert", "authoritative"],
            "score": 85,
        },
        "review": {
            "preferred_ages": [25, 40],
            "preferred_styles": ["young", "energetic", "professional"],
            "score": 88,
        },
        "challenge": {
            "preferred_ages": [22, 35],
            "preferred_styles": ["young", "energetic", "creative"],
            "score": 85,
        },
        "expert": {
            "preferred_ages": [30, 60],
            "preferred_styles": ["professional", "expert", "authoritative"],
            "score": 88,
        },
    }

    ENERGY_LEVELS = {
        "low": ["warm", "calm", "mature", "experienced"],
        "medium": ["professional", "trustworthy", "caring"],
        "high": ["young", "energetic", "creative", "lively"],
    }

    def __init__(self, db: Optional[Session] = None):
        # 支持 API 层 Depends(get_db) 注入, 消除嵌套 SessionLocal 引发的 sqlite 单写者锁
        if db is not None:
            self.db = db
            self._owns_db = False
        else:
            self.db = SessionLocal()
            self._owns_db = True

    def close(self):
        if getattr(self, '_owns_db', True):
            self.db.close()

    def score_creator_fit(self, plan_id: int, creator_id: int = None) -> Dict[str, Any]:
        """评分主播适配度"""
        plan = self._get_plan(plan_id)
        if not plan:
            return {"success": False, "error": "导演方案不存在"}

        segments = self._get_segments(plan_id)

        if not creator_id:
            creator_id = getattr(plan, "creator_id", None) or plan.user_id

        if not creator_id:
            return {"success": True, "score": 70, "message": "无主播信息，使用默认分"}

        creator_profile = self._get_creator_profile(creator_id)
        strategy_profile = self._get_creator_strategy(creator_id)
        user = self._get_user(creator_id)

        content_type = self._identify_content_type(segments, plan)
        fit_result = self._evaluate_fit(content_type, creator_profile, strategy_profile, user)

        return {
            "success": True,
            "creator_id": creator_id,
            "content_type": content_type,
            "fit_score": fit_result["score"],
            "fit_level": self._get_fit_level(fit_result["score"]),
            "match_details": fit_result["details"],
            "suggestions": fit_result["suggestions"],
        }

    def _identify_content_type(self, segments: List[VideoEditSegment], plan: VideoEditPlan) -> str:
        """识别内容类型"""
        role_count = {}
        for segment in segments:
            role = segment.role or "general"
            role_count[role] = role_count.get(role, 0) + 1

        max_role = max(role_count.items(), key=lambda x: x[1])[0] if role_count else "general"

        role_to_type = {
            "hook": "story",
            "problem": "story",
            "knowledge": "knowledge",
            "solution": "knowledge",
            "social_proof": "experience",
            "conversion": "review",
            "story": "story",
            "experience": "experience",
            "emotion": "emotion",
            "review": "review",
            "challenge": "challenge",
            "expert": "expert",
        }

        return role_to_type.get(max_role, "story")

    def _evaluate_fit(self, content_type: str, creator_profile: CreatorProfile,
                     strategy_profile: CreatorStrategyProfile, user: User) -> Dict[str, Any]:
        """评估匹配度"""
        if content_type not in self.CONTENT_CREATOR_FIT:
            content_type = "story"

        fit_config = self.CONTENT_CREATOR_FIT[content_type]

        score = 70
        details = []
        suggestions = []

        if user and hasattr(user, "age") and user.age:
            age_min, age_max = fit_config["preferred_ages"]
            if age_min <= user.age <= age_max:
                score += 10
                details.append(f"年龄匹配（{age_min}-{age_max}岁）")
            else:
                if user.age < age_min:
                    suggestions.append(f"内容类型偏好{age_min}岁以上主播，当前{user.age}岁偏年轻")
                else:
                    suggestions.append(f"内容类型偏好{age_max}岁以下主播，当前{user.age}岁偏成熟")

        if creator_profile:
            style = getattr(creator_profile, "creator_style", "")
            if style and style in fit_config.get("preferred_styles", []):
                score += 10
                details.append(f"风格匹配：{style}")
            elif style:
                suggestions.append(f"建议发挥主播{style}风格优势")

        if strategy_profile:
            energy_level = self._get_energy_level(creator_profile)
            preferred_energies = fit_config.get("preferred_styles", [])

            for energy_styles in self.ENERGY_LEVELS.values():
                if energy_level in energy_styles and any(es in preferred_energies for es in energy_styles):
                    score += 5
                    details.append(f"能量水平匹配：{energy_level}")
                    break

        history_fit = self._evaluate_history_fit(creator_profile, content_type)
        if history_fit > 0:
            score += history_fit
            details.append(f"历史匹配度+{history_fit}")

        score = min(100, max(0, score))

        return {
            "score": score,
            "details": details,
            "suggestions": suggestions,
        }

    def _evaluate_history_fit(self, creator_profile: CreatorProfile, content_type: str) -> int:
        """评估历史匹配度"""
        if not creator_profile:
            return 0

        bonus = 0
        for attr in ["story_video_count", "knowledge_video_count", "experience_video_count"]:
            if hasattr(creator_profile, attr):
                count = getattr(creator_profile, attr, 0)
                if count and count > 5:
                    bonus += 2
                    break

        return min(10, bonus)

    def _get_energy_level(self, creator_profile: CreatorProfile) -> str:
        """获取能量水平"""
        if not creator_profile:
            return "medium"

        style = getattr(creator_profile, "creator_style", "")
        for level, styles in self.ENERGY_LEVELS.items():
            if style in styles:
                return level
        return "medium"

    def _get_fit_level(self, score: int) -> str:
        """获取适配等级"""
        if score >= 85:
            return "excellent"
        elif score >= 70:
            return "good"
        elif score >= 55:
            return "acceptable"
        else:
            return "poor"

    def _get_plan(self, plan_id: int):
        if not plan_id:
            return None
        return self.db.query(VideoEditPlan).filter(VideoEditPlan.id == plan_id).first()

    def _get_segments(self, plan_id: int):
        if not plan_id:
            return []
        return self.db.query(VideoEditSegment).filter(
            VideoEditSegment.edit_plan_id == plan_id
        ).all()

    def _get_creator_profile(self, creator_id: int):
        return self.db.query(CreatorProfile).filter(
            CreatorProfile.user_id == creator_id
        ).first()

    def _get_creator_strategy(self, creator_id: int):
        return self.db.query(CreatorStrategyProfile).filter(
            CreatorStrategyProfile.user_id == creator_id
        ).first()

    def _get_user(self, user_id: int):
        return self.db.query(User).filter(User.id == user_id).first()
