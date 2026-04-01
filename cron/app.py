"""
FastAPI application entry point for the Cron Service v4.0.

Event registration and trigger service. External services register
scheduled events via API; the cron engine polls DB Manager for due
events and dispatches them via event broker or HTTP callback.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from .clients.db_manager_client import DBManagerClient
from .config.settings import get_settings
from .events.publisher import EventPublisher
from .routes.event_routes import router as event_router
from .routes.health_routes import router as health_router
from .routes.schedule_routes import router as legacy_router
from .services.scheduler import CronScheduler

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Module-level singletons (set during lifespan)
# ------------------------------------------------------------------ #

_scheduler: Optional[CronScheduler] = None
_db_client: Optional[DBManagerClient] = None


def get_app_scheduler() -> CronScheduler:
    """Return the application-level CronScheduler singleton."""
    assert _scheduler is not None, "CronScheduler not initialized."
    return _scheduler


def get_app_db_client() -> DBManagerClient:
    """Return the application-level DBManagerClient singleton."""
    assert _db_client is not None, "DBManagerClient not initialized."
    return _db_client


# ------------------------------------------------------------------ #
# Application Lifespan
# ------------------------------------------------------------------ #


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Startup:
        1. Create DBManagerClient.
        2. Create EventPublisher.
        3. Create CronScheduler.
        4. Register default schedules into DB (if enabled).
        5. Start the scheduler background loop.

    Shutdown:
        1. Stop the scheduler.
        2. Close the EventPublisher.
        3. Close the DBManagerClient.
    """
    global _scheduler, _db_client

    settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    logger.info(
        "Starting %s v%s ...",
        settings.SERVICE_NAME,
        settings.SERVICE_VERSION,
    )

    # 1. DB Manager client
    _db_client = DBManagerClient(
        base_url=settings.DB_MANAGER_URL,
        timeout_seconds=settings.DB_MANAGER_TIMEOUT,
        api_key=settings.DB_MANAGER_API_KEY,
    )

    # 2. Event Publisher
    publisher = EventPublisher(
        broker_url=settings.EVENT_BROKER_URL,
        timeout_seconds=settings.EVENT_PUBLISH_TIMEOUT,
        max_retries=settings.EVENT_PUBLISH_RETRIES,
    )

    # 3. Scheduler
    _scheduler = CronScheduler(
        publisher=publisher,
        db_client=_db_client,
        tick_interval_seconds=settings.TICK_INTERVAL_SECONDS,
    )

    # 4. Register default schedules into DB
    if settings.AUTO_REGISTER_DEFAULTS:
        try:
            await _scheduler.register_defaults(settings.get_schedules())
            logger.info("Default schedules registered into DB.")
        except Exception as e:
            logger.warning(
                "Failed to register default schedules (DB Manager may not be ready): %s",
                str(e),
            )

    # 5. Start scheduler
    await _scheduler.start()

    logger.info(
        "%s v%s started (tick=%ds, db_manager=%s).",
        settings.SERVICE_NAME,
        settings.SERVICE_VERSION,
        settings.TICK_INTERVAL_SECONDS,
        settings.DB_MANAGER_URL,
    )

    yield  # Application is running

    # Shutdown
    logger.info("Shutting down %s ...", settings.SERVICE_NAME)
    if _scheduler and _scheduler.running:
        await _scheduler.stop()
    await publisher.close()
    if _db_client:
        await _db_client.close()
    _scheduler = None
    _db_client = None
    logger.info("Shutdown complete.")


# ------------------------------------------------------------------ #
# FastAPI Application
# ------------------------------------------------------------------ #


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Cron Service",
        description=(
            "Event registration and trigger service for the ECHO platform. "
            "External services register scheduled events via API; the cron "
            "engine polls the database for due events and dispatches them."
        ),
        version=settings.SERVICE_VERSION,
        lifespan=lifespan,
    )

    app.include_router(health_router)
    app.include_router(event_router)
    app.include_router(legacy_router)

    return app


app = create_app()
