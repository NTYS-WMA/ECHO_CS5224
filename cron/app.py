"""
FastAPI application entry point for the Cron Service v3.0.

Lightweight global time-trigger service.  Maintains an in-memory
schedule table and publishes events to the broker when schedules fire.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from .config.settings import get_settings
from .events.publisher import EventPublisher
from .routes.health_routes import router as health_router
from .routes.schedule_routes import router as schedule_router
from .services.scheduler import CronScheduler

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Module-level singleton (set during lifespan)
# ------------------------------------------------------------------ #

_scheduler: Optional[CronScheduler] = None


def get_app_scheduler() -> CronScheduler:
    """Return the application-level CronScheduler singleton."""
    assert _scheduler is not None, "CronScheduler not initialized."
    return _scheduler


# ------------------------------------------------------------------ #
# Application Lifespan
# ------------------------------------------------------------------ #


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Startup:
        1. Create EventPublisher.
        2. Create CronScheduler and load schedules from config.
        3. Start the scheduler background loop.

    Shutdown:
        1. Stop the scheduler.
        2. Close the EventPublisher.
    """
    global _scheduler

    settings = get_settings()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    logger.info(
        "Starting %s v%s ...",
        settings.SERVICE_NAME,
        settings.SERVICE_VERSION,
    )

    # 1. Event Publisher
    publisher = EventPublisher(
        broker_url=settings.EVENT_BROKER_URL,
        timeout_seconds=settings.EVENT_PUBLISH_TIMEOUT,
        max_retries=settings.EVENT_PUBLISH_RETRIES,
    )

    # 2. Scheduler
    _scheduler = CronScheduler(
        publisher=publisher,
        tick_interval_seconds=settings.TICK_INTERVAL_SECONDS,
    )
    _scheduler.load_schedules(settings.get_schedules())

    # 3. Start
    await _scheduler.start()

    logger.info(
        "%s v%s started (tick_interval=%ds, schedules=%d).",
        settings.SERVICE_NAME,
        settings.SERVICE_VERSION,
        settings.TICK_INTERVAL_SECONDS,
        len(_scheduler.get_schedules()),
    )

    yield  # Application is running

    # Shutdown
    logger.info("Shutting down %s ...", settings.SERVICE_NAME)
    if _scheduler and _scheduler.running:
        await _scheduler.stop()
    await publisher.close()
    _scheduler = None
    logger.info("Shutdown complete.")


# ------------------------------------------------------------------ #
# FastAPI Application
# ------------------------------------------------------------------ #


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Cron Service",
        description=(
            "Lightweight global time-trigger service for the ECHO platform.  "
            "Maintains a cron schedule table and publishes events to the "
            "internal messaging layer when schedules fire."
        ),
        version=settings.SERVICE_VERSION,
        lifespan=lifespan,
    )

    # Register routes
    app.include_router(health_router)
    app.include_router(schedule_router)

    return app


# Module-level app instance for uvicorn
app = create_app()
