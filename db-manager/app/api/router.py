from fastapi import APIRouter

from app.api.routes import health, internal, memories, profile

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(internal.router, prefix="/internal", tags=["internal"])
api_router.include_router(memories.router, tags=["memories"])
api_router.include_router(profile.router, tags=["profile"])

