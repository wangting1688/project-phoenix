"""
AI导演学习记忆服务

TASK-016.3A.8：AI导演学习记忆层 V2

核心能力：
1. 多平台效果评分
2. 导演经验库学习与积累
3. 导演评分 V3（内容质量40% + 主播适配20% + 平台匹配20% + 历史数据20%）
4. 主播策略画像
5. 平台策略画像
6. Phoenix商业评分权重（GMV35% + 咨询25% + 转化15% + 停留10% + 互动10% + 播放5%）
"""

import random
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple
from app.core.database import SessionLocal
from app.models import (
    VideoMasterContent,
    VideoPublishRecord,
    PlatformPerformanceScore,
    DirectorLearningMemory,
    PlatformStrategyProfile,
    CreatorStrategyProfile,
    VideoEditPlan,
    VideoEditSegment,
    CreatorPerformanceProfile,
    AssetSegment,
    User,
)


class DirectorLearningService:
    """AI导演学习记忆服务"""

    # Phoenix默认商业评分权重（私域电商导向）
    PHOENIX_COMMERCIAL_WEIGHTS = {
        "gmv": 0.35,              # 成交金额 GMV 35%
        "consultation": 0.25,     # 有效咨询人数 25%
        "conversion_rate": 0.15,  # 成交转化率 15%
        "retention": 0.10,        # 用户停留 10%
        "engagement": 0.10,       # 互动 10%
        "views": 0.05,            # 播放 5%
    }

    # 各平台评分权重
    PLATFORM_WEIGHTS = {
        "douyin": {
            "traffic": 0.40,
            "engagement": 0.30,
            "conversion": 0.15,
            "customer_value": 0.15,
        },
        "wechat_video": {
            "traffic": 0.20,
            "engagement": 0.25,
            "conversion": 0.40,
            "customer_value": 0.15,
        },
        "xiaohongshu": {
            "traffic": 0.25,
            "engagement": 0.35,
            "conversion": 0.20,
            "customer_value": 0.20,
        },
        "kuaishou": {
            "traffic": 0.30,
            "engagement": 0.35,
            "conversion": 0.25,
            "customer_value": 0.10,
        },
    }

    # 导演评分 V3 权重
    DIRECTOR_SCORE_V3 = {
        "content_quality": {"weight": 0.40, "max": 40},   # 内容质量 40%
        "creator_fit": {"weight": 0.20, "max": 20},        # 主播适配 20%
        "platform_match": {"weight": 0.20, "max": 20},    # 平台匹配 20%
        "historical_data": {"weight": 0.20, "max": 20},   # 历史经验 20%
    }

    def __init__(self):
        self.db = SessionLocal()

    # ==================== 1. 多平台效果评分 ====================

    def calculate_platform_score(
        self, publish_record: VideoPublishRecord
    ) -> PlatformPerformanceScore:
        """
        计算单平台效果评分

        不同平台有不同的评价维度和权重
        """
        platform = publish_record.platform
        weights = self.PLATFORM_WEIGHTS.get(platform, self.PLATFORM_WEIGHTS["douyin"])

        # 流量分
        traffic_score = self._calc_traffic_score(publish_record, platform)

        # 互动分
        engagement_score = self._calc_engagement_score(publish_record, platform)

        # 转化分
        conversion_score = self._calc_conversion_score(publish_record, platform)

        # 客户价值分
        customer_value_score = self._calc_customer_value_score(publish_record, platform)

        # 综合评分
        overall_score = round(
            traffic_score * weights["traffic"] +
            engagement_score * weights["engagement"] +
            conversion_score * weights["conversion"] +
            customer_value_score * weights["customer_value"]
        )

        # 保存评分记录
        existing = self.db.query(PlatformPerformanceScore).filter(
            PlatformPerformanceScore.publish_record_id == publish_record.id
        ).first()

        if existing:
            score_record = existing
        else:
            score_record = PlatformPerformanceScore(
                publish_record_id=publish_record.id,
                video_id=publish_record.video_id,
                user_id=publish_record.user_id,
                platform=platform,
            )

        score_record.overall_score = overall_score
        score_record.traffic_score = traffic_score
        score_record.engagement_score = engagement_score
        score_record.conversion_score = conversion_score
        score_record.customer_value_score = customer_value_score
        score_record.score_breakdown = {
            "traffic": {"score": traffic_score, "weight": weights["traffic"]},
            "engagement": {"score": engagement_score, "weight": weights["engagement"]},
            "conversion": {"score": conversion_score, "weight": weights["conversion"]},
            "customer_value": {"score": customer_value_score, "weight": weights["customer_value"]},
        }
        score_record.platform_specific = self._get_platform_specific_score(publish_record)

        if not existing:
            self.db.add(score_record)
        self.db.commit()
        self.db.refresh(score_record)

        return score_record

    def _calc_traffic_score(self, record: VideoPublishRecord, platform: str) -> int:
        """计算流量表现评分"""
        views = record.views or 0
        # 各平台基准不同
        benchmarks = {
            "douyin": 100000,
            "wechat_video": 10000,
            "xiaohongshu": 5000,
            "kuaishou": 50000,
        }
        benchmark = benchmarks.get(platform, 50000)
        ratio = views / benchmark if benchmark > 0 else 0
        return min(round(ratio * 100), 100)

    def _calc_engagement_score(self, record: VideoPublishRecord, platform: str) -> int:
        """计算互动表现评分"""
        views = max(record.views, 1)
        likes = record.likes or 0
        comments = record.comments or 0
        shares = record.shares or 0
        favorites = record.favorites or 0

        # 互动率 = (点赞+评论+分享+收藏) / 播放
        engagement_count = likes + comments * 2 + shares * 3 + favorites * 1.5
        engagement_rate = engagement_count / views

        # 基准互动率 5%
        score = min(round(engagement_rate / 0.05 * 100), 100)
        return score

    def _calc_conversion_score(self, record: VideoPublishRecord, platform: str) -> int:
        """计算转化表现评分"""
        views = max(record.views, 1)
        consultation = record.consultation_count or 0
        orders = record.order_count or 0
        gmv = record.gmv or 0

        # 综合转化指标
        consultation_rate = consultation / views
        order_rate = orders / views

        # 各平台转化基准
        benchmarks = {
            "douyin": {"consultation": 0.005, "order": 0.001},
            "wechat_video": {"consultation": 0.02, "order": 0.005},
            "xiaohongshu": {"consultation": 0.01, "order": 0.002},
            "kuaishou": {"consultation": 0.008, "order": 0.003},
        }
        bench = benchmarks.get(platform, benchmarks["douyin"])

        consult_score = min(round(consultation_rate / bench["consultation"] * 60), 60)
        order_score = min(round(order_rate / bench["order"] * 40), 40)

        return min(consult_score + order_score, 100)

    def _calc_customer_value_score(self, record: VideoPublishRecord, platform: str) -> int:
        """计算客户价值评分"""
        consultations = max(record.consultation_count, 1)
        gmv = record.gmv or 0
        avg_gmv_per_consult = gmv / consultations

        # 每咨询平均GMV基准 100元
        score = min(round(avg_gmv_per_consult / 100 * 100), 100)
        return score

    def _get_platform_specific_score(self, record: VideoPublishRecord) -> Dict:
        """获取平台特性评分"""
        platform = record.platform
        specific = {}

        if platform == "douyin":
            specific["fans_growth_score"] = min(round((record.follows or 0) / max(record.views, 1) / 0.02 * 100), 100)
            specific["hot_potential"] = min(round((record.shares or 0) / max(record.views, 1) / 0.01 * 100), 100)

        elif platform == "wechat_video":
            specific["share_rate_score"] = min(round((record.shares or 0) / max(record.views, 1) / 0.03 * 100), 100)
            specific["private_conversion"] = min(round((record.private_message_count or 0) / max(record.views, 1) / 0.01 * 100), 100)

        elif platform == "xiaohongshu":
            specific["collection_score"] = min(round((record.favorites or 0) / max(record.views, 1) / 0.05 * 100), 100)
            specific["search_value"] = min(round((record.favorites or 0) / max(record.views, 1) / 0.03 * 100), 100)

        return specific

    # ==================== 2. 导演评分 V3 ====================

    def calculate_director_score_v3(
        self,
        plan: VideoEditPlan,
        segments: List[VideoEditSegment],
        target_platform: str = "wechat_video",
        user_id: Optional[int] = None,
    ) -> Tuple[int, Dict[str, Any], List[str]]:
        """
        导演评分 V3

        内容质量 40% + 主播适配 20% + 平台匹配 20% + 历史经验 20%
        """
        breakdown = {}
        reasons = []

        # 1. 内容质量 (40分)
        content_score, content_reasons = self._score_content_quality_v3(segments, plan)
        breakdown["content_quality"] = {
            "score": content_score,
            "max": self.DIRECTOR_SCORE_V3["content_quality"]["max"],
            "reason": "；".join(content_reasons),
        }
        reasons.extend(content_reasons)

        # 2. 主播适配 (20分)
        creator_score, creator_reasons = self._score_creator_fit_v3(segments, user_id)
        breakdown["creator_fit"] = {
            "score": creator_score,
            "max": self.DIRECTOR_SCORE_V3["creator_fit"]["max"],
            "reason": "；".join(creator_reasons),
        }
        reasons.extend(creator_reasons)

        # 3. 平台匹配 (20分)
        platform_score, platform_reasons = self._score_platform_match_v3(plan, target_platform)
        breakdown["platform_match"] = {
            "score": platform_score,
            "max": self.DIRECTOR_SCORE_V3["platform_match"]["max"],
            "reason": "；".join(platform_reasons),
        }
        reasons.extend(platform_reasons)

        # 4. 历史经验 (20分)
        history_score, history_reasons = self._score_historical_data_v3(user_id, plan, target_platform)
        breakdown["historical_data"] = {
            "score": history_score,
            "max": self.DIRECTOR_SCORE_V3["historical_data"]["max"],
            "reason": "；".join(history_reasons),
        }
        reasons.extend(history_reasons)

        # 总分
        total = content_score + creator_score + platform_score + history_score
        return min(total, 100), breakdown, reasons

    def _score_content_quality_v3(
        self, segments: List[VideoEditSegment], plan: VideoEditPlan
    ) -> Tuple[int, List[str]]:
        """评分：内容质量（V3 40分）"""
        score = 0
        reasons = []

        matched = [s for s in segments if s.match_status == "matched"]
        match_rate = len(matched) / len(segments) if segments else 0

        # 素材完整度 20分
        if match_rate == 1.0:
            score += 20
            reasons.append("+ 所有镜头素材已匹配")
        elif match_rate >= 0.8:
            score += 14
            reasons.append("+ 80%以上镜头已匹配")
        elif match_rate >= 0.5:
            score += 8
            reasons.append("- 部分镜头素材缺失")
        else:
            reasons.append("- 大量镜头素材缺失")

        # Hook质量 10分
        hook = next((s for s in segments if s.role == "hook" and s.match_status == "matched"), None)
        if hook and hook.match_score >= 80:
            score += 10
            reasons.append("+ Hook素材强")
        elif hook:
            score += 6
            reasons.append("+ Hook素材可用")
        else:
            reasons.append("- 缺少Hook素材")

        # 转化结构 10分
        has_product = any(s.role == "product" and s.match_status == "matched" for s in segments)
        has_ending = any(s.role == "ending" and s.match_status == "matched" for s in segments)
        has_trust = any(s.role == "trust" and s.match_status == "matched" for s in segments)

        struct_score = 0
        if has_product:
            struct_score += 4
            reasons.append("+ 产品镜头完整")
        if has_ending:
            struct_score += 3
            reasons.append("+ 结尾引导完整")
        if has_trust:
            struct_score += 3
            reasons.append("+ 信任建立完整")
        score += struct_score

        if not has_product:
            reasons.append("- 缺少产品镜头")

        return min(score, 40), reasons

    def _score_creator_fit_v3(
        self, segments: List[VideoEditSegment], user_id: Optional[int]
    ) -> Tuple[int, List[str]]:
        """评分：主播适配（V3 20分）"""
        score = 0
        reasons = []

        if not user_id:
            return 10, ["- 无主播数据，使用默认分"]

        # 主播整体表现 10分
        profile = self.db.query(CreatorPerformanceProfile).filter(
            CreatorPerformanceProfile.user_id == user_id
        ).first()

        if profile:
            if profile.overall_performance_score >= 85:
                score += 10
                reasons.append("+ 主播整体表现优秀")
            elif profile.overall_performance_score >= 70:
                score += 7
                reasons.append("+ 主播整体表现良好")
            else:
                score += 4
                reasons.append("+ 主播基础表现")

            # 最佳情绪匹配 5分
            matched = [s for s in segments if s.match_status == "matched"]
            best_emotion_count = 0
            for seg in matched:
                if seg.asset_segment_id:
                    asset_seg = self.db.query(AssetSegment).filter(
                        AssetSegment.id == seg.asset_segment_id
                    ).first()
                    if asset_seg and profile.best_emotion and asset_seg.emotion == profile.best_emotion:
                        best_emotion_count += 1

            if best_emotion_count >= 2:
                score += 5
                reasons.append(f"+ 匹配主播最佳情绪({profile.best_emotion})")
            elif best_emotion_count >= 1:
                score += 3
                reasons.append("+ 部分匹配主播情绪")
        else:
            score += 5
            reasons.append("- 暂无主播画像")

        # 主播策略画像 5分
        strategy_profile = self.db.query(CreatorStrategyProfile).filter(
            CreatorStrategyProfile.user_id == user_id
        ).first()

        if strategy_profile and strategy_profile.analyzed_videos >= 5:
            score += 5
            reasons.append(f"+ 有{strategy_profile.analyzed_videos}个视频历史数据")
        else:
            score += 2
            reasons.append("- 历史数据不足，持续积累中")

        return min(score, 20), reasons

    def _score_platform_match_v3(
        self, plan: VideoEditPlan, target_platform: str
    ) -> Tuple[int, List[str]]:
        """评分：平台匹配（V3 20分）"""
        score = 0
        reasons = []

        platform_labels = {
            "douyin": "抖音",
            "wechat_video": "视频号",
            "xiaohongshu": "小红书",
            "kuaishou": "快手",
        }
        label = platform_labels.get(target_platform, target_platform)

        # 平台特性匹配
        template_type = None
        if plan.director_analysis and isinstance(plan.director_analysis, dict):
            template_type = plan.director_analysis.get("template_type")

        # 抖音适合强Hook、短时长
        if target_platform == "douyin":
            if plan.total_duration <= 30:
                score += 8
                reasons.append(f"+ 30秒内适合抖音流量分发")
            else:
                score += 4
                reasons.append("- 时长稍长，可能影响抖音完播率")

            if template_type in ("pain_point", "product"):
                score += 12
                reasons.append(f"+ 痛点型/产品型适合抖音")
            else:
                score += 7
                reasons.append("+ 内容类型适配抖音")

        # 视频号适合信任型、长一点
        elif target_platform == "wechat_video":
            if plan.total_duration >= 30:
                score += 8
                reasons.append(f"+ 30秒以上适合视频号深度转化")
            else:
                score += 5
                reasons.append("- 时长较短，视频号转化可能不足")

            if template_type in ("story", "trust", "expert"):
                score += 12
                reasons.append("+ 故事/专家型适合视频号私域转化")
            else:
                score += 8
                reasons.append("+ 内容类型适配视频号")

        # 小红书适合知识/种草
        elif target_platform == "xiaohongshu":
            if template_type in ("knowledge", "product", "expert"):
                score += 12
                reasons.append("+ 知识/产品型适合小红书种草")
            else:
                score += 7
                reasons.append("+ 内容类型适配小红书")
            score += 8
            reasons.append(f"+ 建议发布到{label}")

        else:
            score = 12
            reasons.append(f"+ 通用适配{label}")

        return min(score, 20), reasons

    def _score_historical_data_v3(
        self, user_id: Optional[int], plan: VideoEditPlan, target_platform: str
    ) -> Tuple[int, List[str]]:
        """评分：历史经验（V3 20分）"""
        score = 0
        reasons = []

        if not user_id:
            return 5, ["- 无历史数据"]

        # 从经验库匹配相关经验
        template_type = None
        if plan.director_analysis and isinstance(plan.director_analysis, dict):
            template_type = plan.director_analysis.get("template_type")

        memories = self.db.query(DirectorLearningMemory).filter(
            DirectorLearningMemory.user_id == user_id,
            DirectorLearningMemory.is_active == True,
        ).all()

        # 筛选相关经验
        relevant_memories = []
        for mem in memories:
            if mem.memory_type == "template_success" and template_type:
                if isinstance(mem.condition, dict) and mem.condition.get("template_type") == template_type:
                    relevant_memories.append(mem)
            elif mem.memory_type == "platform_success":
                if isinstance(mem.condition, dict) and mem.condition.get("platform") == target_platform:
                    relevant_memories.append(mem)

        if relevant_memories:
            # 按置信度加权
            avg_confidence = sum(m.confidence_score for m in relevant_memories) / len(relevant_memories)
            experience_bonus = round(avg_confidence * 15)
            score += experience_bonus
            reasons.append(f"+ 匹配{len(relevant_memories)}条历史经验")
        else:
            score += 5
            reasons.append("- 暂无相关历史经验，持续学习中")

        # 平台策略画像
        platform_profile = self.db.query(PlatformStrategyProfile).filter(
            PlatformStrategyProfile.user_id == user_id,
            PlatformStrategyProfile.platform == target_platform,
        ).first()

        if platform_profile and platform_profile.total_published >= 3:
            score += 5
            reasons.append(f"+ 已有{platform_profile.total_published}个{target_platform}视频数据")

        return min(score, 20), reasons

    # ==================== 3. 导演复盘Agent ====================

    def run_review(
        self, video_id: int
    ) -> Dict[str, Any]:
        """
        导演复盘Agent

        流程：
        视频发布 → 获取数据 → AI分析 → 和原导演方案比较 →
        找到偏差 → 更新导演经验库 → 更新策略画像
        """
        video = self.db.query(VideoMasterContent).filter(
            VideoMasterContent.id == video_id
        ).first()

        if not video:
            return {"success": False, "error": "视频不存在"}

        # 获取所有平台发布记录
        publish_records = self.db.query(VideoPublishRecord).filter(
            VideoPublishRecord.video_id == video_id
        ).all()

        if not publish_records:
            return {"success": False, "error": "暂无发布数据"}

        # 计算各平台评分
        platform_scores = []
        for record in publish_records:
            score = self.calculate_platform_score(record)
            platform_scores.append(score)

        # 获取原导演方案（如果有）
        original_plan = None
        if video.edit_plan_id:
            original_plan = self.db.query(VideoEditPlan).filter(
                VideoEditPlan.id == video.edit_plan_id
            ).first()

        # 分析偏差
        deviations = self._analyze_deviations(video, original_plan, platform_scores)

        # 更新经验库
        new_memories = self._update_learning_memory(video, publish_records, platform_scores)

        # 更新主播策略画像
        self._update_creator_strategy_profile(video.user_id, video, publish_records)

        # 更新平台策略画像
        for record in publish_records:
            self._update_platform_strategy_profile(video.user_id, record.platform, record)

        # 更新视频汇总效果
        video.actual_performance = self._summarize_performance(publish_records, platform_scores)
        self.db.commit()

        return {
            "success": True,
            "video_id": video_id,
            "platforms_analyzed": len(publish_records),
            "deviations": deviations,
            "new_memories": len(new_memories),
            "best_platform": self._find_best_platform(platform_scores),
        }

    def _analyze_deviations(
        self,
        video: VideoMasterContent,
        original_plan: Optional[VideoEditPlan],
        platform_scores: List[PlatformPerformanceScore],
    ) -> List[Dict]:
        """分析预测与实际的偏差"""
        deviations = []

        if not original_plan:
            return [{"type": "info", "message": "无原始导演方案，跳过偏差分析"}]

        # 完播率偏差
        avg_completion = 0
        scores = [s for s in platform_scores if s.platform == "wechat_video"]
        if scores:
            # 用视频号数据做主要对比
            pass

        # 根据实际效果和预测对比
        if original_plan.predicted_completion_rate > 0:
            # 简化：根据评分判断
            best_score = max(s.overall_score for s in platform_scores) if platform_scores else 0
            if best_score >= 80 and original_plan.director_score >= 80:
                deviations.append({
                    "type": "success",
                    "message": "预测准确，视频表现优秀",
                    "predicted_score": original_plan.director_score,
                    "actual_score": best_score,
                })
            elif best_score < 60 and original_plan.director_score >= 70:
                deviations.append({
                    "type": "negative",
                    "message": "预测偏乐观，实际表现低于预期",
                    "predicted_score": original_plan.director_score,
                    "actual_score": best_score,
                    "analysis": "可能原因：Hook不够强/产品植入生硬",
                })

        return deviations

    def _update_learning_memory(
        self,
        video: VideoMasterContent,
        publish_records: List[VideoPublishRecord],
        platform_scores: List[PlatformPerformanceScore],
    ) -> List[DirectorLearningMemory]:
        """更新导演经验库"""
        new_memories = []
        user_id = video.user_id

        # 1. 模板成功经验
        if video.template_type:
            best_score = max(s.overall_score for s in platform_scores) if platform_scores else 0
            if best_score >= 70:
                memory = DirectorLearningMemory(
                    user_id=user_id,
                    memory_type="template_success",
                    condition={
                        "template_type": video.template_type,
                        "product_category": video.product_category,
                    },
                    recommendation={
                        "template_type": video.template_type,
                        "performance_score": best_score,
                        "duration": video.duration,
                    },
                    confidence_score=min(best_score / 100, 1.0),
                    usage_count=1,
                    success_count=1 if best_score >= 70 else 0,
                    source_video_ids=[video.id],
                    source_data_points=1,
                    is_verified=best_score >= 80,
                )
                self.db.add(memory)
                new_memories.append(memory)

        # 2. 平台成功经验
        for score in platform_scores:
            if score.overall_score >= 70:
                memory = DirectorLearningMemory(
                    user_id=user_id,
                    memory_type="platform_success",
                    condition={
                        "platform": score.platform,
                        "template_type": video.template_type,
                    },
                    recommendation={
                        "platform": score.platform,
                        "score": score.overall_score,
                        "strength": "conversion" if score.conversion_score >= 80 else "traffic",
                    },
                    confidence_score=min(score.overall_score / 100, 1.0),
                    usage_count=1,
                    success_count=1,
                    source_video_ids=[video.id],
                    source_data_points=1,
                    is_verified=score.overall_score >= 85,
                )
                self.db.add(memory)
                new_memories.append(memory)

        self.db.commit()
        return new_memories

    def _update_creator_strategy_profile(
        self, user_id: int, video: VideoMasterContent, publish_records: List[VideoPublishRecord]
    ):
        """更新主播策略画像"""
        profile = self.db.query(CreatorStrategyProfile).filter(
            CreatorStrategyProfile.user_id == user_id
        ).first()

        if not profile:
            profile = CreatorStrategyProfile(user_id=user_id)
            self.db.add(profile)

        # 统计各平台表现
        platform_perf = {}
        for record in publish_records:
            platform_perf[record.platform] = {
                "avg_views": record.views,
                "avg_commercial_score": record.consultation_count,
            }

        profile.platform_performance = platform_perf
        profile.analyzed_videos = (profile.analyzed_videos or 0) + 1

        # 简单更新最佳内容类型
        if video.template_type:
            best_types = profile.best_content_types or []
            if video.template_type not in best_types:
                best_types.append(video.template_type)
                profile.best_content_types = best_types
            if not profile.best_content_type:
                profile.best_content_type = video.template_type

        profile.last_updated = datetime.now()
        self.db.commit()

    def _update_platform_strategy_profile(
        self, user_id: int, platform: str, record: VideoPublishRecord
    ):
        """更新平台策略画像"""
        profile = self.db.query(PlatformStrategyProfile).filter(
            PlatformStrategyProfile.user_id == user_id,
            PlatformStrategyProfile.platform == platform,
        ).first()

        if not profile:
            profile = PlatformStrategyProfile(
                user_id=user_id,
                platform=platform,
                weight_config=self.PLATFORM_WEIGHTS.get(platform),
            )
            self.db.add(profile)

        # 滚动平均
        if profile.total_published > 0:
            profile.avg_views = round(
                (profile.avg_views * profile.total_published + (record.views or 0)) / (profile.total_published + 1)
            )
        else:
            profile.avg_views = record.views or 0

        if record.completion_rate:
            if profile.avg_completion_rate > 0:
                profile.avg_completion_rate = round(
                    (profile.avg_completion_rate * profile.total_published + record.completion_rate) / (profile.total_published + 1),
                    3
                )
            else:
                profile.avg_completion_rate = record.completion_rate

        if record.conversion_rate:
            if profile.avg_conversion_rate > 0:
                profile.avg_conversion_rate = round(
                    (profile.avg_conversion_rate * profile.total_published + record.conversion_rate) / (profile.total_published + 1),
                    4
                )
            else:
                profile.avg_conversion_rate = record.conversion_rate

        profile.total_published += 1
        self.db.commit()

    def _summarize_performance(
        self, publish_records: List[VideoPublishRecord], platform_scores: List[PlatformPerformanceScore]
    ) -> Dict:
        """汇总跨平台效果"""
        total_views = sum(r.views or 0 for r in publish_records)

        # 找出各维度最佳平台
        best_traffic = None
        best_conversion = None

        for score in platform_scores:
            if best_traffic is None or score.traffic_score > best_traffic[1]:
                best_traffic = (score.platform, score.traffic_score)
            if best_conversion is None or score.conversion_score > best_conversion[1]:
                best_conversion = (score.platform, score.conversion_score)

        # 计算Phoenix商业评分（跨平台加权）
        total_gmv = sum(r.gmv or 0 for r in publish_records)
        total_consultation = sum(r.consultation_count or 0 for r in publish_records)

        return {
            "total_views": total_views,
            "total_gmv": total_gmv,
            "total_consultations": total_consultation,
            "best_platform": {
                "traffic": best_traffic[0] if best_traffic else None,
                "conversion": best_conversion[0] if best_conversion else None,
            },
            "platform_count": len(publish_records),
        }

    def _find_best_platform(self, platform_scores: List[PlatformPerformanceScore]) -> Optional[str]:
        """找出最佳平台"""
        if not platform_scores:
            return None
        best = max(platform_scores, key=lambda s: s.overall_score)
        return best.platform

    # ==================== 经验库查询 ====================

    def get_memories(
        self,
        user_id: Optional[int] = None,
        memory_type: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 50,
    ) -> List[DirectorLearningMemory]:
        """获取导演经验库"""
        query = self.db.query(DirectorLearningMemory).filter(
            DirectorLearningMemory.is_active == True,
            DirectorLearningMemory.confidence_score >= min_confidence,
        )

        if user_id:
            query = query.filter(DirectorLearningMemory.user_id == user_id)
        if memory_type:
            query = query.filter(DirectorLearningMemory.memory_type == memory_type)

        return query.order_by(
            DirectorLearningMemory.confidence_score.desc()
        ).limit(limit).all()

    def get_creator_strategy_profile(self, user_id: int) -> Optional[CreatorStrategyProfile]:
        """获取主播策略画像"""
        return self.db.query(CreatorStrategyProfile).filter(
            CreatorStrategyProfile.user_id == user_id
        ).first()

    def get_platform_strategy_profiles(self, user_id: int) -> List[PlatformStrategyProfile]:
        """获取所有平台策略画像"""
        return self.db.query(PlatformStrategyProfile).filter(
            PlatformStrategyProfile.user_id == user_id
        ).all()

    def close(self):
        self.db.close()
