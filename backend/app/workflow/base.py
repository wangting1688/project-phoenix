from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import json

from app.models import WorkflowTask, ContentProject
from app.core.database import SessionLocal


class BaseWorkflow(ABC):
    def __init__(self, project_id: int):
        self.project_id = project_id
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

    @abstractmethod
    def execute(self, input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pass

    def close(self):
        self.db.close()
