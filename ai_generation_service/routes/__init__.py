from .generation_routes import router as generation_router
from .health_routes import router as health_router

__all__ = ["generation_router", "health_router"]
