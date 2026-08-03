from typing import Dict, Any, Optional
import json

from app.workflow.base import BaseWorkflow
from app.experts.ai_expert import AIExpertService
from app.models import Review, Script


class ReviewWorkflow(BaseWorkflow):
    STEP_NAME = "reviewing"

    def __init__(self, project_id: int):
        super().__init__(project_id)
        self.ai_service = AIExpertService()

    def execute(self, input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result = {"success": False, "data": None, "error": None}

        try:
            self._update_project(self.STEP_NAME)
            self._update_task("full_creation", "running", 65)

            script = input_data or {}
            all_scripts = [
                script.get("story_version", ""),
                script.get("knowledge_version", ""),
                script.get("chat_version", "")
            ]
            combined_script = "\n\n".join(all_scripts)

            ai_result = self.ai_service.compliance_expert(combined_script)

            # 首轮不通过时, 用 AI 给出的合规改写稿复审一次, 通过则改写入库继续流程
            if not ai_result.get("pass"):
                fixed = (ai_result.get("modified_text") or "").strip()
                if fixed:
                    recheck = self.ai_service.compliance_expert(fixed)
                    if recheck.get("pass"):
                        self._apply_compliant_rewrite(fixed)
                        ai_result = recheck
                        ai_result["auto_fixed"] = True

            review = Review(
                project_id=self.project_id,
                original_score=script.get("score", {}).get("total"),
                marketing_score=None,
                risk_score=ai_result.get("risk_score"),
                consult_score=None,
                result="pass" if ai_result.get("pass") else "fail"
            )
            self.db.add(review)
            self.db.commit()

            if not ai_result.get("pass"):
                problems = ai_result.get("problems") or ["未给出具体原因"]
                result["error"] = "合规审核未通过: " + "; ".join(str(x) for x in problems)
                self._update_task("full_creation", "failed", 65, result["error"])
                return result

            self._update_task("full_creation", "running", 80, json.dumps(ai_result, ensure_ascii=False))

            result["success"] = True
            result["data"] = ai_result

        except Exception as e:
            result["error"] = f"审核失败: {str(e)}"
            self._update_task("full_creation", "failed", 65, result["error"])

        return result

    def _apply_compliant_rewrite(self, fixed_text: str):
        """把合规改写稿写回文案, 避免违规内容留在库里"""
        scripts = self.db.query(Script).filter(
            Script.project_id == self.project_id
        ).order_by(Script.id).all()
        if scripts:
            scripts[0].content = fixed_text
            self.db.commit()
