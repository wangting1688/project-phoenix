from typing import Dict, Any, List

from app.core.database import SessionLocal
from app.models import RecommendationLog, CreatorProfile, ContentTopic
from app.services.ai_service import AIService
from app.services.prompt_service import PromptService
import json


class RecommendService:
    def __init__(self):
        self.db = SessionLocal()
        self.ai_service = AIService()
        self.prompt_service = PromptService()

    def recommend_topics(self, user_id: int, count: int = 5) -> List[Dict[str, Any]]:
        creator_profile = self.db.query(CreatorProfile).filter(
            CreatorProfile.user_id == user_id
        ).first()

        profile_info = {}
        if creator_profile:
            profile_info = {
                "style": creator_profile.style,
                "good_topics": creator_profile.good_topics or [],
                "fan_interests": creator_profile.fan_interests or [],
                "content_preferences": creator_profile.content_preferences or [],
            }

        prompt = self.prompt_service.get_prompt(
            "recommend_expert",
            profile=json.dumps(profile_info, ensure_ascii=False),
            count=count
        )

        result = self.ai_service.generate(prompt)
        recommendations = result.get("topics", [])

        for rec in recommendations:
            self._log_recommendation(user_id, rec)

        return recommendations

    def _log_recommendation(self, user_id: int, recommendation: Dict[str, Any]):
        log = RecommendationLog(
            user_id=user_id,
            topic=recommendation.get("title", ""),
            category=recommendation.get("category", ""),
            score=recommendation.get("consultation_score", 0),
            source="ai",
        )
        self.db.add(log)
        self.db.commit()

    def get_recommendation_history(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        logs = self.db.query(RecommendationLog).filter(
            RecommendationLog.user_id == user_id
        ).order_by(RecommendationLog.created_at.desc()).limit(limit).all()

        return [
            {
                "id": log.id,
                "topic": log.topic,
                "category": log.category,
                "score": log.score,
                "source": log.source,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]

    def close(self):
        self.db.close()
        self.prompt_service.close()