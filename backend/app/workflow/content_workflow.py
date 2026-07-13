from typing import TypedDict, List, Optional, Dict, Any
import json
import time

from app.experts.ai_expert import AIExpertService
from app.models import ContentProject, Content, Planning, Script, Review, WorkflowTask, Video
from app.core.database import SessionLocal


class WorkflowState(TypedDict):
    project_id: int
    step: str
    content_result: Optional[Dict[str, Any]]
    planning_result: Optional[Dict[str, Any]]
    script_result: Optional[Dict[str, Any]]
    review_result: Optional[Dict[str, Any]]
    video_result: Optional[Dict[str, Any]]
    operation_result: Optional[Dict[str, Any]]
    error: Optional[str]
    completed: bool


class ContentCreationWorkflow:
    WORKFLOW_STEPS = [
        "analyzing",
        "planning",
        "scripting",
        "reviewing",
        "generating_video",
        "optimizing",
        "completed"
    ]

    def __init__(self, project_id: int, topic: str):
        self.project_id = project_id
        self.topic = topic
        self.ai_service = AIExpertService()
        self.db = SessionLocal()

    def _update_task(self, task_type: str, status: str, progress: int, result: Optional[str] = None):
        task = self.db.query(WorkflowTask).filter(
            WorkflowTask.project_id == self.project_id,
            WorkflowTask.task_type == task_type
        ).first()
        if task:
            task.status = status
            task.progress = progress
            if result:
                task.result = result
            self.db.commit()

    def _update_project(self, workflow_status: str):
        project = self.db.query(ContentProject).filter(
            ContentProject.id == self.project_id
        ).first()
        if project:
            project.workflow_status = workflow_status
            self.db.commit()

    def execute(self) -> WorkflowState:
        state: WorkflowState = {
            "project_id": self.project_id,
            "step": "analyzing",
            "content_result": None,
            "planning_result": None,
            "script_result": None,
            "review_result": None,
            "video_result": None,
            "operation_result": None,
            "error": None,
            "completed": False
        }

        try:
            state["content_result"] = self._step_content_analysis(state)
            if state["error"]:
                return state

            state["planning_result"] = self._step_planning(state)
            if state["error"]:
                return state

            state["script_result"] = self._step_scripting(state)
            if state["error"]:
                return state

            state["review_result"] = self._step_reviewing(state)
            if state["error"]:
                return state

            state["video_result"] = self._step_video_generation(state)
            if state["error"]:
                return state

            state["operation_result"] = self._step_optimization(state)
            if state["error"]:
                return state

            state["completed"] = True
            state["step"] = "completed"
            self._update_project("completed")
            self._update_task("full_creation", "completed", 100)

        except Exception as e:
            state["error"] = str(e)
            self._update_task("full_creation", "failed", 0, str(e))

        finally:
            self.db.close()

        return state

    def _step_content_analysis(self, state: WorkflowState) -> Optional[Dict[str, Any]]:
        self._update_project("analyzing")
        self._update_task("full_creation", "running", 10)
        
        try:
            result = self.ai_service.content_expert(self.topic)
            
            content = Content(
                project_id=self.project_id,
                title=result.get("title"),
                summary=result.get("reason"),
                audience=result.get("audience"),
                emotion=result.get("content_angle"),
                tags=json.dumps({
                    "category": result.get("category"),
                    "pain_point": result.get("pain_point")
                }),
                score=result.get("consultation_score")
            )
            self.db.add(content)
            self.db.commit()

            state["step"] = "analyzing"
            self._update_task("full_creation", "running", 20, json.dumps(result, ensure_ascii=False))
            
            return result
        except Exception as e:
            state["error"] = f"内容分析失败: {str(e)}"
            return None

    def _step_planning(self, state: WorkflowState) -> Optional[Dict[str, Any]]:
        self._update_project("planning")
        self._update_task("full_creation", "running", 25)

        try:
            result = self.ai_service.planning_expert(state["content_result"] or {})
            
            planning = Planning(
                project_id=self.project_id,
                target="建立信任",
                style=result.get("style"),
                duration=result.get("duration"),
                scene=result.get("scene"),
                strategy=result.get("structure")
            )
            self.db.add(planning)
            self.db.commit()

            state["step"] = "planning"
            self._update_task("full_creation", "running", 35, json.dumps(result, ensure_ascii=False))
            
            return result
        except Exception as e:
            state["error"] = f"策划失败: {str(e)}"
            return None

    def _step_scripting(self, state: WorkflowState) -> Optional[Dict[str, Any]]:
        self._update_project("scripting")
        self._update_task("full_creation", "running", 40)

        try:
            result = self.ai_service.script_expert(
                self.topic,
                state["planning_result"] or {}
            )

            script_story = Script(
                project_id=self.project_id,
                type="story",
                content=result.get("story_version", ""),
                version=1,
                score=result.get("score", {}).get("total")
            )
            self.db.add(script_story)

            script_knowledge = Script(
                project_id=self.project_id,
                type="knowledge",
                content=result.get("knowledge_version", ""),
                version=1,
                score=result.get("score", {}).get("total")
            )
            self.db.add(script_knowledge)

            script_chat = Script(
                project_id=self.project_id,
                type="chat",
                content=result.get("chat_version", ""),
                version=1,
                score=result.get("score", {}).get("total")
            )
            self.db.add(script_chat)

            self.db.commit()

            state["step"] = "scripting"
            self._update_task("full_creation", "running", 60, json.dumps(result, ensure_ascii=False))
            
            return result
        except Exception as e:
            state["error"] = f"文案生成失败: {str(e)}"
            return None

    def _step_reviewing(self, state: WorkflowState) -> Optional[Dict[str, Any]]:
        self._update_project("reviewing")
        self._update_task("full_creation", "running", 65)

        try:
            script = state["script_result"] or {}
            all_scripts = [
                script.get("story_version", ""),
                script.get("knowledge_version", ""),
                script.get("chat_version", "")
            ]
            combined_script = "\n\n".join(all_scripts)

            result = self.ai_service.compliance_expert(combined_script)

            review = Review(
                project_id=self.project_id,
                original_score=script.get("score", {}).get("total"),
                marketing_score=None,
                risk_score=result.get("risk_score"),
                consult_score=None,
                result="pass" if result.get("pass") else "fail"
            )
            self.db.add(review)
            self.db.commit()

            if not result.get("pass"):
                state["error"] = f"审核未通过: {result.get('problems', [])}"
                return None

            state["step"] = "reviewing"
            self._update_task("full_creation", "running", 80, json.dumps(result, ensure_ascii=False))
            
            return result
        except Exception as e:
            state["error"] = f"审核失败: {str(e)}"
            return None

    def _step_video_generation(self, state: WorkflowState) -> Optional[Dict[str, Any]]:
        self._update_project("generating_video")
        self._update_task("full_creation", "running", 85)

        try:
            script = state["script_result"] or {}
            main_script = script.get("story_version", "") or script.get("knowledge_version", "")

            result = self.ai_service.video_expert(main_script)

            video = Video(
                project_id=self.project_id,
                url=None,
                cover_url=None,
                duration=60,
                resolution="1080p",
                status="generated"
            )
            self.db.add(video)
            self.db.commit()

            state["step"] = "generating_video"
            self._update_task("full_creation", "running", 90, json.dumps(result, ensure_ascii=False))
            
            return result
        except Exception as e:
            state["error"] = f"视频生成失败: {str(e)}"
            return None

    def _step_optimization(self, state: WorkflowState) -> Optional[Dict[str, Any]]:
        self._update_project("optimizing")
        self._update_task("full_creation", "running", 95)

        try:
            script = state["script_result"] or {}
            main_script = script.get("story_version", "") or script.get("knowledge_version", "")

            result = self.ai_service.operation_expert(self.topic, main_script)

            state["step"] = "optimizing"
            self._update_task("full_creation", "running", 98, json.dumps(result, ensure_ascii=False))
            
            return result
        except Exception as e:
            state["error"] = f"运营优化失败: {str(e)}"
            return None
