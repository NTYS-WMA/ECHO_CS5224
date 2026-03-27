from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import Settings

_mongo_client: AsyncIOMotorClient | None = None
_mongo_db: AsyncIOMotorDatabase | None = None


def init_mongo_client(settings: Settings) -> None:
    global _mongo_client, _mongo_db
    if _mongo_client is not None:
        return

    _mongo_client = AsyncIOMotorClient(settings.mongodb_uri)
    _mongo_db = _mongo_client[settings.mongodb_database]


def get_mongo_db() -> AsyncIOMotorDatabase:
    if _mongo_db is None:
        raise RuntimeError("MongoDB is not initialized.")
    return _mongo_db


async def ping_mongo() -> bool:
    db = get_mongo_db()
    await db.command("ping")
    return True


async def close_mongo_client() -> None:
    global _mongo_client, _mongo_db
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None
        _mongo_db = None

