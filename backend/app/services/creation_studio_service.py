from typing import Dict, Any, Optional
from datetime import datetime

from app.core.database import SessionLocal
from app.models import (
    CreationSession, ContentProject, ContentOpportunity,
    Planning, Script, Review, Content, WorkflowTask
)
from app.workflow.orchestrator import WorkflowOrchestrator


class CreationStudioService:
    """AI创作工作台服务 - 统一创作入口"""

    STYLE_TEMPLATES = {
        "story": {
            "name": "故事版",
            "description": "以真实案例或故事切入，引发情感共鸣",
            "structure": "故事引入 → 问题分析 → 解决方案 → 行动号召",
        },
        "knowledge": {
            "name": "科普版",
            "description": "专业知识科普，建立权威形象",
            "structure": "核心观点 → 原理解释 → 实用建议 → 总结",
        },
        "emotion": {
            "name": "情绪版",
            "description": "直击痛点，引发强烈情绪共鸣",
            "structure": "痛点提问 → 情绪激发 → 共鸣建立 → 引导行动",
        },
    }

    TONE_OPTIONS = {
        "friendly": "亲切",
        "professional": "专业",
        "casual": "朋友聊天",
    }

    DURATION_OPTIONS = {
        30: "30秒",
        60: "60秒",
        90: "90秒",
    }

    def __init__(self):
        self.db = SessionLocal()

    def create_session(
        self,
        user_id: int,
        source_type: str,
        opportunity_id: Optional[int] = None,
        topic: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> CreationSession:
        """创建创作会话"""
        merged_config = dict(config or {})
        if topic and "topic" not in merged_config:
            merged_config["topic"] = topic
        session = CreationSession(
            user_id=user_id,
            source_type=source_type,
            opportunity_id=opportunity_id,
            workflow_state="init",
            current_step="config",
            status="active",
            config=merged_config,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: int) -> Optional[CreationSession]:
        """获取创作会话"""
        return self.db.query(CreationSession).filter(
            CreationSession.id == session_id
        ).first()

    def get_user_active_sessions(self, user_id: int) -> list:
        """获取用户活跃会话"""
        return self.db.query(CreationSession).filter(
            CreationSession.user_id == user_id,
            CreationSession.status == "active"
        ).order_by(CreationSession.updated_at.desc()).all()

    def configure_session(
        self,
        session_id: int,
        style: str,
        duration: int,
        tone: str,
    ) -> CreationSession:
        """配置创作参数"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError("创作会话不存在")

        merged = dict(session.config or {})
        merged.update({
            "style": style,
            "duration": duration,
            "tone": tone,
            "style_name": self.STYLE_TEMPLATES.get(style, {}).get("name", style),
            "tone_name": self.TONE_OPTIONS.get(tone, tone),
        })
        session.config = merged
        session.current_step = "planning"
        self.db.commit()
        self.db.refresh(session)
        return session

    def generate_content(self, session_id: int) -> Dict[str, Any]:
        """生成完整内容（Planning + Script + Review）"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError("创作会话不存在")

        topic = self._get_topic(session)
        config = session.config or {}

        # 创建项目
        project = ContentProject(
            user_id=session.user_id,
            source_type=session.source_type,
            topic=topic,
            status="generating",
            workflow_status="planning",
        )
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)

        session.project_id = project.id
        session.workflow_state = "generating"
        session.current_step = "planning"
        self.db.commit()

        # 创建 Planning
        planning = Planning(
            project_id=project.id,
            target=f"生成{config.get('duration', 60)}秒{config.get('style_name', '')}风格短视频",
            style=config.get("style", "story"),
            duration=config.get("duration", 60),
            scene=config.get("tone_name", "亲切"),
            strategy=f"采用{config.get('style_name')}结构，语气为{config.get('tone_name')}",
        )
        self.db.add(planning)
        self.db.commit()

        session.current_step = "scripting"
        self.db.commit()

        # 创建 Script（模拟AI生成）
        script_content = self._generate_mock_script(topic, config)
        script = Script(
            project_id=project.id,
            type=config.get("style", "story"),
            content=script_content,
            version=1,
            score=85.0,
        )
        self.db.add(script)
        self.db.commit()

        session.current_step = "reviewing"
        self.db.commit()

        # 创建 Review
        review = Review(
            project_id=project.id,
            original_score=88.0,
            marketing_score=85.0,
            risk_score=95.0,
            consult_score=82.0,
            result="pass",
        )
        self.db.add(review)

        # 创建 Content
        content = Content(
            project_id=project.id,
            title=topic,
            summary=script_content[:200] + "...",
            audience="30-55岁关注健康的中青年人群",
            emotion=config.get("tone_name", "亲切"),
            tags=[config.get("style", "story"), config.get("tone", "friendly")],
            score=85.0,
        )
        self.db.add(content)

        # 更新项目状态
        project.status = "ready"
        project.workflow_status = "completed"

        session.workflow_state = "completed"
        session.current_step = "completed"
        session.status = "completed"
        session.result = {
            "project_id": project.id,
            "script_content": script_content,
            "planning": {
                "target": planning.target,
                "style": planning.style,
                "duration": planning.duration,
                "strategy": planning.strategy,
            },
            "review": {
                "original_score": float(review.original_score),
                "marketing_score": float(review.marketing_score),
                "risk_score": float(review.risk_score),
                "consult_score": float(review.consult_score),
                "result": review.result,
            }
        }

        self.db.commit()

        return {
            "session_id": session.id,
            "project_id": project.id,
            "topic": topic,
            "config": config,
            "script": script_content,
            "planning": {
                "target": planning.target,
                "style": planning.style,
                "duration": planning.duration,
                "strategy": planning.strategy,
            },
            "review": {
                "original_score": float(review.original_score),
                "marketing_score": float(review.marketing_score),
                "risk_score": float(review.risk_score),
                "consult_score": float(review.consult_score),
                "result": review.result,
            }
        }

    def get_session_result(self, session_id: int) -> Optional[Dict[str, Any]]:
        """获取创作结果"""
        session = self.get_session(session_id)
        if not session:
            return None

        return {
            "session_id": session.id,
            "status": session.status,
            "current_step": session.current_step,
            "config": session.config,
            "result": session.result,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        }

    def _get_topic(self, session: CreationSession) -> str:
        """获取创作主题"""
        if session.opportunity_id:
            opportunity = self.db.query(ContentOpportunity).filter(
                ContentOpportunity.id == session.opportunity_id
            ).first()
            if opportunity:
                return opportunity.title

        if session.config and session.config.get("topic"):
            return session.config["topic"]

        return "未命名主题"

    def _generate_mock_script(self, topic: str, config: Dict[str, Any]) -> str:
        """生成模拟脚本（后续替换为真实AI生成）"""
        style = config.get("style", "story")
        duration = config.get("duration", 60)
        tone = config.get("tone_name", "亲切")

        if style == "story":
            return f"""【故事版 - {topic}】

开头（5秒）：
"你有没有发现，身边越来越多30岁以后的朋友，明明睡够了8小时，第二天还是没精神？"

故事引入（15秒）：
"我的一位朋友李姐，今年42岁，之前也是这样。她试过各种方法，换枕头、买眼罩、喝助眠茶...但都没有用。"

问题分析（15秒）：
"后来她才了解到，问题的关键不在睡眠时长，而在于睡眠质量。30岁以后，人体深度睡眠的比例会自然下降。"

解决方案（15秒）：
"今天我分享3个真正有效的方法，帮助提升深度睡眠质量：
第一，睡前1小时远离蓝光；
第二，保持卧室温度在18-22度；
第三，建立固定的入睡仪式。"

行动号召（10秒）：
"如果你也有睡眠困扰，评论区告诉我，我会根据你的情况给出更具体的建议。"
"""
        elif style == "knowledge":
            return f"""【科普版 - {topic}】

核心观点（5秒）：
"30岁以后睡眠质量下降，核心原因是深度睡眠比例减少。"

原理解释（25秒）：
"人体的睡眠分为浅睡眠和深睡眠。深睡眠是身体修复的关键阶段。研究表明，30岁以后，深睡眠时间每年减少约2%。这不是缺觉，而是睡眠结构发生了变化。"

实用建议（20秒）：
"改善方法：
1. 调整作息节律，固定入睡时间
2. 控制午后咖啡因摄入
3. 增加日间运动量
4. 睡前进行放松训练"

总结（10秒）：
"记住，睡眠质量比时长更重要。关注深度睡眠，才能真正恢复精力。"
"""
        else:  # emotion
            return f"""【情绪版 - {topic}】

痛点提问（5秒）：
"你是不是也觉得，30岁以后，睡觉越来越累？"

情绪激发（20秒）：
"早上闹钟响了三次才爬起来，上班路上还在打哈欠，开会时注意力根本无法集中...你以为是工作太累？不，是睡眠质量出了问题！"

共鸣建立（20秒）：
"很多人以为只要睡够8小时就够了。但你知道吗？如果你一直在浅睡眠中徘徊，睡10小时也不如别人深度睡眠3小时！"

引导行动（15秒）：
"今天这个视频，我会告诉你为什么30岁以后睡眠越来越差，以及一个很多人不知道但非常有效的方法。"
"""

    def get_style_templates(self) -> Dict[str, Any]:
        """获取风格模板"""
        return self.STYLE_TEMPLATES

    def get_tone_options(self) -> Dict[str, str]:
        """获取语气选项"""
        return self.TONE_OPTIONS

    def get_duration_options(self) -> Dict[int, str]:
        """获取时长选项"""
        return self.DURATION_OPTIONS

    def close(self):
        self.db.close()