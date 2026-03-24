from fastapi import APIRouter

from app.api.routes import health, internal

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(internal.router, prefix="/internal", tags=["internal"])

