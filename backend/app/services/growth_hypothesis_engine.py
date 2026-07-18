"""
Growth Hypothesis Engine - 增长假设引擎

TASK-016.3B.5.5：增长大脑自动学习层

核心职责：
1. 从历史数据中发现潜在规律
2. 主动提出实验假设
3. 评估假设优先级
4. 自动创建实验
"""

from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.video_production import (
    GrowthHypothesis,
    GrowthKnowledgeEdge,
    GrowthExperimentMemory,
    GrowthDecisionMemory,
    AudienceGrowthMemory,
)


class GrowthHypothesisEngine:
    """增长假设引擎"""

    def __init__(self):
        self.db = SessionLocal()

    def close(self):
        self.db.close()

    def discover_patterns(self, user_id: int = 1, limit: int = 10) -> List[Dict[str, Any]]:
        """从历史数据中发现模式并生成假设"""
        hypotheses = []

        decision_memories = self.db.query(GrowthDecisionMemory).filter(
            GrowthDecisionMemory.user_id == user_id
        ).order_by(GrowthDecisionMemory.confidence_score.desc()).limit(50).all()

        for memory in decision_memories:
            if memory.confidence_score > 0.6 and memory.total_count >= 10:
                hypothesis = self._generate_hypothesis_from_decision(memory)
                if hypothesis:
                    hypotheses.append(hypothesis)

        return hypotheses[:limit]

    def _generate_hypothesis_from_decision(self, memory: GrowthDecisionMemory) -> Dict[str, Any]:
        """从决策记忆生成假设"""
        conditions = memory.conditions or {}
        result_data = memory.result or {}

        opening_pattern = conditions.get("opening_pattern") or memory.opening_pattern
        content_type = conditions.get("content_type") or memory.content_type
        platform = conditions.get("platform") or memory.platform
        product_category = memory.product_category

        if not opening_pattern or not platform:
            return None

        success_rate = memory.success_count / max(memory.total_count, 1)

        hypothesis_text = (
            f"假设：{opening_pattern}开头比知识分享开头更适合{platform}平台"
        )

        if product_category:
            hypothesis_text += f"的{product_category}品类"

        return {
            "hypothesis": hypothesis_text,
            "description": f"基于{memory.total_count}个历史案例，{opening_pattern}开头的成功率为{success_rate*100:.1f}%",
            "condition_type": "opening_pattern",
            "condition_value": opening_pattern,
            "predicted_effect": f"提升完播率和关注率",
            "predicted_impact": success_rate * memory.confidence_score,
            "evidence_count": memory.total_count,
            "source_data": {
                "platform": platform,
                "product_category": product_category,
                "content_type": content_type,
                "success_count": memory.success_count,
                "total_count": memory.total_count,
                "confidence": memory.confidence_score,
            },
            "priority_score": success_rate * memory.confidence_score * memory.total_count,
        }

    def propose_hypothesis(self, hypothesis_data: Dict[str, Any]) -> Dict[str, Any]:
        """提出新假设"""
        existing = self.db.query(GrowthHypothesis).filter(
            GrowthHypothesis.user_id == hypothesis_data.get("user_id", 1),
            GrowthHypothesis.hypothesis == hypothesis_data["hypothesis"],
        ).first()

        if existing:
            return {"success": False, "error": "假设已存在"}

        hypothesis = GrowthHypothesis(
            user_id=hypothesis_data.get("user_id", 1),
            hypothesis=hypothesis_data["hypothesis"],
            description=hypothesis_data.get("description"),
            condition_type=hypothesis_data.get("condition_type"),
            condition_value=hypothesis_data.get("condition_value"),
            predicted_effect=hypothesis_data.get("predicted_effect"),
            predicted_impact=hypothesis_data.get("predicted_impact", 0.0),
            evidence_count=hypothesis_data.get("evidence_count", 0),
            source_data=hypothesis_data.get("source_data"),
            priority_score=hypothesis_data.get("priority_score", 0.0),
            created_by=hypothesis_data.get("created_by", "system"),
        )

        self.db.add(hypothesis)
        self.db.commit()

        return {"success": True, "hypothesis_id": hypothesis.id}

    def auto_generate_hypotheses(self, user_id: int = 1) -> Dict[str, Any]:
        """自动生成假设"""
        patterns = self.discover_patterns(user_id)
        created_count = 0

        for pattern in patterns:
            result = self.propose_hypothesis({**pattern, "user_id": user_id})
            if result["success"]:
                created_count += 1

        return {"success": True, "patterns_found": len(patterns), "hypotheses_created": created_count}

    def evaluate_hypothesis(self, hypothesis_id: int) -> Dict[str, Any]:
        """评估假设"""
        hypothesis = self.db.query(GrowthHypothesis).filter(
            GrowthHypothesis.id == hypothesis_id
        ).first()

        if not hypothesis:
            return {"success": False, "error": "假设不存在"}

        score = hypothesis.priority_score
        evidence = hypothesis.evidence_count

        if score > 50 and evidence >= 20:
            status = "high_priority"
            recommendation = "建议创建实验验证"
        elif score > 20 and evidence >= 10:
            status = "medium_priority"
            recommendation = "建议观察更多数据"
        else:
            status = "low_priority"
            recommendation = "暂不建议实验"

        return {
            "success": True,
            "hypothesis_id": hypothesis_id,
            "hypothesis": hypothesis.hypothesis,
            "priority_score": score,
            "evidence_count": evidence,
            "status": status,
            "recommendation": recommendation,
        }

    def create_experiment_from_hypothesis(self, hypothesis_id: int) -> Dict[str, Any]:
        """从假设创建实验"""
        hypothesis = self.db.query(GrowthHypothesis).filter(
            GrowthHypothesis.id == hypothesis_id
        ).first()

        if not hypothesis:
            return {"success": False, "error": "假设不存在"}

        source_data = hypothesis.source_data or {}

        experiment = GrowthExperimentMemory(
            user_id=hypothesis.user_id,
            experiment_type="hypothesis_validation",
            variable=f"{hypothesis.condition_type}: {hypothesis.condition_value}",
            variant_a={"pattern": hypothesis.condition_value},
            variant_b={"pattern": "knowledge_share"},
            status="draft",
            hypothesis=hypothesis.hypothesis,
            related_platform=source_data.get("platform"),
            related_product_category=source_data.get("product_category"),
        )

        self.db.add(experiment)
        self.db.commit()

        hypothesis.status = "experiment_created"
        hypothesis.experiment_id = experiment.id
        self.db.commit()

        return {
            "success": True,
            "hypothesis_id": hypothesis_id,
            "experiment_id": experiment.id,
        }

    def get_pending_hypotheses(self, user_id: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
        """获取待处理假设"""
        hypotheses = self.db.query(GrowthHypothesis).filter(
            GrowthHypothesis.user_id == user_id,
            GrowthHypothesis.status == "proposed",
        ).order_by(GrowthHypothesis.priority_score.desc()).limit(limit).all()

        return [{
            "id": h.id,
            "hypothesis": h.hypothesis,
            "description": h.description,
            "condition_type": h.condition_type,
            "condition_value": h.condition_value,
            "predicted_effect": h.predicted_effect,
            "predicted_impact": h.predicted_impact,
            "evidence_count": h.evidence_count,
            "priority_score": h.priority_score,
            "status": h.status,
            "created_at": str(h.created_at),
        } for h in hypotheses]