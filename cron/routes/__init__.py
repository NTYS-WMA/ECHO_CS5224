"""Routes module for the Cron Service v2.0."""

from .health_routes import router as health_router
from .scheduler_routes import router as scheduler_router
from .task_routes import router as task_router

__all__ = ["health_router", "scheduler_router", "task_router"]
