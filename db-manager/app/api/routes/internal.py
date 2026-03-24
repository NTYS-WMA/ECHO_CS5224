from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.db.bootstrap import bootstrap_mongo, bootstrap_postgres

router = APIRouter()


@router.post("/bootstrap")
async def manual_bootstrap(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    await bootstrap_postgres()
    await bootstrap_mongo(settings)
    return {"status": "ok", "message": "PostgreSQL tables/indexes and MongoDB indexes initialized."}

