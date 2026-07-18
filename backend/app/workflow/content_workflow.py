from typing import Dict, Any, Optional
import json

from app.workflow.base import BaseWorkflow
from app.experts.ai_expert import AIExpertService
from app.models import Content


class ContentAnalysisWorkflow(BaseWorkflow):
    STEP_NAME = "analyzing"

    def __init__(self, project_id: int, topic: str):
        super().__init__(project_id)
        self.topic = topic
        self.ai_service = AIExpertService()

    def execute(self, input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result = {"success": False, "data": None, "error": None}

        try:
            self._update_project(self.STEP_NAME)
            self._update_task("full_creation", "running", 10)

            ai_result = self.ai_service.content_expert(self.topic)

            content = Content(
                project_id=self.project_id,
                title=ai_result.get("title"),
                summary=ai_result.get("reason"),
                audience=ai_result.get("audience"),
                emotion=ai_result.get("content_angle"),
                tags=json.dumps({
                    "category": ai_result.get("category"),
                    "pain_point": ai_result.get("pain_point")
                }),
                score=ai_result.get("consultation_score")
            )
            self.db.add(content)
            self.db.commit()

            self._update_task("full_creation", "running", 20, json.dumps(ai_result, ensure_ascii=False))

            result["success"] = True
            result["data"] = ai_result

        except Exception as e:
            result["error"] = f"内容分析失败: {str(e)}"
            self._update_task("full_creation", "failed", 0, result["error"])

        return result
