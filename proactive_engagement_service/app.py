"""
FastAPI application entry point for the Proactive Engagement Service v2.0.

Wires together all service components:
- DatabaseServiceClient → TaskService → Task CRUD routes
- MessageDispatchClient + TaskExecutor → PollingScheduler → Scheduler routes
- EventPublisher → TaskExecutor (telemetry)
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from .config.settings import get_settings
from .events.publisher import EventPublisher
from .routes.health_routes import router as health_router
from .routes.scheduler_routes import router as scheduler_router
from .routes.task_routes import router as task_router
from .services.db_client import DatabaseServiceClient
from .services.dispatcher import MessageDispatchClient
from .services.scheduler import PollingScheduler
from .services.task_executor import TaskExecutor
from .services.task_service import TaskService

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Module-level singletons (set during lifespan)
# ------------------------------------------------------------------ #

_task_service: Optional[TaskService] = None
_scheduler: Optional[PollingScheduler] = None


def get_app_task_service() -> TaskService:
    """Return the application-level TaskService singleton."""
    assert _task_service is not None, "TaskService not initialized."
    return _task_service


def get_app_scheduler() -> PollingScheduler:
    """Return the application-level PollingScheduler singleton."""
    assert _scheduler is not None, "PollingScheduler not initialized."
    return _scheduler


# ------------------------------------------------------------------ #
# Application Lifespan
# ------------------------------------------------------------------ #


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Startup:
        1. Create DatabaseServiceClient.
        2. Create TaskService.
        3. Create MessageDispatchClient.
        4. Create EventPublisher.
        5. Create TaskExecutor.
        6. Create and start PollingScheduler.

    Shutdown:
        1. Stop PollingScheduler.
        2. Close EventPublisher.
    """
    global _task_service, _scheduler

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

    # 1. Database Service Client
    db_client = DatabaseServiceClient(
        base_url=settings.DATABASE_SERVICE_URL,
        timeout_seconds=settings.DATABASE_SERVICE_TIMEOUT,
    )

    # 2. Task Service
    _task_service = TaskService(db_client=db_client)

    # 3. Message Dispatch Hub Client
    dispatch_client = MessageDispatchClient(
        base_url=settings.DISPATCH_HUB_URL,
        timeout_seconds=settings.DISPATCH_HUB_TIMEOUT,
    )

    # 4. Event Publisher
    event_publisher = EventPublisher(
        broker_url=settings.EVENT_BROKER_URL,
        enabled=settings.EVENT_PUBLISH_ENABLED,
    )

    # 5. Task Executor
    executor = TaskExecutor(
        db_client=db_client,
        dispatch_client=dispatch_client,
        event_publisher=event_publisher,
    )

    # 6. Polling Scheduler
    _scheduler = PollingScheduler(
        db_client=db_client,
        executor=executor,
        poll_interval_seconds=settings.POLL_INTERVAL_SECONDS,
        max_tasks_per_poll=settings.MAX_TASKS_PER_POLL,
    )

    if settings.SCHEDULER_ENABLED:
        await _scheduler.start()

    logger.info(
        "%s v%s started (scheduler=%s, poll_interval=%ds).",
        settings.SERVICE_NAME,
        settings.SERVICE_VERSION,
        "enabled" if settings.SCHEDULER_ENABLED else "disabled",
        settings.POLL_INTERVAL_SECONDS,
    )

    yield  # Application is running

    # Shutdown
    logger.info("Shutting down %s ...", settings.SERVICE_NAME)
    if _scheduler and _scheduler.running:
        await _scheduler.stop()
    await event_publisher.close()
    _task_service = None
    _scheduler = None
    logger.info("Shutdown complete.")


# ------------------------------------------------------------------ #
# FastAPI Application
# ------------------------------------------------------------------ #


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Proactive Engagement Service",
        description=(
            "Scheduled task management and polling engine for proactive "
            "outbound messaging in the ECHO platform. Provides task CRUD "
            "for service registrants and an internal polling scheduler "
            "that dispatches due tasks to the Message Dispatch Hub."
        ),
        version=settings.SERVICE_VERSION,
        lifespan=lifespan,
    )

    # Register routes
    app.include_router(health_router)
    app.include_router(task_router)
    app.include_router(scheduler_router)

    return app


# Module-level app instance for uvicorn
app = create_app()
