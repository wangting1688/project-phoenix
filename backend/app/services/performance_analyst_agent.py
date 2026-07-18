"""
Performance Analyst Agent - 表现分析Agent

TASK-016.3B.5：AI Growth Decision Graph

核心职责：
1. 基于发布数据做事实分析
2. 识别哪里掉流量、哪里产生兴趣、哪里产生转化
3. 输出结构化分析报告
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.video_performance import VideoPublishRecord, PlatformPerformanceScore, VideoMasterContent
from app.models.video_production import GrowthReviewReport


class PerformanceAnalystAgent:
    """表现分析Agent"""

    RETENTION_SEGMENTS = [0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0]

    def __init__(self):
        self.db = SessionLocal()

    def close(self):
        self.db.close()

    def analyze_video_performance(self, video_id: int) -> Dict[str, Any]:
        """分析单个视频表现"""
        video = self.db.query(VideoMasterContent).filter(VideoMasterContent.id == video_id).first()
        if not video:
            return {"success": False, "error": "视频不存在"}

        publish_records = self.db.query(VideoPublishRecord).filter(
            VideoPublishRecord.video_master_id == video_id
        ).all()

        if not publish_records:
            return {"success": False, "error": "无发布记录"}

        analysis = {
            "video_id": video_id,
            "title": video.title,
            "overall_performance": {},
            "platform_analyses": [],
            "drop_points": [],
            "interest_points": [],
            "conversion_points": [],
        }

        for record in publish_records:
            platform_analysis = self._analyze_platform(record)
            analysis["platform_analyses"].append(platform_analysis)

            drop_points = self._find_drop_points(record)
            interest_points = self._find_interest_points(record)
            conversion_points = self._find_conversion_points(record)

            analysis["drop_points"].extend(drop_points)
            analysis["interest_points"].extend(interest_points)
            analysis["conversion_points"].extend(conversion_points)

        analysis["overall_performance"] = self._summarize_overall(analysis["platform_analyses"])

        return {"success": True, **analysis}

    def _analyze_platform(self, record: VideoPublishRecord) -> Dict[str, Any]:
        """分析单个平台表现"""
        score = self.db.query(PlatformPerformanceScore).filter(
            PlatformPerformanceScore.publish_record_id == record.id
        ).first()

        return {
            "platform": record.platform,
            "published_at": str(record.published_at),
            "views": record.views,
            "likes": record.likes,
            "comments": record.comments,
            "shares": record.shares,
            "favorites": record.favorites,
            "completion_rate": record.completion_rate,
            "avg_watch_time": record.avg_watch_time,
            "first_3_second_retention": record.first_3_second_retention,
            "gmv": record.gmv,
            "order_count": record.order_count,
            "conversion_rate": record.conversion_rate,
            "engagement_rate": self._calc_engagement_rate(record),
            "score": score.overall_score if score else None,
            "score_breakdown": score.breakdown if score else None,
        }

    def _calc_engagement_rate(self, record: VideoPublishRecord) -> float:
        """计算互动率"""
        if not record.views:
            return 0.0
        return round((record.likes + record.comments + record.shares) / record.views * 100, 2)

    def _find_drop_points(self, record: VideoPublishRecord) -> List[Dict[str, Any]]:
        """找到掉流量点"""
        drop_points = []
        retention = record.first_3_second_retention or 0
        completion = record.completion_rate or 0

        if retention < 0.4:
            drop_points.append({
                "platform": record.platform,
                "point": "前3秒",
                "severity": "critical",
                "metric": "3秒留存",
                "value": retention,
                "reason": "前3秒吸引力不足",
            })
        elif retention < 0.6:
            drop_points.append({
                "platform": record.platform,
                "point": "前3秒",
                "severity": "high",
                "metric": "3秒留存",
                "value": retention,
                "reason": "前3秒留存偏低",
            })

        if completion < 0.2:
            drop_points.append({
                "platform": record.platform,
                "point": "中间部分",
                "severity": "critical",
                "metric": "完播率",
                "value": completion,
                "reason": "内容留不住用户",
            })
        elif completion < 0.4:
            drop_points.append({
                "platform": record.platform,
                "point": "中间部分",
                "severity": "medium",
                "metric": "完播率",
                "value": completion,
                "reason": "完播率偏低",
            })

        return drop_points

    def _find_interest_points(self, record: VideoPublishRecord) -> List[Dict[str, Any]]:
        """找到产生兴趣的点"""
        interest_points = []
        er = self._calc_engagement_rate(record)

        if er > 8:
            interest_points.append({
                "platform": record.platform,
                "point": "整体",
                "type": "high_engagement",
                "metric": "互动率",
                "value": er,
                "reason": "用户高度参与",
            })

        if record.favorites and record.views and record.favorites / record.views > 0.05:
            interest_points.append({
                "platform": record.platform,
                "point": "整体",
                "type": "high_favorite",
                "metric": "收藏率",
                "value": round(record.favorites / record.views * 100, 2),
                "reason": "内容有收藏价值",
            })

        if record.comments and record.views and record.comments / record.views > 0.02:
            interest_points.append({
                "platform": record.platform,
                "point": "整体",
                "type": "high_comment",
                "metric": "评论率",
                "value": round(record.comments / record.views * 100, 2),
                "reason": "引发用户讨论",
            })

        return interest_points

    def _find_conversion_points(self, record: VideoPublishRecord) -> List[Dict[str, Any]]:
        """找到转化点"""
        conversion_points = []

        if record.conversion_rate and record.conversion_rate > 0.02:
            conversion_points.append({
                "platform": record.platform,
                "point": "整体",
                "type": "high_conversion",
                "metric": "转化率",
                "value": record.conversion_rate,
                "reason": "转化效果优秀",
            })

        if record.gmv and record.gmv > 5000:
            conversion_points.append({
                "platform": record.platform,
                "point": "整体",
                "type": "high_gmv",
                "metric": "GMV",
                "value": record.gmv,
                "reason": "商业价值高",
            })

        return conversion_points

    def _summarize_overall(self, platform_analyses: List[Dict]) -> Dict[str, Any]:
        """汇总多平台表现"""
        total_views = sum(p["views"] or 0 for p in platform_analyses)
        total_engagement = sum(
            (p["likes"] or 0) + (p["comments"] or 0) + (p["shares"] or 0)
            for p in platform_analyses
        )
        avg_completion = sum(p["completion_rate"] or 0 for p in platform_analyses) / len(platform_analyses) if platform_analyses else 0
        total_gmv = sum(p["gmv"] or 0 for p in platform_analyses)

        return {
            "total_views": total_views,
            "total_engagement": total_engagement,
            "avg_completion_rate": round(avg_completion, 4),
            "total_gmv": total_gmv,
            "platform_count": len(platform_analyses),
        }

    def compare_with_prediction(self, video_id: int) -> Dict[str, Any]:
        """对比预测与实际表现"""
        video = self.db.query(VideoMasterContent).filter(VideoMasterContent.id == video_id).first()
        if not video:
            return {"success": False, "error": "视频不存在"}

        predicted = {
            "completion_rate": video.predicted_completion_rate or 0,
            "conversion_rate": video.predicted_conversion_rate or 0,
        }

        actual = self.analyze_video_performance(video_id)
        if not actual["success"]:
            return actual

        actual_completion = actual["overall_performance"]["avg_completion_rate"]

        report = {
            "video_id": video_id,
            "predicted": predicted,
            "actual": {
                "completion_rate": actual_completion,
            },
            "gap": {
                "completion_rate": round(actual_completion - predicted["completion_rate"], 4),
            },
            "accuracy": "high" if abs(actual_completion - predicted["completion_rate"]) < 0.1 else "low",
        }

        return {"success": True, **report}
