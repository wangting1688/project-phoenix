from typing import Dict, Any, Optional
import re
import random

from app.core.database import SessionLocal
from app.models import ViralAnalysisSession, ViralPattern, ContentOpportunity, CreatorProfile
from app.services.ai_service import AIService
from app.services.prompt_service import PromptService


class ViralAnalysisService:
    """AI爆款逆向工程服务 - 拆解爆款成功因素，生成原创机会"""

    def __init__(self):
        self.db = SessionLocal()
        self.ai_service = AIService()
        self.prompt_service = PromptService()

    def create_analysis_session(self, user_id: int, video_url: str) -> ViralAnalysisSession:
        """创建分析会话"""
        platform = self._extract_platform(video_url)
        
        session = ViralAnalysisSession(
            user_id=user_id,
            video_url=video_url,
            platform=platform,
            status="pending",
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def analyze_video(self, session_id: int) -> Dict[str, Any]:
        """执行完整分析流程"""
        session = self.db.query(ViralAnalysisSession).filter(
            ViralAnalysisSession.id == session_id
        ).first()

        if not session:
            raise ValueError("分析会话不存在")

        session.status = "analyzing"
        self.db.commit()

        # 1. 获取基础信息
        basic_info = self._extract_basic_info(session.video_url)
        session.original_data = basic_info

        # 2. AI内容分析
        analysis_result = self._run_ai_analysis(basic_info, session.user_id)
        session.analysis_result = analysis_result

        # 3. 计算主播匹配度
        match_score = self._calculate_creator_match(session.user_id, analysis_result)
        session.creator_match_score = match_score
        analysis_result["creator_match_score"] = match_score

        # 4. 更新状态
        session.status = "completed"
        self.db.commit()

        # 5. 记录爆款规律
        self._save_viral_pattern(analysis_result)

        return analysis_result

    def generate_opportunity(self, session_id: int) -> Dict[str, Any]:
        """基于分析结果生成原创内容机会"""
        session = self.db.query(ViralAnalysisSession).filter(
            ViralAnalysisSession.id == session_id
        ).first()

        if not session or not session.analysis_result:
            raise ValueError("分析会话不存在或未完成分析")

        analysis = session.analysis_result
        creator_profile = self.db.query(CreatorProfile).filter(
            CreatorProfile.user_id == session.user_id
        ).first()

        creator_info = {}
        if creator_profile:
            creator_info = {
                "age": creator_profile.age,
                "gender": creator_profile.gender,
                "style": creator_profile.style,
                "good_topics": creator_profile.good_topics or [],
                "category": creator_profile.category,
            }

        original_title = self._generate_original_title(analysis, creator_info)

        opportunity = ContentOpportunity(
            title=original_title,
            category=analysis.get("category", "健康知识"),
            subcategory=analysis.get("subcategory", ""),
            opening=analysis.get("hook", ""),
            summary=analysis.get("summary", ""),
            pain_point=analysis.get("pain_point", ""),
            recommend_reason=f"基于爆款视频逆向工程生成，原视频爆点：{analysis.get('viral_points', '')}",
            trend_score=analysis.get("trend_score", 80),
            consult_score=analysis.get("consult_score", 75),
            creator_match=session.creator_match_score,
            original_score=90,
            source="viral_analysis",
            source_url=session.video_url,
        )
        opportunity.final_score = self._calculate_final_score(
            opportunity.trend_score,
            opportunity.consult_score,
            opportunity.creator_match,
            opportunity.original_score
        )

        self.db.add(opportunity)
        self.db.commit()
        self.db.refresh(opportunity)

        session.opportunity_id = opportunity.id
        self.db.commit()

        return {
            "session_id": session.id,
            "opportunity_id": opportunity.id,
            "opportunity": {
                "id": opportunity.id,
                "title": opportunity.title,
                "category": opportunity.category,
                "opening": opportunity.opening,
                "final_score": opportunity.final_score,
            },
            "original_analysis": analysis,
        }

    def get_analysis_result(self, session_id: int) -> Optional[Dict[str, Any]]:
        """获取分析结果"""
        session = self.db.query(ViralAnalysisSession).filter(
            ViralAnalysisSession.id == session_id
        ).first()

        if not session:
            return None

        return {
            "session_id": session.id,
            "video_url": session.video_url,
            "platform": session.platform,
            "status": session.status,
            "creator_match_score": session.creator_match_score,
            "original_data": session.original_data,
            "analysis_result": session.analysis_result,
            "opportunity_id": session.opportunity_id,
            "created_at": session.created_at.isoformat() if session.created_at else None,
        }

    def _extract_platform(self, url: str) -> str:
        """从URL提取平台"""
        if "kuaishou.com" in url or "ksdaren.com" in url:
            return "快手"
        elif "douyin.com" in url or "tiktok.com" in url:
            return "抖音"
        elif "weixin.qq.com" in url or "mp.weixin.qq.com" in url:
            return "视频号"
        return "未知"

    def _extract_basic_info(self, url: str) -> Dict[str, Any]:
        """提取视频基础信息（模拟，实际应调用平台API）"""
        return {
            "title": self._generate_mock_title(url),
            "platform": self._extract_platform(url),
            "duration": random.randint(30, 120),
            "like_count": random.randint(10000, 500000),
            "comment_count": random.randint(500, 20000),
            "share_count": random.randint(1000, 50000),
            "collect_count": random.randint(500, 30000),
        }

    def _generate_mock_title(self, url: str) -> str:
        """生成模拟标题"""
        titles = [
            "为什么很多人睡够8小时还是累？这个方法帮你解决",
            "30岁以后身体越来越差？这三个习惯一定要改",
            "吃了这么多年早餐，原来我一直吃错了",
            "失眠的人一定要看！这几种食物千万不能吃",
            "为什么女性更容易失眠？医生终于说出真相",
            "每天坚持这5分钟，一个月后身体大变样",
            "别再瞎养生了！这几个误区很多人都踩过",
            "压力大睡不好？试试这个简单方法",
            "40岁以后，这三个部位一定要保护好",
            "为什么你减肥总是反弹？原因在这里",
        ]
        return titles[hash(url) % len(titles)]

    def _run_ai_analysis(self, basic_info: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """执行AI分析（模拟）"""
        hook_types = ["反常识提问", "痛点直击", "数据冲击", "案例引入", "悬念设置"]
        content_structures = [
            {"opening": "3秒制造疑问", "middle": "案例故事", "climax": "认知反转", "ending": "引导评论"},
            {"opening": "数据对比", "middle": "原理解释", "ending": "行动建议"},
            {"opening": "个人经历", "middle": "解决方案", "ending": "引导关注"},
        ]
        emotions = ["害怕失去健康", "希望改善状态", "寻求简单方法", "渴望被理解"]

        hook_type = hook_types[random.randint(0, len(hook_types) - 1)]
        structure = content_structures[random.randint(0, len(content_structures) - 1)]
        viral_score = random.randint(80, 98)

        return {
            "basic_info": basic_info,
            "content_structure": structure,
            "hook_type": hook_type,
            "hook": f"大家都知道{basic_info['title'][:10]}，但是很少有人知道真正的原因...",
            "viral_points": f"{hook_type} + 中年人健康焦虑 + 简单可操作的解决方案",
            "viral_score": viral_score,
            "emotions": random.sample(emotions, 3),
            "category": "健康知识",
            "subcategory": "生活方式",
            "target_audience": "30-55岁关注健康的人群",
            "pain_point": "健康问题困扰，但找不到有效解决方案",
            "summary": f"该视频通过{hook_type}的方式，成功吸引目标观众，结合真实案例和科学解释，引发强烈共鸣，最终引导用户互动。",
            "trend_score": random.randint(75, 95),
            "consult_score": random.randint(70, 95),
            "commercial_fit": {
                "fit_for": ["健康知识账号", "咨询型主播", "生活方式博主"],
                "not_fit_for": ["纯带货账号", "娱乐搞笑账号"],
            },
            "success_factors": [
                "开头3秒抓住注意力",
                "内容结构清晰，逻辑严谨",
                "情感共鸣强烈",
                "结尾引导互动",
            ],
        }

    def _calculate_creator_match(self, user_id: int, analysis: Dict[str, Any]) -> int:
        """计算主播匹配度"""
        profile = self.db.query(CreatorProfile).filter(
            CreatorProfile.user_id == user_id
        ).first()

        if not profile:
            return random.randint(60, 85)

        score = 60

        good_topics = profile.good_topics or []
        category = analysis.get("category", "")
        if good_topics and any(topic in category for topic in good_topics):
            score += 20

        if profile.category and profile.category in analysis.get("commercial_fit", {}).get("fit_for", []):
            score += 15

        return min(100, score + random.randint(0, 10))

    def _generate_original_title(self, analysis: Dict[str, Any], creator_info: Dict[str, Any]) -> str:
        """基于分析结果生成原创标题"""
        gender = creator_info.get("gender", "")
        age = creator_info.get("age", "")

        title_patterns = [
            f"为什么很多{age or '30岁'}以后的人，{analysis.get('pain_point', '健康问题')}？",
            f"{analysis.get('hook_type', '')}：{analysis.get('viral_points', '')}",
            f"我试了很多方法，终于找到{analysis.get('category', '')}的关键",
            f"别再被误导了！{analysis.get('category', '')}的真相在这里",
        ]

        if gender == "女":
            title_patterns.append(f"女性朋友一定要看！{analysis.get('category', '')}的秘密")
        elif gender == "男":
            title_patterns.append(f"男士必看！{analysis.get('category', '')}的正确做法")

        return title_patterns[random.randint(0, len(title_patterns) - 1)]

    def _calculate_final_score(self, trend: int, consult: int, match: int, original: int) -> float:
        """计算最终评分"""
        return round(trend * 0.30 + consult * 0.35 + match * 0.25 + original * 0.10, 1)

    def _save_viral_pattern(self, analysis: Dict[str, Any]):
        """记录爆款规律"""
        hook_type = analysis.get("hook_type", "")
        category = analysis.get("category", "")
        audience = analysis.get("target_audience", "")

        pattern = self.db.query(ViralPattern).filter(
            ViralPattern.hook_type == hook_type,
            ViralPattern.category == category
        ).first()

        if pattern:
            pattern.examples_count += 1
            pattern.success_rate = min(100, pattern.success_rate + 2)
        else:
            pattern = ViralPattern(
                hook_type=hook_type,
                audience=audience,
                category=category,
                conversion_level="high" if analysis.get("viral_score", 0) > 90 else "medium",
                pattern_description=analysis.get("viral_points", ""),
                examples_count=1,
                success_rate=analysis.get("viral_score", 80),
                tags=analysis.get("success_factors", []),
            )
            self.db.add(pattern)

        self.db.commit()

    def close(self):
        self.db.close()
        self.prompt_service.close()