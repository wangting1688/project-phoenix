from typing import Dict, Any, Optional
import json
import time

from app.workflow.base import BaseWorkflow
from app.workflow.content_workflow import ContentAnalysisWorkflow
from app.workflow.planning_workflow import PlanningWorkflow
from app.workflow.script_workflow import ScriptWorkflow
from app.workflow.review_workflow import ReviewWorkflow
from app.workflow.video_workflow import VideoGenerationWorkflow
from app.workflow.optimization_workflow import OptimizationWorkflow
from app.models import ContentProject, WorkflowTask, AITask
from app.core.database import SessionLocal


class WorkflowOrchestrator:
    WORKFLOW_STEPS = [
        "analyzing",
        "planning",
        "scripting",
        "reviewing",
        "generating_video",
        "optimizing",
        "completed"
    ]

    AGENT_MAP = {
        "analyzing": "Content Agent",
        "planning": "Planning Agent",
        "scripting": "Script Agent",
        "reviewing": "Review Agent",
        "generating_video": "Video Agent",
        "optimizing": "Operation Agent",
    }

    def __init__(self, project_id: int, topic: str, user_id: int = None):
        self.project_id = project_id
        self.topic = topic
        self.user_id = user_id
        self.db = SessionLocal()
        self.states = {
            "content_result": None,
            "planning_result": None,
            "script_result": None,
            "review_result": None,
            "video_result": None,
            "operation_result": None,
            "error": None,
            "completed": False
        }
        self.ai_tasks = []

    def execute(self) -> Dict[str, Any]:
        try:
            step_result = self._run_step("analyzing", self._run_content_analysis)
            if not step_result["success"]:
                return self._build_error_result(step_result)
            self.states["content_result"] = step_result["data"]

            step_result = self._run_step("planning", self._run_planning, self.states["content_result"])
            if not step_result["success"]:
                return self._build_error_result(step_result)
            self.states["planning_result"] = step_result["data"]

            step_result = self._run_step("scripting", self._run_scripting, self.states["planning_result"])
            if not step_result["success"]:
                return self._build_error_result(step_result)
            self.states["script_result"] = step_result["data"]

            step_result = self._run_step("reviewing", self._run_reviewing, self.states["script_result"])
            if not step_result["success"]:
                return self._build_error_result(step_result)
            self.states["review_result"] = step_result["data"]

            step_result = self._run_step("generating_video", self._run_video_generation, self.states["script_result"])
            if not step_result["success"]:
                return self._build_error_result(step_result)
            self.states["video_result"] = step_result["data"]

            step_result = self._run_step("optimizing", self._run_optimization, self.states["script_result"])
            if not step_result["success"]:
                return self._build_error_result(step_result)
            self.states["operation_result"] = step_result["data"]

            self.states["completed"] = True
            self._mark_completed()

        except Exception as e:
            self.states["error"] = str(e)
            self._log_ai_task("orchestrator", "System", "failed", 
                              input_data={"topic": self.topic}, 
                              output_data={"error": str(e)},
                              error_message=str(e))
            self._mark_failed(str(e))

        finally:
            self.db.close()

        return self._build_final_result()

    def _run_step(self, step_name: str, step_func, input_data: Any = None) -> Dict[str, Any]:
        agent_name = self.AGENT_MAP.get(step_name, step_name)
        self._log_ai_task(step_name, agent_name, "running", input_data=input_data)

        start_time = time.time()
        try:
            if input_data is not None:
                result = step_func(input_data)
            else:
                result = step_func()
            duration = time.time() - start_time

            self._log_ai_task(step_name, agent_name, "completed", 
                              input_data=input_data, output_data=result.get("data"),
                              duration=duration)
            return result
        except Exception as e:
            duration = time.time() - start_time
            self._log_ai_task(step_name, agent_name, "failed",
                              input_data=input_data, output_data={"error": str(e)},
                              duration=duration)
            raise

    def _run_content_analysis(self) -> Dict[str, Any]:
        workflow = ContentAnalysisWorkflow(self.project_id, self.topic)
        result = workflow.execute()
        workflow.close()
        return result

    def _run_planning(self, content_result: Dict[str, Any]) -> Dict[str, Any]:
        workflow = PlanningWorkflow(self.project_id)
        result = workflow.execute(content_result)
        workflow.close()
        return result

    def _run_scripting(self, planning_result: Dict[str, Any]) -> Dict[str, Any]:
        workflow = ScriptWorkflow(self.project_id, self.topic)
        result = workflow.execute(planning_result)
        workflow.close()
        return result

    def _run_reviewing(self, script_result: Dict[str, Any]) -> Dict[str, Any]:
        workflow = ReviewWorkflow(self.project_id)
        result = workflow.execute(script_result)
        workflow.close()
        return result

    def _run_video_generation(self, script_result: Dict[str, Any]) -> Dict[str, Any]:
        workflow = VideoGenerationWorkflow(self.project_id)
        result = workflow.execute(script_result)
        workflow.close()
        return result

    def _run_optimization(self, script_result: Dict[str, Any]) -> Dict[str, Any]:
        workflow = OptimizationWorkflow(self.project_id, self.topic)
        result = workflow.execute(script_result)
        workflow.close()
        return result

    def _log_ai_task(self, workflow: str, agent: str, status: str, 
                     input_data: Any = None, output_data: Any = None,
                     duration: float = 0.0, cost: float = 0.0,
                     model: str = None, tokens_input: int = 0, tokens_output: int = 0,
                     error_message: str = None):
        try:
            ai_task = AITask(
                user_id=self.user_id,
                project_id=self.project_id,
                workflow=workflow,
                agent=agent,
                model=model,
                status=status,
                input=json.loads(json.dumps(input_data, ensure_ascii=False)) if input_data else None,
                output=json.loads(json.dumps(output_data, ensure_ascii=False)) if output_data else None,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                cost=cost,
                duration=duration,
                error_message=error_message,
            )
            self.db.add(ai_task)
            self.db.commit()
            self.db.refresh(ai_task)
            self.ai_tasks.append(ai_task.id)
        except Exception:
            self.db.rollback()

    def _mark_completed(self):
        project = self.db.query(ContentProject).filter(
            ContentProject.id == self.project_id
        ).first()
        if project:
            project.workflow_status = "completed"
            project.status = "completed"
            self.db.commit()

        task = self.db.query(WorkflowTask).filter(
            WorkflowTask.project_id == self.project_id,
            WorkflowTask.task_type == "full_creation"
        ).first()
        if task:
            task.status = "completed"
            task.progress = 100
            self.db.commit()

    def _mark_failed(self, error: str):
        project = self.db.query(ContentProject).filter(
            ContentProject.id == self.project_id
        ).first()
        if project:
            project.workflow_status = "failed"
            project.status = "failed"
            self.db.commit()

        task = self.db.query(WorkflowTask).filter(
            WorkflowTask.project_id == self.project_id,
            WorkflowTask.task_type == "full_creation"
        ).first()
        if task:
            task.status = "failed"
            task.progress = 0
            task.result = error
            self.db.commit()

    def _build_error_result(self, step_result: Dict[str, Any]) -> Dict[str, Any]:
        self.states["error"] = step_result["error"]
        return self._build_final_result()

    def _build_final_result(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "completed": self.states["completed"],
            "error": self.states["error"],
            "content_result": self.states["content_result"],
            "planning_result": self.states["planning_result"],
            "script_result": self.states["script_result"],
            "review_result": self.states["review_result"],
            "video_result": self.states["video_result"],
            "operation_result": self.states["operation_result"],
            "ai_tasks": self.ai_tasks,
        }