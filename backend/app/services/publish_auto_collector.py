"""
Publish Auto Collector - 发布数据自动采集服务

TASK-017.3：数据采集

核心职责：
1. 定时/手动触发采集各平台数据
2. 将采集数据更新到 PublishTask
3. 为自动复盘提供数据基础

注：当前为模拟实现，真实环境需对接平台OpenAPI
"""

import random
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.publish_task import PublishTask
from app.models.platform_account import PlatformAccount


class PublishAutoCollector:
    """发布数据自动采集器"""

    # 模拟数据生成基准（根据平台差异化）
    PLATFORM_BASELINES = {
        "douyin": {"base_plays": 8000, "play_variance": 0.6, "engagement_rate": 0.08},
        "video_channel": {"base_plays": 5000, "play_variance": 0.5, "engagement_rate": 0.06},
        "xiaohongshu": {"base_plays": 3000, "play_variance": 0.7, "engagement_rate": 0.12},
        "kuaishou": {"base_plays": 6000, "play_variance": 0.55, "engagement_rate": 0.07},
        "bilibili": {"base_plays": 4000, "play_variance": 0.8, "engagement_rate": 0.10},
    }

    def __init__(self, db: Session):
        self.db = db

    def collect_metrics(self, task_id: int) -> Dict[str, Any]:
        """采集指定任务的平台数据（模拟）"""
        task = self.db.query(PublishTask).filter(PublishTask.id == task_id).first()
        if not task:
            return {"success": False, "error": "任务不存在"}

        if task.status != "published":
            return {"success": False, "error": "任务未发布，无法采集数据"}

        # 获取平台基准
        baseline = self.PLATFORM_BASELINES.get(task.platform, self.PLATFORM_BASELINES["douyin"])

        # 模拟数据生成（基于内容质量因子）
        quality_factor = self._estimate_quality_factor(task)

        plays = int(baseline["base_plays"] * (1 + random.uniform(-baseline["play_variance"], baseline["play_variance"])) * quality_factor)
        engagement_rate = baseline["engagement_rate"] * quality_factor * random.uniform(0.8, 1.2)

        likes = int(plays * engagement_rate * random.uniform(0.5, 0.8))
        comments = int(plays * engagement_rate * random.uniform(0.1, 0.3))
        shares = int(plays * engagement_rate * random.uniform(0.05, 0.15))
        collects = int(plays * engagement_rate * random.uniform(0.1, 0.25))
        followers = int(plays * 0.005 * quality_factor * random.uniform(0.5, 1.5))

        completion_rate = round(random.uniform(15, 45) * quality_factor, 2)
        ctr = round(random.uniform(3, 12) * quality_factor, 2)

        # 更新任务
        task.play_count = plays
        task.like_count = likes
        task.comment_count = comments
        task.share_count = shares
        task.collect_count = collects
        task.follower_gained = followers
        task.completion_rate = completion_rate
        task.ctr = ctr
        task.metrics_collected_at = datetime.utcnow()
        task.status = "collecting"

        self.db.commit()
        self.db.refresh(task)

        return {
            "success": True,
            "task_id": task_id,
            "platform": task.platform,
            "metrics": {
                "play_count": plays,
                "like_count": likes,
                "comment_count": comments,
                "share_count": shares,
                "collect_count": collects,
                "follower_gained": followers,
                "completion_rate": completion_rate,
                "ctr": ctr,
            },
            "quality_factor": round(quality_factor, 2),
        }

    def _estimate_quality_factor(self, task: PublishTask) -> float:
        """估算内容质量因子（基于标签、标题等）"""
        factor = 1.0

        # 有标签说明内容定位清晰
        if task.tags:
            factor += len(task.tags) * 0.05

        # 有描述说明内容完整
        if task.content_description:
            factor += 0.1

        # 有分类说明领域聚焦
        if task.category:
            factor += 0.1

        # 计划发布时间说明有策略
        if task.scheduled_at:
            factor += 0.05

        return min(factor, 2.0)

    def batch_collect(self, user_id: int) -> Dict[str, Any]:
        """批量采集用户所有已发布任务的数据"""
        tasks = self.db.query(PublishTask).filter(
            PublishTask.user_id == user_id,
            PublishTask.status == "published",
        ).all()

        results = []
        for task in tasks:
            result = self.collect_metrics(task.id)
            results.append(result)

        success_count = sum(1 for r in results if r.get("success"))

        return {
            "success": True,
            "total": len(tasks),
            "success_count": success_count,
            "failed_count": len(tasks) - success_count,
            "results": results,
        }
