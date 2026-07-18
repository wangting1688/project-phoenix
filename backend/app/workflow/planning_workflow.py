from typing import Dict, Any, Optional
import json

from app.workflow.base import BaseWorkflow
from app.experts.ai_expert import AIExpertService
from app.models import Planning


class PlanningWorkflow(BaseWorkflow):
    STEP_NAME = "planning"

    def __init__(self, project_id: int):
        super().__init__(project_id)
        self.ai_service = AIExpertService()

    def execute(self, input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result = {"success": False, "data": None, "error": None}

        try:
            self._update_project(self.STEP_NAME)
            self._update_task("full_creation", "running", 25)

            ai_result = self.ai_service.planning_expert(input_data or {})

            planning = Planning(
                project_id=self.project_id,
                target="建立信任",
                style=ai_result.get("style"),
                duration=ai_result.get("duration"),
                scene=ai_result.get("scene"),
                strategy=ai_result.get("structure")
            )
            self.db.add(planning)
            self.db.commit()

            self._update_task("full_creation", "running", 35, json.dumps(ai_result, ensure_ascii=False))

            result["success"] = True
            result["data"] = ai_result

        except Exception as e:
            result["error"] = f"策划失败: {str(e)}"
            self._update_task("full_creation", "failed", 0, result["error"])

        return result
