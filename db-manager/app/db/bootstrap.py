from pathlib import Path

from pymongo import ASCENDING
from sqlalchemy import text

from app.core.config import Settings
from app.db.mongo import get_mongo_db
from app.db.postgres import get_postgres_engine


def _split_sql_script(sql: str) -> list[str]:
    statements: list[str] = []
    buffer: list[str] = []
    in_dollar_block = False
    for raw_line in sql.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if not in_dollar_block and line.startswith("--"):
            continue

        buffer.append(raw_line)

        marker_count = raw_line.count("$$")
        if marker_count % 2 == 1:
            in_dollar_block = not in_dollar_block

        if not in_dollar_block and line.endswith(";"):
            statements.append("\n".join(buffer))
            buffer = []
    if buffer:
        statements.append("\n".join(buffer))
    return statements


async def bootstrap_postgres() -> None:
    engine = get_postgres_engine()
    sql_dir = Path(__file__).resolve().parents[2] / "sql"
    sql_files = sorted(sql_dir.glob("*.sql"))

    async with engine.begin() as conn:
        for sql_file in sql_files:
            script = sql_file.read_text(encoding="utf-8")
            for stmt in _split_sql_script(script):
                await conn.execute(text(stmt))


async def bootstrap_mongo(settings: Settings) -> None:
    db = get_mongo_db()
    profile_collection = db[settings.mongo_profile_collection]

    await profile_collection.create_index([("user_id", ASCENDING)], unique=True, name="uid_unique")
    await profile_collection.create_index([("interests.id", ASCENDING)], name="interests_id_idx")
    await profile_collection.create_index([("skills.id", ASCENDING)], name="skills_id_idx")
    await profile_collection.create_index([("personality.id", ASCENDING)], name="personality_id_idx")
