"""
Director Reflection Agent - 导演反思Agent

TASK-016.3B.5.6：增长大脑自我反思层

核心职责：
1. 分析AI导演建议与实际结果
2. 识别判断失误
3. 提出修正规则
"""

from datetime import datetime
from typing import List, Dict, Any

from app.core.database import SessionLocal
from app.models.video_production import (
    DirectorMistakeMemory,
    GrowthPredictionError,
    GrowthKnowledgeEdge,
    GrowthDecisionMemory,
    GrowthFailureMemory,
)
from app.models.video_edit_plan import VideoEditPlan
from app.services.agent_tool_gateway import AgentToolGateway
from app.services.growth_causal_graph_service import GrowthCausalGraphService


class DirectorReflectionAgent:
    """导演反思Agent"""

    def __init__(self):
        self.db = SessionLocal()
        self.gateway = AgentToolGateway()

    def close(self):
        self.db.close()

    def analyze_director_decision(self, plan_id: int, actual_results: Dict[str, Any]) -> Dict[str, Any]:
        """分析导演决策与实际结果"""
        plan = self.db.query(VideoEditPlan).filter(VideoEditPlan.id == plan_id).first()
        if not plan:
            return {"success": False, "error": "导演方案不存在"}

        strategy_used = plan.editing_strategy or "standard"
        expected_metrics = actual_results.get("expected", {})
        actual_metrics = actual_results.get("actual", {})

        mistakes_found = []

        completion_expected = expected_metrics.get("completion_rate", 0.5)
        completion_actual = actual_metrics.get("completion_rate", 0)

        if completion_actual < completion_expected * 0.5:
            mistake = self._analyze_completion_mistake(plan, completion_expected, completion_actual)
            if mistake:
                mistakes_found.append(mistake)

        engagement_expected = expected_metrics.get("engagement_rate", 0.1)
        engagement_actual = actual_metrics.get("engagement_rate", 0)

        if engagement_actual < engagement_expected * 0.5:
            mistake = self._analyze_engagement_mistake(plan, engagement_expected, engagement_actual)
            if mistake:
                mistakes_found.append(mistake)

        for mistake_data in mistakes_found:
            self._record_mistake(mistake_data, plan)

        return {
            "success": True,
            "plan_id": plan_id,
            "strategy_used": strategy_used,
            "mistakes_found": len(mistakes_found),
            "mistakes": mistakes_found,
        }

    def _analyze_completion_mistake(self, plan: VideoEditPlan, expected: float, actual: float) -> Dict[str, Any]:
        """分析完播率失误"""
        if actual >= expected * 0.7:
            return None

        mistake_type = "completion_prediction_error"

        recommendation = f"推荐使用{plan.editing_strategy}策略"

        possible_reason = self._identify_failure_reason(plan)

        correct_strategy = self._suggest_correct_strategy(plan, "completion")

        return {
            "mistake_type": mistake_type,
            "recommendation": recommendation,
            "expected_outcome": f"完播率 {expected*100:.1f}%",
            "actual_outcome": f"完播率 {actual*100:.1f}%",
            "mistake_reason": possible_reason,
            "correct_strategy": correct_strategy,
            "learning": self._generate_learning(plan, possible_reason, correct_strategy),
        }

    def _analyze_engagement_mistake(self, plan: VideoEditPlan, expected: float, actual: float) -> Dict[str, Any]:
        """分析互动率失误"""
        if actual >= expected * 0.7:
            return None

        mistake_type = "engagement_prediction_error"

        recommendation = f"预期互动率 {expected*100:.1f}%"

        possible_reason = "内容未能引发用户共鸣"

        if plan.platform == "douyin":
            possible_reason = "抖音平台用户更偏好快节奏内容"
        elif plan.platform == "wechat_video":
            possible_reason = "视频号用户更偏好真实内容"

        correct_strategy = "增加互动引导或调整内容节奏"

        return {
            "mistake_type": mistake_type,
            "recommendation": recommendation,
            "expected_outcome": f"互动率 {expected*100:.1f}%",
            "actual_outcome": f"互动率 {actual*100:.1f}%",
            "mistake_reason": possible_reason,
            "correct_strategy": correct_strategy,
            "learning": self._generate_learning(plan, possible_reason, correct_strategy),
        }

    def _identify_failure_reason(self, plan: VideoEditPlan) -> str:
        """识别失败原因"""
        strategy = plan.editing_strategy or ""

        if strategy == "product" and plan.business_stage == "growth":
            return "涨粉期使用产品型策略，商业压力过高导致用户流失"

        if strategy == "knowledge" and plan.platform == "wechat_video":
            return "视频号用户对纯知识内容兴趣较低，更偏好真实故事"

        failure_memories = self.db.query(GrowthFailureMemory).filter(
            GrowthFailureMemory.platform == plan.platform,
        ).order_by(GrowthFailureMemory.occurrence_count.desc()).limit(3).all()

        if failure_memories:
            return failure_memories[0].lesson

        return "内容结构或表达方式与目标用户不匹配"

    def _suggest_correct_strategy(self, plan: VideoEditPlan, metric_type: str) -> str:
        """建议正确策略"""
        if metric_type == "completion":
            if plan.business_stage == "growth":
                return "降低商业压力，使用故事型或共鸣型内容"

            if plan.platform == "douyin":
                return "缩短视频时长，增加Hook吸引力"

            if plan.platform == "wechat_video":
                return "增加真实性和情感共鸣"

        elif metric_type == "engagement":
            return "增加互动引导，优化评论区运营"

        return "根据具体数据调整内容策略"

    def _generate_learning(self, plan: VideoEditPlan, reason: str, correction: str) -> str:
        """生成学习内容"""
        return f"对于{plan.platform or '未知平台'}平台{plan.business_stage or '增长期'}内容，{reason}。建议{correction}。"

    def _record_mistake(self, mistake_data: Dict[str, Any], plan: VideoEditPlan):
        """记录错误"""
        mistake = DirectorMistakeMemory(
            user_id=plan.user_id,
            mistake_type=mistake_data.get("mistake_type"),
            recommendation=mistake_data.get("recommendation"),
            expected_outcome=mistake_data.get("expected_outcome"),
            actual_outcome=mistake_data.get("actual_outcome"),
            mistake_reason=mistake_data.get("mistake_reason"),
            correct_strategy=mistake_data.get("correct_strategy"),
            learning=mistake_data.get("learning"),
            related_plan_id=plan.id,
        )

        self.db.add(mistake)
        self.db.commit()

    def generate_correction_rules(self, user_id: int = 1) -> List[Dict[str, Any]]:
        """生成修正规则"""
        mistakes = self.db.query(DirectorMistakeMemory).filter(
            DirectorMistakeMemory.user_id == user_id,
            DirectorMistakeMemory.verified == False,
        ).order_by(DirectorMistakeMemory.created_at.desc()).limit(20).all()

        rules = []

        for mistake in mistakes:
            if mistake.mistake_type and mistake.correct_strategy:
                rule = {
                    "mistake_type": mistake.mistake_type,
                    "avoid": mistake.recommendation,
                    "instead": mistake.correct_strategy,
                    "reason": mistake.mistake_reason,
                }

                rules.append(rule)

                mistake.verified = True

        self.db.commit()

        return rules

    def update_director_rules(self, user_id: int = 1) -> Dict[str, Any]:
        """更新导演规则"""
        rules = self.generate_correction_rules(user_id)

        edges_updated = 0

        for rule in rules:
            if "产品型" in rule.get("avoid", "") and "涨粉期" in rule.get("reason", ""):
                edges = self.db.query(GrowthKnowledgeEdge).filter(
                    GrowthKnowledgeEdge.user_id == user_id,
                    GrowthKnowledgeEdge.source_value.contains("product"),
                ).all()

                for edge in edges:
                    if not edge.context_condition:
                        edge.context_condition = {}

                    edge.context_condition["business_stage_not"] = "growth"
                    edges_updated += 1

        self.db.commit()

        return {
            "success": True,
            "rules_generated": len(rules),
            "edges_updated": edges_updated,
            "rules": rules[:5],
        }

    def weekly_self_critique(self, user_id: int = 1) -> Dict[str, Any]:
        """每周自我批判"""
        one_week_ago = datetime.now() - datetime.timedelta(days=7)

        mistakes = self.db.query(DirectorMistakeMemory).filter(
            DirectorMistakeMemory.user_id == user_id,
            DirectorMistakeMemory.created_at >= one_week_ago,
        ).all()

        predictions = self.db.query(GrowthPredictionError).filter(
            GrowthPredictionError.user_id == user_id,
            GrowthPredictionError.created_at >= one_week_ago,
        ).all()

        critique = {
            "period": "weekly",
            "total_mistakes": len(mistakes),
            "total_prediction_errors": len(predictions),
            "top_mistakes": [],
            "correction_actions": [],
        }

        mistake_types = {}
        for m in mistakes:
            mistake_types[m.mistake_type] = mistake_types.get(m.mistake_type, 0) + 1

        sorted_mistakes = sorted(mistake_types.items(), key=lambda x: x[1], reverse=True)[:3]
        critique["top_mistakes"] = [{"type": m[0], "count": m[1]} for m in sorted_mistakes]

        if len(predictions) > 5:
            avg_error_rate = sum(p.error_rate for p in predictions) / len(predictions)
            if avg_error_rate > 0.25:
                critique["correction_actions"].append({
                    "action": "增加上下文条件判断",
                    "reason": f"平均预测误差率 {avg_error_rate*100:.1f}% 过高",
                })

        if len(mistakes) > 3:
            critique["correction_actions"].append({
                "action": "优化策略推荐逻辑",
                "reason": f"本周发生 {len(mistakes)} 次判断失误",
            })

        return {
            "success": True,
            "critique": critique,
        }