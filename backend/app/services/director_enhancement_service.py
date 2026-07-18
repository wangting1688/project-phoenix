"""
AI导演决策增强服务

TASK-016.3A.7：AI导演决策增强层

核心增强：
1. 爆款模板匹配 - 根据文案内容自动选择最佳爆款结构模板
2. 导演评分机制 - 对生成的方案进行多维度评分
3. 补拍闭环 - 缺失素材自动生成采集任务，形成闭环
"""

from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple
from app.core.database import SessionLocal
from app.models import (
    VideoScriptTemplate,
    VideoEditPlan,
    VideoEditSegment,
    AssetSegment,
    CreatorPerformanceProfile,
    AssetCollectionTask,
)


class DirectorEnhancementService:
    """AI导演决策增强服务"""

    # 导演评分权重
    SCORE_WEIGHTS = {
        "template_match": {"weight": 0.30, "max": 30},  # 爆款结构匹配 30%
        "asset_quality": {"weight": 0.25, "max": 25},   # 素材质量 25%
        "creator_fit": {"weight": 0.20, "max": 20},     # 主播适配度 20%
        "conversion": {"weight": 0.15, "max": 15},       # 商业转化 15%
        "originality": {"weight": 0.10, "max": 10},      # 原创度 10%
    }

    # 行业关键词映射
    INDUSTRY_KEYWORDS = {
        "health": ["健康", "青汁", "营养", "肠道", "免疫", "疲惫", "便秘", "40岁",
                    "保健", "养生", "膳食纤维", "维生素", "睡眠", "减肥", "排毒"],
        "beauty": ["护肤", "美白", "抗老", "皮肤", "胶原蛋白", "面膜", "精华"],
        "food": ["美食", "食谱", "做法", "食材", "厨房", "烹饪"],
        "finance": ["理财", "投资", "保险", "收入", "存款", "房贷"],
        "education": ["学习", "考试", "知识", "课程", "教育", "干货", "方法"],
    }

    # 内容类型关键词
    CONTENT_TYPE_KEYWORDS = {
        "health_warning": ["警告", "危险", "不要", "错误", "40岁", "老化", "疾病", "问题"],
        "personal_experience": ["我", "以前", "经历", "故事", "改变", "后来", "曾经"],
        "expert_explainer": ["研究", "科学", "数据", "专家", "原理", "因为", "原因", "证明"],
        "product_demo": ["推荐", "好用", "效果", "展示", "试试", "体验", "真实"],
    }

    def __init__(self, db=None):
        if db is not None:
            self.db = db
            self._owns_db = False
        else:
            self.db = SessionLocal()
            self._owns_db = True

    # ==================== 1. 爆款模板匹配 ====================

    def match_best_template(
        self, script_content: str, target_duration: int = 30
    ) -> Optional[VideoScriptTemplate]:
        """
        根据文案内容匹配最佳爆款模板

        匹配逻辑：
        1. 检测文案行业
        2. 检测内容类型
        3. 匹配时长
        4. 返回最佳匹配模板
        """
        templates = self.db.query(VideoScriptTemplate).filter(
            VideoScriptTemplate.is_active == True
        ).all()

        if not templates:
            return None

        # 计算每个模板的匹配分数
        scored_templates = []
        for tpl in templates:
            score = self._calculate_template_match_score(tpl, script_content, target_duration)
            scored_templates.append((tpl, score))

        # 按匹配分数排序
        scored_templates.sort(key=lambda x: x[1], reverse=True)

        return scored_templates[0][0] if scored_templates else None

    def _calculate_template_match_score(
        self, template: VideoScriptTemplate, script_content: str, target_duration: int
    ) -> float:
        """计算模板匹配分数"""
        score = 0.0

        # 行业匹配（40分）
        detected_industry = self._detect_industry(script_content)
        if detected_industry and template.industry == detected_industry:
            score += 40
        elif template.industry == "general":
            score += 25

        # 内容类型匹配（30分）
        detected_content_type = self._detect_content_type(script_content)
        if detected_content_type and template.content_type == detected_content_type:
            score += 30
        else:
            score += 10

        # 时长匹配（15分）
        template_duration = sum(s.get("duration", 0) for s in (template.structure or []))
        if template_duration > 0:
            duration_diff = abs(template_duration - target_duration)
            if duration_diff <= 5:
                score += 15
            elif duration_diff <= 10:
                score += 10
            else:
                score += 5

        # 模板评分（15分）
        score += (template.template_score or 0) / 100 * 15

        return score

    def _detect_industry(self, script_content: str) -> Optional[str]:
        """检测文案行业"""
        scores = {}
        for industry, keywords in self.INDUSTRY_KEYWORDS.items():
            count = sum(1 for kw in keywords if kw in script_content)
            if count > 0:
                scores[industry] = count

        if scores:
            return max(scores, key=scores.get)
        return None

    def _detect_content_type(self, script_content: str) -> Optional[str]:
        """检测内容类型"""
        scores = {}
        for content_type, keywords in self.CONTENT_TYPE_KEYWORDS.items():
            count = sum(1 for kw in keywords if kw in script_content)
            if count > 0:
                scores[content_type] = count

        if scores:
            return max(scores, key=scores.get)
        return None

    def get_template_structure(self, template: VideoScriptTemplate) -> List[Dict]:
        """获取模板结构"""
        return template.structure or []

    # ==================== 2. 导演评分机制 ====================

    def calculate_director_score(
        self,
        plan: VideoEditPlan,
        segments: List[VideoEditSegment],
        template: Optional[VideoScriptTemplate],
        profile: Optional[CreatorPerformanceProfile],
    ) -> Tuple[int, Dict[str, Any], List[str]]:
        """
        计算导演方案评分

        返回：(总分, 评分明细, 评分原因列表)
        """
        breakdown = {}
        reasons = []

        # 1. 爆款结构匹配 (30分)
        template_score, template_reasons = self._score_template_match(plan, segments, template)
        breakdown["template_match"] = {
            "score": template_score,
            "max": self.SCORE_WEIGHTS["template_match"]["max"],
            "reason": "；".join(template_reasons),
        }
        reasons.extend(template_reasons)

        # 2. 素材质量 (25分)
        asset_score, asset_reasons = self._score_asset_quality(segments)
        breakdown["asset_quality"] = {
            "score": asset_score,
            "max": self.SCORE_WEIGHTS["asset_quality"]["max"],
            "reason": "；".join(asset_reasons),
        }
        reasons.extend(asset_reasons)

        # 3. 主播适配度 (20分)
        creator_score, creator_reasons = self._score_creator_fit(segments, profile)
        breakdown["creator_fit"] = {
            "score": creator_score,
            "max": self.SCORE_WEIGHTS["creator_fit"]["max"],
            "reason": "；".join(creator_reasons),
        }
        reasons.extend(creator_reasons)

        # 4. 商业转化 (15分)
        conversion_score, conversion_reasons = self._score_conversion(segments, plan)
        breakdown["conversion"] = {
            "score": conversion_score,
            "max": self.SCORE_WEIGHTS["conversion"]["max"],
            "reason": "；".join(conversion_reasons),
        }
        reasons.extend(conversion_reasons)

        # 5. 原创度 (10分)
        originality_score, originality_reasons = self._score_originality(plan, segments)
        breakdown["originality"] = {
            "score": originality_score,
            "max": self.SCORE_WEIGHTS["originality"]["max"],
            "reason": "；".join(originality_reasons),
        }
        reasons.extend(originality_reasons)

        # 计算总分
        total_score = sum(b["score"] for b in breakdown.values())

        return min(total_score, 100), breakdown, reasons

    def _score_template_match(
        self, plan: VideoEditPlan, segments: List[VideoEditSegment], template: Optional[VideoScriptTemplate]
    ) -> Tuple[int, List[str]]:
        """评分：爆款结构匹配"""
        score = 0
        reasons = []

        if template:
            score += 20
            reasons.append(f"+ 使用爆款模板({template.name})")

            # 检查模板角色覆盖率
            template_roles = set(s.get("role") for s in (template.structure or []))
            plan_roles = set(s.role for s in segments)
            coverage = len(template_roles & plan_roles) / max(len(template_roles), 1)

            if coverage >= 0.8:
                score += 10
                reasons.append("+ 模板角色覆盖率高")
            elif coverage >= 0.6:
                score += 6
                reasons.append("+ 模板角色覆盖率中等")
            else:
                reasons.append("- 模板角色覆盖率低")

            # 模板历史效果
            if template.conversion_rate and template.conversion_rate > 0.04:
                score += 5
                reasons.append("+ 模板历史转化率优秀")
        else:
            reasons.append("- 未使用爆款模板")

        return min(score, 30), reasons

    def _score_asset_quality(self, segments: List[VideoEditSegment]) -> Tuple[int, List[str]]:
        """评分：素材质量"""
        score = 0
        reasons = []

        matched = [s for s in segments if s.match_status == "matched"]
        if not matched:
            return 5, ["- 无匹配素材"]

        match_rate = len(matched) / len(segments) if segments else 0
        if match_rate == 1.0:
            score += 15
            reasons.append("+ 所有镜头已匹配素材")
        elif match_rate >= 0.8:
            score += 10
            reasons.append("+ 80%以上镜头已匹配")
        elif match_rate >= 0.5:
            score += 5
            reasons.append("- 部分镜头缺失素材")
        else:
            reasons.append("- 大量镜头缺失素材")

        # 平均匹配分数
        avg_match_score = sum(s.match_score for s in matched) / len(matched) if matched else 0
        if avg_match_score >= 80:
            score += 10
            reasons.append("+ 素材匹配度高")
        elif avg_match_score >= 60:
            score += 6
            reasons.append("+ 素材匹配度中等")

        return min(score, 25), reasons

    def _score_creator_fit(
        self, segments: List[VideoEditSegment], profile: Optional[CreatorPerformanceProfile]
    ) -> Tuple[int, List[str]]:
        """评分：主播适配度"""
        score = 0
        reasons = []

        if not profile:
            score = 8
            reasons.append("- 暂无主播画像，使用默认评分")
            return min(score, 20), reasons

        # 主播整体表现
        if profile.overall_performance_score >= 85:
            score += 8
            reasons.append("+ 主播整体表现优秀")
        elif profile.overall_performance_score >= 70:
            score += 5
            reasons.append("+ 主播整体表现良好")

        # 最佳情绪匹配
        matched = [s for s in segments if s.match_status == "matched"]
        if matched and profile.best_emotion:
            # 检查是否有片段使用了主播最佳情绪
            best_emotion_segments = self._count_best_emotion_matches(matched, profile.best_emotion)
            if best_emotion_segments > 0:
                score += 7
                reasons.append(f"+ 匹配主播最佳情绪({profile.best_emotion})")

        # 主播擅长角色
        if profile.best_segment_roles:
            plan_roles = set(s.role for s in segments)
            good_roles = set(profile.best_segment_roles) & plan_roles
            if len(good_roles) >= 2:
                score += 5
                reasons.append("+ 使用主播擅长角色")

        return min(score, 20), reasons

    def _count_best_emotion_matches(self, segments: List[VideoEditSegment], best_emotion: str) -> int:
        """计算匹配主播最佳情绪的片段数"""
        count = 0
        for seg in segments:
            if seg.asset_segment_id:
                asset_seg = self.db.query(AssetSegment).filter(
                    AssetSegment.id == seg.asset_segment_id
                ).first()
                if asset_seg and asset_seg.emotion == best_emotion:
                    count += 1
        return count

    def _score_conversion(self, segments: List[VideoEditSegment], plan: VideoEditPlan) -> Tuple[int, List[str]]:
        """评分：商业转化"""
        score = 0
        reasons = []

        # 检查关键角色
        has_product = any(s.role == "product" and s.match_status == "matched" for s in segments)
        has_ending = any(s.role == "ending" and s.match_status == "matched" for s in segments)
        has_hook = any(s.role == "hook" and s.match_status == "matched" for s in segments)

        if has_hook:
            score += 4
            reasons.append("+ hook素材强")

        if has_product:
            score += 5
            reasons.append("+ 产品镜头完整")
        else:
            reasons.append("- 缺少产品镜头")

        if has_ending:
            score += 3
            reasons.append("+ 结尾引导完整")

        # 预测转化率
        if plan.predicted_conversion_rate >= 0.05:
            score += 3
            reasons.append("+ 预测转化率高")

        return min(score, 15), reasons

    def _score_originality(self, plan: VideoEditPlan, segments: List[VideoEditSegment]) -> Tuple[int, List[str]]:
        """评分：原创度"""
        score = 5  # 基础分
        reasons = []

        # 检查是否有独特结构
        roles = [s.role for s in segments]
        unique_roles = set(roles)

        # 非标准结构加分
        if "emotion" in unique_roles:
            score += 3
            reasons.append("+ 包含情感镜头")

        if "transition" in unique_roles:
            score += 2
            reasons.append("+ 包含转场设计")

        return min(score, 10), reasons

    # ==================== 3. 补拍闭环 ====================

    def generate_shooting_tasks(
        self, plan: VideoEditPlan, user_id: int
    ) -> List[AssetCollectionTask]:
        """
        为缺失素材自动生成采集任务

        闭环：
        AI导演 → 发现缺失 → 生成采集任务 → 主播收到通知 → 拍摄上传 → AI分析 → 重新生成方案
        """
        if not plan.shooting_suggestions:
            return []

        tasks = []
        task_ids = []

        for suggestion in plan.shooting_suggestions:
            # 检查是否已有同类任务
            existing = self.db.query(AssetCollectionTask).filter(
                AssetCollectionTask.user_id == user_id,
                AssetCollectionTask.title.like(f"%{suggestion.get('role', '')}%"),
                AssetCollectionTask.status.in_(["pending", "in_progress"]),
            ).first()

            if existing:
                task_ids.append(existing.id)
                continue

            role = suggestion.get("role", "unknown")
            task = AssetCollectionTask(
                user_id=user_id,
                title=self._generate_task_title(role, suggestion),
                description=suggestion.get("description", ""),
                priority="high" if suggestion.get("required") else "medium",
                asset_type="video",
                asset_role="creator",
                shooting_guide={
                    "scene": "正面拍摄",
                    "action": suggestion.get("description", ""),
                    "emotion": suggestion.get("emotion", "自然"),
                    "duration_min": max(suggestion.get("duration", 10), 5),
                    "duration_max": suggestion.get("duration", 30) + 10,
                    "tips": suggestion.get("tips", []),
                },
                tags=[role, suggestion.get("emotion", ""), "补拍"],
                emotion=suggestion.get("emotion"),
                status="pending",
                estimated_time=5,
                due_date=date.today(),
            )

            self.db.add(task)
            self.db.flush()
            tasks.append(task)
            task_ids.append(task.id)

        # 更新计划的采集任务关联
        plan.shooting_task_ids = task_ids
        self.db.commit()

        return tasks

    def _generate_task_title(self, role: str, suggestion: Dict) -> str:
        """生成采集任务标题"""
        role_labels = {
            "hook": "开场抓人",
            "problem": "提出问题",
            "explain": "知识解释",
            "trust": "建立信任",
            "emotion": "情感共鸣",
            "product": "产品关联",
            "ending": "结尾互动",
            "transition": "过渡转场",
        }
        role_label = role_labels.get(role, role)
        emotion = suggestion.get("emotion", "")
        duration = suggestion.get("duration", 10)
        return f"补拍-{role_label}-{emotion}-{duration}秒"

    def check_shooting_tasks_completed(self, plan_id: int) -> Dict[str, Any]:
        """
        检查补拍任务是否已完成

        如果完成，建议重新生成方案
        """
        plan = self.db.query(VideoEditPlan).filter(VideoEditPlan.id == plan_id).first()
        if not plan or not plan.shooting_task_ids:
            return {"has_tasks": False, "completed": False}

        tasks = self.db.query(AssetCollectionTask).filter(
            AssetCollectionTask.id.in_(plan.shooting_task_ids)
        ).all()

        if not tasks:
            return {"has_tasks": False, "completed": False}

        completed = [t for t in tasks if t.status == "completed"]
        pending = [t for t in tasks if t.status in ("pending", "in_progress")]

        return {
            "has_tasks": True,
            "total_tasks": len(tasks),
            "completed_count": len(completed),
            "pending_count": len(pending),
            "all_completed": len(pending) == 0,
            "can_regenerate": len(completed) > 0,
            "tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "status": t.status,
                    "uploaded_asset_id": t.uploaded_asset_id,
                }
                for t in tasks
            ],
        }

    # ==================== 查询接口 ====================

    def get_templates(
        self, template_type: Optional[str] = None, industry: Optional[str] = None
    ) -> List[VideoScriptTemplate]:
        """获取模板列表"""
        query = self.db.query(VideoScriptTemplate).filter(VideoScriptTemplate.is_active == True)
        if template_type:
            query = query.filter(VideoScriptTemplate.template_type == template_type)
        if industry:
            query = query.filter(VideoScriptTemplate.industry == industry)
        return query.order_by(VideoScriptTemplate.template_score.desc()).all()

    def get_template(self, template_id: int) -> Optional[VideoScriptTemplate]:
        """获取模板详情"""
        return self.db.query(VideoScriptTemplate).filter(VideoScriptTemplate.id == template_id).first()

    def close(self):
        if self._owns_db:
            self.db.close()
