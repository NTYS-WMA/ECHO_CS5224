"""Routes module for the Cron Service v3.0."""

from .health_routes import router as health_router
from .schedule_routes import router as schedule_router

__all__ = ["health_router", "schedule_router"]
