from fastapi import APIRouter, HTTPException

from app.db.mongo import ping_mongo
from app.db.postgres import ping_postgres

router = APIRouter()


@router.get("/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def readiness() -> dict[str, bool]:
    pg_ok = False
    mongo_ok = False
    try:
        pg_ok = await ping_postgres()
        mongo_ok = await ping_mongo()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database readiness check failed: {exc}") from exc
    return {"postgres": pg_ok, "mongodb": mongo_ok}

