"""
FastAPI application entry point for the Proactive Engagement Service.

Initializes clients, services, event consumer/publisher, and routes,
and manages the application lifecycle (startup/shutdown).
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from .config.settings import get_settings
from .events.consumer import EventConsumer
from .events.publisher import EventPublisher
from .routes.engagement_routes import router as engagement_router
from .routes.health_routes import router as health_router
from .services.ai_generation_client import AIGenerationServiceClient
from .services.eligibility_checker import EligibilityChecker
from .services.engagement_service import ProactiveEngagementService
from .services.memory_client import MemoryServiceClient
from .services.relationship_client import RelationshipServiceClient
from .services.user_profile_client import UserProfileServiceClient

logger = logging.getLogger(__name__)

# Module-level reference for dependency injection
_engagement_service: Optional[ProactiveEngagementService] = None


def get_app_engagement_service() -> ProactiveEngagementService:
    """Return the initialized ProactiveEngagementService instance."""
    if _engagement_service is None:
        raise RuntimeError("ProactiveEngagementService has not been initialized.")
    return _engagement_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown."""
    global _engagement_service

    settings = get_settings()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    logger.info("Starting Proactive Engagement Service v%s", settings.SERVICE_VERSION)

    # Initialize HTTP clients for dependent services
    relationship_client = RelationshipServiceClient(
        base_url=settings.RELATIONSHIP_SERVICE_BASE_URL,
        timeout_seconds=settings.HTTP_TIMEOUT_SECONDS,
    )

    user_profile_client = UserProfileServiceClient(
        base_url=settings.USER_PROFILE_SERVICE_BASE_URL,
        timeout_seconds=settings.HTTP_TIMEOUT_SECONDS,
    )

    ai_generation_client = AIGenerationServiceClient(
        base_url=settings.AI_GENERATION_SERVICE_BASE_URL,
        timeout_seconds=30,  # AI generation may take longer
    )

    memory_client = MemoryServiceClient(
        base_url=settings.MEMORY_SERVICE_BASE_URL,
        timeout_seconds=settings.HTTP_TIMEOUT_SECONDS,
    )

    # Initialize eligibility checker
    eligibility_checker = EligibilityChecker(
        default_quiet_start=settings.DEFAULT_QUIET_HOURS_START,
        default_quiet_end=settings.DEFAULT_QUIET_HOURS_END,
    )

    # Initialize event publisher
    event_publisher = EventPublisher(
        broker_url=settings.EVENT_BROKER_URL,
        enabled=settings.EVENT_PUBLISH_ENABLED,
    )
    await event_publisher.connect()

    # Initialize the core engagement service
    _engagement_service = ProactiveEngagementService(
        relationship_client=relationship_client,
        user_profile_client=user_profile_client,
        ai_generation_client=ai_generation_client,
        memory_client=memory_client,
        eligibility_checker=eligibility_checker,
        event_publisher=event_publisher,
        settings=settings,
    )

    # Initialize and start event consumer
    event_consumer = EventConsumer(
        broker_url=settings.EVENT_BROKER_URL,
        enabled=settings.EVENT_CONSUME_ENABLED,
    )
    event_consumer.register_scan_handler(_engagement_service.handle_scan_trigger)
    await event_consumer.start()

    logger.info("Proactive Engagement Service initialized successfully.")

    yield

    # Shutdown
    logger.info("Shutting down Proactive Engagement Service...")
    await event_consumer.stop()
    await event_publisher.disconnect()
    _engagement_service = None


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="ECHO Proactive Engagement Service",
        description=(
            "Determines when ECHO should initiate outbound engagement, manages "
            "candidate selection, policy checking, and message dispatch pipeline."
        ),
        version=settings.SERVICE_VERSION,
        lifespan=lifespan,
    )

    # Register routes
    app.include_router(engagement_router)
    app.include_router(health_router)

    return app


# Application instance for ASGI servers (e.g., uvicorn)
app = create_app()
