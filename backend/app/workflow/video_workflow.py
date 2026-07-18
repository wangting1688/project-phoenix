from typing import Dict, Any, Optional
import json

from app.workflow.base import BaseWorkflow
from app.experts.ai_expert import AIExpertService
from app.models import Video


class VideoGenerationWorkflow(BaseWorkflow):
    STEP_NAME = "generating_video"

    def __init__(self, project_id: int):
        super().__init__(project_id)
        self.ai_service = AIExpertService()

    def execute(self, input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result = {"success": False, "data": None, "error": None}

        try:
            self._update_project(self.STEP_NAME)
            self._update_task("full_creation", "running", 85)

            script = input_data or {}
            main_script = script.get("story_version", "") or script.get("knowledge_version", "")

            ai_result = self.ai_service.video_expert(main_script)

            video = Video(
                project_id=self.project_id,
                url=None,
                cover_url=None,
                duration=60,
                resolution="1080p",
                status="generated"
            )
            self.db.add(video)
            self.db.commit()

            self._update_task("full_creation", "running", 90, json.dumps(ai_result, ensure_ascii=False))

            result["success"] = True
            result["data"] = ai_result

        except Exception as e:
            result["error"] = f"视频生成失败: {str(e)}"
            self._update_task("full_creation", "failed", 0, result["error"])

        return result
