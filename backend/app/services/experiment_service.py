"""
Experiment Service - 实验服务

TASK-016.3B.5.2：实验记忆

核心职责：
1. 创建和管理A/B测试实验
2. 记录实验结果和胜负判定
3. 提供实验驱动的导演决策支持
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.video_production import GrowthExperimentMemory
from app.models.video_performance import VideoPublishRecord, VideoMasterContent


class ExperimentService:
    """实验服务"""

    EXPERIMENT_TYPES = {
        "hook_test": {"description": "开场模式测试"},
        "title_test": {"description": "标题测试"},
        "content_structure": {"description": "内容结构测试"},
        "timing_test": {"description": "发布时间测试"},
        "thumbnail_test": {"description": "封面测试"},
        "creator_test": {"description": "主播测试"},
    }

    MIN_SAMPLE_SIZE = 20000

    def __init__(self):
        self.db = SessionLocal()

    def close(self):
        self.db.close()

    def create_experiment(self, experiment_type: str, variable: str,
                         variant_a: Dict, variant_b: Dict) -> Dict[str, Any]:
        """创建实验"""
        if experiment_type not in self.EXPERIMENT_TYPES:
            return {"success": False, "error": f"不支持的实验类型: {experiment_type}"}

        experiment = GrowthExperimentMemory(
            user_id=1,
            experiment_type=experiment_type,
            variable=variable,
            variant_a=variant_a,
            variant_b=variant_b,
            status="running",
        )

        self.db.add(experiment)
        self.db.commit()
        self.db.refresh(experiment)

        return {
            "success": True,
            "experiment_id": experiment.id,
            "experiment_type": experiment_type,
            "variable": variable,
            "status": "running",
        }

    def record_experiment_result(self, experiment_id: int,
                                video_a_id: int, video_b_id: int) -> Dict[str, Any]:
        """记录实验结果"""
        experiment = self.db.query(GrowthExperimentMemory).filter(
            GrowthExperimentMemory.id == experiment_id
        ).first()
        if not experiment:
            return {"success": False, "error": "实验不存在"}

        records_a = self.db.query(VideoPublishRecord).filter(
            VideoPublishRecord.video_master_id == video_a_id
        ).all()
        records_b = self.db.query(VideoPublishRecord).filter(
            VideoPublishRecord.video_master_id == video_b_id
        ).all()

        stats_a = self._calculate_video_stats(records_a)
        stats_b = self._calculate_video_stats(records_b)

        winner, confidence = self._determine_winner(stats_a, stats_b)

        experiment.winner = winner
        experiment.winner_confidence = confidence
        experiment.metrics = {
            "variant_a": stats_a,
            "variant_b": stats_b,
        }
        experiment.sample_size = stats_a["views"] + stats_b["views"]
        experiment.status = "completed"

        self.db.commit()

        return {
            "success": True,
            "experiment_id": experiment_id,
            "winner": winner,
            "confidence": round(confidence, 2),
            "metrics": {
                "A": stats_a,
                "B": stats_b,
            },
        }

    def _calculate_video_stats(self, records: List[VideoPublishRecord]) -> Dict[str, Any]:
        """计算视频统计数据"""
        if not records:
            return {
                "views": 0,
                "likes": 0,
                "comments": 0,
                "shares": 0,
                "followers": 0,
                "completion_rate": 0.0,
                "engagement_rate": 0.0,
                "retention": 0.0,
            }

        total_views = sum(r.views or 0 for r in records)
        total_likes = sum(r.likes or 0 for r in records)
        total_comments = sum(r.comments or 0 for r in records)
        total_shares = sum(r.shares or 0 for r in records)
        avg_completion = sum(r.completion_rate or 0 for r in records) / len(records)
        avg_retention = sum(r.first_3_second_retention or 0 for r in records) / len(records)

        engagement_rate = ((total_likes + total_comments + total_shares) / total_views * 100) if total_views > 0 else 0

        return {
            "views": total_views,
            "likes": total_likes,
            "comments": total_comments,
            "shares": total_shares,
            "completion_rate": round(avg_completion, 4),
            "engagement_rate": round(engagement_rate, 2),
            "retention": round(avg_retention, 4),
        }

    def _determine_winner(self, stats_a: Dict, stats_b: Dict) -> tuple:
        """判定获胜者"""
        if stats_a["views"] < self.MIN_SAMPLE_SIZE and stats_b["views"] < self.MIN_SAMPLE_SIZE:
            return None, 0.0

        a_score = self._calculate_experiment_score(stats_a)
        b_score = self._calculate_experiment_score(stats_b)

        if abs(a_score - b_score) < 0.05:
            return "tie", 0.5

        winner = "A" if a_score > b_score else "B"
        confidence = min(0.99, abs(a_score - b_score) * 2)

        return winner, confidence

    def _calculate_experiment_score(self, stats: Dict) -> float:
        """计算实验评分"""
        score = 0.0

        score += min(1.0, stats["views"] / 100000) * 0.3
        score += stats["completion_rate"] * 0.3
        score += min(1.0, stats["engagement_rate"] / 10) * 0.25
        score += stats["retention"] * 0.15

        return score

    def get_experiment_by_type(self, experiment_type: str) -> List[Dict[str, Any]]:
        """按类型查询实验"""
        experiments = self.db.query(GrowthExperimentMemory).filter(
            GrowthExperimentMemory.experiment_type == experiment_type,
            GrowthExperimentMemory.status == "completed"
        ).order_by(GrowthExperimentMemory.created_at.desc()).all()

        return [{
            "id": e.id,
            "type": e.experiment_type,
            "variable": e.variable,
            "variant_a": e.variant_a,
            "variant_b": e.variant_b,
            "winner": e.winner,
            "confidence": e.winner_confidence,
            "sample_size": e.sample_size,
        } for e in experiments]

    def suggest_experiment(self, video_id: int) -> Dict[str, Any]:
        """建议下一步实验"""
        video = self.db.query(VideoMasterContent).filter(VideoMasterContent.id == video_id).first()
        if not video:
            return {"success": False, "error": "视频不存在"}

        records = self.db.query(VideoPublishRecord).filter(
            VideoPublishRecord.video_master_id == video_id
        ).all()

        if not records:
            return {"success": False, "error": "无发布记录"}

        stats = self._calculate_video_stats(records)

        suggestions = []

        if stats["retention"] < 0.5:
            suggestions.append({
                "experiment_type": "hook_test",
                "reason": "前3秒留存较低，建议测试不同开场模式",
                "variables": ["个人故事", "反常识冲突", "痛点直击"],
            })

        if stats["engagement_rate"] < 3:
            suggestions.append({
                "experiment_type": "content_structure",
                "reason": "互动率较低，建议测试不同内容结构",
                "variables": ["故事型", "知识型", "情绪型"],
            })

        if suggestions:
            return {"success": True, "suggestions": suggestions}

        return {"success": True, "suggestions": [{"message": "当前表现良好，无需实验"}]}
