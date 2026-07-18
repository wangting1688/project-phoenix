"""
Growth Learning Guard Agent - AI学习守卫Agent

TASK-016.3B.5.7：增长大脑治理层

核心职责：
1. 新知识准入检查
2. 证据质量审查
3. 冲突检测
4. 风险评估
5. 批准/拒绝学习
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
)
from app.services.growth_governance_service import GrowthGovernanceService


class GrowthLearningGuardAgent:
    """AI学习守卫Agent"""

    def __init__(self):
        self.db = SessionLocal()
        self.governance = GrowthGovernanceService()

    def close(self):
        self.db.close()
        self.governance.close()

    def review_new_knowledge(self, edge_data: Dict[str, Any]) -> Dict[str, Any]:
        """审核新知识"""
        checks = []

        evidence_check = self._check_evidence_quality(edge_data)
        checks.append(evidence_check)

        conflict_check = self._check_conflicts(edge_data)
        checks.append(conflict_check)

        risk_check = self._check_risk(edge_data)
        checks.append(risk_check)

        total_score = sum(c.get("score", 0) for c in checks) / max(len(checks), 1)

        if total_score >= 0.7:
            decision = "approved"
            action = "批准学习，直接更新知识边"
        elif total_score >= 0.4:
            decision = "observing"
            action = "进入观察池，不影响导演策略"
        else:
            decision = "rejected"
            action = "拒绝，证据不足"

        return {
            "success": True,
            "decision": decision,
            "action": action,
            "confidence": round(total_score, 2),
            "checks": checks,
            "reasons": [c.get("reason", "") for c in checks if c.get("passed")],
            "warnings": [c.get("warning", "") for c in checks if not c.get("passed")],
        }

    def _check_evidence_quality(self, edge_data: Dict[str, Any]) -> Dict[str, Any]:
        """检查证据质量"""
        sample_size = edge_data.get("sample_size", 0)
        experiment_count = edge_data.get("experiment_count", 0)
        confidence = edge_data.get("confidence", 0.5)

        score = 0.0
        passed = True
        reasons = []
        warnings = []

        if sample_size >= 100:
            score += 0.4
            reasons.append(f"样本量充足（{sample_size}）")
        elif sample_size >= 30:
            score += 0.25
            reasons.append(f"样本量一般（{sample_size}）")
        else:
            score += 0.1
            warnings.append(f"样本量不足（{sample_size}）")
            passed = False

        if experiment_count >= 3:
            score += 0.3
            reasons.append(f"实验验证充足（{experiment_count}次）")
        elif experiment_count >= 1:
            score += 0.15
            reasons.append(f"有部分实验验证（{experiment_count}次）")
        else:
            warnings.append("缺乏实验验证")
            passed = False

        if confidence >= 0.7:
            score += 0.3
            reasons.append(f"置信度较高（{confidence}）")
        elif confidence >= 0.5:
            score += 0.2
            reasons.append(f"置信度一般（{confidence}）")
        else:
            score += 0.1
            warnings.append(f"置信度偏低（{confidence}）")
            passed = False

        return {
            "check": "evidence_quality",
            "score": min(1.0, score),
            "passed": passed,
            "reason": "; ".join(reasons),
            "warning": "; ".join(warnings),
        }

    def _check_conflicts(self, edge_data: Dict[str, Any]) -> Dict[str, Any]:
        """检查知识冲突"""
        source_type = edge_data.get("source_type")
        source_value = edge_data.get("source_value")
        target_type = edge_data.get("target_type")
        target_value = edge_data.get("target_value")
        relation_type = edge_data.get("relation_type")

        existing_edges = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.source_type == source_type,
            GrowthKnowledgeEdge.source_value == source_value,
            GrowthKnowledgeEdge.target_type == target_type,
            GrowthKnowledgeEdge.target_value == target_value,
        ).all()

        score = 1.0
        passed = True
        warnings = []

        for existing in existing_edges:
            same_direction = (
                (relation_type in ["improves", "increases"] and existing.relation_type in ["improves", "increases"]) or
                (relation_type in ["hurts", "decreases"] and existing.relation_type in ["hurts", "decreases"])
            )

            if not same_direction:
                score = 0.3
                passed = False
                warnings.append(
                    f"发现相反结论：现有{existing.relation_type}，新{relation_type}"
                )
                break

        return {
            "check": "conflict_detection",
            "score": score,
            "passed": passed,
            "reason": "无冲突" if passed else "",
            "warning": "; ".join(warnings),
        }

    def _check_risk(self, edge_data: Dict[str, Any]) -> Dict[str, Any]:
        """检查风险"""
        relation_type = edge_data.get("relation_type", "")
        source_type = edge_data.get("source_type", "")
        target_type = edge_data.get("target_type", "")

        score = 0.8
        passed = True
        reasons = ["基础风险评估通过"]
        warnings = []

        if relation_type in ["improves", "increases"] and target_type == "metric":
            if edge_data.get("confidence", 0) > 0.9:
                score = 0.6
                warnings.append("过度自信的正向预测，建议谨慎")

        if source_type == "business_structure" and target_type == "metric":
            score = min(score, 0.7)
            reasons.append("商业结构类知识需要更多验证")

        if edge_data.get("sample_size", 0) < 10 and edge_data.get("confidence", 0) > 0.7:
            score = min(score, 0.5)
            passed = False
            warnings.append("小样本高置信度，可能过拟合")

        return {
            "check": "risk_assessment",
            "score": score,
            "passed": passed,
            "reason": "; ".join(reasons),
            "warning": "; ".join(warnings),
        }

    def approve_learning(self, edge_id: int) -> Dict[str, Any]:
        """批准学习"""
        edge = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.id == edge_id
        ).first()

        if not edge:
            return {"success": False, "error": "知识边不存在"}

        if edge.status == "candidate":
            result = self.governance.promote_edge_status(edge_id)
            return result

        return {
            "success": True,
            "edge_id": edge_id,
            "status": edge.status,
            "message": "已处于非候选状态",
        }

    def reject_learning(self, edge_id: int, reason: str = "") -> Dict[str, Any]:
        """拒绝学习"""
        edge = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.id == edge_id
        ).first()

        if not edge:
            return {"success": False, "error": "知识边不存在"}

        edge.status = "deprecated"
        edge.context_condition = edge.context_condition or {}
        edge.context_condition["rejection_reason"] = reason

        self.db.commit()

        return {
            "success": True,
            "edge_id": edge_id,
            "new_status": "deprecated",
            "reason": reason,
        }

    def batch_review_candidates(self, user_id: int = 1, limit: int = 20) -> Dict[str, Any]:
        """批量审核候选知识"""
        candidates = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.user_id == user_id,
            GrowthKnowledgeEdge.status == "candidate",
        ).limit(limit).all()

        results = []
        approved_count = 0
        observing_count = 0
        rejected_count = 0

        for edge in candidates:
            edge_data = {
                "source_type": edge.source_type,
                "source_value": edge.source_value,
                "target_type": edge.target_type,
                "target_value": edge.target_value,
                "relation_type": edge.relation_type,
                "confidence": edge.confidence_score,
                "sample_size": edge.success_count + edge.failure_count,
                "experiment_count": edge.verified_count,
            }

            review = self.review_new_knowledge(edge_data)

            if review["decision"] == "approved":
                self.approve_learning(edge.id)
                approved_count += 1
            elif review["decision"] == "observing":
                if edge.status == "candidate":
                    edge.status = "observing"
                    self.db.commit()
                observing_count += 1
            else:
                rejected_count += 1

            results.append({
                "edge_id": edge.id,
                "source": f"{edge.source_type}: {edge.source_value}",
                "target": f"{edge.target_type}: {edge.target_value}",
                "decision": review["decision"],
                "confidence": review["confidence"],
            })

        return {
            "success": True,
            "total_reviewed": len(candidates),
            "approved": approved_count,
            "observing": observing_count,
            "rejected": rejected_count,
            "details": results,
        }

    def get_observation_pool(self, user_id: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
        """获取观察池"""
        edges = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.user_id == user_id,
            GrowthKnowledgeEdge.status == "observing",
        ).order_by(GrowthKnowledgeEdge.confidence_score.desc()).limit(limit).all()

        return [{
            "id": e.id,
            "source": f"{e.source_type}: {e.source_value}",
            "target": f"{e.target_type}: {e.target_value}",
            "relation": e.relation_type,
            "confidence": e.confidence_score,
            "sample_size": e.success_count + e.failure_count,
            "evidence_level": e.evidence_level,
        } for e in edges]