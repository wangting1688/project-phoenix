"""
Director Learning Agent - 导演学习Agent

TASK-016.3B.5：AI Growth Decision Graph

核心职责：
1. 读取复盘数据、增长洞察、失败经验
2. 修改导演策略（内容结构、Hook方式、主播匹配）
3. 输出优化后的导演方案建议
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.video_production import GrowthDecisionMemory, GrowthFailureMemory, GrowthReviewReport
from app.models.video_edit_plan import VideoEditPlan
from app.services.agent_tool_gateway import AgentToolGateway
from app.services.growth_causal_graph_service import GrowthCausalGraphService


class DirectorLearningAgent:
    """导演学习Agent"""

    def __init__(self):
        self.db = SessionLocal()
        self.gateway = AgentToolGateway()

    def close(self):
        self.db.close()

    def optimize_director_plan(self, plan_id: int, video_id: int = None) -> Dict[str, Any]:
        """优化导演方案"""
        plan = self.db.query(VideoEditPlan).filter(VideoEditPlan.id == plan_id).first()
        if not plan:
            return {"success": False, "error": "导演方案不存在"}

        # 1. 获取相关记忆
        decision_memories = self._query_decision_memories(plan)
        failure_memories = self._query_failure_memories(plan)

        # 2. 查询因果图关系
        causal_recommendations = self._query_causal_graph(plan)
        causal_conflicts = self._query_causal_conflicts(plan)

        # 3. 如果有视频发布数据，获取复盘报告
        review_report = None
        if video_id:
            review_report = self.db.query(GrowthReviewReport).filter(
                GrowthReviewReport.source_video_id == video_id
            ).order_by(GrowthReviewReport.created_at.desc()).first()

        # 4. 生成优化建议（包含因果图）
        suggestions = self._generate_optimization_suggestions(
            plan, decision_memories, failure_memories, review_report,
            causal_recommendations, causal_conflicts
        )

        # 5. 调用LLM生成优化后的方案
        optimized_plan = self._generate_optimized_plan(plan, suggestions)

        strategy_confidence = self._calculate_strategy_confidence(
            causal_recommendations, decision_memories
        )

        evidence_summary = self._summarize_evidence(
            causal_recommendations, decision_memories, causal_conflicts
        )

        risk_warnings = self._identify_risk_warnings(plan, causal_conflicts, suggestions)

        evidence_level = self._determine_evidence_level(causal_recommendations, decision_memories)
        rule_priority = self._determine_rule_priority(evidence_level, strategy_confidence)

        return {
            "success": True,
            "plan_id": plan_id,
            "original_strategy": plan.editing_strategy,
            "suggestions": suggestions,
            "optimized_plan": optimized_plan,
            "causal_recommendations": causal_recommendations,
            "causal_conflicts": causal_conflicts,
            "decision_explanation": {
                "strategy": plan.editing_strategy or "standard",
                "confidence": round(strategy_confidence, 2),
                "evidence_level": evidence_level,
                "priority": rule_priority,
                "source": "causal_graph",
                "evidence": evidence_summary,
                "risk": risk_warnings,
                "action_guidance": self._get_action_guidance(rule_priority),
            },
            "based_on": {
                "decision_memories": len(decision_memories),
                "failure_memories": len(failure_memories),
                "causal_edges": len(causal_recommendations),
                "has_review_report": review_report is not None,
            },
        }

    def _query_decision_memories(self, plan: VideoEditPlan) -> List[GrowthDecisionMemory]:
        """查询相关成功决策记忆"""
        query = self.db.query(GrowthDecisionMemory).filter(
            GrowthDecisionMemory.user_id == plan.user_id
        )

        if plan.platform:
            query = query.filter(GrowthDecisionMemory.platform == plan.platform)
        if plan.product_category:
            query = query.filter(GrowthDecisionMemory.product_category == plan.product_category)

        return query.order_by(GrowthDecisionMemory.confidence_score.desc()).limit(10).all()

    def _query_failure_memories(self, plan: VideoEditPlan) -> List[GrowthFailureMemory]:
        """查询相关失败记忆"""
        query = self.db.query(GrowthFailureMemory).filter(
            GrowthFailureMemory.user_id == plan.user_id
        )

        if plan.platform:
            query = query.filter(GrowthFailureMemory.platform == plan.platform)

        return query.order_by(GrowthFailureMemory.occurrence_count.desc()).limit(10).all()

    def _query_causal_graph(self, plan: VideoEditPlan) -> List[Dict[str, Any]]:
        """查询因果图关系"""
        graph_service = GrowthCausalGraphService()
        try:
            conditions = {
                "platform": plan.platform,
                "product_category": plan.product_category,
                "business_stage": plan.business_stage,
            }
            return graph_service.recommend_strategy(conditions)
        finally:
            graph_service.close()

    def _query_causal_conflicts(self, plan: VideoEditPlan) -> List[Dict[str, Any]]:
        """查询因果冲突"""
        graph_service = GrowthCausalGraphService()
        try:
            conditions = {
                "platform": plan.platform,
                "business_stage": plan.business_stage,
            }
            return graph_service.find_conflicts(conditions)
        finally:
            graph_service.close()

    def _generate_optimization_suggestions(self, plan: VideoEditPlan,
                                          decision_memories: List[GrowthDecisionMemory],
                                          failure_memories: List[GrowthFailureMemory],
                                          review_report: GrowthReviewReport,
                                          causal_recommendations: List[Dict] = None,
                                          causal_conflicts: List[Dict] = None) -> List[Dict[str, Any]]:
        """生成优化建议"""
        suggestions = []

        # 基于因果图推荐
        for rec in causal_recommendations or []:
            suggestions.append({
                "type": "causal_recommendation",
                "source": "growth_causal_graph",
                "suggestion": f"{rec['source']} → {rec['relation']} → {rec['target']}",
                "confidence": rec["confidence"],
                "impact": rec["impact"],
                "verified_count": rec["verified_count"],
            })

        # 基于因果图冲突
        for conflict in causal_conflicts or []:
            suggestions.append({
                "type": "causal_conflict",
                "source": "growth_causal_graph",
                "suggestion": f"避免：{conflict['action']}（与{conflict['conflict']}冲突）",
                "confidence": conflict["confidence"],
            })

        # 基于成功记忆
        for memory in decision_memories:
            if memory.confidence_score >= 0.7:
                suggestions.append({
                    "type": "success_pattern",
                    "source": "growth_decision_memory",
                    "memory_id": memory.id,
                    "suggestion": memory.conclusion,
                    "confidence": memory.confidence_score,
                })

        # 基于失败记忆
        for memory in failure_memories:
            suggestions.append({
                "type": "avoid_pattern",
                "source": "growth_failure_memory",
                "memory_id": memory.id,
                "suggestion": memory.lesson,
                "avoid_actions": memory.avoid_actions,
            })

        # 基于复盘报告
        if review_report:
            if review_report.problems:
                for problem in review_report.problems:
                    suggestions.append({
                        "type": "fix_problem",
                        "source": "review_report",
                        "problem_type": problem.get("type"),
                        "suggestion": problem.get("suggestion"),
                    })

            if review_report.director_actions:
                for action in review_report.director_actions:
                    suggestions.append({
                        "type": "director_action",
                        "source": "review_report",
                        "action": action.get("action"),
                        "priority": action.get("priority"),
                    })

        return suggestions

    def _generate_optimized_plan(self, plan: VideoEditPlan, suggestions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成优化后的方案"""
        # 基于建议调整策略
        strategy = plan.editing_strategy or "standard"
        business_stage = plan.business_stage or "growth"

        # 收集所有建议文本
        suggestion_texts = []
        for s in suggestions:
            if s.get("suggestion"):
                suggestion_texts.append(f"- {s['type']}: {s['suggestion']}")
            if s.get("action"):
                suggestion_texts.append(f"- action: {s['action']}")

        # 如果建议足够多，调用LLM生成优化方案
        if len(suggestion_texts) >= 3:
            try:
                prompt = f"""请根据以下复盘建议，优化短视频导演方案：

当前方案：
- 策略类型：{strategy}
- 业务阶段：{business_stage}
- 文案摘要：{plan.script_content[:100] if plan.script_content else '暂无'}

复盘建议：
{chr(10).join(suggestion_texts[:10])}

请输出优化建议：
1. 是否需要调整内容结构？
2. Hook是否需要重写？
3. 情绪曲线如何优化？
4. 商业压力是否需要调整？
"""

                result = self.gateway.call_tool("llm_completion", prompt=prompt, max_tokens=800)
                if result.get("success"):
                    return {
                        "strategy_adjustment": result["data"].get("content", ""),
                        "suggestion_count": len(suggestions),
                    }
            except Exception:
                pass

        # 兜底：返回结构化建议
        return {
            "strategy_adjustment": self._fallback_strategy_adjustment(suggestions, strategy),
            "suggestion_count": len(suggestions),
        }

    def _fallback_strategy_adjustment(self, suggestions: List[Dict[str, Any]], current_strategy: str) -> str:
        """兜底策略调整"""
        adjustments = []

        has_hook_issue = any(s.get("problem_type") == "weak_hook" for s in suggestions)
        has_commercial_issue = any(s.get("problem_type") == "high_commercial_pressure" for s in suggestions)
        has_emotion_issue = any(s.get("problem_type") == "weak_emotion" for s in suggestions)

        if has_hook_issue:
            adjustments.append("重新设计Hook，增加冲突/悬念/痛点")
        if has_commercial_issue:
            adjustments.append("降低商业压力，将产品信息移至后半段")
        if has_emotion_issue:
            adjustments.append("丰富情绪曲线，增加情感起伏")

        if not adjustments:
            adjustments.append("当前方案基本合理，可继续优化细节")

        return "；".join(adjustments)

    def get_director_guidance(self, plan_id: int) -> Dict[str, Any]:
        """获取导演指导（生产前）"""
        plan = self.db.query(VideoEditPlan).filter(VideoEditPlan.id == plan_id).first()
        if not plan:
            return {"success": False, "error": "导演方案不存在"}

        # 查询相似条件下的成功和失败经验
        decision_memories = self._query_decision_memories(plan)
        failure_memories = self._query_failure_memories(plan)

        # 查询因果图关系
        causal_recommendations = self._query_causal_graph(plan)
        causal_conflicts = self._query_causal_conflicts(plan)

        guidance = {
            "recommended_patterns": [],
            "avoid_patterns": [],
            "causal_recommendations": [],
            "causal_conflicts": [],
            "risk_warnings": [],
        }

        for memory in decision_memories[:5]:
            if memory.confidence_score >= 0.6:
                guidance["recommended_patterns"].append({
                    "pattern": memory.conclusion,
                    "confidence": memory.confidence_score,
                })

        for memory in failure_memories[:5]:
            guidance["avoid_patterns"].append({
                "pattern": memory.lesson,
                "occurrence": memory.occurrence_count,
            })

        for rec in causal_recommendations[:5]:
            guidance["causal_recommendations"].append({
                "source": rec["source"],
                "relation": rec["relation"],
                "target": rec["target"],
                "confidence": rec["confidence"],
                "impact": rec["impact"],
            })

        for conflict in causal_conflicts[:3]:
            guidance["causal_conflicts"].append({
                "action": conflict["action"],
                "conflict": conflict["conflict"],
                "confidence": conflict["confidence"],
            })

        # 检查当前方案的风险
        if plan.editing_strategy == "product" and plan.business_stage == "growth":
            guidance["risk_warnings"].append("涨粉期使用产品型结构，商业压力可能过高")

        if plan.total_duration and plan.total_duration > 60 and plan.platform == "douyin":
            guidance["risk_warnings"].append("抖音视频超过60秒，完播率可能下降")

        strategy_confidence = self._calculate_strategy_confidence(
            causal_recommendations, decision_memories
        )

        evidence_summary = self._summarize_evidence(
            causal_recommendations, decision_memories, causal_conflicts
        )

        risk_warnings = self._identify_risk_warnings(plan, causal_conflicts, [])

        evidence_level = self._determine_evidence_level(causal_recommendations, decision_memories)
        rule_priority = self._determine_rule_priority(evidence_level, strategy_confidence)

        return {
            "success": True,
            "plan_id": plan_id,
            "guidance": guidance,
            "decision_explanation": {
                "strategy": plan.editing_strategy or "standard",
                "confidence": round(strategy_confidence, 2),
                "evidence_level": evidence_level,
                "priority": rule_priority,
                "source": "causal_graph",
                "evidence": evidence_summary,
                "risk": risk_warnings,
                "action_guidance": self._get_action_guidance(rule_priority),
            },
        }

    def _calculate_strategy_confidence(self, causal_recs: List[Dict], decision_mems: List[GrowthDecisionMemory]) -> float:
        """计算策略置信度"""
        if not causal_recs and not decision_mems:
            return 0.5

        confidences = []

        for rec in causal_recs:
            if rec.get("confidence"):
                confidences.append(rec["confidence"])

        for mem in decision_mems:
            if mem.confidence_score >= 0.6:
                confidences.append(mem.confidence_score)

        if confidences:
            return sum(confidences) / len(confidences)
        return 0.5

    def _summarize_evidence(self, causal_recs: List[Dict], decision_mems: List[GrowthDecisionMemory],
                           causal_conflicts: List[Dict]) -> List[Dict]:
        """总结证据"""
        evidence = []

        total_cases = len(decision_mems)
        total_experiments = sum(1 for rec in causal_recs if rec.get("verified_count", 0) > 0)

        if total_cases > 0:
            evidence.append({
                "type": "historical_cases",
                "count": total_cases,
                "description": f"{total_cases}个历史案例支持此策略",
            })

        if total_experiments > 0:
            evidence.append({
                "type": "experiments",
                "count": total_experiments,
                "description": f"{total_experiments}个实验验证支持此策略",
            })

        for rec in causal_recs[:3]:
            evidence.append({
                "type": "causal_edge",
                "description": f"{rec['source']} → {rec['relation']} → {rec['target']}",
                "confidence": rec["confidence"],
                "impact": rec["impact"],
            })

        for conflict in causal_conflicts[:2]:
            evidence.append({
                "type": "conflict",
                "description": f"冲突：{conflict['action']} 与 {conflict['conflict']}",
                "confidence": conflict["confidence"],
            })

        return evidence

    def _identify_risk_warnings(self, plan: VideoEditPlan, causal_conflicts: List[Dict],
                                suggestions: List[Dict]) -> List[str]:
        """识别风险警告"""
        warnings = []

        if plan.editing_strategy == "product" and plan.business_stage == "growth":
            warnings.append("商业压力不能超过30%（涨粉期）")

        if plan.total_duration and plan.total_duration > 60 and plan.platform == "douyin":
            warnings.append("抖音视频建议控制在60秒以内")

        for conflict in causal_conflicts:
            if conflict.get("confidence", 0) >= 0.7:
                warnings.append(f"避免使用{conflict['action']}（与{conflict['conflict']}冲突）")

        for suggestion in suggestions:
            if suggestion.get("problem_type") == "high_commercial_pressure":
                warnings.append("建议降低商业压力")

        return warnings

    def _determine_evidence_level(self, causal_recs: List[Dict],
                                    decision_mems: List[GrowthDecisionMemory]) -> str:
        """确定证据等级"""
        total_cases = len(decision_mems)
        experiment_count = sum(1 for rec in causal_recs if rec.get("verified_count", 0) > 0)
        avg_confidence = self._calculate_strategy_confidence(causal_recs, decision_mems)

        if avg_confidence >= 0.8 and total_cases >= 500 and experiment_count >= 5:
            return "A"
        elif avg_confidence >= 0.65 and total_cases >= 100:
            return "B"
        elif avg_confidence >= 0.5 and total_cases >= 20:
            return "C"
        else:
            return "D"

    def _determine_rule_priority(self, evidence_level: str, confidence: float) -> str:
        """确定规则优先级"""
        if evidence_level == "A" and confidence >= 0.8:
            return "recommended"
        elif evidence_level in ["A", "B"] and confidence >= 0.65:
            return "suggested"
        elif evidence_level in ["B", "C"] and confidence >= 0.5:
            return "test"
        else:
            return "experimental"

    def _get_action_guidance(self, priority: str) -> str:
        """获取行动指导"""
        guidance_map = {
            "recommended": "A级证据，直接采用",
            "suggested": "B级证据，推荐使用",
            "test": "C级证据，建议小范围测试",
            "experimental": "D级证据，禁止自动应用，仅供参考",
        }
        return guidance_map.get(priority, "请人工审核")
