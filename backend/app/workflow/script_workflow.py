from typing import Dict, Any, Optional
import json

from app.workflow.base import BaseWorkflow
from app.experts.ai_expert import AIExpertService
from app.models import Script


class ScriptWorkflow(BaseWorkflow):
    STEP_NAME = "scripting"

    def __init__(self, project_id: int, topic: str):
        super().__init__(project_id)
        self.topic = topic
        self.ai_service = AIExpertService()

    def execute(self, input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result = {"success": False, "data": None, "error": None}

        try:
            self._update_project(self.STEP_NAME)
            self._update_task("full_creation", "running", 40)

            ai_result = self.ai_service.script_expert(
                self.topic,
                input_data or {}
            )

            script_story = Script(
                project_id=self.project_id,
                type="story",
                content=ai_result.get("story_version", ""),
                version=1,
                score=ai_result.get("score", {}).get("total")
            )
            self.db.add(script_story)

            script_knowledge = Script(
                project_id=self.project_id,
                type="knowledge",
                content=ai_result.get("knowledge_version", ""),
                version=1,
                score=ai_result.get("score", {}).get("total")
            )
            self.db.add(script_knowledge)

            script_chat = Script(
                project_id=self.project_id,
                type="chat",
                content=ai_result.get("chat_version", ""),
                version=1,
                score=ai_result.get("score", {}).get("total")
            )
            self.db.add(script_chat)

            self.db.commit()

            self._update_task("full_creation", "running", 60, json.dumps(ai_result, ensure_ascii=False))

            result["success"] = True
            result["data"] = ai_result

        except Exception as e:
            result["error"] = f"文案生成失败: {str(e)}"
            self._update_task("full_creation", "failed", 0, result["error"])

        return result
