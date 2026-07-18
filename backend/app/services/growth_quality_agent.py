"""
Growth Quality Agent - 增长质量检测Agent

TASK-016.3B.3：增长质量控制层

核心职责：
1. 在视频生产前判断是否有爆款潜力
2. 检测Hook吸引力、前3秒留存、情绪曲线
3. 识别硬广风险、产品出现时机
4. 输出增长评分和优化建议
5. 低于阈值时阻止生产并反馈给导演Agent

当前阶段目标：涨粉期
目标函数：播放量 + 停留率 + 完播率 + 互动率 + 关注转化率
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.video_edit_plan import VideoEditPlan, VideoEditSegment
from app.models.video_production import VideoProductionJob, VideoTimeline
from app.services.agent_tool_gateway import AgentToolGateway


class GrowthQualityAgent:
    """增长质量检测Agent"""

    MIN_GROWTH_SCORE = 70

    STAGE_WEIGHTS = {
        "growth": {"play": 40, "completion": 25, "engagement": 20, "follow": 15},
        "private_domain": {"comment": 30, "message": 30, "profile": 20, "contact": 20},
        "conversion": {"gmv": 35, "consultation": 25, "conversion": 15, "retention": 25},
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
        "链接", "店铺", "官网", "微信", "加我", "私信", "联系方式", "客服", "咨询",
        "功效", "效果", "作用", "好处", "推荐", "爆款", "热销", "销量", "排名",
    ]

    def __init__(self):
        self.db = SessionLocal()
        self.gateway = AgentToolGateway()

    def close(self):
        self.db.close()

    def assess_growth_quality(self, job_id: int) -> Dict[str, Any]:
        """评估增长质量"""
        job = self._get_job(job_id)
        if not job:
            return {"success": False, "error": "任务不存在"}

        plan = self._get_plan(job.source_plan_id)
        if not plan:
            return {"success": False, "error": "导演方案不存在"}

        segments = self._get_segments(job.source_plan_id)
        timeline_items = self._get_timeline_items(job_id)

        hook_score = self._evaluate_hook(plan, segments, timeline_items)
        retention_prediction = self._predict_retention(hook_score, plan)
        emotion_curve = self._analyze_emotion_curve(plan, segments)
        info_density = self._calculate_info_density(plan)
        follow_reasons = self._identify_follow_reasons(plan)
        risks = self._detect_risks(plan, segments)

        growth_score = self._calculate_growth_score(
            hook_score, retention_prediction, emotion_curve, info_density, follow_reasons, risks
        )

        suggestions = self._generate_suggestions(
            growth_score, hook_score, retention_prediction, emotion_curve, info_density, risks
        )

        can_produce = growth_score >= self.MIN_GROWTH_SCORE

        return {
            "success": True,
            "job_id": job_id,
            "stage": "growth",
            "growth_score": growth_score,
            "can_produce": can_produce,
            "details": {
                "hook_score": hook_score,
                "retention_prediction": retention_prediction,
                "emotion_curve": emotion_curve,
                "info_density": info_density,
                "follow_reasons": follow_reasons,
                "risks": risks,
            },
            "suggestions": suggestions,
        }

    def _evaluate_hook(self, plan: VideoEditPlan, segments: List[VideoEditSegment], timeline_items: List[VideoTimeline]) -> int:
        """评估Hook吸引力"""
        score = 50

        hook_segment = next((s for s in segments if s.role == "hook"), None)
        if not hook_segment:
            return 30

        # 段落文案落在 subtitle_text，历史误写为 script_content
        hook_content = hook_segment.subtitle_text or ""
        hook_duration = hook_segment.duration or 0

        if hook_duration >= 2.5 and hook_duration <= 4.0:
            score += 15
        elif hook_duration < 2.5:
            score += 5

        script_content = plan.script_content or ""
        first_50_chars = script_content[:50]

        matched_patterns = []
        for pattern_name, pattern_config in self.HOOK_PATTERNS.items():
            for keyword in pattern_config["keywords"]:
                if keyword in first_50_chars:
                    matched_patterns.append((pattern_name, pattern_config["score"]))
                    break

        if matched_patterns:
            avg_pattern_score = sum(s[1] for s in matched_patterns) / len(matched_patterns)
            score += min(35, int(avg_pattern_score / 3))

        if "？" in first_50_chars or "!" in first_50_chars:
            score += 5

        if len(first_50_chars) >= 20:
            score += 5

        return min(100, score)

    def _predict_retention(self, hook_score: int, plan: VideoEditPlan) -> str:
        """预测前3秒留存"""
        if hook_score >= 85:
            return "high"
        elif hook_score >= 70:
            return "medium"
        else:
            return "low"

    def _analyze_emotion_curve(self, plan: VideoEditPlan, segments: List[VideoEditSegment]) -> Dict[str, Any]:
        """分析情绪曲线"""
        emotion_flow = []
        expected_emotions = {
            "hook": ["curiosity", "surprise", "concern"],
            "problem": ["empathy", "frustration", "pain"],
            "knowledge": ["curiosity", "interest", "understanding"],
            "solution": ["hope", "relief", "excitement"],
            "social_proof": ["trust", "confidence", "urgency"],
            "conversion": ["desire", "action", "satisfaction"],
        }

        for segment in segments:
            role = segment.role or "general"
            emotion_config = segment.effect_config or {}
            actual_emotion = emotion_config.get("emotion", "neutral")
            expected = expected_emotions.get(role, ["neutral"])

            match_score = 80 if actual_emotion in expected else 50

            emotion_flow.append({
                "segment_id": segment.id,
                "role": role,
                "start_time": sum(s.duration or 5 for s in segments[:segments.index(segment)]),
                "duration": segment.duration or 5,
                "actual_emotion": actual_emotion,
                "expected_emotions": expected,
                "match_score": match_score,
            })

        avg_match = sum(e["match_score"] for e in emotion_flow) / len(emotion_flow) if emotion_flow else 50

        return {
            "flow": emotion_flow,
            "avg_match_score": round(avg_match),
            "has_peak": any(e["match_score"] >= 85 for e in emotion_flow),
            "has_valley": any(e["match_score"] < 40 for e in emotion_flow),
        }

    def _calculate_info_density(self, plan: VideoEditPlan) -> Dict[str, Any]:
        """计算信息密度"""
        script_content = plan.script_content or ""
        duration = plan.total_duration or 60

        char_count = len(script_content)
        chars_per_second = char_count / duration if duration > 0 else 0

        # VideoEditPlan 是内容级实体，不承载平台维度；平台落 VideoPublishRecord
        platform = getattr(plan, "platform", None) or "wechat_video"
        ideal_ranges = {
            "douyin": (4, 6),
            "wechat_video": (3, 5),
            "xiaohongshu": (3.5, 5.5),
            "kuaishou": (4, 6),
        }

        ideal_min, ideal_max = ideal_ranges.get(platform, (3, 5))

        if ideal_min <= chars_per_second <= ideal_max:
            density_score = 85
            status = "optimal"
        elif chars_per_second < ideal_min:
            density_score = min(70, int(chars_per_second / ideal_min * 100))
            status = "sparse"
        else:
            density_score = max(50, int((ideal_max / chars_per_second) * 100))
            status = "dense"

        return {
            "chars_per_second": round(chars_per_second, 1),
            "ideal_range": f"{ideal_min}-{ideal_max}",
            "status": status,
            "score": density_score,
        }

    def _identify_follow_reasons(self, plan: VideoEditPlan) -> List[Dict[str, Any]]:
        """识别用户关注理由"""
        script_content = plan.script_content or ""
        reasons = []

        reason_patterns = [
            ("value", ["干货", "知识", "技巧", "方法", "经验", "分享", "教程"]),
            ("curiosity", ["下次", "下集", "后续", "明天", "更新", "继续", "揭秘"]),
            ("relationship", ["姐妹", "朋友", "大家", "我们", "一起", "共同"]),
            ("personality", ["我", "自己", "亲身", "经历", "真实", "故事"]),
        ]

        for reason_type, keywords in reason_patterns:
            found_keywords = [k for k in keywords if k in script_content]
            if found_keywords:
                reasons.append({
                    "type": reason_type,
                    "keywords": found_keywords,
                    "strength": min(100, len(found_keywords) * 25),
                })

        if not reasons:
            reasons.append({
                "type": "weak",
                "keywords": [],
                "strength": 20,
            })

        return reasons

    def _detect_risks(self, plan: VideoEditPlan, segments: List[VideoEditSegment]) -> Dict[str, Any]:
        """检测风险"""
        script_content = plan.script_content or ""
        risks = {
            "commercial_too_early": False,
            "hard_sell": False,
            "effect_exaggeration": False,
            "sensitive_content": False,
        }

        commercial_positions = []
        for idx, char in enumerate(script_content):
            for word in self.COMMERCIAL_WORDS:
                if script_content[idx:idx+len(word)] == word:
                    commercial_positions.append(idx)
                    break

        if commercial_positions:
            first_commercial_pos = min(commercial_positions)
            first_commercial_ratio = first_commercial_pos / len(script_content)

            if first_commercial_ratio < 0.3:
                risks["commercial_too_early"] = True

            if len(commercial_positions) >= 3:
                risks["hard_sell"] = True

        effect_words = ["根治", "治愈", "神奇", "特效", "立刻", "马上", "永久", "绝对"]
        for word in effect_words:
            if word in script_content:
                risks["effect_exaggeration"] = True
                break

        sensitive_words = ["疾病", "治疗", "医疗", "药品", "减肥", "瘦身", "丰胸"]
        for word in sensitive_words:
            if word in script_content:
                risks["sensitive_content"] = True
                break

        return risks

    def _calculate_growth_score(self, hook_score: int, retention_prediction: str,
                               emotion_curve: Dict[str, Any], info_density: Dict[str, Any],
                               follow_reasons: List[Dict[str, Any]], risks: Dict[str, Any]) -> int:
        """计算增长评分"""
        weights = {
            "hook": 25,
            "retention": 20,
            "emotion": 20,
            "density": 15,
            "follow_reasons": 15,
            "risk_penalty": -10,
        }

        score = 0

        score += min(100, hook_score) * weights["hook"] / 100

        retention_scores = {"high": 90, "medium": 65, "low": 30}
        score += retention_scores.get(retention_prediction, 50) * weights["retention"] / 100

        score += emotion_curve["avg_match_score"] * weights["emotion"] / 100

        score += info_density["score"] * weights["density"] / 100

        if follow_reasons:
            avg_reason_strength = sum(r["strength"] for r in follow_reasons) / len(follow_reasons)
            score += avg_reason_strength * weights["follow_reasons"] / 100

        risk_count = sum(1 for v in risks.values() if v)
        score += risk_count * weights["risk_penalty"]

        return max(0, min(100, round(score)))

    def _generate_suggestions(self, growth_score: int, hook_score: int,
                             retention_prediction: str, emotion_curve: Dict[str, Any],
                             info_density: Dict[str, Any], risks: Dict[str, Any]) -> List[str]:
        """生成优化建议"""
        suggestions = []

        if hook_score < 70:
            suggestions.append("前三秒缺少吸引力，建议增加悬念、冲突或痛点")

        if retention_prediction == "low":
            suggestions.append("前3秒留存预测较低，建议重新设计开头")

        if emotion_curve["avg_match_score"] < 60:
            suggestions.append("情绪曲线不够流畅，建议调整各段落情绪设计")

        if info_density["status"] == "sparse":
            suggestions.append(f"信息密度偏低（{info_density['chars_per_second']}字/秒），建议增加内容")
        elif info_density["status"] == "dense":
            suggestions.append(f"信息密度偏高（{info_density['chars_per_second']}字/秒），建议精简文案")

        if risks["commercial_too_early"]:
            suggestions.append("产品出现过早，建议将产品介绍移至30秒以后")

        if risks["hard_sell"]:
            suggestions.append("营销意图过于明显，建议降低商业密度")

        if risks["effect_exaggeration"]:
            suggestions.append("存在功效夸大风险，建议修改表述方式")

        if risks["sensitive_content"]:
            suggestions.append("内容包含敏感词，建议替换或删除")

        if growth_score < 70 and not suggestions:
            suggestions.append("整体增长潜力不足，建议重新构思内容结构")

        return suggestions

    def suggest_revision(self, job_id: int) -> Dict[str, Any]:
        """生成修改建议"""
        assessment = self.assess_growth_quality(job_id)
        if not assessment["success"]:
            return assessment

        if assessment["can_produce"]:
            return {"success": True, "message": "视频质量合格，可以生产"}

        plan = self._get_plan(self._get_job(job_id).source_plan_id)
        if not plan:
            return {"success": False, "error": "导演方案不存在"}

        suggestions = assessment["suggestions"]
        script_content = plan.script_content or ""

        revision_prompt = f"""请根据以下增长质量检测结果，修改短视频文案：

当前文案：
{script_content}

检测问题：
{chr(10).join(suggestions)}

修改要求：
1. 当前阶段：涨粉期（不要直接介绍产品）
2. 结构：用户兴趣 → 情绪价值 → 知识价值 → 主播人格 → 自然关注
3. 前三秒必须制造冲突或悬念
4. 产品信息移至后半段（如果有）
5. 避免硬广词汇：产品、购买、下单、价格、优惠、活动等
6. 增加个人经历或真实感受
7. 时长控制在原时长左右

请返回修改后的完整文案。"""

        try:
            result = self.gateway.call_tool(
                "llm_completion",
                prompt=revision_prompt,
                max_tokens=1500,
            )

            if result.get("success"):
                revised_content = result["data"].get("content", script_content)
                return {
                    "success": True,
                    "revised_content": revised_content,
                    "suggestions_applied": suggestions,
                }

            return {"success": False, "error": "LLM修改失败"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_job(self, job_id: int):
        return self.db.query(VideoProductionJob).filter(VideoProductionJob.id == job_id).first()

    def _get_plan(self, plan_id: int):
        if not plan_id:
            return None
        return self.db.query(VideoEditPlan).filter(VideoEditPlan.id == plan_id).first()

    def _get_segments(self, plan_id: int):
        if not plan_id:
            return []
        return self.db.query(VideoEditSegment).filter(
            VideoEditSegment.edit_plan_id == plan_id
        ).order_by(VideoEditSegment.sequence).all()

    def _get_timeline_items(self, job_id: int):
        return self.db.query(VideoTimeline).filter(
            VideoTimeline.production_job_id == job_id
        ).order_by(VideoTimeline.sequence).all()
