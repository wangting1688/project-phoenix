from typing import Dict, Any, Optional
import json

from app.workflow.base import BaseWorkflow
from app.experts.ai_expert import AIExpertService
from app.models import Script


class ScriptWorkflow(BaseWorkflow):
    STEP_NAME = "scripting"

    def __init__(self, project_id: int, topic: str,
                 platform: str = "抖音", persona: str = ""):
        super().__init__(project_id)
        self.topic = topic
        self.platform = platform or "抖音"
        self.persona = persona or ""
        self.ai_service = AIExpertService()

    def execute(self, input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result = {"success": False, "data": None, "error": None}

        try:
            self._update_project(self.STEP_NAME)
            self._update_task("full_creation", "running", 40)

            hot_samples = self._load_hot_samples()
            ai_result = self.ai_service.script_expert(
                self.topic,
                input_data or {},
                platform=self.platform,
                persona=self.persona,
                hot_samples=hot_samples,
            )

            # 自评低分时自动重写一次，保留分数更高的一版
            if not ai_result.get("_degraded") and ai_result.get("story_version"):
                critic = self.ai_service.critic_expert(ai_result.get("story_version", ""))
                if not critic.get("pass", True):
                    retry = self.ai_service.script_expert(
                        self.topic,
                        input_data or {},
                        platform=self.platform,
                        persona=self.persona,
                        hot_samples=hot_samples,
                    )
                    if (not retry.get("_degraded")
                            and retry.get("story_version")
                            and self._score_of(retry) >= self._score_of(ai_result)):
                        ai_result = retry

            # 真实 AI 失败时 ai_expert 会降级返回写死模板文案（只替换 topic）。
            # 交付这种文案等于骗用户：每条视频口播内容都一样，谈不上实时 AI 创作。
            # 宁可明确失败让用户重试，也不能把模板当 AI 文案入库。
            if ai_result.get("_degraded"):
                reason = ai_result.get("_degraded_reason") or "AI 服务不可用"
                raise RuntimeError(
                    f"AI 未实时生成文案（已降级为模板，已拒绝保存）: {reason}"
                )

            # AI 失败时 (含 ark_provider_failed) 不保存空记录, 让 workflow 标 failed
            if "error" in ai_result or not ai_result.get("story_version"):
                raise RuntimeError(
                    f"AI 未生成有效文案: {ai_result.get('error', 'empty_result')}"
                )

            script_story = Script(
                project_id=self.project_id,
                type="story",
                content=ai_result.get("story_version", ""),
                version=1,
                score=ai_result.get("score", {}).get("total"),
                meta=self._metadata_for(ai_result, "story_version"),
            )
            self.db.add(script_story)

            script_knowledge = Script(
                project_id=self.project_id,
                type="knowledge",
                content=ai_result.get("knowledge_version", ""),
                version=1,
                score=ai_result.get("score", {}).get("total"),
                meta=self._metadata_for(ai_result, "knowledge_version"),
            )
            self.db.add(script_knowledge)

            script_chat = Script(
                project_id=self.project_id,
                type="chat",
                content=ai_result.get("chat_version", ""),
                version=1,
                score=ai_result.get("score", {}).get("total"),
                meta=self._metadata_for(ai_result, "chat_version"),
            )
            self.db.add(script_chat)

            self.db.commit()

            self._update_task("full_creation", "running", 60, json.dumps(ai_result, ensure_ascii=False))

            result["success"] = True
            result["data"] = ai_result

        except Exception as e:
            result["error"] = f"文案生成失败: {str(e)}"
            self._update_task("full_creation", "failed", 40, result["error"])

        return result

    @staticmethod
    def _score_of(ai_result: Dict[str, Any]) -> float:
        try:
            return float((ai_result.get("score") or {}).get("total") or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _metadata_for(ai_result: Dict[str, Any], version_key: str) -> dict:
        emphasis_map = ai_result.get("emphasis") or {}
        return {
            "emphasis": emphasis_map.get(version_key, []) or [],
            "hooks": ai_result.get("hooks") or [],
        }

    def _load_hot_samples(self) -> str:
        """取当前用户历史标记为爆款的文案片段，回灌进提示词。"""
        rows = (self.db.query(Script)
                .filter(Script.meta.isnot(None))
                .order_by(Script.id.desc())
                .limit(50)
                .all())
        samples = []
        for s in rows:
            md = s.meta or {}
            if not md.get("is_hot"):
                continue
            samples.append(s.content[:300])
            if len(samples) >= 2:
                break
        return "\n---\n".join(samples)
