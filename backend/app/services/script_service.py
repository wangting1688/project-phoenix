from typing import Dict, Any, Optional
import json

from app.core.database import SessionLocal
from app.models import Script, ContentProject
from app.services.ai_service import AIService
from app.services.prompt_service import PromptService


class ScriptService:
    def __init__(self):
        self.db = SessionLocal()
        self.ai_service = AIService()
        self.prompt_service = PromptService()

    def generate_script(self, topic: str, planning_data: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self.prompt_service.get_prompt(
            "script_expert",
            topic=topic,
            planning=json.dumps(planning_data, ensure_ascii=False)
        )
        result = self.ai_service.generate(prompt)
        return result

    def save_scripts(self, project_id: int, script_data: Dict[str, Any]) -> list:
        saved = []
        script_types = [
            ("story", "story_version"),
            ("knowledge", "knowledge_version"),
            ("chat", "chat_version"),
        ]

        for script_type, key in script_types:
            content = script_data.get(key, "")
            if content:
                script = Script(
                    project_id=project_id,
                    type=script_type,
                    content=content,
                    version=1,
                    score=script_data.get("score", {}).get("total")
                )
                self.db.add(script)
                saved.append({"type": script_type, "id": script.id})

        self.db.commit()
        return saved

    def get_project_scripts(self, project_id: int) -> list:
        scripts = self.db.query(Script).filter(Script.project_id == project_id).all()
        return [
            {
                "id": s.id,
                "type": s.type,
                "content": s.content,
                "version": s.version,
                "score": s.score,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in scripts
        ]

    def get_script_by_id(self, script_id: int) -> Optional[dict]:
        script = self.db.query(Script).filter(Script.id == script_id).first()
        if not script:
            return None
        return {
            "id": script.id,
            "project_id": script.project_id,
            "type": script.type,
            "content": script.content,
            "version": script.version,
            "score": script.score,
            "created_at": script.created_at.isoformat() if script.created_at else None,
        }

    def update_script(self, script_id: int, content: str) -> Optional[dict]:
        script = self.db.query(Script).filter(Script.id == script_id).first()
        if not script:
            return None
        script.content = content
        script.version += 1
        self.db.commit()
        self.db.refresh(script)
        return {"id": script.id, "version": script.version}

    def close(self):
        self.db.close()
        self.prompt_service.close()
