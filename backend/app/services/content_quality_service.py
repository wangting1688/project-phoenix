"""
AI内容质量控制服务

整合四大审核Agent，对内容进行全面质量审核。
大健康领域内容需要特殊审核标准：
- 健康合规（不涉及医疗违规）
- 营销自然度（不像硬广告）
- 爆款质量（开头、节奏、互动）
- 咨询转化（自然引导私信）
"""

from typing import Dict, Any, Optional, List
from app.core.database import SessionLocal
from app.models import ContentReview, Content, Script, ContentOpportunity
from app.services.quality_agents import (
    HealthComplianceAgent,
    MarketingRiskAgent,
    ViralQualityAgent,
    ConversionAgent,
)


class ContentQualityService:
    """AI内容质量控制服务"""

    def __init__(self):
        self.db = SessionLocal()
        self.health_agent = HealthComplianceAgent()
        self.marketing_agent = MarketingRiskAgent()
        self.viral_agent = ViralQualityAgent()
        self.conversion_agent = ConversionAgent()

    def review_content(
        self,
        user_id: int,
        content_type: str,
        content_id: int,
        content_text: str,
    ) -> ContentReview:
        """
        对内容进行全面审核

        Args:
            user_id: 用户ID
            content_type: 内容类型（opportunity/script/video）
            content_id: 内容ID
            content_text: 内容文本

        Returns:
            ContentReview: 审核结果
        """

        # 1. 健康合规审核
        health_result = self.health_agent.analyze(content_text)

        # 2. 营销自然度审核
        marketing_result = self.marketing_agent.analyze(content_text)

        # 3. 爆款质量审核
        viral_result = self.viral_agent.analyze(content_text)

        # 4. 咨询转化审核
        conversion_result = self.conversion_agent.analyze(content_text)

        # 5. 计算原创度（基于内容相似度，这里简化处理）
        originality_score = self._calculate_originality(content_text)

        # 6. 综合评分（加权计算）
        final_score = self._calculate_final_score(
            health_result["score"],
            marketing_result["score"],
            viral_result["score"],
            conversion_result["score"],
            originality_score,
        )

        # 7. 确定风险等级
        risk_level = self._determine_risk_level(
            health_result["risk_level"],
            marketing_result["risk_level"],
        )

        # 8. 汇总建议
        suggestions = self._collect_suggestions(
            health_result,
            marketing_result,
            viral_result,
            conversion_result,
        )

        # 9. 生成自动修复建议
        auto_fixes = self._generate_auto_fixes(content_text, suggestions)

        # 10. 创建审核记录
        review = ContentReview(
            user_id=user_id,
            content_type=content_type,
            content_id=content_id,
            health_score=health_result["score"],
            marketing_score=marketing_result["score"],
            viral_score=viral_result["score"],
            conversion_score=conversion_result["score"],
            originality_score=originality_score,
            final_score=final_score,
            risk_level=risk_level,
            health_analysis=health_result,
            marketing_analysis=marketing_result,
            viral_analysis=viral_result,
            conversion_analysis=conversion_result,
            suggestions=suggestions,
            auto_fixes=auto_fixes,
            status="completed",
        )

        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)

        return review

    def get_review_result(self, review_id: int) -> Optional[Dict[str, Any]]:
        """获取审核结果"""
        review = self.db.query(ContentReview).filter(
            ContentReview.id == review_id
        ).first()

        if not review:
            return None

        return self._format_review_result(review)

    def get_review_by_content(
        self,
        content_type: str,
        content_id: int,
    ) -> Optional[Dict[str, Any]]:
        """根据内容获取最新审核结果"""
        review = self.db.query(ContentReview).filter(
            ContentReview.content_type == content_type,
            ContentReview.content_id == content_id,
        ).order_by(ContentReview.created_at.desc()).first()

        if not review:
            return None

        return self._format_review_result(review)

    def optimize_content(
        self,
        content_type: str,
        content_id: int,
        content_text: str,
    ) -> Dict[str, Any]:
        """
        基于审核结果优化内容

        Returns:
            优化后的内容和建议
        """
        review = self.db.query(ContentReview).filter(
            ContentReview.content_type == content_type,
            ContentReview.content_id == content_id,
        ).order_by(ContentReview.created_at.desc()).first()

        if not review:
            # 如果没有审核记录，先审核
            user_id = 1  # 默认用户
            review = self.review_content(user_id, content_type, content_id, content_text)

        optimized_text = content_text
        changes = []

        # 应用自动修复
        if review.auto_fixes:
            for fix in review.auto_fixes:
                if fix.get("type") == "replace":
                    old_text = fix.get("old", "")
                    new_text = fix.get("new", "")
                    if old_text in optimized_text:
                        optimized_text = optimized_text.replace(old_text, new_text)
                        changes.append(fix)

        return {
            "original_text": content_text,
            "optimized_text": optimized_text,
            "changes": changes,
            "review": self._format_review_result(review),
        }

    def _calculate_originality(self, content: str) -> int:
        """计算原创度（简化版本）"""
        # 实际应该使用AI模型计算相似度
        # 这里基于内容长度和特征简化计算
        base_score = 85

        # 有独特表达加5分
        if any(word in content for word in ["我发现", "我试过", "我的经验"]):
            base_score += 5

        # 有引用减分
        if "转载" in content or "引用" in content:
            base_score -= 10

        return min(100, max(0, base_score))

    def _calculate_final_score(
        self,
        health: int,
        marketing: int,
        viral: int,
        conversion: int,
        originality: int,
    ) -> int:
        """计算综合评分（加权）"""
        # 大健康领域，健康合规权重最高
        weights = {
            "health": 0.30,      # 健康合规30%
            "marketing": 0.20,   # 营销自然度20%
            "viral": 0.25,       # 爆款质量25%
            "conversion": 0.15,  # 咨询转化15%
            "originality": 0.10, # 原创度10%
        }

        score = (
            health * weights["health"] +
            marketing * weights["marketing"] +
            viral * weights["viral"] +
            conversion * weights["conversion"] +
            originality * weights["originality"]
        )

        return int(score)

    def _determine_risk_level(self, health_risk: str, marketing_risk: str) -> str:
        """确定综合风险等级"""
        risk_order = ["safe", "low", "medium", "high", "danger"]

        health_level = risk_order.index(health_risk) if health_risk in risk_order else 0
        marketing_level = risk_order.index(marketing_risk) if marketing_risk in risk_order else 0

        # 取最高风险等级
        max_level = max(health_level, marketing_level)

        return risk_order[max_level]

    def _collect_suggestions(self, *results) -> List[str]:
        """汇总所有建议"""
        suggestions = []

        for result in results:
            if "suggestions" in result:
                suggestions.extend(result["suggestions"])

        # 去重
        return list(set(suggestions))

    def _generate_auto_fixes(self, content: str, suggestions: List[str]) -> List[Dict[str, Any]]:
        """生成自动修复建议"""
        fixes = []

        # 基于健康合规建议生成替换
        for keyword, replacement in HealthComplianceAgent.SUGGEST_REPLACEMENTS.items():
            if keyword in content:
                fixes.append({
                    "type": "replace",
                    "old": keyword,
                    "new": replacement,
                    "reason": "健康合规优化",
                })

        return fixes

    def _format_review_result(self, review: ContentReview) -> Dict[str, Any]:
        """格式化审核结果"""
        return {
            "review_id": review.id,
            "content_type": review.content_type,
            "content_id": review.content_id,
            "scores": {
                "health": review.health_score,
                "marketing": review.marketing_score,
                "viral": review.viral_score,
                "conversion": review.conversion_score,
                "originality": review.originality_score,
                "final": review.final_score,
            },
            "risk_level": review.risk_level,
            "analysis": {
                "health": review.health_analysis,
                "marketing": review.marketing_analysis,
                "viral": review.viral_analysis,
                "conversion": review.conversion_analysis,
            },
            "suggestions": review.suggestions,
            "auto_fixes": review.auto_fixes,
            "status": review.status,
            "created_at": review.created_at.isoformat() if review.created_at else None,
        }

    def close(self):
        self.db.close()