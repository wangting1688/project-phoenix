"""
Growth Scientist Agent - 增长科学Agent

TASK-016.3B.5：AI Growth Decision Graph

核心职责：
1. 从大量视频表现数据中寻找规律
2. 发现 "内容 × 主播 × 平台 × 阶段" 之间的因果关系
3. 生成 Growth Insight 并存储到知识库
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session
from collections import Counter

from app.core.database import SessionLocal
from app.models.video_performance import VideoPublishRecord, VideoMasterContent
from app.models.video_edit_plan import VideoEditPlan
from app.models.video_production import GrowthDecisionMemory, GrowthFailureMemory


class GrowthScientistAgent:
    """增长科学Agent"""

    MIN_SAMPLE_SIZE = 10
    SUCCESS_THRESHOLD = {"views": 50000, "engagement_rate": 5.0, "completion_rate": 0.4}

    def __init__(self):
        self.db = SessionLocal()

    def close(self):
        self.db.close()

    def discover_patterns(self, user_id: int, time_range_days: int = 90) -> Dict[str, Any]:
        """发现增长规律"""
        from datetime import datetime, timedelta

        start_date = datetime.now() - timedelta(days=time_range_days)

        videos = self.db.query(VideoMasterContent).filter(
            VideoMasterContent.user_id == user_id,
            VideoMasterContent.created_at >= start_date
        ).all()

        if len(videos) < self.MIN_SAMPLE_SIZE:
            return {"success": False, "error": f"样本不足，需要至少{self.MIN_SAMPLE_SIZE}条，当前{len(videos)}条"}

        patterns = {
            "content_patterns": self._analyze_content_patterns(videos),
            "creator_patterns": self._analyze_creator_patterns(videos),
            "platform_patterns": self._analyze_platform_patterns(videos),
            "timing_patterns": self._analyze_timing_patterns(videos),
        }

        insights = self._generate_insights(patterns)
        self._save_decision_memories(user_id, insights)

        return {
            "success": True,
            "sample_size": len(videos),
            "patterns": patterns,
            "insights": insights,
        }

    def _analyze_content_patterns(self, videos: List[VideoMasterContent]) -> List[Dict[str, Any]]:
        """分析内容结构规律"""
        successful_videos = [v for v in videos if self._is_successful(v)]
        failed_videos = [v for v in videos if not self._is_successful(v)]

        patterns = []

        success_templates = Counter(v.template_type for v in successful_videos if v.template_type)
        failed_templates = Counter(v.template_type for v in failed_videos if v.template_type)

        for template, success_count in success_templates.most_common(5):
            failed_count = failed_templates.get(template, 0)
            total = success_count + failed_count
            if total >= 3:
                rate = success_count / total
                patterns.append({
                    "type": "template",
                    "value": template,
                    "success_rate": round(rate, 2),
                    "success_count": success_count,
                    "total_count": total,
                })

        success_products = Counter(v.product_category for v in successful_videos if v.product_category)
        for product, count in success_products.most_common(5):
            patterns.append({
                "type": "product",
                "value": product,
                "success_count": count,
            })

        return patterns

    def _analyze_creator_patterns(self, videos: List[VideoMasterContent]) -> List[Dict[str, Any]]:
        """分析主播规律"""
        patterns = []

        creator_groups = {}
        for v in videos:
            creator_id = getattr(v, "creator_id", None)
            if creator_id:
                if creator_id not in creator_groups:
                    creator_groups[creator_id] = {"total": 0, "success": 0}
                creator_groups[creator_id]["total"] += 1
                if self._is_successful(v):
                    creator_groups[creator_id]["success"] += 1

        for creator_id, stats in creator_groups.items():
            if stats["total"] >= 3:
                rate = stats["success"] / stats["total"]
                patterns.append({
                    "creator_id": creator_id,
                    "success_rate": round(rate, 2),
                    "total_videos": stats["total"],
                })

        return sorted(patterns, key=lambda x: x["success_rate"], reverse=True)[:10]

    def _analyze_platform_patterns(self, videos: List[VideoMasterContent]) -> List[Dict[str, Any]]:
        """分析平台规律"""
        patterns = []

        platform_groups = {}
        for v in videos:
            records = self.db.query(VideoPublishRecord).filter(
                VideoPublishRecord.video_master_id == v.id
            ).all()

            for r in records:
                platform = r.platform
                if platform not in platform_groups:
                    platform_groups[platform] = {"total": 0, "success": 0, "avg_views": 0}
                platform_groups[platform]["total"] += 1
                platform_groups[platform]["avg_views"] += (r.views or 0)
                if self._is_successful_by_record(r):
                    platform_groups[platform]["success"] += 1

        for platform, stats in platform_groups.items():
            if stats["total"] >= 3:
                rate = stats["success"] / stats["total"]
                avg_views = stats["avg_views"] / stats["total"]
                patterns.append({
                    "platform": platform,
                    "success_rate": round(rate, 2),
                    "avg_views": round(avg_views),
                    "total_videos": stats["total"],
                })

        return sorted(patterns, key=lambda x: x["success_rate"], reverse=True)

    def _analyze_timing_patterns(self, videos: List[VideoMasterContent]) -> List[Dict[str, Any]]:
        """分析时间规律"""
        patterns = []
        hour_groups = {}

        for v in videos:
            records = self.db.query(VideoPublishRecord).filter(
                VideoPublishRecord.video_master_id == v.id
            ).all()

            for r in records:
                if r.published_at:
                    hour = r.published_at.hour
                    if hour not in hour_groups:
                        hour_groups[hour] = {"total": 0, "success": 0, "avg_views": 0}
                    hour_groups[hour]["total"] += 1
                    hour_groups[hour]["avg_views"] += (r.views or 0)
                    if self._is_successful_by_record(r):
                        hour_groups[hour]["success"] += 1

        for hour, stats in hour_groups.items():
            if stats["total"] >= 3:
                rate = stats["success"] / stats["total"]
                avg_views = stats["avg_views"] / stats["total"]
                patterns.append({
                    "hour": hour,
                    "success_rate": round(rate, 2),
                    "avg_views": round(avg_views),
                    "total_videos": stats["total"],
                })

        return sorted(patterns, key=lambda x: x["success_rate"], reverse=True)[:5]

    def _generate_insights(self, patterns: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成增长洞察"""
        insights = []

        for pattern in patterns.get("content_patterns", []):
            if pattern.get("success_rate", 0) > 0.6:
                insights.append({
                    "type": "content",
                    "pattern": pattern,
                    "conclusion": f"{pattern['value']}类型内容成功率{pattern['success_rate']}",
                    "confidence": min(0.9, pattern["success_rate"]),
                })

        for pattern in patterns.get("platform_patterns", []):
            if pattern.get("success_rate", 0) > 0.5:
                insights.append({
                    "type": "platform",
                    "pattern": pattern,
                    "conclusion": f"在{pattern['platform']}平台发布成功率{pattern['success_rate']}",
                    "confidence": min(0.85, pattern["success_rate"]),
                })

        for pattern in patterns.get("timing_patterns", []):
            if pattern.get("success_rate", 0) > 0.5:
                insights.append({
                    "type": "timing",
                    "pattern": pattern,
                    "conclusion": f"{pattern['hour']}点发布成功率{pattern['success_rate']}",
                    "confidence": min(0.8, pattern["success_rate"]),
                })

        return insights

    def _save_decision_memories(self, user_id: int, insights: List[Dict[str, Any]]):
        """保存决策记忆"""
        for insight in insights:
            memory = GrowthDecisionMemory(
                user_id=user_id,
                insight_type=insight["type"],
                conditions=insight["pattern"],
                conclusion=insight["conclusion"],
                confidence_score=insight["confidence"],
                usage_count=0,
            )
            self.db.add(memory)

        self.db.commit()

    def analyze_failures(self, user_id: int, time_range_days: int = 90) -> Dict[str, Any]:
        """分析失败经验"""
        from datetime import datetime, timedelta

        start_date = datetime.now() - timedelta(days=time_range_days)

        videos = self.db.query(VideoMasterContent).filter(
            VideoMasterContent.user_id == user_id,
            VideoMasterContent.created_at >= start_date
        ).all()

        failures = []
        for v in videos:
            if not self._is_successful(v):
                records = self.db.query(VideoPublishRecord).filter(
                    VideoPublishRecord.video_master_id == v.id
                ).all()

                for r in records:
                    failure = self._classify_failure(v, r)
                    if failure:
                        failures.append(failure)

        if not failures:
            return {"success": True, "failure_count": 0, "patterns": []}

        failure_types = Counter(f["failure_type"] for f in failures)

        patterns = []
        for ftype, count in failure_types.most_common(5):
            related = [f for f in failures if f["failure_type"] == ftype]
            patterns.append({
                "failure_type": ftype,
                "count": count,
                "lesson": related[0]["lesson"] if related else "",
            })

        self._save_failure_memories(user_id, patterns)

        return {
            "success": True,
            "failure_count": len(failures),
            "patterns": patterns,
        }

    def _classify_failure(self, video: VideoMasterContent, record: VideoPublishRecord) -> Dict[str, Any]:
        """分类失败原因"""
        retention = record.first_3_second_retention or 0
        completion = record.completion_rate or 0
        views = record.views or 0

        if views < 1000:
            return {
                "failure_type": "low_distribution",
                "lesson": "内容未被平台推荐，可能Hook不够强或标签不精准",
                "platform": record.platform,
            }

        if retention < 0.3:
            return {
                "failure_type": "hook_failure",
                "lesson": "前3秒留存极低，需要重新设计开头",
                "platform": record.platform,
            }

        if completion < 0.15:
            return {
                "failure_type": "retention_failure",
                "lesson": "用户快速流失，中间内容缺乏吸引力",
                "platform": record.platform,
            }

        if views > 10000 and record.conversion_rate and record.conversion_rate < 0.005:
            return {
                "failure_type": "conversion_failure",
                "lesson": "有流量但无转化，CTA或信任背书不足",
                "platform": record.platform,
            }

        return None

    def _save_failure_memories(self, user_id: int, patterns: List[Dict[str, Any]]):
        """保存失败记忆"""
        for pattern in patterns:
            memory = GrowthFailureMemory(
                user_id=user_id,
                failure_type=pattern["failure_type"],
                lesson=pattern["lesson"],
                occurrence_count=pattern["count"],
                confidence_score=0.6,
            )
            self.db.add(memory)

        self.db.commit()

    def _is_successful(self, video: VideoMasterContent) -> bool:
        """判断视频是否成功"""
        records = self.db.query(VideoPublishRecord).filter(
            VideoPublishRecord.video_master_id == video.id
        ).all()

        if not records:
            return False

        total_views = sum(r.views or 0 for r in records)
        avg_completion = sum(r.completion_rate or 0 for r in records) / len(records)

        return total_views >= self.SUCCESS_THRESHOLD["views"] and avg_completion >= self.SUCCESS_THRESHOLD["completion_rate"]

    def _is_successful_by_record(self, record: VideoPublishRecord) -> bool:
        """通过记录判断成功"""
        views = record.views or 0
        completion = record.completion_rate or 0
        er = ((record.likes or 0) + (record.comments or 0) + (record.shares or 0)) / views * 100 if views else 0

        return views >= self.SUCCESS_THRESHOLD["views"] and er >= self.SUCCESS_THRESHOLD["engagement_rate"]
