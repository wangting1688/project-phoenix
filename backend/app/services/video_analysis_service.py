from typing import Dict, Any

from app.core.database import SessionLocal
from app.models import SuccessCase
from app.services.ai_service import AIService
from app.services.prompt_service import PromptService


class VideoAnalysisService:
    def __init__(self):
        self.db = SessionLocal()
        self.ai_service = AIService()
        self.prompt_service = PromptService()

    def analyze_video_url(self, url: str) -> Dict[str, Any]:
        prompt = self.prompt_service.get_prompt(
            "video_analyzer",
            url=url
        )
        result = self.ai_service.generate(prompt)
        return result

    def analyze_video_content(self, content: str) -> Dict[str, Any]:
        prompt = self.prompt_service.get_prompt(
            "video_content_analyzer",
            content=content
        )
        result = self.ai_service.generate(prompt)
        return result

    def extract_success_patterns(self, video_data: Dict[str, Any]) -> Dict[str, Any]:
        patterns = {
            "structure": video_data.get("structure", {}),
            "opening_hook": video_data.get("opening_hook", ""),
            "emotion_triggers": video_data.get("emotion_triggers", []),
            "consultation_points": video_data.get("consultation_points", []),
            "tags": video_data.get("tags", []),
        }

        self._save_success_case(video_data)
        return patterns

    def _save_success_case(self, video_data: Dict[str, Any]):
        case = SuccessCase(
            topic=video_data.get("topic", ""),
            creator_style=video_data.get("creator_style", ""),
            structure=video_data.get("structure", ""),
            opening=video_data.get("opening_hook", ""),
            emotion=video_data.get("emotion", ""),
            view_count=video_data.get("view_count", 0),
            like_count=video_data.get("like_count", 0),
            comment_count=video_data.get("comment_count", 0),
            consultation_count=video_data.get("consultation_count", 0),
            tags=video_data.get("tags", []),
        )
        self.db.add(case)
        self.db.commit()

    def close(self):
        self.db.close()
        self.prompt_service.close()