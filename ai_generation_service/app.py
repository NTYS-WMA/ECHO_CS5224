"""
FastAPI application entry point for the AI Generation Service.

Initializes providers, services, and routes, and manages the application
lifecycle (startup/shutdown).
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from .config.settings import get_settings
from .events.publisher import EventPublisher
from .routes.generation_routes import router as generation_router
from .routes.health_routes import router as health_router
from .services.bedrock_provider import BedrockProvider
from .services.conversation_store_client import ConversationStoreClient
from .services.fallback_provider import FallbackProvider
from .services.generation_service import GenerationService

logger = logging.getLogger(__name__)

# Module-level reference for dependency injection
_generation_service: Optional[GenerationService] = None


def get_app_generation_service() -> GenerationService:
    """Return the initialized GenerationService instance."""
    if _generation_service is None:
        raise RuntimeError("GenerationService has not been initialized.")
    return _generation_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown."""
    global _generation_service

    settings = get_settings()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    logger.info("Starting AI Generation Service v%s", settings.SERVICE_VERSION)

    # Initialize primary provider (Amazon Bedrock / Claude)
    primary_provider = BedrockProvider(
        region=settings.BEDROCK_REGION,
        model_id=settings.BEDROCK_MODEL_ID,
        timeout_seconds=settings.BEDROCK_TIMEOUT_SECONDS,
        max_retries=settings.BEDROCK_MAX_RETRIES,
    )

    # Initialize fallback provider (optional)
    fallback_provider = None
    if (
        settings.FALLBACK_PROVIDER
        and settings.FALLBACK_API_BASE_URL
        and settings.FALLBACK_API_KEY
        and settings.FALLBACK_MODEL_ID
    ):
        fallback_provider = FallbackProvider(
            api_base_url=settings.FALLBACK_API_BASE_URL,
            api_key=settings.FALLBACK_API_KEY,
            model_id=settings.FALLBACK_MODEL_ID,
        )
        logger.info("Fallback provider configured: %s", settings.FALLBACK_PROVIDER)

    # Initialize event publisher
    event_publisher = EventPublisher(
        broker_url=settings.EVENT_BROKER_URL,
        enabled=settings.EVENT_PUBLISH_ENABLED,
    )
    await event_publisher.connect()

    # Initialize conversation store client
    conversation_store = ConversationStoreClient(
        base_url=settings.CONVERSATION_STORE_BASE_URL,
    )

    # Initialize the core generation service
    _generation_service = GenerationService(
        primary_provider=primary_provider,
        fallback_provider=fallback_provider,
        event_publisher=event_publisher,
        conversation_store=conversation_store,
        settings=settings,
    )

    logger.info("AI Generation Service initialized successfully.")

    yield

    # Shutdown
    logger.info("Shutting down AI Generation Service...")
    await event_publisher.disconnect()
    _generation_service = None


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="ECHO AI Generation Service",
        description=(
            "Provides model-agnostic text generation capabilities for the ECHO platform, "
            "including chat completions, memory summarization, and proactive message generation."
        ),
        version=settings.SERVICE_VERSION,
        lifespan=lifespan,
    )

    # Register routes
    app.include_router(generation_router)
    app.include_router(health_router)

    return app


# Application instance for ASGI servers (e.g., uvicorn)
app = create_app()
