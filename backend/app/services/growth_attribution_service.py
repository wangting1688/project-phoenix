"""
Growth Attribution Service - 增长归因服务

TASK-016.3B.5.1：增长归因层

核心职责：
1. 分析视频成功/失败的因素及贡献度
2. 量化各因素对增长的影响
3. 存储归因记录供导演学习
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.video_production import GrowthAttributionRecord
from app.models.video_performance import VideoPublishRecord, VideoMasterContent
from app.models.video_edit_plan import VideoEditPlan


class GrowthAttributionService:
    """增长归因服务"""

    ATTRIBUTION_FACTORS = {
        "hook_pattern": {"weight": 0.35, "description": "开场模式"},
        "creator_fit": {"weight": 0.20, "description": "主播适配"},
        "platform": {"weight": 0.15, "description": "平台匹配"},
        "timing": {"weight": 0.10, "description": "发布时间"},
        "title": {"weight": 0.08, "description": "标题吸引力"},
        "commercial_pressure": {"weight": 0.12, "description": "商业压力"},
    }

    HOOK_PATTERN_SCORES = {
        "反常识冲突": 0.9,
        "个人故事": 0.85,
        "痛点直击": 0.8,
        "知识提醒": 0.6,
        "产品开场": 0.3,
        "平淡叙述": 0.2,
    }

    def __init__(self):
        self.db = SessionLocal()

    def close(self):
        self.db.close()

    def calculate_attribution(self, video_id: int, publish_record_id: int = None) -> Dict[str, Any]:
        """计算增长归因"""
        video = self.db.query(VideoMasterContent).filter(VideoMasterContent.id == video_id).first()
        if not video:
            return {"success": False, "error": "视频不存在"}

        plan = self.db.query(VideoEditPlan).filter(VideoEditPlan.id == video.edit_plan_id).first()

        records = []
        if publish_record_id:
            record = self.db.query(VideoPublishRecord).filter(
                VideoPublishRecord.id == publish_record_id
            ).first()
            if record:
                records.append(record)
        else:
            records = self.db.query(VideoPublishRecord).filter(
                VideoPublishRecord.video_master_id == video_id
            ).all()

        if not records:
            return {"success": False, "error": "无发布记录"}

        success_factors = []
        failure_factors = []

        total_views = sum(r.views or 0 for r in records)
        avg_retention = sum(r.first_3_second_retention or 0 for r in records) / len(records)
        avg_completion = sum(r.completion_rate or 0 for r in records) / len(records)

        is_success = total_views >= 50000 and avg_completion >= 0.3

        hook_factor = self._attribute_hook(plan, records)
        if hook_factor["contribution"] > 0.1:
            success_factors.append(hook_factor)
        else:
            failure_factors.append({
                "factor": "hook_pattern",
                "value": hook_factor["value"],
                "score": hook_factor["contribution"] * 100,
            })

        creator_factor = self._attribute_creator_fit(plan)
        success_factors.append(creator_factor)

        platform_factor = self._attribute_platform(records)
        success_factors.append(platform_factor)

        timing_factor = self._attribute_timing(records)
        success_factors.append(timing_factor)

        commercial_factor = self._attribute_commercial_pressure(plan, is_success)
        if commercial_factor["contribution"] > 0:
            success_factors.append(commercial_factor)
        else:
            failure_factors.append({
                "factor": "commercial_pressure",
                "score": abs(commercial_factor["contribution"]) * 100,
            })

        attribution_record = GrowthAttributionRecord(
            user_id=video.user_id,
            video_id=video_id,
            video_plan_id=video.edit_plan_id,
            platform=records[0].platform if records else None,
            success_factors=success_factors,
            failure_factors=failure_factors if failure_factors else None,
            overall_outcome="success" if is_success else "failure",
            total_contribution=sum(f["contribution"] for f in success_factors),
            confidence_score=self._calculate_confidence(success_factors, records),
        )

        self.db.add(attribution_record)
        self.db.commit()

        return {
            "success": True,
            "video_id": video_id,
            "attribution_id": attribution_record.id,
            "overall_outcome": "success" if is_success else "failure",
            "success_factors": success_factors,
            "failure_factors": failure_factors,
            "total_contribution": round(sum(f["contribution"] for f in success_factors), 2),
            "confidence_score": round(attribution_record.confidence_score, 2),
        }

    def _attribute_hook(self, plan: VideoEditPlan, records: List[VideoPublishRecord]) -> Dict[str, Any]:
        """归因Hook因素"""
        hook_pattern = "平淡叙述"
        if plan:
            script = plan.script_content or ""
            if "不知道" in script[:50] or "秘密" in script[:50]:
                hook_pattern = "知识提醒"
            elif "我" in script[:10] and ("岁" in script[:20] or "发现" in script[:20]):
                hook_pattern = "个人故事"
            elif "很多人" in script[:20] or "困扰" in script[:20]:
                hook_pattern = "痛点直击"
            elif "不要" in script[:20] or "其实" in script[:20]:
                hook_pattern = "反常识冲突"

        base_score = self.HOOK_PATTERN_SCORES.get(hook_pattern, 0.5)

        avg_retention = sum(r.first_3_second_retention or 0 for r in records) / len(records)
        retention_multiplier = 0.5 + avg_retention

        contribution = base_score * retention_multiplier * self.ATTRIBUTION_FACTORS["hook_pattern"]["weight"]

        return {
            "factor": "hook_pattern",
            "value": hook_pattern,
            "description": self.ATTRIBUTION_FACTORS["hook_pattern"]["description"],
            "contribution": round(min(1.0, contribution), 4),
            "details": {
                "base_score": base_score,
                "retention_multiplier": round(retention_multiplier, 2),
            },
        }

    def _attribute_creator_fit(self, plan: VideoEditPlan) -> Dict[str, Any]:
        """归因主播适配"""
        if not plan:
            return {
                "factor": "creator_fit",
                "value": "未知",
                "description": self.ATTRIBUTION_FACTORS["creator_fit"]["description"],
                "contribution": 0.0,
            }

        creator_profile = {
            "age_range": "40-50",
            "style": "温暖",
        }

        content_type = plan.editing_strategy or "standard"

        fit_score = 0.7
        if content_type == "story":
            if creator_profile["style"] in ["温暖", "experienced"]:
                fit_score = 0.9
        elif content_type == "expert":
            if creator_profile["style"] == "professional":
                fit_score = 0.85

        contribution = fit_score * self.ATTRIBUTION_FACTORS["creator_fit"]["weight"]

        return {
            "factor": "creator_fit",
            "value": f"{creator_profile['age_range']}岁{creator_profile['style']}型",
            "description": self.ATTRIBUTION_FACTORS["creator_fit"]["description"],
            "contribution": round(contribution, 4),
        }

    def _attribute_platform(self, records: List[VideoPublishRecord]) -> Dict[str, Any]:
        """归因平台因素"""
        if not records:
            return {"factor": "platform", "value": "未知", "contribution": 0.0}

        platform = records[0].platform
        total_views = sum(r.views or 0 for r in records)

        platform_multiplier = {
            "douyin": 1.0,
            "wechat_video": 0.85,
            "xiaohongshu": 0.9,
            "kuaishou": 0.8,
        }.get(platform, 0.9)

        contribution = platform_multiplier * self.ATTRIBUTION_FACTORS["platform"]["weight"]

        return {
            "factor": "platform",
            "value": platform,
            "description": self.ATTRIBUTION_FACTORS["platform"]["description"],
            "contribution": round(contribution, 4),
        }

    def _attribute_timing(self, records: List[VideoPublishRecord]) -> Dict[str, Any]:
        """归因发布时间"""
        if not records:
            return {"factor": "timing", "value": "未知", "contribution": 0.0}

        hour_distribution = {}
        for r in records:
            if r.published_at:
                hour = r.published_at.hour
                hour_distribution[hour] = hour_distribution.get(hour, 0) + (r.views or 0)

        best_hour = max(hour_distribution.items(), key=lambda x: x[1])[0] if hour_distribution else 20

        peak_hours = {19, 20, 21, 22}
        is_peak = best_hour in peak_hours

        timing_score = 0.9 if is_peak else 0.6

        contribution = timing_score * self.ATTRIBUTION_FACTORS["timing"]["weight"]

        return {
            "factor": "timing",
            "value": f"{best_hour}:00" + ("(高峰期)" if is_peak else ""),
            "description": self.ATTRIBUTION_FACTORS["timing"]["description"],
            "contribution": round(contribution, 4),
        }

    def _attribute_commercial_pressure(self, plan: VideoEditPlan, is_success: bool) -> Dict[str, Any]:
        """归因商业压力"""
        if not plan:
            return {"factor": "commercial_pressure", "value": "未知", "contribution": 0.0}

        script = plan.script_content or ""
        commercial_words = ["产品", "购买", "价格", "优惠", "买", "送"]
        commercial_count = sum(1 for w in commercial_words if w in script)

        pressure_score = min(100, commercial_count * 20)

        if plan.business_stage == "growth":
            if pressure_score < 30:
                contribution = 0.12
            else:
                contribution = -0.1 * (pressure_score / 100)
        else:
            contribution = 0.05 if pressure_score > 30 else 0.0

        return {
            "factor": "commercial_pressure",
            "value": str(pressure_score),
            "description": self.ATTRIBUTION_FACTORS["commercial_pressure"]["description"],
            "contribution": round(contribution, 4),
        }

    def _calculate_confidence(self, factors: List[Dict], records: List[VideoPublishRecord]) -> float:
        """计算置信度"""
        factor_count = len(factors)
        record_count = len(records)

        confidence = 0.5

        if factor_count >= 4:
            confidence += 0.2
        elif factor_count >= 2:
            confidence += 0.1

        if record_count >= 3:
            confidence += 0.15
        elif record_count >= 2:
            confidence += 0.05

        high_contribution = sum(1 for f in factors if f["contribution"] > 0.15)
        if high_contribution >= 2:
            confidence += 0.1

        return min(1.0, confidence)
