from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def init_postgres_engine(settings: Settings) -> None:
    global _engine, _session_maker
    if _engine is not None:
        return

    _engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=8,
        max_overflow=16,
    )
    _session_maker = async_sessionmaker(_engine, expire_on_commit=False)


def get_postgres_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("PostgreSQL engine is not initialized.")
    return _engine


def get_postgres_session_maker() -> async_sessionmaker[AsyncSession]:
    if _session_maker is None:
        raise RuntimeError("PostgreSQL session maker is not initialized.")
    return _session_maker


async def get_pg_session() -> AsyncGenerator[AsyncSession, None]:
    session_maker = get_postgres_session_maker()
    async with session_maker() as session:
        yield session


async def ping_postgres() -> bool:
    engine = get_postgres_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True


async def close_postgres_engine() -> None:
    global _engine, _session_maker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_maker = None

