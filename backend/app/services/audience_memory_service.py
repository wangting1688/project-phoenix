"""
Audience Memory Service - 用户认知服务

TASK-016.3B.5.3：用户认知层

核心职责：
1. 分析用户群体特征和偏好
2. 提取高频评论关键词
3. 构建用户画像供选题和导演使用
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session
from collections import Counter

from app.core.database import SessionLocal
from app.models.video_production import AudienceGrowthMemory
from app.models.video_performance import VideoPublishRecord


class AudienceMemoryService:
    """用户认知服务"""

    AUDIENCE_SEGMENTS = {
        "middle_age_health_women": {
            "name": "中年健康女性",
            "age_range": "35-55",
            "gender": "female",
        },
        "young_career_women": {
            "name": "年轻职场女性",
            "age_range": "25-35",
            "gender": "female",
        },
        "senior_health_care": {
            "name": "老年健康关注者",
            "age_range": "55+",
            "gender": "mixed",
        },
    }

    PAIN_POINT_KEYWORDS = {
        "睡眠": ["失眠", "睡眠", "睡不着", "入睡", "熬夜"],
        "疲劳": ["疲劳", "累", "乏力", "没精神", "精力"],
        "气色": ["气色", "皮肤", "暗沉", "斑", "黄"],
        "体重": ["体重", "减肥", "胖", "瘦", "身材"],
        "情绪": ["焦虑", "情绪", "压力", "烦躁", "抑郁"],
        "免疫力": ["免疫", "抵抗力", "生病", "感冒"],
    }

    CONTENT_PREFERENCE_KEYWORDS = {
        "story": ["故事", "经历", "真实", "亲身", "我"],
        "expert": ["专家", "研究", "科学", "数据", "证明"],
        "promotion": ["产品", "买", "优惠", "活动", "链接"],
        "knowledge": ["知识", "干货", "技巧", "方法", "教程"],
    }

    def __init__(self):
        self.db = SessionLocal()

    def close(self):
        self.db.close()

    def analyze_audience(self, user_id: int, platform: str = None) -> Dict[str, Any]:
        """分析用户群体"""
        records = self.db.query(VideoPublishRecord).filter(
            VideoPublishRecord.user_id == user_id
        )
        if platform:
            records = records.filter(VideoPublishRecord.platform == platform)

        records = records.all()

        if not records:
            return {"success": False, "error": "无发布记录"}

        pain_points = self._extract_pain_points(records)
        content_preferences = self._extract_content_preferences(records)
        high_frequency_comments = self._extract_high_frequency_comments(records)
        engagement_patterns = self._extract_engagement_patterns(records)

        audience_segment = self._identify_audience_segment(records)

        memory = AudienceGrowthMemory(
            user_id=user_id,
            audience_segment=audience_segment,
            demographic=self.AUDIENCE_SEGMENTS.get(audience_segment, {}),
            pain_points=pain_points,
            content_preferences=content_preferences,
            high_frequency_comments=high_frequency_comments,
            engagement_patterns=engagement_patterns,
            confidence_score=min(0.9, len(records) / 50),
            sample_size=len(records),
            related_platforms=[platform] if platform else ["all"],
        )

        self.db.add(memory)
        self.db.commit()

        return {
            "success": True,
            "audience_segment": audience_segment,
            "segment_info": self.AUDIENCE_SEGMENTS.get(audience_segment, {}),
            "pain_points": pain_points,
            "content_preferences": content_preferences,
            "high_frequency_comments": high_frequency_comments,
            "engagement_patterns": engagement_patterns,
            "sample_size": len(records),
            "confidence_score": round(memory.confidence_score, 2),
        }

    def _extract_pain_points(self, records: List[VideoPublishRecord]) -> List[Dict[str, Any]]:
        """提取痛点"""
        all_comments = []
        for r in records:
            comment_keywords = r.comment_keywords or []
            all_comments.extend(comment_keywords)

        pain_point_counts = {}
        for pain_point, keywords in self.PAIN_POINT_KEYWORDS.items():
            count = sum(1 for c in all_comments if any(k in c for k in keywords))
            if count > 0:
                pain_point_counts[pain_point] = count

        total = sum(pain_point_counts.values())
        if total == 0:
            return []

        sorted_points = sorted(pain_point_counts.items(), key=lambda x: x[1], reverse=True)

        return [{
            "pain_point": point,
            "count": count,
            "ratio": round(count / total, 2),
        } for point, count in sorted_points]

    def _extract_content_preferences(self, records: List[VideoPublishRecord]) -> Dict[str, float]:
        """提取内容偏好"""
        preferences = {}

        all_comments = []
        for r in records:
            comment_keywords = r.comment_keywords or []
            all_comments.extend(comment_keywords)

        for pref_type, keywords in self.CONTENT_PREFERENCE_KEYWORDS.items():
            count = sum(1 for c in all_comments if any(k in c for k in keywords))
            preferences[pref_type] = round(min(1.0, count / max(1, len(all_comments))), 2)

        return preferences

    def _extract_high_frequency_comments(self, records: List[VideoPublishRecord]) -> List[Dict[str, Any]]:
        """提取高频评论"""
        all_comments = []
        for r in records:
            comment_keywords = r.comment_keywords or []
            all_comments.extend(comment_keywords)

        counter = Counter(all_comments)
        top_comments = counter.most_common(10)

        total = sum(counter.values())
        if total == 0:
            return []

        return [{
            "keyword": keyword,
            "count": count,
            "ratio": round(count / total, 3),
        } for keyword, count in top_comments]

    def _extract_engagement_patterns(self, records: List[VideoPublishRecord]) -> Dict[str, Any]:
        """提取互动模式"""
        patterns = {}

        total_views = sum(r.views or 0 for r in records)
        total_comments = sum(r.comments or 0 for r in records)
        total_likes = sum(r.likes or 0 for r in records)
        total_shares = sum(r.shares or 0 for r in records)

        if total_views > 0:
            patterns["comment_rate"] = round(total_comments / total_views * 100, 3)
            patterns["like_rate"] = round(total_likes / total_views * 100, 3)
            patterns["share_rate"] = round(total_shares / total_views * 100, 3)
        else:
            patterns["comment_rate"] = 0.0
            patterns["like_rate"] = 0.0
            patterns["share_rate"] = 0.0

        avg_retention = sum(r.first_3_second_retention or 0 for r in records) / len(records)
        avg_completion = sum(r.completion_rate or 0 for r in records) / len(records)

        patterns["avg_retention"] = round(avg_retention, 4)
        patterns["avg_completion"] = round(avg_completion, 4)

        return patterns

    def _identify_audience_segment(self, records: List[VideoPublishRecord]) -> str:
        """识别用户群体"""
        all_comments = []
        for r in records:
            comment_keywords = r.comment_keywords or []
            all_comments.extend(comment_keywords)

        segment_scores = {}

        for segment, info in self.AUDIENCE_SEGMENTS.items():
            score = 0

            if info["age_range"] == "35-55":
                score += sum(1 for c in all_comments if any(k in c for k in ["40", "45", "50", "55", "中年", "更年期"]))
            elif info["age_range"] == "25-35":
                score += sum(1 for c in all_comments if any(k in c for k in ["25", "30", "35", "职场", "加班"]))
            elif info["age_range"] == "55+":
                score += sum(1 for c in all_comments if any(k in c for k in ["60", "妈妈", "阿姨", "退休"]))

            if info["gender"] == "female":
                score += sum(1 for c in all_comments if any(k in c for k in ["女性", "女人", "姐妹", "妈妈"]))

            segment_scores[segment] = score

        if not segment_scores:
            return "unknown"

        return max(segment_scores.items(), key=lambda x: x[1])[0]

    def get_audience_memory(self, audience_segment: str = None) -> List[Dict[str, Any]]:
        """获取用户认知记忆"""
        query = self.db.query(AudienceGrowthMemory)
        if audience_segment:
            query = query.filter(AudienceGrowthMemory.audience_segment == audience_segment)

        memories = query.order_by(AudienceGrowthMemory.confidence_score.desc()).all()

        return [{
            "id": m.id,
            "audience_segment": m.audience_segment,
            "segment_info": m.demographic,
            "pain_points": m.pain_points,
            "content_preferences": m.content_preferences,
            "high_frequency_comments": m.high_frequency_comments,
            "engagement_patterns": m.engagement_patterns,
            "confidence_score": m.confidence_score,
            "sample_size": m.sample_size,
        } for m in memories]

    def suggest_topics(self, audience_segment: str) -> List[str]:
        """基于用户认知推荐选题"""
        memory = self.db.query(AudienceGrowthMemory).filter(
            AudienceGrowthMemory.audience_segment == audience_segment
        ).order_by(AudienceGrowthMemory.confidence_score.desc()).first()

        if not memory:
            return ["健康生活", "女性保养", "日常护理"]

        topics = []
        pain_points = memory.pain_points or []
        for point in pain_points[:3]:
            topics.append(f"{point['pain_point']}怎么办")
            topics.append(f"如何改善{point['pain_point']}")

        high_comments = memory.high_frequency_comments or []
        for comment in high_comments[:3]:
            topics.append(f"关于{comment['keyword']}的真相")

        return topics[:10]
