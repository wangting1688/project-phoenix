from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.creation import router as creation_router
from app.api.tasks import router as tasks_router
from app.api.content import router as content_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(creation_router)
api_router.include_router(tasks_router)
api_router.include_router(content_router)
