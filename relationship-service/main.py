"""
Relationship Service — standalone FastAPI microservice.

Runs on port 18089 (internal network only).

Endpoints:
  GET   /api/v1/relationships/{user_id}/context
  PATCH /api/v1/relationships/{user_id}/score
  GET   /health

Cron jobs:
  session_score_job     every 15 min  — score ended conversation sessions
  inactivity_decay_job  daily 03:00   — apply passive score decay
"""
import logging
from contextlib import asynccontextmanager

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine

from api.relationships import router as relationships_router
from config import get_settings
from managers import db_manager, relationship_manager
from managers.db_manager import AsyncSessionLocal
from models.schema import Base

settings = get_settings()

logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
logger = logging.getLogger(__name__)


# ─── Cron jobs ────────────────────────────────────────────────────────────────


async def session_score_job() -> None:
    """Score completed conversation sessions for all eligible users."""
    async with AsyncSessionLocal() as session:
        await relationship_manager.run_session_scoring(session)


async def inactivity_decay_job() -> None:
    """Apply daily relationship score decay to long-inactive users."""
    async with AsyncSessionLocal() as session:
        await relationship_manager.run_inactivity_decay(session, inactive_hours=24)


def _create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        session_score_job,
        trigger=IntervalTrigger(minutes=15),
        id="session_score",
        replace_existing=True,
        misfire_grace_time=120,
    )
    scheduler.add_job(
        inactivity_decay_job,
        trigger=CronTrigger(hour=3, minute=0),
        id="inactivity_decay",
        replace_existing=True,
    )

    return scheduler


# ─── Lifespan ─────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create relationship_scores table if it doesn't exist
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

    scheduler = _create_scheduler()
    scheduler.start()
    logger.info("Relationship Service started on port %d", settings.port)

    yield

    scheduler.shutdown(wait=False)
    logger.info("Relationship Service shutdown complete")


# ─── App ──────────────────────────────────────────────────────────────────────


app = FastAPI(
    title="ECHO Relationship Service",
    version="1.0.0",
    description="Manages affinity scores and tiers per user.",
    lifespan=lifespan,
)

app.include_router(relationships_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "relationship"}


# ─── Entry point ──────────────────────────────────────────────────────────────


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=False)
