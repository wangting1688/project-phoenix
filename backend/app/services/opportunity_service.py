from typing import Dict, Any, List, Optional
import random
from datetime import datetime, timedelta

from app.core.database import SessionLocal
from app.models import ContentOpportunity, CreatorProfile, CreatorAction
from app.services.ai_service import AIService
from app.services.prompt_service import PromptService


class OpportunityService:
    """内容机会服务 - AI内容中心核心"""
    
    SCORE_WEIGHTS = {
        "trend": 0.30,
        "consult": 0.35,
        "match": 0.25,
        "original": 0.10,
    }

    def __init__(self):
        self.db = SessionLocal()
        self.ai_service = AIService()
        self.prompt_service = PromptService()

    def get_recommendations(self, user_id: int, category: str, count: int = 5) -> List[Dict[str, Any]]:
        """获取推荐内容
        
        Categories:
        - A: 最近最火 (trending)
        - B: 咨询潜力最高 (consultation)
        - C: 最适合你的 (personal)
        - D: 新趋势 (emerging)
        - E: 历史爆款 (historical)
        """
        if category == "A":
            return self._get_trending(count)
        elif category == "B":
            return self._get_top_consultation(count)
        elif category == "C":
            return self._get_personal_recommendations(user_id, count)
        elif category == "D":
            return self._get_emerging(count)
        elif category == "E":
            return self._get_historical_best(count)
        else:
            return self._get_all_categories(user_id, count)

    def _get_trending(self, count: int) -> List[Dict[str, Any]]:
        """A: 最近最火 - 热点分数最高"""
        opportunities = self.db.query(ContentOpportunity).filter(
            ContentOpportunity.status == "active"
        ).order_by(ContentOpportunity.trend_score.desc()).limit(count).all()
        
        if not opportunities:
            return self._generate_mock_opportunities("trending", count)
        
        return [self._format_opportunity(o) for o in opportunities]

    def _get_top_consultation(self, count: int) -> List[Dict[str, Any]]:
        """B: 咨询潜力最高"""
        opportunities = self.db.query(ContentOpportunity).filter(
            ContentOpportunity.status == "active"
        ).order_by(ContentOpportunity.consult_score.desc()).limit(count).all()
        
        if not opportunities:
            return self._generate_mock_opportunities("consultation", count)
        
        return [self._format_opportunity(o) for o in opportunities]

    def _get_personal_recommendations(self, user_id: int, count: int) -> List[Dict[str, Any]]:
        """C: 最适合你的 - 基于用户画像"""
        profile = self.db.query(CreatorProfile).filter(
            CreatorProfile.user_id == user_id
        ).first()
        
        opportunities = self.db.query(ContentOpportunity).filter(
            ContentOpportunity.status == "active"
        ).order_by(ContentOpportunity.creator_match.desc()).limit(count).all()
        
        if not opportunities:
            return self._generate_mock_opportunities("personal", count)
        
        return [self._format_opportunity(o) for o in opportunities]

    def _get_emerging(self, count: int) -> List[Dict[str, Any]]:
        """D: 新趋势 - 新创建的机会"""
        recent_time = datetime.utcnow() - timedelta(hours=24)
        opportunities = self.db.query(ContentOpportunity).filter(
            ContentOpportunity.status == "active",
            ContentOpportunity.created_at >= recent_time
        ).order_by(ContentOpportunity.created_at.desc()).limit(count).all()
        
        if not opportunities:
            return self._generate_mock_opportunities("emerging", count)
        
        return [self._format_opportunity(o) for o in opportunities]

    def _get_historical_best(self, count: int) -> List[Dict[str, Any]]:
        """E: 历史爆款 - 综合评分最高"""
        opportunities = self.db.query(ContentOpportunity).filter(
            ContentOpportunity.status == "active"
        ).order_by(ContentOpportunity.final_score.desc()).limit(count).all()
        
        if not opportunities:
            return self._generate_mock_opportunities("historical", count)
        
        return [self._format_opportunity(o) for o in opportunities]

    def _get_all_categories(self, user_id: int, count: int) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有分类"""
        return {
            "A": self._get_trending(count),
            "B": self._get_top_consultation(count),
            "C": self._get_personal_recommendations(user_id, count),
            "D": self._get_emerging(count),
            "E": self._get_historical_best(count),
        }

    def calculate_final_score(self, trend: int, consult: int, match: int, original: int) -> float:
        """计算最终评分
        
        公式：热点30% + 咨询潜力35% + 账号匹配25% + 原创度10%
        """
        return round(
            trend * self.SCORE_WEIGHTS["trend"] +
            consult * self.SCORE_WEIGHTS["consult"] +
            match * self.SCORE_WEIGHTS["match"] +
            original * self.SCORE_WEIGHTS["original"],
            1
        )

    def get_opportunity_detail(self, opportunity_id: int, user_id: int = None) -> Optional[Dict[str, Any]]:
        """获取内容机会详情"""
        opportunity = self.db.query(ContentOpportunity).filter(
            ContentOpportunity.id == opportunity_id
        ).first()
        
        if not opportunity:
            return None
        
        return self._format_opportunity_detail(opportunity, user_id)

    def refresh_recommendations(self, user_id: int, category: str, count: int = 5) -> List[Dict[str, Any]]:
        """换一批 - 重新推荐"""
        self._log_refresh_action(user_id, category)
        return self.get_recommendations(user_id, category, count)

    def _format_opportunity(self, o: ContentOpportunity) -> Dict[str, Any]:
        """格式化输出"""
        return {
            "id": o.id,
            "title": o.title,
            "category": o.category,
            "opening": o.opening,
            "summary": o.summary,
            "trend_score": o.trend_score,
            "consult_score": o.consult_score,
            "creator_match": o.creator_match,
            "original_score": o.original_score,
            "final_score": o.final_score,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }

    def _format_opportunity_detail(self, o: ContentOpportunity, user_id: int = None) -> Dict[str, Any]:
        """格式化详情"""
        detail = self._format_opportunity(o)
        detail.update({
            "pain_point": o.pain_point,
            "recommend_reason": o.recommend_reason,
            "subcategory": o.subcategory,
            "source": o.source,
        })
        return detail

    def _log_refresh_action(self, user_id: int, category: str):
        """记录换一批行为"""
        action = CreatorAction(
            user_id=user_id,
            action_type="refresh_recommendations",
            target_type="content_opportunity",
            metadata={"category": category}
        )
        self.db.add(action)
        self.db.commit()

    def _generate_mock_opportunities(self, category: str, count: int) -> List[Dict[str, Any]]:
        """生成模拟数据（开发阶段）"""
        mock_titles = {
            "trending": [
                "为什么很多人每天睡够8小时，第二天还是没精神？",
                "肠道健康影响全身，这三个信号要注意",
                "中年女性必看的养生误区",
                "30岁后代谢变慢？这样调整最有效",
                "压力大会导致哪些健康问题？",
            ],
            "consultation": [
                "失眠困扰？这几个方法帮你改善睡眠质量",
                "肠胃不适的日常调理建议",
                "女性荷尔蒙失衡的表现和调理方法",
                "慢性疲劳综合征的自我检测与改善",
                "免疫力低下的信号和提升方法",
            ],
            "personal": [
                "根据您的账号画像，这类内容最适合",
                "结合您的粉丝特征推荐",
                "匹配您擅长领域的选题",
                "您的历史表现最佳的类型",
                "您的粉丝最感兴趣的话题",
            ],
            "emerging": [
                "新发现的健康趋势：间歇性断食",
                "最近开始火的养生方式",
                "新兴的健康管理理念",
                "刚刚被讨论的话题",
                "新话题新角度",
            ],
            "historical": [
                "过去30天效果最好的选题",
                "高转化率内容类型",
                "爆款案例分析",
                "成功案例复刻建议",
                "历史最佳表现内容",
            ],
        }
        
        titles = mock_titles.get(category, mock_titles["trending"])
        results = []
        
        for i, title in enumerate(titles[:count]):
            trend_score = random.randint(70, 95)
            consult_score = random.randint(80, 98)
            match_score = random.randint(60, 90)
            original_score = random.randint(75, 95)
            
            results.append({
                "id": i + 1,
                "title": title,
                "category": "健康知识",
                "opening": f"大家都知道{title.split('？')[0]}，但是很少有人知道真正的原因...",
                "summary": f"本期内容将深入解析{title}",
                "trend_score": trend_score,
                "consult_score": consult_score,
                "creator_match": match_score,
                "original_score": original_score,
                "final_score": self.calculate_final_score(trend_score, consult_score, match_score, original_score),
                "created_at": datetime.utcnow().isoformat(),
            })
        
        return results

    def close(self):
        self.db.close()
        self.prompt_service.close()