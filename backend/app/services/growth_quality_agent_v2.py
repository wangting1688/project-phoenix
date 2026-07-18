"""
Growth Quality Agent V2 - 增长质量检测Agent

TASK-016.3B.4：AI Growth Review Memory

核心升级：
1. 增加有机增长指数（Organic Growth Score）
2. 增强商业压力指数（Commercial Pressure Index）
3. 增加主播适配评分（Creator Fit Score）
4. 生成导演反馈报告（Growth Review Report）
5. 形成导演反馈闭环
6. 集成三版本策略建议
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.video_edit_plan import VideoEditPlan, VideoEditSegment
from app.models.video_production import VideoProductionJob, VideoTimeline, GrowthReviewReport
from app.models.user import User
from app.services.agent_tool_gateway import AgentToolGateway
from app.services.creator_fit_scorer import CreatorFitScorer


class GrowthQualityAgentV2:
    """增长质量检测Agent V2"""

    MIN_ORGANIC_GROWTH_SCORE = 70
    MAX_COMMERCIAL_PRESSURE = 30

    ORGANIC_GROWTH_WEIGHTS = {
        "hook": 25,
        "retention": 25,
        "emotion": 20,
        "follow_reason": 15,
        "platform_fit": 15,
    }

    COMMERCIAL_PRESSURE_CONFIG = {
        "product_in_first_3s": 90,
        "brand_name_mention": 60,
        "show_packaging": 50,
        "talk_experience": 20,
        "talk_life_scene": 10,
        "price_stimulus": 80,
        "buy_promotion": 85,
        "effect_claim": 70,
    }

    FOLLOW_REASONS = {
        "persona": "这个姐姐懂我",
        "knowledge": "以后还想听她讲",
        "serial": "想看下一集",
        "companion": "每天刷一下",
        "inspiration": "给我启发",
        "entertainment": "有趣",
    }

    HOOK_PATTERNS = {
        "curiosity": {"keywords": ["为什么", "你不知道", "秘密", "真相", "90%", "很少有人"], "score": 90},
        "pain_point": {"keywords": ["很多人", "发现一个", "变化", "困扰", "痛苦", "焦虑"], "score": 85},
        "contradiction": {"keywords": ["不要", "其实", "反而", "颠覆", "反转", "没想到"], "score": 88},
        "story": {"keywords": ["那天", "记得", "我", "经历", "发现", "终于"], "score": 80},
        "question": {"keywords": ["你有没有", "是不是", "为什么", "怎么办", "如何", "谁"], "score": 82},
    }

    COMMERCIAL_WORDS = [
        "产品", "购买", "下单", "价格", "优惠", "活动", "买", "送", "限时", "抢购",
        "链接", "店铺", "官网", "加我", "私信", "功效", "效果", "作用", "好处", "推荐",
        "根治", "治愈", "神奇", "立刻", "马上", "永久", "绝对", "买3送1",
    ]

    def __init__(self):
        self.db = SessionLocal()
        self.gateway = AgentToolGateway()
        self.creator_fit_scorer = CreatorFitScorer()

    def close(self):
        self.db.close()
        self.creator_fit_scorer.close()

    def assess_growth_quality_v2(self, plan_id: int, version_type: str = "growth") -> Dict[str, Any]:
        """评估增长质量 V2"""
        plan = self._get_plan(plan_id)
        if not plan:
            return {"success": False, "error": "导演方案不存在"}

        segments = self._get_segments(plan_id)

        hook_result = self._evaluate_hook_v2(plan, segments)
        retention_result = self._predict_retention_v2(hook_result["score"], plan)
        emotion_result = self._analyze_emotion_curve_v2(plan, segments)
        follow_result = self._identify_follow_reasons_v2(plan, segments)
        platform_result = self._evaluate_platform_fit_v2(plan)
        commercial_pressure = self._calculate_commercial_pressure(plan, segments)
        creator_fit = self.creator_fit_scorer.score_creator_fit(plan_id)

        organic_growth_score = self._calculate_organic_growth_score(
            hook_result["score"],
            retention_result["score"],
            emotion_result["avg_match_score"],
            follow_result["avg_strength"],
            platform_result["score"],
        )

        problems = self._collect_problems(
            hook_result, retention_result, emotion_result, follow_result,
            platform_result, commercial_pressure, creator_fit, plan
        )

        director_actions = self._generate_director_actions(problems)

        passed = self._check_pass_criteria(organic_growth_score, commercial_pressure, creator_fit, version_type)

        suggestions = self._generate_suggestions_v2(
            organic_growth_score, commercial_pressure, creator_fit, problems, version_type
        )

        return {
            "success": True,
            "plan_id": plan_id,
            "stage": version_type,
            "organic_growth_score": organic_growth_score,
            "commercial_pressure_index": commercial_pressure["index"],
            "creator_fit_score": creator_fit.get("fit_score", 70),
            "passed": passed,
            "can_produce": passed,
            "details": {
                "hook": hook_result,
                "retention": retention_result,
                "emotion": emotion_result,
                "follow_reasons": follow_result,
                "platform_fit": platform_result,
                "commercial_pressure": commercial_pressure,
                "creator_fit": creator_fit,
            },
            "problems": problems,
            "director_actions": director_actions,
            "suggestions": suggestions,
        }

    def generate_growth_review_report(self, plan_id: int, version_type: str = "growth") -> Dict[str, Any]:
        """生成增长复盘报告"""
        assessment = self.assess_growth_quality_v2(plan_id, version_type)
        if not assessment["success"]:
            return assessment

        plan = self._get_plan(plan_id)
        if not plan:
            return {"success": False, "error": "导演方案不存在"}

        previous_report = self.db.query(GrowthReviewReport).filter(
            GrowthReviewReport.video_plan_id == plan_id,
            GrowthReviewReport.stage == version_type
        ).order_by(GrowthReviewReport.created_at.desc()).first()

        report = GrowthReviewReport(
            user_id=plan.user_id,
            video_plan_id=plan_id,
            stage=version_type,
            overall_score=assessment["organic_growth_score"],
            passed=assessment["passed"],
            hook_score=assessment["details"]["hook"]["score"],
            retention_score=assessment["details"]["retention"]["score"],
            emotion_score=assessment["details"]["emotion"]["avg_match_score"],
            follow_reason_score=assessment["details"]["follow_reasons"]["avg_strength"],
            platform_fit_score=assessment["details"]["platform_fit"]["score"],
            creator_fit_score=assessment["creator_fit_score"],
            commercial_pressure_index=assessment["commercial_pressure_index"],
            organic_growth_score=assessment["organic_growth_score"],
            problems=assessment["problems"],
            director_actions=assessment["director_actions"],
            suggestions=assessment["suggestions"],
            review_count=(previous_report.review_count + 1) if previous_report else 1,
            previous_report_id=previous_report.id if previous_report else None,
            version_type=version_type,
        )

        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        return {
            "success": True,
            "report_id": report.id,
            "report": {
                "id": report.id,
                "overall_score": report.overall_score,
                "passed": report.passed,
                "review_count": report.review_count,
                "problems": report.problems,
                "director_actions": report.director_actions,
                "suggestions": report.suggestions,
            },
        }

    def _evaluate_hook_v2(self, plan: VideoEditPlan, segments: List[VideoEditSegment]) -> Dict[str, Any]:
        """评估Hook吸引力 V2"""
        score = 50
        details = []

        hook_segment = next((s for s in segments if s.role == "hook"), None)
        if not hook_segment:
            return {"score": 30, "details": ["无Hook片段"], "matched_patterns": []}

        hook_duration = hook_segment.duration or 0
        if 2.5 <= hook_duration <= 4.0:
            score += 15
            details.append("Hook时长合理（2.5-4秒）")
        elif hook_duration < 2.5:
            score += 5
            details.append("Hook时长偏短")

        script_content = plan.script_content or ""
        first_50_chars = script_content[:50]

        matched_patterns = []
        for pattern_name, pattern_config in self.HOOK_PATTERNS.items():
            for keyword in pattern_config["keywords"]:
                if keyword in first_50_chars:
                    matched_patterns.append(pattern_name)
                    break

        if matched_patterns:
            avg_score = sum(
                self.HOOK_PATTERNS[p]["score"]
                for p in matched_patterns
            ) / len(matched_patterns)
            score += min(35, int(avg_score / 3))
            details.append(f"匹配Hook模式：{', '.join(matched_patterns)}")

        if "？" in first_50_chars or "!" in first_50_chars:
            score += 5
            details.append("有疑问/感叹句增强吸引力")

        return {
            "score": min(100, score),
            "details": details,
            "matched_patterns": matched_patterns,
            "first_50_chars": first_50_chars,
        }

    def _predict_retention_v2(self, hook_score: int, plan: VideoEditPlan) -> Dict[str, Any]:
        """预测前3秒留存 V2"""
        if hook_score >= 85:
            level = "high"
            score = 90
        elif hook_score >= 70:
            level = "medium"
            score = 65
        else:
            level = "low"
            score = 30

        return {
            "level": level,
            "score": score,
            "prediction": f"前3秒留存预测：{level}（基于Hook评分{hook_score}）",
        }

    def _analyze_emotion_curve_v2(self, plan: VideoEditPlan, segments: List[VideoEditSegment]) -> Dict[str, Any]:
        """分析情绪曲线 V2"""
        expected_emotions = {
            "hook": ["curiosity", "surprise", "concern"],
            "problem": ["empathy", "frustration", "pain"],
            "knowledge": ["curiosity", "interest", "understanding"],
            "solution": ["hope", "relief", "excitement"],
            "social_proof": ["trust", "confidence", "urgency"],
            "conversion": ["desire", "action", "satisfaction"],
        }

        emotion_flow = []
        emotions = []

        for segment in segments:
            role = segment.role or "general"
            emotion_config = segment.effect_config or {}
            actual_emotion = emotion_config.get("emotion", "neutral")
            expected = expected_emotions.get(role, ["neutral"])

            match_score = 80 if actual_emotion in expected else 50
            emotions.append(actual_emotion)

            emotion_flow.append({
                "role": role,
                "actual_emotion": actual_emotion,
                "expected_emotions": expected,
                "match_score": match_score,
            })

        avg_match = sum(e["match_score"] for e in emotion_flow) / len(emotion_flow) if emotion_flow else 50
        variety = len(set(emotions))

        return {
            "flow": emotion_flow,
            "avg_match_score": round(avg_match),
            "variety": variety,
            "has_peak": any(e["match_score"] >= 85 for e in emotion_flow),
        }

    def _identify_follow_reasons_v2(self, plan: VideoEditPlan, segments: List[VideoEditSegment]) -> Dict[str, Any]:
        """识别用户关注理由 V2"""
        script_content = plan.script_content or ""
        reasons = []

        reason_patterns = [
            ("persona", ["姐妹", "朋友", "大家", "我们", "一起", "我懂你", "理解"]),
            ("knowledge", ["干货", "知识", "技巧", "方法", "经验", "分享", "教程", "今天教"]),
            ("serial", ["下次", "下集", "后续", "明天", "更新", "继续", "揭秘", "记得关注"]),
            ("companion", ["每天", "陪伴", "日常", "一直", "长期"]),
            ("inspiration", ["启发", "感悟", "思考", "重新", "改变", "成长"]),
        ]

        for reason_type, keywords in reason_patterns:
            found_keywords = [k for k in keywords if k in script_content]
            if found_keywords:
                reasons.append({
                    "type": reason_type,
                    "description": self.FOLLOW_REASONS.get(reason_type, ""),
                    "keywords": found_keywords,
                    "strength": min(100, len(found_keywords) * 25),
                })

        if not reasons:
            reasons.append({
                "type": "weak",
                "description": "无明确关注理由",
                "keywords": [],
                "strength": 20,
            })

        avg_strength = sum(r["strength"] for r in reasons) / len(reasons)

        return {
            "reasons": reasons,
            "avg_strength": round(avg_strength),
            "count": len(reasons),
        }

    def _evaluate_platform_fit_v2(self, plan: VideoEditPlan) -> Dict[str, Any]:
        """评估平台适配度 V2"""
        platform = plan.platform or "wechat_video"
        script_content = plan.script_content or ""
        duration = plan.total_duration or 60

        platform_configs = {
            "douyin": {
                "ideal_duration": 35,
                "preferred_style": "fast_paced",
                "max_chars_per_second": 6,
            },
            "wechat_video": {
                "ideal_duration": 60,
                "preferred_style": "trust_building",
                "max_chars_per_second": 5,
            },
            "xiaohongshu": {
                "ideal_duration": 45,
                "preferred_style": "lifestyle",
                "max_chars_per_second": 5.5,
            },
            "kuaishou": {
                "ideal_duration": 40,
                "preferred_style": "authentic",
                "max_chars_per_second": 6,
            },
        }

        config = platform_configs.get(platform, platform_configs["wechat_video"])
        score = 80

        duration_diff = abs(duration - config["ideal_duration"])
        if duration_diff > 20:
            score -= 15
        elif duration_diff > 10:
            score -= 5

        return {
            "platform": platform,
            "score": max(0, score),
            "ideal_duration": config["ideal_duration"],
            "actual_duration": duration,
        }

    def _calculate_commercial_pressure(self, plan: VideoEditPlan, segments: List[VideoEditSegment]) -> Dict[str, Any]:
        """计算商业压力指数"""
        script_content = plan.script_content or ""

        pressure = 0
        detected_behaviors = []

        for word in self.COMMERCIAL_WORDS:
            count = script_content.count(word)
            if count > 0:
                if word in ["产品", "购买", "下单"]:
                    pressure += count * 25
                elif word in ["价格", "优惠", "活动", "买", "送", "限时", "抢购"]:
                    pressure += count * 20
                elif word in ["根治", "治愈", "神奇", "立刻", "马上", "永久", "绝对"]:
                    pressure += count * 30
                else:
                    pressure += count * 10
                detected_behaviors.append(f"{word}×{count}")

        first_3s_chars = script_content[:30]
        for word in self.COMMERCIAL_WORDS:
            if word in first_3s_chars:
                pressure += 50
                detected_behaviors.append(f"前3秒出现{word}")
                break

        if "买3送1" in script_content or "限时优惠" in script_content:
            pressure += 30
            detected_behaviors.append("强促销话术")

        pressure = min(100, pressure)

        return {
            "index": pressure,
            "level": self._get_pressure_level(pressure),
            "detected_behaviors": detected_behaviors,
        }

    def _get_pressure_level(self, pressure: int) -> str:
        if pressure >= 70:
            return "extreme"
        elif pressure >= 50:
            return "high"
        elif pressure >= 30:
            return "medium"
        elif pressure >= 10:
            return "low"
        else:
            return "minimal"

    def _calculate_organic_growth_score(self, hook: int, retention: int, emotion: int,
                                       follow: int, platform_fit: int) -> int:
        """计算有机增长指数"""
        weights = self.ORGANIC_GROWTH_WEIGHTS

        score = (
            hook * weights["hook"] / 100 +
            retention * weights["retention"] / 100 +
            emotion * weights["emotion"] / 100 +
            follow * weights["follow_reason"] / 100 +
            platform_fit * weights["platform_fit"] / 100
        )

        return round(score)

    def _collect_problems(self, hook: Dict, retention: Dict, emotion: Dict, follow: Dict,
                         platform: Dict, commercial: Dict, creator_fit: Dict, plan: VideoEditPlan) -> List[Dict]:
        """收集问题"""
        problems = []

        if hook["score"] < 70:
            problems.append({
                "type": "weak_hook",
                "scene": 1,
                "severity": "high",
                "reason": f"前三秒吸引力不足（评分{hook['score']}），缺少Hook模式",
                "suggestion": "建议在开头增加痛点、悬念或冲突",
            })

        if retention["level"] == "low":
            problems.append({
                "type": "low_retention_prediction",
                "scene": 1,
                "severity": "high",
                "reason": "前3秒留存预测较低",
                "suggestion": "重新设计开头以提升前3秒吸引力",
            })

        if emotion["avg_match_score"] < 60:
            problems.append({
                "type": "weak_emotion",
                "severity": "medium",
                "reason": "情绪曲线不够流畅",
                "suggestion": "调整各段落情绪设计",
            })

        if follow["avg_strength"] < 50:
            problems.append({
                "type": "weak_follow_reason",
                "severity": "high",
                "reason": f"无明确关注理由（强度{follow['avg_strength']}）",
                "suggestion": "增加人设/知识/连续剧/陪伴等关注理由",
            })

        if commercial["index"] > self.MAX_COMMERCIAL_PRESSURE:
            problems.append({
                "type": "high_commercial_pressure",
                "severity": "high",
                "reason": f"商业压力过高（{commercial['index']}），超过涨粉期上限{self.MAX_COMMERCIAL_PRESSURE}",
                "suggestion": "当前阶段为涨粉期，需降低商业压力。建议将产品介绍移至30%以后",
            })

        if creator_fit.get("fit_score", 70) < 60:
            problems.append({
                "type": "creator_mismatch",
                "severity": "medium",
                "reason": f"主播与内容类型不匹配（适配分{creator_fit.get('fit_score')}）",
                "suggestion": "; ".join(creator_fit.get("suggestions", ["建议调整内容结构"])),
            })

        return problems

    def _generate_director_actions(self, problems: List[Dict]) -> List[Dict]:
        """生成导演修改动作"""
        actions = []

        action_map = {
            "weak_hook": {"action": "rewrite_hook", "priority": "high"},
            "low_retention_prediction": {"action": "redesign_opening", "priority": "high"},
            "weak_emotion": {"action": "optimize_emotion_flow", "priority": "medium"},
            "weak_follow_reason": {"action": "add_follow_reasons", "priority": "high"},
            "high_commercial_pressure": {"action": "reduce_commercial", "priority": "high"},
            "creator_mismatch": {"action": "adjust_content_type", "priority": "medium"},
        }

        for problem in problems:
            action = action_map.get(problem["type"])
            if action:
                actions.append({
                    **action,
                    "problem_type": problem["type"],
                    "reason": problem["reason"],
                })

        return actions

    def _check_pass_criteria(self, organic_score: int, commercial: Dict, creator_fit: Dict, version_type: str) -> bool:
        """检查通过标准"""
        if organic_score < self.MIN_ORGANIC_GROWTH_SCORE:
            return False

        if version_type == "growth" and commercial["index"] > self.MAX_COMMERCIAL_PRESSURE:
            return False

        creator_score = creator_fit.get("fit_score", 70)
        if creator_score < 50:
            return False

        return True

    def _generate_suggestions_v2(self, organic_score: int, commercial: Dict, creator_fit: Dict,
                                 problems: List[Dict], version_type: str) -> List[str]:
        """生成优化建议 V2"""
        suggestions = []

        if organic_score < self.MIN_ORGANIC_GROWTH_SCORE:
            suggestions.append(f"有机增长指数{organic_score}，低于涨粉期阈值{self.MIN_ORGANIC_GROWTH_SCORE}")

        if commercial["index"] > self.MAX_COMMERCIAL_PRESSURE and version_type == "growth":
            suggestions.append(f"商业压力指数{commercial['index']}过高，涨粉期需降至{self.MAX_COMMERCIAL_PRESSURE}以下")
            suggestions.append("建议将产品介绍移至视频后半段")
            suggestions.append("避免使用'买3送1'、'限时优惠'等促销话术")

        creator_score = creator_fit.get("fit_score", 70)
        if creator_score < 60:
            suggestions.append(f"主播适配度仅{creator_score}分，建议调整内容结构匹配主播风格")
            for s in creator_fit.get("suggestions", []):
                suggestions.append(s)

        for problem in problems:
            if problem["suggestion"]:
                suggestions.append(problem["suggestion"])

        return suggestions

    def _get_plan(self, plan_id: int):
        if not plan_id:
            return None
        return self.db.query(VideoEditPlan).filter(VideoEditPlan.id == plan_id).first()

    def _get_segments(self, plan_id: int):
        if not plan_id:
            return []
        return self.db.query(VideoEditSegment).filter(
            VideoEditSegment.edit_plan_id == plan_id
        ).all()
