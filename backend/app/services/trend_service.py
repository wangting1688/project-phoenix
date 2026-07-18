from typing import Dict, Any, List

from app.core.database import SessionLocal
from app.models import ContentTopic, SuccessCase
from app.services.ai_service import AIService
from app.services.prompt_service import PromptService


class TrendService:
    def __init__(self):
        self.db = SessionLocal()
        self.ai_service = AIService()
        self.prompt_service = PromptService()

    def get_trending_topics(self, limit: int = 10) -> List[Dict[str, Any]]:
        prompt = self.prompt_service.get_prompt("trending_expert")
        result = self.ai_service.generate(prompt)
        trending_topics = result.get("trending_topics", [])

        for topic in trending_topics:
            self._update_or_create_topic(topic)

        return trending_topics

    def get_hot_topics_by_category(self, category: str, limit: int = 5) -> List[Dict[str, Any]]:
        topics = self.db.query(ContentTopic).filter(
            ContentTopic.category == category,
            ContentTopic.status == "active"
        ).order_by(ContentTopic.trend_score.desc()).limit(limit).all()

        return [
            {
                "id": t.id,
                "title": t.title,
                "category": t.category,
                "trend_score": t.trend_score,
                "consultation_score": t.consultation_score,
                "sub_tags": t.sub_tags,
            }
            for t in topics
        ]

    def get_success_cases(self, limit: int = 10) -> List[Dict[str, Any]]:
        cases = self.db.query(SuccessCase).order_by(
            SuccessCase.view_count.desc()
        ).limit(limit).all()

        return [
            {
                "id": c.id,
                "topic": c.topic,
                "creator_style": c.creator_style,
                "view_count": c.view_count,
                "like_count": c.like_count,
                "comment_count": c.comment_count,
                "consultation_count": c.consultation_count,
                "tags": c.tags,
            }
            for c in cases
        ]

    def _update_or_create_topic(self, topic_data: Dict[str, Any]):
        topic = self.db.query(ContentTopic).filter(
            ContentTopic.title == topic_data.get("title")
        ).first()

        if topic:
            topic.trend_score = topic_data.get("trend_score", 50)
            topic.consultation_score = topic_data.get("consultation_score", 50)
        else:
            topic = ContentTopic(
                title=topic_data.get("title", ""),
                category=topic_data.get("category", ""),
                trend_score=topic_data.get("trend_score", 50),
                consultation_score=topic_data.get("consultation_score", 50),
            )
            self.db.add(topic)

        self.db.commit()

    def close(self):
        self.db.close()
        self.prompt_service.close()