from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.db.bootstrap import bootstrap_mongo, bootstrap_postgres
from app.db.mongo import close_mongo_client, init_mongo_client
from app.db.postgres import close_postgres_engine, init_postgres_engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    init_postgres_engine(settings)
    init_mongo_client(settings)

    if settings.auto_init_db:
        await bootstrap_postgres()
        await bootstrap_mongo(settings)

    try:
        yield
    finally:
        await close_postgres_engine()
        await close_mongo_client()


app = FastAPI(
    title="DB Manager",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(api_router)

