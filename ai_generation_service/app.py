"""
FastAPI application entry point for the AI Generation Service.

Initializes providers, template management, services, and routes,
and manages the application lifecycle (startup/shutdown).
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from .config.settings import get_settings
from .events.publisher import EventPublisher
from .routes.generation_routes import router as generation_router
from .routes.health_routes import router as health_router
from .routes.template_routes import router as template_router
from .services.bedrock_provider import BedrockProvider
from .services.fallback_provider import FallbackProvider
from .services.generation_service import GenerationService
from .services.template_manager import TemplateManager
from .services.template_renderer import TemplateRenderer

logger = logging.getLogger(__name__)

# Module-level references for dependency injection
_generation_service: Optional[GenerationService] = None
_template_manager: Optional[TemplateManager] = None


def get_app_generation_service() -> GenerationService:
    """Return the initialized GenerationService instance."""
    if _generation_service is None:
        raise RuntimeError("GenerationService has not been initialized.")
    return _generation_service


def get_app_template_manager() -> TemplateManager:
    """Return the initialized TemplateManager instance."""
    if _template_manager is None:
        raise RuntimeError("TemplateManager has not been initialized.")
    return _template_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown."""
    global _generation_service, _template_manager

    settings = get_settings()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    logger.info("Starting AI Generation Service v%s", settings.SERVICE_VERSION)

    # ---- Template Management ----
    templates_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "prompt_templates",
    )
    _template_manager = TemplateManager(templates_dir=templates_dir)
    loaded = _template_manager.load_templates()
    logger.info("Loaded %d prompt templates from %s", loaded, templates_dir)

    template_renderer = TemplateRenderer(template_manager=_template_manager)

    # ---- AI Providers ----
    primary_provider = BedrockProvider(
        region=settings.BEDROCK_REGION,
        model_id=settings.BEDROCK_MODEL_ID,
        timeout_seconds=settings.BEDROCK_TIMEOUT_SECONDS,
        max_retries=settings.BEDROCK_MAX_RETRIES,
        embedding_model_id=settings.BEDROCK_EMBEDDING_MODEL_ID,
    )

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

    # ---- Event Publisher ----
    event_publisher = EventPublisher(
        broker_url=settings.EVENT_BROKER_URL,
        enabled=settings.EVENT_PUBLISH_ENABLED,
    )
    await event_publisher.connect()

    # ---- Core Generation Service ----
    _generation_service = GenerationService(
        primary_provider=primary_provider,
        fallback_provider=fallback_provider,
        event_publisher=event_publisher,
        template_renderer=template_renderer,
        settings=settings,
    )

    logger.info("AI Generation Service initialized successfully.")

    yield

    # Shutdown
    logger.info("Shutting down AI Generation Service...")
    await event_publisher.disconnect()
    _generation_service = None
    _template_manager = None


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="ECHO AI Generation Service",
        description=(
            "AI execution engine for the ECHO platform. Provides template-managed, "
            "model-agnostic text generation with prompt template registration, "
            "rendering, retry, and fallback capabilities."
        ),
        version=settings.SERVICE_VERSION,
        lifespan=lifespan,
    )

    # Register routes
    app.include_router(generation_router)
    app.include_router(template_router)
    app.include_router(health_router)

    return app


# Application instance for ASGI servers (e.g., uvicorn)
app = create_app()
