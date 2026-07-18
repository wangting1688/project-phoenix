from typing import Dict, Any, List, Optional
import re
from collections import defaultdict

from app.core.database import SessionLocal
from app.models import ContentOpportunity, CreatorProfile, CreatorPreference, ScoringConfig


class RecommendationEngine:
    """推荐引擎 - 负责评分、去重、排序"""

    DEFAULT_WEIGHTS = {
        "trend": 0.30,
        "consult": 0.35,
        "creator": 0.25,
        "original": 0.10,
    }

    def __init__(self, user_id: int = None):
        self.db = SessionLocal()
        self.user_id = user_id
        self.creator_profile = None
        self.creator_preference = None
        if user_id:
            self.creator_profile = self._load_creator_profile()
            self.creator_preference = self._load_creator_preference()
        self.weights = self._get_weights()

    def _get_weights(self) -> Dict[str, float]:
        """获取评分权重（优先用户个性化，其次全局配置，最后默认）"""
        if self.creator_preference and self.creator_preference.score_weights:
            w = self.creator_preference.score_weights
            return {
                "trend": w.get("trend_weight", 30) / 100,
                "consult": w.get("consult_weight", 35) / 100,
                "creator": w.get("creator_weight", 25) / 100,
                "original": w.get("original_weight", 10) / 100,
            }

        config = self.db.query(ScoringConfig).filter(
            ScoringConfig.is_active == 1
        ).first()

        if config:
            return {
                "trend": config.trend_weight / 100,
                "consult": config.consult_weight / 100,
                "creator": config.creator_weight / 100,
                "original": config.original_weight / 100,
            }

        return self.DEFAULT_WEIGHTS

    def _load_creator_profile(self) -> Optional[CreatorProfile]:
        return self.db.query(CreatorProfile).filter(
            CreatorProfile.user_id == self.user_id
        ).first()

    def _load_creator_preference(self) -> Optional[CreatorPreference]:
        return self.db.query(CreatorPreference).filter(
            CreatorPreference.user_id == self.user_id
        ).first()

    def calculate_final_score(self, opportunity: ContentOpportunity) -> float:
        """计算最终评分"""
        creator_match = self._calculate_creator_match(opportunity)
        
        return round(
            opportunity.trend_score * self.weights["trend"] +
            opportunity.consult_score * self.weights["consult"] +
            creator_match * self.weights["creator"] +
            opportunity.original_score * self.weights["original"],
            1
        )

    def _calculate_creator_match(self, opportunity: ContentOpportunity) -> float:
        """计算账号匹配度"""
        if not self.creator_profile:
            return opportunity.creator_match

        score = opportunity.creator_match
        good_topics = self.creator_profile.good_topics or []
        
        if good_topics:
            for topic in good_topics:
                if topic and topic in opportunity.title:
                    score = min(100, score + 10)

        category_weights = {}
        if self.creator_preference and self.creator_preference.category_weights:
            category_weights = self.creator_preference.category_weights

        if opportunity.category in category_weights:
            weight = category_weights[opportunity.category]
            score = score * (0.5 + weight / 100)

        return min(100, max(0, score))

    def get_recommendations_by_category(
        self,
        category: str,
        count: int = 5
    ) -> List[Dict[str, Any]]:
        """按分类获取推荐"""
        all_opportunities = self.db.query(ContentOpportunity).filter(
            ContentOpportunity.status == "active"
        ).all()

        if not all_opportunities:
            return []

        scored = []
        for opp in all_opportunities:
            final_score = self.calculate_final_score(opp)
            scored.append({
                "id": opp.id,
                "title": opp.title,
                "category": opp.category,
                "opening": opp.opening,
                "summary": opp.summary,
                "pain_point": opp.pain_point,
                "recommend_reason": opp.recommend_reason,
                "trend_score": opp.trend_score,
                "consult_score": opp.consult_score,
                "creator_match": self._calculate_creator_match(opp),
                "original_score": opp.original_score,
                "final_score": final_score,
                "source": opp.source,
                "created_at": opp.created_at.isoformat() if opp.created_at else None,
            })

        if category == "A":
            scored.sort(key=lambda x: x["trend_score"], reverse=True)
        elif category == "B":
            scored.sort(key=lambda x: x["consult_score"], reverse=True)
        elif category == "C":
            scored.sort(key=lambda x: x["creator_match"], reverse=True)
        elif category == "D":
            scored.sort(key=lambda x: x["original_score"], reverse=True)
        elif category == "E":
            scored.sort(key=lambda x: x["final_score"], reverse=True)
        else:
            scored.sort(key=lambda x: x["final_score"], reverse=True)

        deduplicated = self._deduplicate(scored)
        return deduplicated[:count]

    def _deduplicate(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """去重 - 同主题最多出现一次"""
        seen_themes = set()
        result = []

        for item in items:
            theme = self._extract_theme(item["title"])
            
            if theme not in seen_themes:
                seen_themes.add(theme)
                result.append(item)

        return result

    def _extract_theme(self, title: str) -> str:
        """提取主题关键词用于去重"""
        theme_keywords = [
            "睡眠", "失眠", "肠道", "肠胃", "养生", "健康", "压力",
            "情绪", "女性", "男性", "中年", "老年", "代谢", "免疫力",
            "疲劳", "内分泌", "荷尔蒙", "营养", "饮食", "运动",
            "皮肤", "美容", "减肥", "塑形", "颈椎", "腰椎",
        ]

        for keyword in theme_keywords:
            if keyword in title:
                return keyword

        words = re.findall(r'[\u4e00-\u9fa5]{2,4}', title)
        return words[0] if words else title[:4]

    def get_all_categories(self, count: int = 5) -> Dict[str, Any]:
        """获取所有分类推荐"""
        return {
            "A": {
                "title": "最近最火 🔥",
                "description": "最近24小时热度增长最快",
                "items": self.get_recommendations_by_category("A", count)
            },
            "B": {
                "title": "咨询潜力最高 💬",
                "description": "最容易引发私信咨询",
                "items": self.get_recommendations_by_category("B", count)
            },
            "C": {
                "title": "最适合你的 ⭐",
                "description": "结合账号画像推荐",
                "items": self.get_recommendations_by_category("C", count)
            },
            "D": {
                "title": "新趋势 🌱",
                "description": "刚开始爆发的话题",
                "items": self.get_recommendations_by_category("D", count)
            },
            "E": {
                "title": "历史爆款 📈",
                "description": "过去30天效果最好的内容",
                "items": self.get_recommendations_by_category("E", count)
            }
        }

    def get_weight_info(self) -> Dict[str, Any]:
        """获取当前权重配置信息"""
        account_type = "通用型"
        if self.creator_profile:
            if self.creator_profile.account_type == "consultation":
                account_type = "咨询型"
            elif self.creator_profile.account_type == "growth":
                account_type = "涨粉型"

        return {
            "account_type": account_type,
            "weights": {
                "trend": int(self.weights["trend"] * 100),
                "consult": int(self.weights["consult"] * 100),
                "creator": int(self.weights["creator"] * 100),
                "original": int(self.weights["original"] * 100),
            },
            "is_customized": self.creator_preference is not None and self.creator_preference.score_weights is not None
        }

    def close(self):
        self.db.close()