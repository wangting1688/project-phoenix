"""
Growth Causal Graph Service - 增长因果图服务

TASK-016.3B.5.4：增长因果图层
TASK-016.3B.5.5：增长大脑自动学习层

核心职责：
1. 管理知识边（因果关系）
2. 从实验/归因/决策记忆中学习
3. 查询因果关系供导演决策
4. 因果权重演化与自动学习
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.video_production import (
    GrowthKnowledgeEdge,
    GrowthExperimentMemory,
    GrowthAttributionRecord,
    GrowthDecisionMemory,
    GrowthFailureMemory,
    AudienceBeliefMemory,
)


class GrowthCausalGraphService:
    """增长因果图服务"""

    RELATION_TYPES = {
        "improves": {"description": "提升", "direction": "positive"},
        "suitable_for": {"description": "适合", "direction": "positive"},
        "increases": {"description": "增加", "direction": "positive"},
        "recommended_for": {"description": "推荐用于", "direction": "positive"},
        "hurts": {"description": "损害", "direction": "negative"},
        "avoid": {"description": "避免", "direction": "negative"},
        "conflicts_with": {"description": "冲突", "direction": "negative"},
        "correlates_with": {"description": "相关", "direction": "neutral"},
    }

    NODE_TYPES = [
        "hook_pattern",
        "content_type",
        "creator_profile",
        "platform",
        "product_category",
        "business_stage",
        "metric",
        "audience_segment",
        "publish_time",
    ]

    def __init__(self):
        self.db = SessionLocal()

    def close(self):
        self.db.close()

    def add_knowledge_edge(self, source_type: str, source_value: str,
                          relation_type: str, target_type: str,
                          target_value: str, impact_score: float = 0.0,
                          confidence: float = 0.5, conditions: Dict = None,
                          source_memory_type: str = None) -> Dict[str, Any]:
        """添加知识边"""
        if relation_type not in self.RELATION_TYPES:
            return {"success": False, "error": f"不支持的关系类型: {relation_type}"}

        existing = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.user_id == 1,
            GrowthKnowledgeEdge.source_type == source_type,
            GrowthKnowledgeEdge.source_value == source_value,
            GrowthKnowledgeEdge.relation_type == relation_type,
            GrowthKnowledgeEdge.target_type == target_type,
            GrowthKnowledgeEdge.target_value == target_value,
        ).first()

        if existing:
            existing.impact_score = (existing.impact_score * existing.verified_count + impact_score) / (existing.verified_count + 1)
            existing.confidence_score = min(1.0, existing.confidence_score + 0.05)
            existing.verified_count += 1
            self.db.commit()
            return {"success": True, "edge_id": existing.id, "updated": True}

        edge = GrowthKnowledgeEdge(
            user_id=1,
            source_type=source_type,
            source_value=source_value,
            relation_type=relation_type,
            target_type=target_type,
            target_value=target_value,
            impact_score=impact_score,
            confidence_score=confidence,
            conditions=conditions,
            source_memory_type=source_memory_type,
            verified_count=1,
        )

        self.db.add(edge)
        self.db.commit()

        return {"success": True, "edge_id": edge.id, "updated": False}

    def query_causal_path(self, source_type: str, source_value: str,
                         target_type: str = None) -> List[Dict[str, Any]]:
        """查询因果路径"""
        query = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.source_type == source_type,
            GrowthKnowledgeEdge.source_value == source_value,
        )

        if target_type:
            query = query.filter(GrowthKnowledgeEdge.target_type == target_type)

        edges = query.order_by(GrowthKnowledgeEdge.confidence_score.desc()).all()

        return [{
            "id": e.id,
            "source": {"type": e.source_type, "value": e.source_value},
            "relation": e.relation_type,
            "relation_description": self.RELATION_TYPES.get(e.relation_type, {}).get("description"),
            "target": {"type": e.target_type, "value": e.target_value},
            "impact_score": e.impact_score,
            "confidence": e.confidence_score,
            "conditions": e.conditions,
            "verified_count": e.verified_count,
        } for e in edges]

    def learn_from_experiment(self, experiment_id: int) -> Dict[str, Any]:
        """从实验中学习因果关系"""
        experiment = self.db.query(GrowthExperimentMemory).filter(
            GrowthExperimentMemory.id == experiment_id
        ).first()
        if not experiment:
            return {"success": False, "error": "实验不存在"}

        if experiment.status != "completed":
            return {"success": False, "error": "实验未完成"}

        if experiment.winner is None:
            return {"success": False, "error": "实验无结果"}

        metrics = experiment.metrics or {}
        variant_a = metrics.get("variant_a", {})
        variant_b = metrics.get("variant_b", {})

        winner_data = variant_a if experiment.winner == "A" else variant_b
        loser_data = variant_b if experiment.winner == "A" else variant_a

        completion_diff = winner_data.get("completion_rate", 0) - loser_data.get("completion_rate", 0)
        engagement_diff = winner_data.get("engagement_rate", 0) - loser_data.get("engagement_rate", 0)

        edges_created = []

        winner_pattern = experiment.variant_a.get("pattern") if experiment.winner == "A" else experiment.variant_b.get("pattern")
        loser_pattern = experiment.variant_b.get("pattern") if experiment.winner == "A" else experiment.variant_a.get("pattern")

        if winner_pattern:
            result = self.add_knowledge_edge(
                source_type="hook_pattern",
                source_value=winner_pattern,
                relation_type="improves",
                target_type="metric",
                target_value="completion_rate",
                impact_score=completion_diff,
                confidence=experiment.winner_confidence,
                conditions={
                    "platform": experiment.related_platform,
                    "product_category": experiment.related_product_category,
                },
                source_memory_type="experiment",
            )
            if result["success"]:
                edges_created.append(result)

            result = self.add_knowledge_edge(
                source_type="hook_pattern",
                source_value=winner_pattern,
                relation_type="improves",
                target_type="metric",
                target_value="engagement_rate",
                impact_score=engagement_diff / 100,
                confidence=experiment.winner_confidence,
                conditions={
                    "platform": experiment.related_platform,
                    "product_category": experiment.related_product_category,
                },
                source_memory_type="experiment",
            )
            if result["success"]:
                edges_created.append(result)

        if loser_pattern:
            result = self.add_knowledge_edge(
                source_type="hook_pattern",
                source_value=loser_pattern,
                relation_type="hurts",
                target_type="metric",
                target_value="completion_rate",
                impact_score=-completion_diff,
                confidence=experiment.winner_confidence,
                conditions={
                    "platform": experiment.related_platform,
                    "product_category": experiment.related_product_category,
                },
                source_memory_type="experiment",
            )
            if result["success"]:
                edges_created.append(result)

        experiment.status = "learned"
        self.db.commit()

        return {
            "success": True,
            "experiment_id": experiment_id,
            "edges_created": len(edges_created),
            "knowledge_edges": edges_created,
        }

    def learn_from_attribution(self, attribution_id: int) -> Dict[str, Any]:
        """从归因中学习因果关系"""
        attribution = self.db.query(GrowthAttributionRecord).filter(
            GrowthAttributionRecord.id == attribution_id
        ).first()
        if not attribution:
            return {"success": False, "error": "归因记录不存在"}

        edges_created = []

        success_factors = attribution.success_factors or []
        for factor in success_factors:
            factor_name = factor.get("factor")
            factor_value = factor.get("value")
            contribution = factor.get("contribution", 0)

            if factor_name and factor_value and contribution > 0.1:
                result = self.add_knowledge_edge(
                    source_type=factor_name,
                    source_value=str(factor_value),
                    relation_type="improves",
                    target_type="metric",
                    target_value="growth",
                    impact_score=contribution,
                    confidence=attribution.confidence_score,
                    conditions={"platform": attribution.platform},
                    source_memory_type="attribution",
                )
                if result["success"]:
                    edges_created.append(result)

        failure_factors = attribution.failure_factors or []
        for factor in failure_factors:
            factor_name = factor.get("factor")
            score = factor.get("score", 0)

            if factor_name and score > 30:
                result = self.add_knowledge_edge(
                    source_type=factor_name,
                    source_value="high",
                    relation_type="hurts",
                    target_type="metric",
                    target_value="growth",
                    impact_score=-score / 100,
                    confidence=attribution.confidence_score,
                    conditions={"platform": attribution.platform},
                    source_memory_type="attribution",
                )
                if result["success"]:
                    edges_created.append(result)

        return {
            "success": True,
            "attribution_id": attribution_id,
            "edges_created": len(edges_created),
        }

    def learn_from_decision_memory(self, decision_id: int) -> Dict[str, Any]:
        """从决策记忆中学习"""
        memory = self.db.query(GrowthDecisionMemory).filter(
            GrowthDecisionMemory.id == decision_id
        ).first()
        if not memory:
            return {"success": False, "error": "决策记忆不存在"}

        result_data = memory.result or {}
        conditions = memory.conditions or {}

        edge_type = "improves" if memory.confidence_score > 0.6 else "correlates_with"

        content_type = conditions.get("content_type") or memory.content_type
        opening_pattern = conditions.get("opening_pattern") or memory.opening_pattern
        platform = conditions.get("platform") or memory.platform

        edges_created = []

        if content_type:
            result = self.add_knowledge_edge(
                source_type="content_type",
                source_value=content_type,
                relation_type="suitable_for",
                target_type="platform",
                target_value=platform or "all",
                impact_score=memory.confidence_score,
                confidence=memory.confidence_score,
                source_memory_type="decision",
            )
            if result["success"]:
                edges_created.append(result)

        if opening_pattern:
            views = result_data.get("views", 0)
            followers = result_data.get("followers", 0)

            if views > 50000 or followers > 1000:
                result = self.add_knowledge_edge(
                    source_type="hook_pattern",
                    source_value=opening_pattern,
                    relation_type="recommended_for",
                    target_type="product_category",
                    target_value=memory.product_category or "health",
                    impact_score=memory.confidence_score,
                    confidence=memory.confidence_score,
                    conditions={"platform": platform},
                    source_memory_type="decision",
                )
                if result["success"]:
                    edges_created.append(result)

        memory.usage_count += 1
        self.db.commit()

        return {
            "success": True,
            "decision_id": decision_id,
            "edges_created": len(edges_created),
        }

    def learn_from_failure_memory(self, failure_id: int) -> Dict[str, Any]:
        """从失败记忆中学习"""
        memory = self.db.query(GrowthFailureMemory).filter(
            GrowthFailureMemory.id == failure_id
        ).first()
        if not memory:
            return {"success": False, "error": "失败记忆不存在"}

        edges_created = []

        if memory.failure_type and memory.failure_pattern:
            result = self.add_knowledge_edge(
                source_type="failure_pattern",
                source_value=memory.failure_pattern,
                relation_type="avoid",
                target_type="business_stage",
                target_value=memory.business_stage or "growth",
                impact_score=-0.8,
                confidence=min(0.9, memory.confidence_score + memory.occurrence_count * 0.05),
                conditions={"platform": memory.platform},
                source_memory_type="failure",
            )
            if result["success"]:
                edges_created.append(result)

        memory.usage_count += 1
        self.db.commit()

        return {
            "success": True,
            "failure_id": failure_id,
            "edges_created": len(edges_created),
        }

    def recommend_strategy(self, conditions: Dict) -> List[Dict[str, Any]]:
        """基于因果图推荐策略"""
        recommendations = []

        platform = conditions.get("platform", "wechat_video")
        product_category = conditions.get("product_category", "health")
        business_stage = conditions.get("business_stage", "growth")
        creator_profile = conditions.get("creator_profile", "")

        edges = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.user_id == 1,
            GrowthKnowledgeEdge.confidence_score >= 0.6,
        )

        if platform:
            edges = edges.filter(
                (GrowthKnowledgeEdge.source_value == platform) |
                (GrowthKnowledgeEdge.conditions.op("->")(platform))
            )

        edges = edges.order_by(GrowthKnowledgeEdge.confidence_score.desc()).limit(20).all()

        for edge in edges:
            is_relevant = True
            if edge.conditions:
                if edge.conditions.get("platform") and edge.conditions["platform"] != platform:
                    is_relevant = False
                if edge.conditions.get("product_category") and edge.conditions["product_category"] != product_category:
                    is_relevant = False

            if not is_relevant:
                continue

            recommendations.append({
                "source": f"{edge.source_type}: {edge.source_value}",
                "relation": self.RELATION_TYPES.get(edge.relation_type, {}).get("description"),
                "target": f"{edge.target_type}: {edge.target_value}",
                "impact": round(edge.impact_score, 3),
                "confidence": round(edge.confidence_score, 2),
                "verified_count": edge.verified_count,
                "conditions": edge.conditions,
            })

        return recommendations

    def find_conflicts(self, conditions: Dict) -> List[Dict[str, Any]]:
        """查找冲突关系"""
        conflicts = []

        platform = conditions.get("platform")
        business_stage = conditions.get("business_stage")

        negative_edges = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.user_id == 1,
            GrowthKnowledgeEdge.relation_type.in_(["hurts", "avoid", "conflicts_with"]),
            GrowthKnowledgeEdge.confidence_score >= 0.5,
        )

        edges = negative_edges.all()

        for edge in edges:
            if edge.conditions:
                if edge.conditions.get("platform") == platform:
                    conflicts.append({
                        "action": edge.source_value,
                        "conflict": edge.target_value,
                        "relation": edge.relation_type,
                        "confidence": edge.confidence_score,
                    })

                if edge.conditions.get("business_stage") == business_stage:
                    conflicts.append({
                        "action": edge.source_value,
                        "conflict": edge.target_value,
                        "relation": edge.relation_type,
                        "confidence": edge.confidence_score,
                    })

        return conflicts

    def update_edge_confidence(self, edge_id: int, success: bool) -> Dict[str, Any]:
        """更新知识边置信度"""
        edge = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.id == edge_id
        ).first()

        if not edge:
            return {"success": False, "error": "知识边不存在"}

        edge.previous_confidence = edge.confidence_score

        if success:
            edge.success_count += 1
        else:
            edge.failure_count += 1

        total = edge.success_count + edge.failure_count
        if total > 0:
            edge.confidence_score = edge.success_count / total

        edge.confidence_delta = edge.confidence_score - edge.previous_confidence
        edge.last_verified_at = datetime.now()

        edge.status = self._determine_edge_status(edge)

        self.db.commit()

        return {
            "success": True,
            "edge_id": edge_id,
            "success_count": edge.success_count,
            "failure_count": edge.failure_count,
            "confidence": edge.confidence_score,
            "delta": edge.confidence_delta,
            "status": edge.status,
        }

    def _determine_edge_status(self, edge: GrowthKnowledgeEdge) -> str:
        """确定知识边状态"""
        total = edge.success_count + edge.failure_count

        if total < 5:
            return "candidate"
        elif edge.confidence_score >= 0.7 and edge.success_count >= 10:
            return "strong"
        elif edge.confidence_score >= 0.5:
            return "validated"
        elif edge.confidence_score < 0.4 or edge.failure_count > edge.success_count * 2:
            return "deprecated"
        else:
            return edge.status

    def apply_decay(self) -> Dict[str, Any]:
        """应用衰减机制"""
        edges = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.user_id == 1,
            GrowthKnowledgeEdge.status != "deprecated",
        ).all()

        updated_count = 0
        deprecated_count = 0

        for edge in edges:
            if edge.last_verified_at:
                days_since_verified = (datetime.now() - edge.last_verified_at).days
                if days_since_verified > 30:
                    decay_amount = edge.decay_rate * days_since_verified
                    edge.previous_confidence = edge.confidence_score
                    edge.confidence_score = max(0.1, edge.confidence_score - decay_amount)
                    edge.confidence_delta = edge.confidence_score - edge.previous_confidence

                    new_status = self._determine_edge_status(edge)
                    if new_status != edge.status:
                        edge.status = new_status
                        if new_status == "deprecated":
                            deprecated_count += 1

                    updated_count += 1

        self.db.commit()

        return {
            "success": True,
            "edges_updated": updated_count,
            "edges_deprecated": deprecated_count,
        }

    def auto_learn(self) -> Dict[str, Any]:
        """自动学习入口"""
        results = {}

        unlearned_experiments = self.db.query(GrowthExperimentMemory).filter(
            GrowthExperimentMemory.status == "completed",
        ).all()

        for experiment in unlearned_experiments:
            self.learn_from_experiment(experiment.id)

        results["experiments_learned"] = len(unlearned_experiments)

        recent_decisions = self.db.query(GrowthDecisionMemory).filter(
            GrowthDecisionMemory.usage_count == 0,
        ).limit(20).all()

        for decision in recent_decisions:
            self.learn_from_decision_memory(decision.id)

        results["decisions_learned"] = len(recent_decisions)

        recent_failures = self.db.query(GrowthFailureMemory).filter(
            GrowthFailureMemory.usage_count == 0,
        ).limit(20).all()

        for failure in recent_failures:
            self.learn_from_failure_memory(failure.id)

        results["failures_learned"] = len(recent_failures)

        decay_result = self.apply_decay()
        results["decay_applied"] = decay_result

        return {
            "success": True,
            "summary": results,
        }

    def get_edge_detail(self, edge_id: int) -> Dict[str, Any]:
        """获取知识边详情（用于决策解释）"""
        edge = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.id == edge_id
        ).first()

        if not edge:
            return {"success": False, "error": "知识边不存在"}

        return {
            "success": True,
            "data": {
                "id": edge.id,
                "source": {"type": edge.source_type, "value": edge.source_value},
                "relation": edge.relation_type,
                "relation_description": self.RELATION_TYPES.get(edge.relation_type, {}).get("description"),
                "target": {"type": edge.target_type, "value": edge.target_value},
                "impact_score": edge.impact_score,
                "confidence_score": edge.confidence_score,
                "calibrated_confidence": edge.calibrated_confidence,
                "previous_confidence": edge.previous_confidence,
                "confidence_delta": edge.confidence_delta,
                "success_count": edge.success_count,
                "failure_count": edge.failure_count,
                "prediction_count": edge.prediction_count,
                "prediction_success_count": edge.prediction_success_count,
                "status": edge.status,
                "usage_count": edge.usage_count,
                "verified_count": edge.verified_count,
                "last_verified_at": str(edge.last_verified_at) if edge.last_verified_at else None,
                "conditions": edge.conditions,
                "context_condition": edge.context_condition,
                "source_memory_type": edge.source_memory_type,
            },
        }

    def calibrate_edge_confidence(self, edge_id: int, user_id: int = 1) -> Dict[str, Any]:
        """校准知识边置信度"""
        edge = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.id == edge_id,
            GrowthKnowledgeEdge.user_id == user_id,
        ).first()

        if not edge:
            return {"success": False, "error": "知识边不存在"}

        total_predictions = edge.prediction_count
        successful_predictions = edge.prediction_success_count

        if total_predictions >= 5:
            actual_accuracy = successful_predictions / total_predictions

            edge.calibrated_confidence = actual_accuracy

            original_confidence = edge.confidence_score
            adjustment = original_confidence - actual_accuracy

            edge.confidence_delta = -adjustment

        self.db.commit()

        return {
            "success": True,
            "edge_id": edge_id,
            "original_confidence": edge.confidence_score,
            "calibrated_confidence": edge.calibrated_confidence,
            "prediction_count": edge.prediction_count,
            "accuracy": edge.calibrated_confidence,
        }

    def add_context_condition(self, edge_id: int, context: Dict[str, Any]) -> Dict[str, Any]:
        """添加上下文条件"""
        edge = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.id == edge_id
        ).first()

        if not edge:
            return {"success": False, "error": "知识边不存在"}

        if not edge.context_condition:
            edge.context_condition = {}

        for key, value in context.items():
            edge.context_condition[key] = value

        self.db.commit()

        return {
            "success": True,
            "edge_id": edge_id,
            "context_condition": edge.context_condition,
        }

    def query_edges_with_context(self, source_type: str, source_value: str,
                                  context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """查询带上下文条件的知识边"""
        query = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.source_type == source_type,
            GrowthKnowledgeEdge.source_value == source_value,
            GrowthKnowledgeEdge.status != "deprecated",
        )

        edges = query.order_by(GrowthKnowledgeEdge.calibrated_confidence.desc()).all()

        results = []
        for edge in edges:
            matches_context = True
            if context and edge.context_condition:
                for key, value in context.items():
                    if key in edge.context_condition:
                        if edge.context_condition[key] != value:
                            if edge.context_condition.get(key + "_not") != value:
                                matches_context = True
                            else:
                                matches_context = False
                                break

            if matches_context:
                results.append({
                    "id": edge.id,
                    "source": {"type": edge.source_type, "value": edge.source_value},
                    "relation": edge.relation_type,
                    "target": {"type": edge.target_type, "value": edge.target_value},
                    "confidence": edge.confidence_score,
                    "calibrated_confidence": edge.calibrated_confidence,
                    "context_condition": edge.context_condition,
                    "status": edge.status,
                })

        return results

    def auto_correct_from_errors(self, user_id: int = 1) -> Dict[str, Any]:
        """从预测误差自动纠错"""
        from app.models.video_production import GrowthPredictionError

        errors = self.db.query(GrowthPredictionError).filter(
            GrowthPredictionError.user_id == user_id,
            GrowthPredictionError.reflection_status == "pending",
            GrowthPredictionError.error_rate > 0.2,
        ).limit(20).all()

        corrections_applied = 0

        for error in errors:
            causal_edges = error.causal_edges_used or []
            context = error.context_conditions or {}

            for edge_id in causal_edges:
                edge = self.db.query(GrowthKnowledgeEdge).filter(
                    GrowthKnowledgeEdge.id == edge_id
                ).first()

                if edge:
                    if error.error_direction == "over_estimate":
                        edge.calibrated_confidence = max(0.3, edge.calibrated_confidence - 0.05)
                        edge.prediction_count += 1
                    else:
                        edge.prediction_count += 1
                        edge.prediction_success_count += 1

                    if error.error_rate > 0.3:
                        if not edge.context_condition:
                            edge.context_condition = {}
                        for key, value in context.items():
                            if key not in edge.context_condition:
                                edge.context_condition[key] = value

                    corrections_applied += 1

            error.reflection_status = "corrected"
            error.analyzed_at = datetime.now()

        self.db.commit()

        return {
            "success": True,
            "errors_processed": len(errors),
            "corrections_applied": corrections_applied,
        }

    def get_low_accuracy_edges(self, user_id: int = 1, threshold: float = 0.6) -> List[Dict[str, Any]]:
        """获取低准确率知识边"""
        edges = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.user_id == user_id,
            GrowthKnowledgeEdge.calibrated_confidence < threshold,
            GrowthKnowledgeEdge.prediction_count >= 5,
        ).all()

        return [{
            "id": e.id,
            "source": f"{e.source_type}: {e.source_value}",
            "target": f"{e.target_type}: {e.target_value}",
            "original_confidence": e.confidence_score,
            "calibrated_confidence": e.calibrated_confidence,
            "prediction_count": e.prediction_count,
            "accuracy": e.prediction_success_count / max(e.prediction_count, 1),
        } for e in edges]
