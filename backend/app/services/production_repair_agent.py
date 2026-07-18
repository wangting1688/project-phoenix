"""
Production Repair Agent - 生产失败自动修复Agent

TASK-016.3B.2：AI生产执行引擎

核心职责：
1. 检测生产过程中的问题
2. 自动修复或建议修复方案
3. 支持素材不足、字幕过密、前三秒弱等场景
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.video_production import VideoProductionJob, VideoProductionStep, VideoTimeline, ProductionBlockTask
from app.models.video_edit_plan import VideoEditPlan, VideoEditSegment
from app.models.asset_segment import AssetSegment
from app.services.agent_tool_gateway import AgentToolGateway
from app.services.growth_quality_agent_v2 import GrowthQualityAgentV2


class ProductionRepairAgent:
    """生产修复Agent"""

    ISSUE_TYPES = {
        "material_missing": {"priority": "high", "auto_repair": False},
        "material_insufficient": {"priority": "medium", "auto_repair": True},
        "caption_too_dense": {"priority": "medium", "auto_repair": True},
        "hook_weak": {"priority": "high", "auto_repair": True},
        "duration_exceeded": {"priority": "medium", "auto_repair": True},
        "content_repetition": {"priority": "low", "auto_repair": True},
        "no_conflict": {"priority": "high", "auto_repair": True},
        "commercial_too_early": {"priority": "high", "auto_repair": True},
        "weak_expression": {"priority": "medium", "auto_repair": False},
        "emotion_flat": {"priority": "medium", "auto_repair": True},
    }

    READING_SPEEDS = {
        "douyin": 5,
        "wechat_video": 4,
        "xiaohongshu": 4.5,
        "kuaishou": 5,
    }

    HOOK_THRESHOLD = 0.6

    def __init__(self):
        self.db = SessionLocal()
        self.gateway = AgentToolGateway()

    def close(self):
        self.db.close()

    def inspect_job(self, job_id: int) -> Dict[str, Any]:
        """检查生产任务中的问题"""
        job = self._get_job(job_id)
        if not job:
            return {"success": False, "error": "任务不存在"}

        issues = []

        issues.extend(self._check_material_issues(job_id))
        issues.extend(self._check_caption_issues(job_id))
        issues.extend(self._check_hook_issues(job_id))
        issues.extend(self._check_duration_issues(job_id))
        issues.extend(self._check_content_issues(job_id))

        if issues:
            return {
                "success": True,
                "job_id": job_id,
                "has_issues": True,
                "issues": issues,
                "recommendations": self._generate_recommendations(issues),
            }

        return {
            "success": True,
            "job_id": job_id,
            "has_issues": False,
            "issues": [],
            "message": "未发现问题",
        }

    def auto_repair(self, job_id: int) -> Dict[str, Any]:
        """自动修复问题"""
        inspection = self.inspect_job(job_id)
        if not inspection["success"] or not inspection["has_issues"]:
            return inspection

        issues = inspection["issues"]
        repaired_issues = []
        unrepairable_issues = []

        for issue in issues:
            issue_type = issue["type"]
            config = self.ISSUE_TYPES.get(issue_type, {})

            if config.get("auto_repair", False):
                result = self._repair_issue(job_id, issue)
                if result["success"]:
                    repaired_issues.append({**issue, "repaired": True})
                else:
                    unrepairable_issues.append({**issue, "reason": result["error"]})
            else:
                unrepairable_issues.append({**issue, "reason": "需要人工处理"})

        return {
            "success": True,
            "job_id": job_id,
            "repaired_count": len(repaired_issues),
            "unrepairable_count": len(unrepairable_issues),
            "repaired_issues": repaired_issues,
            "unrepairable_issues": unrepairable_issues,
        }

    def _check_material_issues(self, job_id: int) -> List[Dict[str, Any]]:
        """检查素材问题"""
        issues = []

        timelines = self.db.query(VideoTimeline).filter(
            VideoTimeline.production_job_id == job_id
        ).all()

        for timeline in timelines:
            if not timeline.material_found:
                issues.append({
                    "type": "material_missing",
                    "priority": "high",
                    "timeline_id": timeline.id,
                    "role": timeline.role,
                    "required_duration": timeline.end_time - timeline.start_time,
                    "message": f"缺少{timeline.role}素材",
                })

            elif timeline.material_gap > 0:
                issues.append({
                    "type": "material_insufficient",
                    "priority": "medium",
                    "timeline_id": timeline.id,
                    "role": timeline.role,
                    "gap_duration": timeline.material_gap,
                    "message": f"{timeline.role}素材时长不足，缺口{timeline.material_gap:.1f}秒",
                })

        return issues

    def _check_caption_issues(self, job_id: int) -> List[Dict[str, Any]]:
        """检查字幕问题"""
        issues = []

        job = self._get_job(job_id)
        if not job:
            return issues

        plan = self._get_plan(job.source_plan_id)
        if not plan:
            return issues

        platform = job.target_platforms[0] if job.target_platforms else "wechat_video"
        reading_speed = self.READING_SPEEDS.get(platform, 4)

        script_content = plan.script_content or ""
        duration = plan.total_duration or 60

        if duration > 0:
            char_count = len(script_content)
            actual_speed = char_count / duration

            if actual_speed > reading_speed * 1.5:
                issues.append({
                    "type": "caption_too_dense",
                    "priority": "medium",
                    "platform": platform,
                    "expected_speed": reading_speed,
                    "actual_speed": round(actual_speed, 1),
                    "message": f"字幕过密，{platform}建议{reading_speed}字/秒，当前{actual_speed:.1f}字/秒",
                })

        return issues

    def _check_hook_issues(self, job_id: int) -> List[Dict[str, Any]]:
        """检查前三秒Hook问题"""
        issues = []

        job = self._get_job(job_id)
        if not job:
            return issues

        plan = self._get_plan(job.source_plan_id)
        if not plan:
            return issues

        hook_score = getattr(plan, "hook_score", 0) / 100 if hasattr(plan, "hook_score") else 0

        if hook_score < self.HOOK_THRESHOLD:
            issues.append({
                "type": "hook_weak",
                "priority": "high",
                "hook_score": hook_score,
                "threshold": self.HOOK_THRESHOLD,
                "message": f"前三秒吸引力不足，评分{hook_score:.2f}，低于阈值{self.HOOK_THRESHOLD}",
            })

        return issues

    def _check_duration_issues(self, job_id: int) -> List[Dict[str, Any]]:
        """检查时长问题"""
        issues = []

        job = self._get_job(job_id)
        if not job:
            return issues

        platform = job.target_platforms[0] if job.target_platforms else "wechat_video"

        duration_limits = {
            "douyin": 35,
            "wechat_video": 60,
            "xiaohongshu": 45,
            "kuaishou": 40,
        }

        limit = duration_limits.get(platform, 60)
        actual_duration = job.total_duration or 0

        if actual_duration > limit * 1.2:
            issues.append({
                "type": "duration_exceeded",
                "priority": "medium",
                "platform": platform,
                "actual_duration": actual_duration,
                "limit": limit,
                "message": f"视频时长{actual_duration}秒，超过{platform}建议上限{limit}秒",
            })

        return issues

    def _check_content_issues(self, job_id: int) -> List[Dict[str, Any]]:
        """检查内容问题"""
        issues = []

        job = self._get_job(job_id)
        if not job:
            return issues

        plan = self._get_plan(job.source_plan_id)
        if not plan:
            return issues

        script_content = plan.script_content or ""

        issues.extend(self._check_conflict_issues(script_content))
        issues.extend(self._check_commercial_timing_issues(job_id, plan))
        issues.extend(self._check_emotion_issues(job_id, plan))

        return issues

    def _check_conflict_issues(self, script_content: str) -> List[Dict[str, Any]]:
        """检查冲突问题"""
        issues = []

        first_50_chars = script_content[:50]

        conflict_keywords = ["为什么", "你不知道", "秘密", "真相", "矛盾", "不要", "其实", "反而"]
        has_conflict = any(keyword in first_50_chars for keyword in conflict_keywords)

        if not has_conflict and len(first_50_chars) > 0:
            issues.append({
                "type": "no_conflict",
                "priority": "high",
                "message": "前5秒缺少冲突或悬念",
                "suggestion": "建议在开头增加冲突、悬念或痛点",
            })

        return issues

    def _check_commercial_timing_issues(self, job_id: int, plan: VideoEditPlan) -> List[Dict[str, Any]]:
        """检查商业时机问题"""
        issues = []

        script_content = plan.script_content or ""
        commercial_words = ["产品", "购买", "下单", "价格", "优惠", "活动", "买", "送", "功效", "效果"]

        commercial_positions = []
        for word in commercial_words:
            idx = script_content.find(word)
            if idx != -1:
                commercial_positions.append(idx)

        if commercial_positions:
            first_commercial = min(commercial_positions)
            ratio = first_commercial / len(script_content)

            if ratio < 0.3:
                issues.append({
                    "type": "commercial_too_early",
                    "priority": "high",
                    "position": first_commercial,
                    "ratio": round(ratio, 2),
                    "message": f"产品出现过早（位置{first_commercial}，占比{ratio:.2f}）",
                    "suggestion": "建议将产品介绍移至30%以后",
                })

        return issues

    def _check_emotion_issues(self, job_id: int, plan: VideoEditPlan) -> List[Dict[str, Any]]:
        """检查情绪问题"""
        issues = []

        segments = self.db.query(VideoEditSegment).filter(
            VideoEditSegment.edit_plan_id == plan.id
        ).all()

        emotion_variety = set()
        for segment in segments:
            effect_config = segment.effect_config or {}
            emotion = effect_config.get("emotion", "neutral")
            emotion_variety.add(emotion)

        if len(emotion_variety) <= 2:
            issues.append({
                "type": "emotion_flat",
                "priority": "medium",
                "emotions": list(emotion_variety),
                "message": "情绪曲线过于平淡，缺少起伏",
                "suggestion": "建议增加情绪变化，如好奇→共鸣→希望",
            })

        return issues

    def _repair_issue(self, job_id: int, issue: Dict[str, Any]) -> Dict[str, Any]:
        """修复单个问题"""
        issue_type = issue["type"]

        if issue_type == "material_insufficient":
            return self._repair_material_insufficient(job_id, issue)
        elif issue_type == "caption_too_dense":
            return self._repair_caption_too_dense(job_id, issue)
        elif issue_type == "hook_weak":
            return self._repair_hook_weak(job_id, issue)
        elif issue_type == "duration_exceeded":
            return self._repair_duration_exceeded(job_id, issue)
        elif issue_type == "no_conflict":
            return self._repair_no_conflict(job_id, issue)
        elif issue_type == "commercial_too_early":
            return self._repair_commercial_too_early(job_id, issue)
        elif issue_type == "emotion_flat":
            return self._repair_emotion_flat(job_id, issue)
        else:
            return {"success": False, "error": f"不支持自动修复: {issue_type}"}

    def _repair_material_insufficient(self, job_id: int, issue: Dict[str, Any]) -> Dict[str, Any]:
        """修复素材不足"""
        timeline_id = issue["timeline_id"]
        gap_duration = issue["gap_duration"]

        timeline = self.db.query(VideoTimeline).filter(VideoTimeline.id == timeline_id).first()
        if not timeline:
            return {"success": False, "error": "时间线不存在"}

        timeline.end_time = timeline.start_time + (timeline.material_duration or 5.0)
        self.db.commit()

        job = self._get_job(job_id)
        if job:
            job.total_duration = sum(
                t.end_time - t.start_time
                for t in self.db.query(VideoTimeline).filter(VideoTimeline.production_job_id == job_id).all()
            )
            self.db.commit()

        return {"success": True, "data": {"adjusted_duration": timeline.end_time - timeline.start_time}}

    def _repair_caption_too_dense(self, job_id: int, issue: Dict[str, Any]) -> Dict[str, Any]:
        """修复字幕过密"""
        job = self._get_job(job_id)
        if not job:
            return {"success": False, "error": "任务不存在"}

        plan = self._get_plan(job.source_plan_id)
        if not plan:
            return {"success": False, "error": "导演方案不存在"}

        script_content = plan.script_content or ""
        platform = issue["platform"]
        reading_speed = self.READING_SPEEDS.get(platform, 4)

        try:
            optimized_text = self.gateway.call_tool(
                "llm_completion",
                prompt=f"请优化以下字幕文本，使其符合{platform}平台{reading_speed}字/秒的阅读速度要求，保持原意但删减冗余内容：\n\n{script_content}",
                max_tokens=1000,
            )

            if optimized_text.get("success"):
                plan.script_content = optimized_text["data"].get("content", script_content)
                self.db.commit()
                return {"success": True, "data": {"optimized": True}}

            return {"success": False, "error": "LLM优化失败"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _repair_hook_weak(self, job_id: int, issue: Dict[str, Any]) -> Dict[str, Any]:
        """修复Hook弱"""
        job = self._get_job(job_id)
        if not job:
            return {"success": False, "error": "任务不存在"}

        plan = self._get_plan(job.source_plan_id)
        if not plan:
            return {"success": False, "error": "导演方案不存在"}

        try:
            new_hook = self.gateway.call_tool(
                "llm_completion",
                prompt=f"请为以下产品生成一个更吸引人的3秒开头文案，要求：\n1. 痛点直击\n2. 制造悬念\n3. 引发好奇\n\n产品：{plan.product_name or ''}\n产品类别：{plan.product_category or ''}\n原文案：{plan.script_content[:100] if plan.script_content else ''}",
                max_tokens=50,
            )

            if new_hook.get("success"):
                new_content = new_hook["data"].get("content", "") + (plan.script_content[100:] if plan.script_content else "")
                plan.script_content = new_content
                plan.hook_score = 85
                self.db.commit()
                return {"success": True, "data": {"new_hook": new_content[:50]}}

            return {"success": False, "error": "Hook生成失败"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _repair_duration_exceeded(self, job_id: int, issue: Dict[str, Any]) -> Dict[str, Any]:
        """修复时长超限"""
        job = self._get_job(job_id)
        if not job:
            return {"success": False, "error": "任务不存在"}

        plan = self._get_plan(job.source_plan_id)
        if not plan:
            return {"success": False, "error": "导演方案不存在"}

        target_duration = issue["limit"]
        current_duration = issue["actual_duration"]

        try:
            optimized_script = self.gateway.call_tool(
                "llm_completion",
                prompt=f"请将以下视频文案精简到{target_duration}秒以内，保留核心信息，删减非必要内容：\n\n当前时长：{current_duration}秒\n目标时长：{target_duration}秒\n\n文案：{plan.script_content}",
                max_tokens=1000,
            )

            if optimized_script.get("success"):
                plan.script_content = optimized_script["data"].get("content", plan.script_content)
                plan.total_duration = target_duration
                job.total_duration = target_duration
                self.db.commit()
                return {"success": True, "data": {"target_duration": target_duration}}

            return {"success": False, "error": "文案精简失败"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _repair_no_conflict(self, job_id: int, issue: Dict[str, Any]) -> Dict[str, Any]:
        """修复缺少冲突问题"""
        job = self._get_job(job_id)
        if not job:
            return {"success": False, "error": "任务不存在"}

        plan = self._get_plan(job.source_plan_id)
        if not plan:
            return {"success": False, "error": "导演方案不存在"}

        script_content = plan.script_content or ""

        try:
            revised_hook = self.gateway.call_tool(
                "llm_completion",
                prompt=f"请为以下短视频开头增加冲突或悬念：\n\n当前开头：{script_content[:50]}\n\n要求：\n1. 制造好奇心\n2. 提出反常识观点\n3. 引发用户共鸣\n4. 保持原主题\n5. 不要超过50字\n\n请返回修改后的开头：",
                max_tokens=50,
            )

            if revised_hook.get("success"):
                new_hook = revised_hook["data"].get("content", "")
                new_content = new_hook + script_content[50:]
                plan.script_content = new_content
                self.db.commit()
                return {"success": True, "data": {"new_hook": new_hook}}

            return {"success": False, "error": "Hook修改失败"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _repair_commercial_too_early(self, job_id: int, issue: Dict[str, Any]) -> Dict[str, Any]:
        """修复产品出现过早问题"""
        job = self._get_job(job_id)
        if not job:
            return {"success": False, "error": "任务不存在"}

        plan = self._get_plan(job.source_plan_id)
        if not plan:
            return {"success": False, "error": "导演方案不存在"}

        script_content = plan.script_content or ""

        try:
            revised_content = self.gateway.call_tool(
                "llm_completion",
                prompt=f"请将以下文案中的产品介绍移至后半部分（30%以后），前半部分增加用户兴趣、情绪价值和知识价值：\n\n当前文案：\n{script_content}\n\n修改原则：\n1. 当前阶段：涨粉期（不要直接介绍产品）\n2. 结构：用户兴趣 → 情绪价值 → 知识价值 → 主播人格 → 自然关注\n3. 产品信息移至30%以后\n4. 避免硬广词汇\n5. 增加个人经历或真实感受\n\n请返回修改后的完整文案：",
                max_tokens=1000,
            )

            if revised_content.get("success"):
                plan.script_content = revised_content["data"].get("content", script_content)
                self.db.commit()
                return {"success": True, "data": {"revised": True}}

            return {"success": False, "error": "文案修改失败"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _repair_emotion_flat(self, job_id: int, issue: Dict[str, Any]) -> Dict[str, Any]:
        """修复情绪平淡问题"""
        job = self._get_job(job_id)
        if not job:
            return {"success": False, "error": "任务不存在"}

        plan = self._get_plan(job.source_plan_id)
        if not plan:
            return {"success": False, "error": "导演方案不存在"}

        segments = self.db.query(VideoEditSegment).filter(
            VideoEditSegment.edit_plan_id == plan.id
        ).all()

        emotion_flow = ["curiosity", "empathy", "interest", "hope", "confidence"]

        for i, segment in enumerate(segments):
            if not segment.effect_config:
                segment.effect_config = {}
            segment.effect_config["emotion"] = emotion_flow[i % len(emotion_flow)]

        self.db.commit()

        return {"success": True, "data": {"emotion_flow": emotion_flow[:len(segments)]}}

    def _generate_recommendations(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生成修复建议"""
        recommendations = []

        for issue in issues:
            issue_type = issue["type"]

            if issue_type == "material_missing":
                recommendations.append({
                    "issue_type": issue_type,
                    "action": "create_collection_task",
                    "description": f"创建素材采集任务，拍摄{issue['role']}相关素材",
                    "priority": issue["priority"],
                })
            elif issue_type == "material_insufficient":
                recommendations.append({
                    "issue_type": issue_type,
                    "action": "extend_material",
                    "description": f"延长现有素材使用，缺口{issue['gap_duration']:.1f}秒",
                    "priority": issue["priority"],
                })
            elif issue_type == "caption_too_dense":
                recommendations.append({
                    "issue_type": issue_type,
                    "action": "optimize_caption",
                    "description": f"优化字幕，降低阅读速度",
                    "priority": issue["priority"],
                })
            elif issue_type == "hook_weak":
                recommendations.append({
                    "issue_type": issue_type,
                    "action": "regenerate_hook",
                    "description": "重新生成前三秒文案",
                    "priority": issue["priority"],
                })
            elif issue_type == "duration_exceeded":
                recommendations.append({
                    "issue_type": issue_type,
                    "action": "trim_duration",
                    "description": f"精简文案至{issue['limit']}秒以内",
                    "priority": issue["priority"],
                })
            elif issue_type == "no_conflict":
                recommendations.append({
                    "issue_type": issue_type,
                    "action": "add_conflict",
                    "description": "增加冲突或悬念",
                    "priority": issue["priority"],
                })
            elif issue_type == "commercial_too_early":
                recommendations.append({
                    "issue_type": issue_type,
                    "action": "move_commercial",
                    "description": "将产品介绍移至后半部分",
                    "priority": issue["priority"],
                })
            elif issue_type == "emotion_flat":
                recommendations.append({
                    "issue_type": issue_type,
                    "action": "enrich_emotion",
                    "description": "丰富情绪曲线",
                    "priority": issue["priority"],
                })

        return recommendations

    def _get_job(self, job_id: int):
        return self.db.query(VideoProductionJob).filter(VideoProductionJob.id == job_id).first()

    def _get_plan(self, plan_id: int):
        if not plan_id:
            return None
        return self.db.query(VideoEditPlan).filter(VideoEditPlan.id == plan_id).first()

    def create_block_task(self, job_id: int, issue: Dict[str, Any]) -> Dict[str, Any]:
        """创建阻塞任务"""
        task = ProductionBlockTask(
            production_job_id=job_id,
            timeline_id=issue.get("timeline_id"),
            block_type=issue["type"],
            priority=issue["priority"],
            status="pending",
            required_content_type=issue.get("role"),
            required_duration=issue.get("required_duration", 0),
            gap_duration=issue.get("gap_duration", 0),
            target_role=issue.get("role"),
            reason=issue["message"],
            suggested_action=self._get_suggested_action(issue),
        )

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        return {"success": True, "task_id": task.id}

    def _get_suggested_action(self, issue: Dict[str, Any]) -> str:
        """获取建议操作"""
        issue_type = issue["type"]

        if issue_type == "material_missing":
            return f"请拍摄{issue['role']}相关素材"
        elif issue_type == "material_insufficient":
            return f"请补充{issue['gap_duration']:.1f}秒{issue['role']}素材"
        elif issue_type == "caption_too_dense":
            return "请优化字幕文本，降低阅读速度"
        elif issue_type == "hook_weak":
            return "请重新设计前三秒开头"
        elif issue_type == "duration_exceeded":
            return f"请将视频精简至{issue['limit']}秒以内"
        else:
            return "请检查并修复此问题"

    def suggest_three_versions(self, job_id: int) -> Dict[str, Any]:
        """建议三版本策略"""
        growth_agent = GrowthQualityAgentV2()
        try:
            job = self._get_job(job_id)
            if not job:
                return {"success": False, "error": "任务不存在"}

            plan = self._get_plan(job.source_plan_id)
            if not plan:
                return {"success": False, "error": "导演方案不存在"}

            assessment = growth_agent.assess_growth_quality_v2(plan.id, "growth")
            if not assessment["success"]:
                return assessment

            commercial_pressure = assessment["details"]["commercial_pressure"]["index"]

            versions = []

            growth_config = self._build_growth_version_config(plan, commercial_pressure)
            versions.append({
                "version_type": "growth",
                "version_name": "纯涨粉版",
                "commercial_pressure_target": "<30",
                "config": growth_config,
                "expected_outcome": "自然流量增长，粉丝沉淀",
            })

            private_config = self._build_private_version_config(plan, commercial_pressure)
            versions.append({
                "version_type": "private_traffic",
                "version_name": "私域引流版",
                "commercial_pressure_target": "30-50",
                "config": private_config,
                "expected_outcome": "引导评论/私信/主页访问",
            })

            conversion_config = self._build_conversion_version_config(plan, commercial_pressure)
            versions.append({
                "version_type": "conversion",
                "version_name": "成交版",
                "commercial_pressure_target": "50+",
                "config": conversion_config,
                "expected_outcome": "促进GMV转化",
            })

            return {
                "success": True,
                "job_id": job_id,
                "current_commercial_pressure": commercial_pressure,
                "versions": versions,
            }
        finally:
            growth_agent.close()

    def _build_growth_version_config(self, plan: VideoEditPlan, current_pressure: int) -> Dict[str, Any]:
        """构建涨粉版配置"""
        return {
            "commercial_pressure": min(30, current_pressure),
            "product_position": "late",
            "max_commercial_words": 0,
            "structure": "用户兴趣 → 情绪价值 → 知识价值 → 主播人格 → 自然关注",
            "emphasis": "关注理由、连续剧钩子",
            "cta_type": "follow",
        }

    def _build_private_version_config(self, plan: VideoEditPlan, current_pressure: int) -> Dict[str, Any]:
        """构建私域版配置"""
        return {
            "commercial_pressure": min(50, current_pressure + 20),
            "product_position": "mid",
            "max_commercial_words": 3,
            "structure": "痛点 → 解决方案 → 案例 → 咨询引导",
            "emphasis": "轻咨询引导、评论互动",
            "cta_type": "comment_or_message",
        }

    def _build_conversion_version_config(self, plan: VideoEditPlan, current_pressure: int) -> Dict[str, Any]:
        """构建成交版配置"""
        return {
            "commercial_pressure": max(60, current_pressure),
            "product_position": "early",
            "max_commercial_words": 10,
            "structure": "产品介绍 → 使用场景 → 案例 → 活动 → 购买入口",
            "emphasis": "产品介绍、信任背书、购买引导",
            "cta_type": "purchase",
        }
