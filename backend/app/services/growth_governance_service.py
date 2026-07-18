"""
Growth Governance Service - 增长大脑治理服务

TASK-016.3B.5.7：增长大脑治理层

核心职责：
1. 因果证据评分
2. 知识冲突检测与解决
3. 学习准入机制
4. 知识生命周期管理
"""

from datetime import datetime
from typing import List, Dict, Any

from app.core.database import SessionLocal
from app.models.video_production import (
    GrowthKnowledgeEdge,
    GrowthEvidenceScore,
    GrowthKnowledgeConflict,
    GrowthDecisionMemory,
    GrowthExperimentMemory,
    GrowthFailureMemory,
    GrowthPredictionError,
)


class GrowthGovernanceService:
    """增长治理服务"""

    def __init__(self):
        self.db = SessionLocal()

    def close(self):
        self.db.close()

    def calculate_evidence_score(self, edge_id: int) -> Dict[str, Any]:
        """计算知识边的证据评分"""
        edge = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.id == edge_id
        ).first()

        if not edge:
            return {"success": False, "error": "知识边不存在"}

        sample_size = edge.success_count + edge.failure_count
        experiment_count = edge.verified_count

        platform_set = set()
        creator_set = set()
        time_spans = []

        decision_memories = self.db.query(GrowthDecisionMemory).filter(
            GrowthDecisionMemory.user_id == edge.user_id,
        ).limit(100).all()

        for mem in decision_memories:
            conds = mem.conditions or {}
            if conds.get("platform"):
                platform_set.add(conds["platform"])
            if mem.created_at:
                time_spans.append(mem.created_at)

        platform_count = len(platform_set)
        creator_count = 1

        time_span_days = 0
        if time_spans:
            time_span_days = (max(time_spans) - min(time_spans)).days if len(time_spans) > 1 else 0

        prediction_accuracy = edge.calibrated_confidence if edge.prediction_count >= 5 else 0.5

        sample_diversity = min(1.0, (platform_count / 4) * 0.5 + (creator_count / 10) * 0.5)

        experiment_validation = min(1.0, experiment_count / 10) if experiment_count > 0 else 0.0

        context_stability = 1.0
        if edge.context_condition:
            context_stability = 0.8

        final_confidence = (
            prediction_accuracy * 0.35 +
            min(1.0, sample_size / 500) * 0.25 +
            experiment_validation * 0.25 +
            context_stability * 0.15
        )

        if final_confidence >= 0.8 and sample_size >= 500 and experiment_count >= 5:
            evidence_level = "A"
        elif final_confidence >= 0.65 and sample_size >= 100:
            evidence_level = "B"
        elif final_confidence >= 0.5 and sample_size >= 20:
            evidence_level = "C"
        else:
            evidence_level = "D"

        existing_score = self.db.query(GrowthEvidenceScore).filter(
            GrowthEvidenceScore.edge_id == edge_id
        ).first()

        if existing_score:
            existing_score.sample_size = sample_size
            existing_score.experiment_count = experiment_count
            existing_score.platform_count = platform_count
            existing_score.creator_count = creator_count
            existing_score.time_span_days = time_span_days
            existing_score.prediction_accuracy = prediction_accuracy
            existing_score.sample_diversity = sample_diversity
            existing_score.experiment_validation = experiment_validation
            existing_score.context_stability = context_stability
            existing_score.final_confidence = final_confidence
            existing_score.evidence_level = evidence_level
        else:
            score = GrowthEvidenceScore(
                user_id=edge.user_id,
                edge_id=edge_id,
                sample_size=sample_size,
                experiment_count=experiment_count,
                platform_count=platform_count,
                creator_count=creator_count,
                time_span_days=time_span_days,
                prediction_accuracy=prediction_accuracy,
                sample_diversity=sample_diversity,
                experiment_validation=experiment_validation,
                context_stability=context_stability,
                final_confidence=final_confidence,
                evidence_level=evidence_level,
            )
            self.db.add(score)

        edge.evidence_level = evidence_level
        self.db.commit()

        return {
            "success": True,
            "edge_id": edge_id,
            "final_confidence": round(final_confidence, 2),
            "evidence_level": evidence_level,
            "breakdown": {
                "sample_size": sample_size,
                "experiment_count": experiment_count,
                "platform_count": platform_count,
                "creator_count": creator_count,
                "time_span_days": time_span_days,
                "prediction_accuracy": round(prediction_accuracy, 2),
                "sample_diversity": round(sample_diversity, 2),
                "experiment_validation": round(experiment_validation, 2),
                "context_stability": round(context_stability, 2),
            },
        }

    def detect_conflicts(self, user_id: int = 1) -> List[Dict[str, Any]]:
        """检测知识冲突"""
        edges = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.user_id == user_id,
            GrowthKnowledgeEdge.status != "deprecated",
            GrowthKnowledgeEdge.status != "archived",
        ).all()

        conflicts = []
        edge_map = {}

        for edge in edges:
            key = (edge.source_type, edge.source_value, edge.target_type, edge.target_value)
            if key not in edge_map:
                edge_map[key] = []
            edge_map[key].append(edge)

        for key, edge_list in edge_map.items():
            if len(edge_list) >= 2:
                positive_edges = [e for e in edge_list if e.relation_type in ["improves", "increases", "suitable_for"]]
                negative_edges = [e for e in edge_list if e.relation_type in ["hurts", "decreases", "avoid"]]

                if positive_edges and negative_edges:
                    for pos_edge in positive_edges:
                        for neg_edge in negative_edges:
                            conflict = self._record_conflict(
                                pos_edge.id, neg_edge.id, "opposite_effect", user_id
                            )
                            if conflict:
                                conflicts.append(conflict)

        return conflicts

    def _record_conflict(self, edge_a_id: int, edge_b_id: int,
                         conflict_type: str, user_id: int) -> Dict[str, Any]:
        """记录冲突"""
        existing = self.db.query(GrowthKnowledgeConflict).filter(
            GrowthKnowledgeConflict.user_id == user_id,
            GrowthKnowledgeConflict.edge_a_id == edge_a_id,
            GrowthKnowledgeConflict.edge_b_id == edge_b_id,
        ).first()

        if existing:
            return None

        edge_a = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.id == edge_a_id
        ).first()
        edge_b = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.id == edge_b_id
        ).first()

        conflict = GrowthKnowledgeConflict(
            user_id=user_id,
            edge_a_id=edge_a_id,
            edge_b_id=edge_b_id,
            conflict_type=conflict_type,
            resolution_status="detected",
            context_a=edge_a.context_condition if edge_a else None,
            context_b=edge_b.context_condition if edge_b else None,
        )

        self.db.add(conflict)
        self.db.commit()

        return {
            "conflict_id": conflict.id,
            "edge_a": f"{edge_a.source_value if edge_a else ''} → {edge_a.target_value if edge_a else ''}",
            "edge_b": f"{edge_b.source_value if edge_b else ''} → {edge_b.target_value if edge_b else ''}",
            "conflict_type": conflict_type,
            "status": "detected",
        }

    def resolve_conflict(self, conflict_id: int, resolution: str,
                          resolved_by: str = "system") -> Dict[str, Any]:
        """解决冲突"""
        conflict = self.db.query(GrowthKnowledgeConflict).filter(
            GrowthKnowledgeConflict.id == conflict_id
        ).first()

        if not conflict:
            return {"success": False, "error": "冲突记录不存在"}

        conflict.resolution = resolution
        conflict.resolution_status = "resolved"
        conflict.resolved_by = resolved_by
        conflict.resolved_at = datetime.now()

        if "context_dependent" in resolution or "depends_on" in resolution:
            edge_a = self.db.query(GrowthKnowledgeEdge).filter(
                GrowthKnowledgeEdge.id == conflict.edge_a_id
            ).first()
            edge_b = self.db.query(GrowthKnowledgeEdge).filter(
                GrowthKnowledgeEdge.id == conflict.edge_b_id
            ).first()

            if edge_a and edge_b:
                if not edge_a.context_condition:
                    edge_a.context_condition = {}
                edge_a.context_condition["conflict_resolved"] = "context_dependent"

                if not edge_b.context_condition:
                    edge_b.context_condition = {}
                edge_b.context_condition["conflict_resolved"] = "context_dependent"

        self.db.commit()

        return {
            "success": True,
            "conflict_id": conflict_id,
            "resolution": resolution,
            "resolved_by": resolved_by,
        }

    def promote_edge_status(self, edge_id: int) -> Dict[str, Any]:
        """提升知识边状态（生命周期推进）"""
        edge = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.id == edge_id
        ).first()

        if not edge:
            return {"success": False, "error": "知识边不存在"}

        score = self.calculate_evidence_score(edge_id)
        if not score["success"]:
            return score

        current_status = edge.status
        new_status = current_status
        reason = ""

        evidence_level = score["evidence_level"]
        sample_size = score["breakdown"]["sample_size"]
        experiment_count = score["breakdown"]["experiment_count"]

        if current_status == "candidate":
            if sample_size >= 20:
                new_status = "observing"
                reason = "样本量达到20，进入观察期"
            else:
                reason = "样本量不足20，保持候选状态"

        elif current_status == "observing":
            if sample_size >= 50 and experiment_count >= 2:
                new_status = "validated"
                reason = "样本量50+且有实验验证，进入验证状态"
            else:
                reason = "需要更多样本或实验验证"

        elif current_status == "validated":
            if evidence_level == "A" or (sample_size >= 200 and experiment_count >= 5):
                new_status = "trusted"
                reason = "证据等级A或大量数据验证，进入可信状态"
            else:
                reason = "需要更高等级证据"

        elif current_status == "trusted":
            if evidence_level == "A" and sample_size >= 500 and experiment_count >= 10:
                new_status = "core_rule"
                reason = "达到核心规则标准，成为导演默认策略"
            else:
                reason = "已处于可信状态，需要更多积累"

        else:
            reason = "当前状态不可提升"

        if new_status != current_status:
            edge.status = new_status
            self.db.commit()

        return {
            "success": True,
            "edge_id": edge_id,
            "previous_status": current_status,
            "new_status": new_status,
            "reason": reason,
            "evidence_level": evidence_level,
        }

    def review_pending_knowledge(self, user_id: int = 1) -> Dict[str, Any]:
        """审核待处理知识"""
        candidate_edges = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.user_id == user_id,
            GrowthKnowledgeEdge.status == "candidate",
        ).count()

        observing_edges = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.user_id == user_id,
            GrowthKnowledgeEdge.status == "observing",
        ).count()

        pending_conflicts = self.db.query(GrowthKnowledgeConflict).filter(
            GrowthKnowledgeConflict.user_id == user_id,
            GrowthKnowledgeConflict.resolution_status.in_(["detected", "analyzing"]),
        ).count()

        low_evidence = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.user_id == user_id,
            GrowthKnowledgeEdge.evidence_level == "D",
            GrowthKnowledgeEdge.status.notin_(["deprecated", "archived", "candidate"]),
        ).count()

        return {
            "success": True,
            "summary": {
                "candidate_edges": candidate_edges,
                "observing_edges": observing_edges,
                "pending_conflicts": pending_conflicts,
                "low_evidence_edges": low_evidence,
            },
        }

    def get_edge_lifecycle(self, edge_id: int) -> Dict[str, Any]:
        """获取知识边生命周期信息"""
        edge = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.id == edge_id
        ).first()

        if not edge:
            return {"success": False, "error": "知识边不存在"}

        score = self.db.query(GrowthEvidenceScore).filter(
            GrowthEvidenceScore.edge_id == edge_id
        ).first()

        return {
            "success": True,
            "edge_id": edge_id,
            "status": edge.status,
            "evidence_level": edge.evidence_level,
            "lifecycle_stage": self._get_lifecycle_description(edge.status),
            "evidence_breakdown": {
                "sample_size": score.sample_size if score else 0,
                "experiment_count": score.experiment_count if score else 0,
                "final_confidence": score.final_confidence if score else 0,
            },
        }

    def _get_lifecycle_description(self, status: str) -> str:
        """获取生命周期状态描述"""
        descriptions = {
            "candidate": "AI刚发现，待验证",
            "observing": "等待更多数据验证",
            "validated": "实验验证通过",
            "trusted": "大量成功验证",
            "core_rule": "成为导演默认策略",
            "deprecated": "效果下降，已弃用",
            "archived": "已归档",
        }
        return descriptions.get(status, "未知状态")