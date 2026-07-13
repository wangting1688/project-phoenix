import random
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.models import (
    User, CreatorProfile, ContentTopic, SuccessCase,
    RecommendationLog, Footage,
)


class IntelligenceEngine:
    """内容智能引擎 - A-E推荐系统"""

    # 推荐评分权重
    TREND_WEIGHT = 0.30
    CONSULT_WEIGHT = 0.30
    CREATOR_MATCH_WEIGHT = 0.25
    HISTORY_WEIGHT = 0.15

    DEFAULT_TOPICS = [
        {"title": "睡眠不好怎么办", "category": "健康知识", "sub_tags": ["睡眠", "压力"]},
        {"title": "肠胃不好怎么调理", "category": "健康知识", "sub_tags": ["肠道", "营养"]},
        {"title": "更年期怎么调理", "category": "女性健康", "sub_tags": ["更年期", "荷尔蒙"]},
        {"title": "三伏天怎么养生", "category": "养生", "sub_tags": ["夏季", "养生"]},
        {"title": "气血不足怎么补", "category": "健康知识", "sub_tags": ["气血", "营养"]},
        {"title": "焦虑情绪怎么缓解", "category": "情绪健康", "sub_tags": ["焦虑", "压力"]},
        {"title": "中年女性怎么抗衰", "category": "美丽管理", "sub_tags": ["抗衰", "女性"]},
        {"title": "湿气重怎么调理", "category": "养生", "sub_tags": ["湿气", "中医"]},
    ]

    def get_recommendations(self, db: Session, user_id: int) -> List[Dict[str, Any]]:
        """生成A-E五级推荐"""
        profile = db.query(CreatorProfile).filter(
            CreatorProfile.user_id == user_id
        ).first()

        # 优先使用数据库中的主题，不够用默认主题补充
        topics = db.query(ContentTopic).filter(
            ContentTopic.status == "active"
        ).limit(20).all()

        topic_data = []
        for t in topics:
            topic_data.append({
                "title": t.title,
                "category": t.category,
                "sub_tags": t.sub_tags or [],
                "trend_score": t.trend_score,
                "consult_score": t.consultation_score,
            })

        if len(topic_data) < 5:
            for dt in self.DEFAULT_TOPICS:
                if not any(d["title"] == dt["title"] for d in topic_data):
                    topic_data.append({
                        **dt,
                        "trend_score": random.randint(60, 95),
                        "consult_score": random.randint(60, 95),
                    })

        recommendations = []
        levels = ["A", "B", "C", "D", "E"]
        reasons_map = {
            "A": "近期热度飙升，适合快速跟进热点",
            "B": "咨询转化率最高，容易引发私信",
            "C": "最匹配你的风格和粉丝画像",
            "D": "新趋势话题，有增长潜力",
            "E": "你历史表现最好的内容方向",
        }

        for i, topic in enumerate(topic_data[:5]):
            level = levels[i]
            score = self._calculate_score(topic, profile, user_id, db)

            reason = reasons_map[level]
            if profile and profile.good_topics:
                tags = topic.get("sub_tags", [])
                if any(t in (profile.good_topics or []) for t in tags):
                    reason = f"你的粉丝对{tags[0] if tags else '该主题'}话题互动率最高"

            rec = {
                "level": level,
                "title": topic["title"],
                "category": topic["category"],
                "reason": reason,
                "score": round(score, 1),
                "topic": topic["title"],
            }
            recommendations.append(rec)

            log = RecommendationLog(
                user_id=user_id,
                level=level,
                score=score,
                reason=reason,
                selected=0,
            )
            db.add(log)

        db.commit()
        return recommendations

    def _calculate_score(
        self, topic: Dict, profile: Any, user_id: int, db: Session
    ) -> float:
        """计算推荐评分"""
        trend = topic.get("trend_score", 50)
        consult = topic.get("consult_score", 50)

        creator_match = 50
        if profile:
            tags = topic.get("sub_tags", [])
            good = profile.good_topics or []
            matches = sum(1 for t in tags if t in good)
            creator_match = min(100, 50 + matches * 20)

        history_score = 50
        recent_projects = db.query(RecommendationLog).filter(
            RecommendationLog.user_id == user_id,
            RecommendationLog.selected == 1
        ).count()
        if recent_projects > 0:
            history_score = min(100, 50 + recent_projects * 5)

        score = (
            trend * self.TREND_WEIGHT
            + consult * self.CONSULT_WEIGHT
            + creator_match * self.CREATOR_MATCH_WEIGHT
            + history_score * self.HISTORY_WEIGHT
        )
        return score

    def get_or_create_profile(self, db: Session, user_id: int) -> CreatorProfile:
        """获取或创建主播画像"""
        profile = db.query(CreatorProfile).filter(
            CreatorProfile.user_id == user_id
        ).first()

        if not profile:
            profile = CreatorProfile(
                user_id=user_id,
                style="温暖陪伴型",
                speech_speed="medium",
                good_topics=["睡眠", "养生", "女性健康"],
                overall_score=50.0,
            )
            db.add(profile)
            db.commit()
            db.refresh(profile)

        return profile

    def update_profile_from_selection(self, db: Session, user_id: int, topic: str):
        """根据主播选择更新画像"""
        profile = self.get_or_create_profile(db, user_id)

        good_topics = profile.good_topics or []
        if topic not in good_topics:
            good_topics.append(topic)
            profile.good_topics = good_topics

        logs = db.query(RecommendationLog).filter(
            RecommendationLog.user_id == user_id,
        ).order_by(RecommendationLog.created_at.desc()).first()

        if logs:
            logs.selected = 1
            db.commit()


intelligence_engine = IntelligenceEngine()
