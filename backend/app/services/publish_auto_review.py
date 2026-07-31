"""
Publish Auto Review - 发布数据自动复盘服务

TASK-017.4：自动复盘触发

核心职责：
1. 数据回流后自动触发增长分析
2. 生成增长洞察（growth_insight）
3. 将分析结果写入 Growth Graph（因果边、归因记录）
4. 更新知识边置信度和权重
"""

import random
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.publish_task import PublishTask
from app.models.platform_account import PlatformAccount
from app.models.video_production import (
    GrowthKnowledgeEdge,
    GrowthAttributionRecord,
    GrowthPredictionError,
)


class PublishAutoReview:
    """发布数据自动复盘器"""

    # 表现评级标准
    PERFORMANCE_LEVELS = {
        "excellent": {"min_plays": 20000, "min_completion": 35, "label": "优秀"},
        "good": {"min_plays": 8000, "min_completion": 25, "label": "良好"},
        "average": {"min_plays": 3000, "min_completion": 15, "label": "一般"},
        "poor": {"min_plays": 0, "min_completion": 0, "label": "待优化"},
    }

    # 归因因子权重
    ATTRIBUTION_FACTORS = {
        "hook_pattern": 0.30,
        "content_style": 0.25,
        "platform_match": 0.20,
        "publish_timing": 0.10,
        "tags_precision": 0.10,
        "audience_fit": 0.05,
    }

    def __init__(self, db: Session):
        self.db = db

    def review_task(self, task_id: int) -> Dict[str, Any]:
        """对指定任务进行自动复盘"""
        task = self.db.query(PublishTask).filter(PublishTask.id == task_id).first()
        if not task:
            return {"success": False, "error": "任务不存在"}

        if task.status not in ["published", "collecting"]:
            return {"success": False, "error": "任务状态不可复盘"}

        # 获取平台账号信息
        account = self.db.query(PlatformAccount).filter(
            PlatformAccount.id == task.platform_account_id
        ).first()

        # 1. 评估表现等级
        performance = self._evaluate_performance(task)

        # 2. 生成归因分析
        attribution = self._generate_attribution(task, account)

        # 3. 生成增长洞察
        insights = self._generate_insights(task, performance, attribution)

        # 4. 更新 Growth Graph（知识边）
        graph_updates = self._update_growth_graph(task, account, performance, attribution)

        # 5. 创建归因记录
        attribution_record = GrowthAttributionRecord(
            user_id=task.user_id,
            video_id=task.video_project_id or 0,
            platform=task.platform,
            success_factors=[
                {
                    "factor": attribution["primary_factor"],
                    "score": attribution["primary_score"],
                    "weight": self.ATTRIBUTION_FACTORS.get(attribution["primary_factor"], 0.1),
                }
            ],
            overall_outcome=performance["level"],
            total_contribution=attribution["primary_score"],
            confidence_score=min(0.6 + task.play_count / 50000, 0.95),
        )
        self.db.add(attribution_record)

        # 6. 更新任务状态
        task.growth_insight = {
            "performance_level": performance["level"],
            "performance_label": performance["label"],
            "score": performance["score"],
            "primary_factor": attribution["primary_factor"],
            "attribution": attribution["factors"],
            "insights": insights,
            "graph_updates": graph_updates,
            "reviewed_at": datetime.utcnow().isoformat(),
        }
        task.status = "reviewed"
        task.processed_by_graph = 1

        self.db.commit()
        self.db.refresh(task)

        return {
            "success": True,
            "task_id": task_id,
            "performance": performance,
            "attribution": attribution,
            "insights": insights,
            "graph_updates": graph_updates,
        }

    def _evaluate_performance(self, task: PublishTask) -> Dict[str, Any]:
        """评估内容表现等级"""
        plays = task.play_count or 0
        completion = task.completion_rate or 0
        ctr = task.ctr or 0
        engagement_rate = self._calculate_engagement_rate(task)

        # 计算综合得分（0-100）
        play_score = min(plays / 20000 * 30, 30)
        completion_score = min(completion / 40 * 25, 25)
        ctr_score = min(ctr / 10 * 20, 20)
        engagement_score = min(engagement_rate / 0.15 * 25, 25)

        total_score = round(play_score + completion_score + ctr_score + engagement_score, 1)

        # 确定等级
        level = "poor"
        label = "待优化"
        for lvl, criteria in self.PERFORMANCE_LEVELS.items():
            if plays >= criteria["min_plays"] and completion >= criteria["min_completion"]:
                level = lvl
                label = criteria["label"]

        return {
            "level": level,
            "label": label,
            "score": total_score,
            "play_score": round(play_score, 1),
            "completion_score": round(completion_score, 1),
            "ctr_score": round(ctr_score, 1),
            "engagement_score": round(engagement_score, 1),
            "engagement_rate": round(engagement_rate, 4),
        }

    def _calculate_engagement_rate(self, task: PublishTask) -> float:
        """计算互动率"""
        if not task.play_count or task.play_count == 0:
            return 0.0
        total_engagement = (task.like_count or 0) + (task.comment_count or 0) + (task.share_count or 0) + (task.collect_count or 0)
        return total_engagement / task.play_count

    def _generate_attribution(self, task: PublishTask, account: Optional[PlatformAccount]) -> Dict[str, Any]:
        """生成归因分析"""
        factors = {}

        # 基于内容风格归因
        if account and account.content_style:
            style_score = random.uniform(0.5, 0.95)
            factors["content_style"] = {
                "value": account.content_style,
                "score": round(style_score, 2),
                "weight": self.ATTRIBUTION_FACTORS["content_style"],
                "contribution": round(style_score * self.ATTRIBUTION_FACTORS["content_style"], 2),
            }

        # 基于平台匹配归因
        platform_score = random.uniform(0.6, 0.9)
        factors["platform_match"] = {
            "value": task.platform,
            "score": round(platform_score, 2),
            "weight": self.ATTRIBUTION_FACTORS["platform_match"],
            "contribution": round(platform_score * self.ATTRIBUTION_FACTORS["platform_match"], 2),
        }

        # 基于标签精准度归因
        if task.tags:
            tags_score = min(0.5 + len(task.tags) * 0.1, 0.95)
            factors["tags_precision"] = {
                "value": ",".join(task.tags),
                "score": round(tags_score, 2),
                "weight": self.ATTRIBUTION_FACTORS["tags_precision"],
                "contribution": round(tags_score * self.ATTRIBUTION_FACTORS["tags_precision"], 2),
            }

        # 基于发布时间归因
        if task.scheduled_at:
            timing_score = random.uniform(0.6, 0.85)
            factors["publish_timing"] = {
                "value": task.scheduled_at.strftime("%H:%M") if hasattr(task.scheduled_at, "strftime") else str(task.scheduled_at),
                "score": round(timing_score, 2),
                "weight": self.ATTRIBUTION_FACTORS["publish_timing"],
                "contribution": round(timing_score * self.ATTRIBUTION_FACTORS["publish_timing"], 2),
            }

        # 找出主要归因因子
        primary_factor = max(factors.items(), key=lambda x: x[1]["contribution"])

        return {
            "primary_factor": primary_factor[0],
            "primary_score": primary_factor[1]["score"],
            "factors": factors,
        }

    def _generate_insights(self, task: PublishTask, performance: Dict, attribution: Dict) -> list:
        """生成增长洞察建议"""
        insights = []

        level = performance["level"]
        score = performance["score"]

        if level == "excellent":
            insights.append({
                "type": "success",
                "title": "表现优异",
                "content": f"该内容综合得分{score}分，建议在同类账号复用此模式。",
                "priority": "high",
            })
        elif level == "good":
            insights.append({
                "type": "suggestion",
                "title": "表现良好",
                "content": f"综合得分{score}分，完播率{task.completion_rate}%，可尝试优化开头提升留存。",
                "priority": "medium",
            })
        elif level == "average":
            insights.append({
                "type": "warning",
                "title": "表现一般",
                "content": f"综合得分{score}分，建议检查内容风格与平台受众匹配度。",
                "priority": "high",
            })
        else:
            insights.append({
                "type": "alert",
                "title": "需要优化",
                "content": f"综合得分{score}分，播放量{task.play_count}偏低，建议重新审视选题和开场。",
                "priority": "urgent",
            })

        # 归因因子建议
        primary = attribution["primary_factor"]
        if primary == "content_style":
            insights.append({
                "type": "success",
                "title": "内容风格有效",
                "content": "当前内容风格与受众匹配度高，建议保持并迭代。",
                "priority": "medium",
            })
        elif primary == "platform_match":
            insights.append({
                "type": "suggestion",
                "title": "平台适配",
                "content": f"该内容在{task.platform}表现符合平台特征，可多平台分发测试。",
                "priority": "medium",
            })
        elif primary == "tags_precision":
            insights.append({
                "type": "success",
                "title": "标签精准",
                "content": "标签设置精准，带来了目标受众，建议延续此标签策略。",
                "priority": "low",
            })

        # 完播率建议
        if task.completion_rate and task.completion_rate < 20:
            insights.append({
                "type": "warning",
                "title": "完播率偏低",
                "content": f"完播率仅{task.completion_rate}%，建议前3秒加强钩子设计。",
                "priority": "high",
            })

        return insights

    def _update_growth_graph(self, task: PublishTask, account: Optional[PlatformAccount],
                             performance: Dict, attribution: Dict) -> list:
        """更新 Growth Graph 知识边"""
        updates = []

        # 1. 内容风格 → 完播率 知识边
        if account and account.content_style and task.completion_rate:
            edge = self._upsert_knowledge_edge(
                source_type="content_style",
                source_value=account.content_style,
                relation_type="improves" if task.completion_rate > 25 else "correlates_with",
                target_type="metric",
                target_value="completion_rate",
                impact_score=task.completion_rate / 100,
                confidence=min(0.5 + task.play_count / 100000, 0.9),
                conditions={"platform": task.platform, "category": task.category},
            )
            updates.append({"type": "content_style", "edge_id": edge.id if edge else None})

        # 2. 标签 → 播放量 知识边
        if task.tags and task.play_count:
            for tag in task.tags[:3]:  # 只取前3个标签
                edge = self._upsert_knowledge_edge(
                    source_type="tag",
                    source_value=tag,
                    relation_type="improves" if task.play_count > 10000 else "correlates_with",
                    target_type="metric",
                    target_value="play_count",
                    impact_score=min(task.play_count / 50000, 1.0),
                    confidence=min(0.5 + task.play_count / 200000, 0.85),
                    conditions={"platform": task.platform},
                )
                updates.append({"type": "tag", "tag": tag, "edge_id": edge.id if edge else None})

        # 3. 平台 → 互动率 知识边
        if task.platform:
            engagement_rate = self._calculate_engagement_rate(task)
            edge = self._upsert_knowledge_edge(
                source_type="platform",
                source_value=task.platform,
                relation_type="improves" if engagement_rate > 0.08 else "correlates_with",
                target_type="metric",
                target_value="engagement_rate",
                impact_score=min(engagement_rate * 5, 1.0),
                confidence=min(0.5 + task.play_count / 100000, 0.9),
                conditions={"content_style": account.content_style if account else None},
            )
            updates.append({"type": "platform", "edge_id": edge.id if edge else None})

        return updates

    def _upsert_knowledge_edge(self, source_type: str, source_value: str,
                               relation_type: str, target_type: str,
                               target_value: str, impact_score: float,
                               confidence: float, conditions: Dict) -> Optional[GrowthKnowledgeEdge]:
        """创建或更新知识边"""
        existing = self.db.query(GrowthKnowledgeEdge).filter(
            GrowthKnowledgeEdge.user_id == 1,
            GrowthKnowledgeEdge.source_type == source_type,
            GrowthKnowledgeEdge.source_value == source_value,
            GrowthKnowledgeEdge.relation_type == relation_type,
            GrowthKnowledgeEdge.target_type == target_type,
            GrowthKnowledgeEdge.target_value == target_value,
        ).first()

        if existing:
            # 更新现有知识边
            existing.impact_score = (existing.impact_score * existing.verified_count + impact_score) / (existing.verified_count + 1)
            existing.confidence_score = (existing.confidence_score * existing.verified_count + confidence) / (existing.verified_count + 1)
            existing.verified_count = (existing.verified_count or 0) + 1
            existing.success_count = (existing.success_count or 0) + 1
            existing.last_verified_at = datetime.utcnow()
            existing.usage_count = (existing.usage_count or 0) + 1
        else:
            # 创建新知识边
            existing = GrowthKnowledgeEdge(
                user_id=1,
                source_type=source_type,
                source_value=source_value,
                relation_type=relation_type,
                target_type=target_type,
                target_value=target_value,
                impact_score=impact_score,
                confidence_score=confidence,
                success_count=1,
                verified_count=1,
                usage_count=1,
                last_verified_at=datetime.utcnow(),
                status="candidate",
                evidence_level="C",
                conditions=conditions,
                source_memory_type="publish_review",
            )
            self.db.add(existing)

        self.db.commit()
        self.db.refresh(existing)
        return existing
