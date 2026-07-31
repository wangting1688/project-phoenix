"""
Scheduler Service - 后台定时任务调度器

TASK-017.4：自动复盘触发
核心职责：
1. 定时自动扫描已发布任务，执行数据采集
2. 定时自动扫描已采集任务，执行复盘
3. 实现真正的无人值守增长闭环
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.publish_task import PublishTask
from app.services.publish_auto_collector import PublishAutoCollector
from app.services.publish_auto_review import PublishAutoReview

logger = logging.getLogger(__name__)


class GrowthSchedulerService:
    """增长定时任务服务"""

    def __init__(self):
        self._scheduler = None
        self._running = False

    def start(self):
        """启动定时任务调度器"""
        from apscheduler.schedulers.background import BackgroundScheduler

        if self._running:
            logger.info("调度器已在运行")
            return

        self._scheduler = BackgroundScheduler()

        # 每10分钟扫描一次：自动采集 published 任务的数据
        self._scheduler.add_job(
            self._auto_collect_job,
            trigger="interval",
            minutes=10,
            id="auto_collect",
            replace_existing=True,
        )

        # 每10分钟扫描一次：自动复盘 collecting 状态的任务
        self._scheduler.add_job(
            self._auto_review_job,
            trigger="interval",
            minutes=10,
            id="auto_review",
            replace_existing=True,
        )

        # 每30分钟执行一次完整闭环：published → 采集 → 复盘
        self._scheduler.add_job(
            self._full_pipeline_job,
            trigger="interval",
            minutes=30,
            id="full_pipeline",
            replace_existing=True,
        )

        self._scheduler.start()
        self._running = True
        logger.info("增长定时调度器已启动")

    def stop(self):
        """停止定时任务调度器"""
        if self._scheduler:
            self._scheduler.shutdown()
            self._running = False
            logger.info("增长定时调度器已停止")

    def status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        jobs = []
        if self._scheduler:
            for job in self._scheduler.get_jobs():
                jobs.append({
                    "id": job.id,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger),
                })
        return {
            "running": self._running,
            "jobs": jobs,
        }

    def _get_db(self) -> Session:
        """获取数据库会话"""
        return SessionLocal()

    def _auto_collect_job(self):
        """自动采集任务"""
        db = self._get_db()
        try:
            # 查找 published 状态且未采集或超过1小时未更新的任务
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            tasks = db.query(PublishTask).filter(
                PublishTask.status == "published",
            ).filter(
                (PublishTask.metrics_collected_at == None) |
                (PublishTask.metrics_collected_at < one_hour_ago)
            ).all()

            if not tasks:
                return

            collector = PublishAutoCollector(db)
            success_count = 0
            for task in tasks:
                try:
                    result = collector.collect_metrics(task.id)
                    if result.get("success"):
                        success_count += 1
                        logger.info(f"自动采集成功: task_id={task.id}, plays={result['metrics']['play_count']}")
                except Exception as e:
                    logger.error(f"自动采集失败: task_id={task.id}, error={e}")

            logger.info(f"自动采集完成: 成功 {success_count}/{len(tasks)}")
        finally:
            db.close()

    def _auto_review_job(self):
        """自动复盘任务"""
        db = self._get_db()
        try:
            # 查找 collecting 状态的任务
            tasks = db.query(PublishTask).filter(
                PublishTask.status == "collecting",
            ).all()

            if not tasks:
                return

            reviewer = PublishAutoReview(db)
            success_count = 0
            for task in tasks:
                try:
                    result = reviewer.review_task(task.id)
                    if result.get("success"):
                        success_count += 1
                        logger.info(f"自动复盘成功: task_id={task.id}, score={result['performance']['score']}")
                except Exception as e:
                    logger.error(f"自动复盘失败: task_id={task.id}, error={e}")

            logger.info(f"自动复盘完成: 成功 {success_count}/{len(tasks)}")
        finally:
            db.close()

    def _full_pipeline_job(self):
        """完整闭环任务：published → 采集 → 复盘"""
        db = self._get_db()
        try:
            # 查找 published 状态的任务
            tasks = db.query(PublishTask).filter(
                PublishTask.status == "published",
            ).all()

            if not tasks:
                return

            collector = PublishAutoCollector(db)
            reviewer = PublishAutoReview(db)
            success_count = 0

            for task in tasks:
                try:
                    # Step 1: 采集
                    collect_result = collector.collect_metrics(task.id)
                    if not collect_result.get("success"):
                        continue

                    # Step 2: 复盘
                    review_result = reviewer.review_task(task.id)
                    if review_result.get("success"):
                        success_count += 1
                        logger.info(f"完整闭环成功: task_id={task.id}, score={review_result['performance']['score']}")
                except Exception as e:
                    logger.error(f"完整闭环失败: task_id={task.id}, error={e}")

            logger.info(f"完整闭环完成: 成功 {success_count}/{len(tasks)}")
        finally:
            db.close()


# 全局调度器实例
_growth_scheduler: Optional[GrowthSchedulerService] = None


def get_growth_scheduler() -> GrowthSchedulerService:
    """获取全局调度器实例"""
    global _growth_scheduler
    if _growth_scheduler is None:
        _growth_scheduler = GrowthSchedulerService()
    return _growth_scheduler
