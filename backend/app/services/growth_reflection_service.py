"""
Growth Reflection Service - 增长反思服务

TASK-016.3B.5.6：增长大脑自我反思层

核心职责：
1. 分析预测误差
2. 校准策略置信度
3. 记录导演错误
4. 自动纠错
"""

from datetime import datetime
from typing import List, Dict, Any

from app.core.database import SessionLocal
from app.models.video_production import (
    GrowthPredictionError,
    StrategyCalibrationRecord,
    DirectorMistakeMemory,
    GrowthKnowledgeEdge,
    GrowthDecisionMemory,
    GrowthFailureMemory,
)


class GrowthReflectionService:
    """增长反思服务"""

    def __init__(self):
        self.db = SessionLocal()

    def close(self):
        self.db.close()

    def record_prediction_error(self, error_data: Dict[str, Any]) -> Dict[str, Any]:
        """记录预测误差"""
        predicted = error_data.get("predicted_value", 0)
        actual = error_data.get("actual_value", 0)

        if predicted == 0:
            error_rate = 1.0 if actual > 0 else 0.0
        else:
            error_rate = abs(predicted - actual) / predicted

        error_direction = "over_estimate" if predicted > actual else "under_estimate"

        error = GrowthPredictionError(
            user_id=error_data.get("user_id", 1),
            prediction_type=error_data.get("prediction_type"),
            predicted_value=predicted,
            actual_value=actual,
            error_rate=error_rate,
            error_direction=error_direction,
            strategy_used=error_data.get("strategy_used"),
            causal_edges_used=error_data.get("causal_edges_used"),
            context_conditions=error_data.get("context_conditions"),
            related_video_id=error_data.get("related_video_id"),
            related_plan_id=error_data.get("related_plan_id"),
        )

        self.db.add(error)
        self.db.commit()

        return {"success": True, "error_id": error.id, "error_rate": error_rate}

    def analyze_prediction_error(self, error_id: int) -> Dict[str, Any]:
        """分析预测误差根因"""
        error = self.db.query(GrowthPredictionError).filter(
            GrowthPredictionError.id == error_id
        ).first()

        if not error:
            return {"success": False, "error": "预测误差记录不存在"}

        analysis = {
            "error_id": error_id,
            "prediction_type": error.prediction_type,
            "error_rate": error.error_rate,
            "error_direction": error.error_direction,
        }

        causal_edges_used = error.causal_edges_used or []
        context_conditions = error.context_conditions or {}

        if error.error_direction == "over_estimate":
            possible_reasons = []

            if len(causal_edges_used) == 0:
                possible_reasons.append("预测时未使用任何因果边，可能过度依赖经验")
            else:
                for edge_id in causal_edges_used[:3]:
                    edge = self.db.query(GrowthKnowledgeEdge).filter(
                        GrowthKnowledgeEdge.id == edge_id
                    ).first()
                    if edge and edge.calibrated_confidence < edge.confidence_score:
                        possible_reasons.append(
                            f"因果边{edge_id}置信度已被校准降低，但预测时仍使用原始值"
                        )

            if error.prediction_type == "completion_rate":
                creator_context = context_conditions.get("creator_profile", {})
                if creator_context.get("expression_ability") == "weak":
                    possible_reasons.append("主播表达能力不足，故事型Hook效果受限")

            analysis["possible_reasons"] = possible_reasons

            if possible_reasons:
                error.root_cause_analysis = "; ".join(possible_reasons)

        else:  # under_estimate
            possible_reasons = ["可能存在未发现的正向因素"]
            analysis["possible_reasons"] = possible_reasons
            error.root_cause_analysis = "预测低估，可能存在未考虑的增强因素"

        error.reflection_status = "analyzed"
        error.analyzed_at = datetime.now()
        self.db.commit()

        return {"success": True, "analysis": analysis}

    def calibrate_strategy_confidence(self, strategy_type: str, user_id: int = 1) -> Dict[str, Any]:
        """校准策略置信度"""
        errors = self.db.query(GrowthPredictionError).filter(
            GrowthPredictionError.user_id == user_id,
            GrowthPredictionError.strategy_used == strategy_type,
            GrowthPredictionError.reflection_status == "analyzed",
        ).all()

        if not errors:
            return {"success": True, "message": "无足够数据进行校准"}

        total_predictions = len(errors)
        successful_predictions = sum(1 for e in errors if e.error_rate < 0.2)

        original_confidence = 0.85
        calibrated_confidence = successful_predictions / total_predictions if total_predictions > 0 else 0.5

        calibration = StrategyCalibrationRecord(
            user_id=user_id,
            strategy_type=strategy_type,
            original_confidence=original_confidence,
            calibrated_confidence=calibrated_confidence,
            prediction_count=total_predictions,
            success_count=successful_predictions,
            calibration_date=datetime.now(),
        )

        self.db.add(calibration)

        edges_to_update = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.user_id == user_id,
            GrowthKnowledgeEdge.source_value == strategy_type,
        ).all()

        for edge in edges_to_update:
            edge.calibrated_confidence = calibrated_confidence
            edge.prediction_count = total_predictions
            edge.prediction_success_count = successful_predictions

        self.db.commit()

        return {
            "success": True,
            "strategy_type": strategy_type,
            "original_confidence": original_confidence,
            "calibrated_confidence": round(calibrated_confidence, 2),
            "total_predictions": total_predictions,
            "successful_predictions": successful_predictions,
        }

    def record_director_mistake(self, mistake_data: Dict[str, Any]) -> Dict[str, Any]:
        """记录导演错误"""
        mistake = DirectorMistakeMemory(
            user_id=mistake_data.get("user_id", 1),
            mistake_type=mistake_data.get("mistake_type"),
            recommendation=mistake_data.get("recommendation"),
            expected_outcome=mistake_data.get("expected_outcome"),
            actual_outcome=mistake_data.get("actual_outcome"),
            mistake_reason=mistake_data.get("mistake_reason"),
            missing_context=mistake_data.get("missing_context"),
            correct_strategy=mistake_data.get("correct_strategy"),
            learning=mistake_data.get("learning"),
            related_video_id=mistake_data.get("related_video_id"),
            related_plan_id=mistake_data.get("related_plan_id"),
        )

        self.db.add(mistake)
        self.db.commit()

        return {"success": True, "mistake_id": mistake.id}

    def get_weekly_reflection(self, user_id: int = 1) -> Dict[str, Any]:
        """获取每周反思总结"""
        one_week_ago = datetime.now() - datetime.timedelta(days=7)

        prediction_errors = self.db.query(GrowthPredictionError).filter(
            GrowthPredictionError.user_id == user_id,
            GrowthPredictionError.created_at >= one_week_ago,
        ).all()

        mistake_memories = self.db.query(DirectorMistakeMemory).filter(
            DirectorMistakeMemory.user_id == user_id,
            DirectorMistakeMemory.created_at >= one_week_ago,
        ).all()

        total_predictions = len(prediction_errors)
        successful_predictions = sum(1 for e in prediction_errors if e.error_rate < 0.2)
        avg_error_rate = sum(e.error_rate for e in prediction_errors) / max(total_predictions, 1)

        total_mistakes = len(mistake_memories)
        mistake_types = {}
        for m in mistake_memories:
            mistake_types[m.mistake_type] = mistake_types.get(m.mistake_type, 0) + 1

        common_mistakes = sorted(mistake_types.items(), key=lambda x: x[1], reverse=True)[:3]

        return {
            "success": True,
            "period": "weekly",
            "predictions": {
                "total": total_predictions,
                "successful": successful_predictions,
                "success_rate": round(successful_predictions / max(total_predictions, 1), 2),
                "avg_error_rate": round(avg_error_rate, 2),
            },
            "mistakes": {
                "total": total_mistakes,
                "common_types": common_mistakes,
            },
            "recommendations": self._generate_reflection_recommendations(
                avg_error_rate, common_mistakes
            ),
        }

    def _generate_reflection_recommendations(self, avg_error_rate: float,
                                             common_mistakes: List) -> List[str]:
        """生成反思建议"""
        recommendations = []

        if avg_error_rate > 0.3:
            recommendations.append("预测误差偏高，建议增加上下文条件判断")

        if common_mistakes:
            top_mistake_type = common_mistakes[0][0] if common_mistakes else None
            if top_mistake_type:
                recommendations.append(f"常见错误类型：{top_mistake_type}，建议针对性优化")

        if not recommendations:
            recommendations.append("本周预测表现良好，继续保持")

        return recommendations

    def auto_correct_causal_edges(self, user_id: int = 1) -> Dict[str, Any]:
        """自动纠错因果边"""
        errors = self.db.query(GrowthPredictionError).filter(
            GrowthPredictionError.user_id == user_id,
            GrowthPredictionError.reflection_status == "analyzed",
            GrowthPredictionError.error_rate > 0.3,
        ).limit(20).all()

        corrected_count = 0

        for error in errors:
            causal_edges_used = error.causal_edges_used or []
            context_conditions = error.context_conditions or {}

            for edge_id in causal_edges_used:
                edge = self.db.query(GrowthKnowledgeEdge).filter(
                    GrowthKnowledgeEdge.id == edge_id
                ).first()

                if edge:
                    if not edge.context_condition:
                        edge.context_condition = {}

                    for key, value in context_conditions.items():
                        if key not in edge.context_condition:
                            edge.context_condition[key] = value

                    if error.error_direction == "over_estimate":
                        edge.calibrated_confidence = max(0.3, edge.calibrated_confidence - 0.1)

                    corrected_count += 1

            error.reflection_status = "corrected"

        self.db.commit()

        return {
            "success": True,
            "errors_analyzed": len(errors),
            "edges_corrected": corrected_count,
        }