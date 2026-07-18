from typing import Dict, Any, Optional
import json

from app.workflow.base import BaseWorkflow
from app.experts.ai_expert import AIExpertService


class OptimizationWorkflow(BaseWorkflow):
    STEP_NAME = "optimizing"

    def __init__(self, project_id: int, topic: str):
        super().__init__(project_id)
        self.topic = topic
        self.ai_service = AIExpertService()

    def execute(self, input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result = {"success": False, "data": None, "error": None}

        try:
            self._update_project(self.STEP_NAME)
            self._update_task("full_creation", "running", 95)

            script = input_data or {}
            main_script = script.get("story_version", "") or script.get("knowledge_version", "")

            ai_result = self.ai_service.operation_expert(self.topic, main_script)

            self._update_task("full_creation", "running", 98, json.dumps(ai_result, ensure_ascii=False))

            result["success"] = True
            result["data"] = ai_result

        except Exception as e:
            result["error"] = f"运营优化失败: {str(e)}"
            self._update_task("full_creation", "failed", 0, result["error"])

        return result
