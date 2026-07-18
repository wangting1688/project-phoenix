import os
import json
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import PromptTemplate


class PromptService:
    PROMPT_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts")

    def __init__(self):
        self.db = SessionLocal()

    def load_prompt(self, prompt_name: str) -> str:
        db_prompt = self.db.query(PromptTemplate).filter(
            PromptTemplate.name == prompt_name,
            PromptTemplate.status == "active"
        ).first()
        if db_prompt:
            return db_prompt.content

        file_path = os.path.join(self.PROMPT_DIR, f"{prompt_name}.txt")
        file_path = os.path.abspath(file_path)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Prompt file not found: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def format_prompt(self, prompt_template: str, **kwargs) -> str:
        for key, value in kwargs.items():
            prompt_template = prompt_template.replace(f"{{{key}}}", str(value))
        return prompt_template

    def get_prompt(self, prompt_name: str, **kwargs) -> str:
        template = self.load_prompt(prompt_name)
        return self.format_prompt(template, **kwargs)

    def list_prompts(self) -> list:
        prompts = self.db.query(PromptTemplate).all()
        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "status": p.status,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
            for p in prompts
        ]

    def get_prompt_by_id(self, prompt_id: int) -> Optional[dict]:
        prompt = self.db.query(PromptTemplate).filter(
            PromptTemplate.id == prompt_id
        ).first()
        if not prompt:
            return None
        return {
            "id": prompt.id,
            "name": prompt.name,
            "description": prompt.description,
            "content": prompt.content,
            "status": prompt.status,
            "version": prompt.version,
            "updated_at": prompt.updated_at.isoformat() if prompt.updated_at else None,
        }

    def create_prompt(self, data: Dict[str, Any]) -> dict:
        prompt = PromptTemplate(
            name=data["name"],
            description=data.get("description", ""),
            content=data["content"],
            status=data.get("status", "active"),
            version=1,
        )
        self.db.add(prompt)
        self.db.commit()
        self.db.refresh(prompt)
        return {
            "id": prompt.id,
            "name": prompt.name,
            "status": prompt.status,
        }

    def update_prompt(self, prompt_id: int, data: Dict[str, Any]) -> Optional[dict]:
        prompt = self.db.query(PromptTemplate).filter(
            PromptTemplate.id == prompt_id
        ).first()
        if not prompt:
            return None

        if "name" in data:
            prompt.name = data["name"]
        if "description" in data:
            prompt.description = data["description"]
        if "content" in data:
            prompt.content = data["content"]
            prompt.version += 1
        if "status" in data:
            prompt.status = data["status"]

        self.db.commit()
        self.db.refresh(prompt)
        return {
            "id": prompt.id,
            "name": prompt.name,
            "version": prompt.version,
            "status": prompt.status,
        }

    def delete_prompt(self, prompt_id: int) -> bool:
        prompt = self.db.query(PromptTemplate).filter(
            PromptTemplate.id == prompt_id
        ).first()
        if not prompt:
            return False
        self.db.delete(prompt)
        self.db.commit()
        return True

    def close(self):
        self.db.close()
