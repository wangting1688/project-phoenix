from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.creation import router as creation_router
from app.api.tasks import router as tasks_router
from app.api.content import router as content_router
from app.api.footage import router as footage_router
from app.api.intelligence import router as intelligence_router
from app.api.video import router as video_router
from app.api.content_hub import router as content_hub_router
from app.api.creator_profile import router as creator_profile_router
from app.api.creation_studio import router as creation_studio_router
from app.api.viral_analysis import router as viral_analysis_router
from app.api.content_quality import router as content_quality_router
from app.api.video_production import router as video_production_router
from app.api.shooting_assistant import router as shooting_assistant_router
from app.api.asset_collection import router as asset_collection_router
from app.api.asset_intelligence import router as asset_intelligence_router
from app.api.asset_segment import router as asset_segment_router
from app.api.video_director import router as video_director_router
from app.api.director_learning import router as director_learning_router
from app.api.agent_gateway import router as agent_gateway_router
from app.api.production_execution import router as production_execution_router
from app.api.growth_quality import router as growth_quality_router
from app.api.growth_review import router as growth_review_router
from app.api.growth_decision_graph import router as growth_decision_router
from app.api.growth_insights import router as growth_insights_router
from app.api.growth_causal_graph import router as growth_causal_router
from app.api.ingest import router as ingest_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(creation_router)
api_router.include_router(tasks_router)
api_router.include_router(content_router)
api_router.include_router(footage_router)
api_router.include_router(intelligence_router)
api_router.include_router(video_router)
api_router.include_router(content_hub_router)
api_router.include_router(creator_profile_router)
api_router.include_router(creation_studio_router)
api_router.include_router(viral_analysis_router)
api_router.include_router(content_quality_router)
api_router.include_router(video_production_router)
api_router.include_router(shooting_assistant_router)
api_router.include_router(asset_collection_router)
api_router.include_router(asset_intelligence_router)
api_router.include_router(asset_segment_router)
api_router.include_router(video_director_router)
api_router.include_router(director_learning_router)
api_router.include_router(agent_gateway_router)
api_router.include_router(production_execution_router)
api_router.include_router(growth_quality_router)
api_router.include_router(growth_review_router)
api_router.include_router(growth_decision_router)
api_router.include_router(growth_insights_router)
api_router.include_router(growth_causal_router)
api_router.include_router(ingest_router)
