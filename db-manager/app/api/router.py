from fastapi import APIRouter, Depends

from app.api.auth import require_admin_api_key, require_api_key
from app.api.routes import health, internal, memories, profile, relationship_db, scheduled_events, templates

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(
    internal.router,
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(require_admin_api_key)],
)
api_router.include_router(memories.router, tags=["memories"], dependencies=[Depends(require_api_key)])
api_router.include_router(profile.router, tags=["profile"], dependencies=[Depends(require_api_key)])
api_router.include_router(relationship_db.router, dependencies=[Depends(require_api_key)])
api_router.include_router(templates.router, dependencies=[Depends(require_api_key)])
api_router.include_router(scheduled_events.router, dependencies=[Depends(require_api_key)])
