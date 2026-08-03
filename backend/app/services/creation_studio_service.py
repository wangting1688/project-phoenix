from typing import Dict, Any, Optional
from datetime import datetime

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models import (
    CreationSession, ContentProject, ContentOpportunity,
    Planning, Script, Review, Content, WorkflowTask, User
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

    def __init__(self, db: Optional[Session] = None):
        # 支持 API 层 Depends(get_db) 注入, 消除嵌套 SessionLocal 引发的 sqlite 单写者锁
        if db is not None:
            self.db = db
            self._owns_db = False
        else:
            self.db = SessionLocal()
            self._owns_db = True

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

        # 创建项目前校验视频项目配额
        from app.services import tenant_service
        owner = self.db.query(User).filter(User.id == session.user_id).first()
        if owner:
            tenant_service.ensure_project_quota(self.db, owner)

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

        # 真实 AI 生成文案 (原为硬编码模板, 产出的是假文案)
        ai_result = self._generate_script_by_ai(topic, config)
        script_content = ai_result["content"]

        script = Script(
            project_id=project.id,
            type=config.get("style", "story"),
            content=script_content,
            version=1,
            score=ai_result["score"],
        )
        self.db.add(script)
        self.db.commit()

        session.current_step = "reviewing"
        self.db.commit()

        # 真实 AI 合规审核 (原为硬编码 pass)
        review_result = self._review_by_ai(script_content)
        review = Review(
            project_id=project.id,
            original_score=ai_result["score"],
            marketing_score=None,
            risk_score=review_result["risk_score"],
            consult_score=None,
            result=review_result["result"],
        )
        self.db.add(review)

        content = Content(
            project_id=project.id,
            title=topic,
            summary=script_content[:200],
            audience="30-55岁关注健康的中青年人群",
            emotion=config.get("tone_name", "亲切"),
            tags=[config.get("style", "story"), config.get("tone", "friendly")],
            score=ai_result["score"],
        )
        self.db.add(content)

        project.status = "ready"
        project.workflow_status = "completed"

        session.workflow_state = "completed"
        session.current_step = "completed"
        session.status = "completed"

        result_payload = {
            "session_id": session.id,
            "project_id": project.id,
            "topic": topic,
            "config": config,
            "script": script_content,
            "ai_generated": ai_result["ai_generated"],
            "planning": {
                "target": planning.target,
                "style": planning.style,
                "duration": planning.duration,
                "strategy": planning.strategy,
            },
            "review": {
                "original_score": ai_result["score"],
                "risk_score": review_result["risk_score"],
                "result": review_result["result"],
                "problems": review_result["problems"],
            },
        }
        session.result = result_payload
        self.db.commit()

        return result_payload

    def _generate_script_by_ai(self, topic: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """调用真实 AI 生成文案, 按配置的风格挑选对应版本"""
        from app.experts.ai_expert import AIExpertService

        planning_hint = {
            "style": config.get("style_name") or config.get("style", "story"),
            "tone": config.get("tone_name") or config.get("tone", "friendly"),
            "duration": config.get("duration", 60),
            "structure": self.STYLE_TEMPLATES.get(
                config.get("style", "story"), {}
            ).get("structure", ""),
        }
        ai = AIExpertService()
        result = ai.script_expert(topic, planning_hint)

        version_key = {
            "story": "story_version",
            "knowledge": "knowledge_version",
            "emotion": "chat_version",
        }.get(config.get("style", "story"), "story_version")

        content = (result.get(version_key) or result.get("story_version") or "").strip()
        if not content:
            raise ValueError("AI 未生成有效文案，请稍后重试")

        score = (result.get("score") or {}).get("total")
        return {
            "content": content,
            "score": float(score) if score is not None else None,
            "ai_generated": True,
        }

    def _review_by_ai(self, script_content: str) -> Dict[str, Any]:
        """调用真实 AI 做合规审核"""
        from app.experts.ai_expert import AIExpertService

        ai = AIExpertService()
        result = ai.compliance_expert(script_content)
        return {
            "risk_score": result.get("risk_score"),
            "result": "pass" if result.get("pass") else "fail",
            "problems": result.get("problems") or [],
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