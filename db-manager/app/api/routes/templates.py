from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.db.postgres import get_postgres_session_maker
from app.repositories.template_repository import TemplateRepository

router = APIRouter(prefix="/templates", tags=["templates"])
template_repo = TemplateRepository()


class TemplateUpsertRequest(BaseModel):
    template_id: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    owner: str
    category: str = "general"
    system_prompt: str
    user_prompt_template: str
    variables: Dict[str, Any] = {}
    defaults: Optional[Dict[str, Any]] = None
    tags: List[str] = []
    created_at: str
    updated_at: str


class TemplateResponse(BaseModel):
    template_id: str
    name: str
    description: str
    version: str
    owner: str
    category: str
    system_prompt: str
    user_prompt_template: str
    variables: Dict[str, Any]
    defaults: Optional[Dict[str, Any]]
    tags: List[str]
    created_at: str
    updated_at: str


def _row_to_response(row: dict) -> TemplateResponse:
    return TemplateResponse(
        template_id=row["template_id"],
        name=row["name"],
        description=row["description"],
        version=row["version"],
        owner=row["owner"],
        category=row["category"],
        system_prompt=row["system_prompt"],
        user_prompt_template=row["user_prompt_template"],
        variables=row["variables"] if row["variables"] else {},
        defaults=row["defaults"],
        tags=row["tags"] if row["tags"] else [],
        created_at=row["created_at"].isoformat() if isinstance(row["created_at"], datetime) else str(row["created_at"]),
        updated_at=row["updated_at"].isoformat() if isinstance(row["updated_at"], datetime) else str(row["updated_at"]),
    )


@router.get("", response_model=Dict[str, Any])
async def list_templates(
    category: Optional[str] = Query(None),
    owner: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
):
    async with get_postgres_session_maker()() as session:
        rows = await template_repo.list_by_filters(
            session, category=category, owner=owner, tag=tag
        )
    templates = [_row_to_response(r) for r in rows]
    return {"templates": [t.model_dump() for t in templates], "total": len(templates)}


@router.get("/all", response_model=Dict[str, Any])
async def get_all_templates():
    async with get_postgres_session_maker()() as session:
        rows = await template_repo.get_all(session)
    templates = [_row_to_response(r) for r in rows]
    return {"templates": [t.model_dump() for t in templates], "total": len(templates)}


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: str):
    async with get_postgres_session_maker()() as session:
        row = await template_repo.get_by_id(session, template_id)
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    return _row_to_response(row)


@router.put("", response_model=TemplateResponse)
async def upsert_template(request: TemplateUpsertRequest):
    template_data = request.model_dump()
    async with get_postgres_session_maker()() as session:
        await template_repo.upsert(session, template_data)
        await session.commit()
        row = await template_repo.get_by_id(session, request.template_id)
    if not row:
        raise HTTPException(status_code=500, detail="Failed to upsert template")
    return _row_to_response(row)


@router.delete("/{template_id}")
async def delete_template(template_id: str):
    async with get_postgres_session_maker()() as session:
        deleted = await template_repo.delete(session, template_id)
        await session.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"message": "Template deleted successfully"}


@router.get("/lookup/by-name-owner", response_model=Optional[TemplateResponse])
async def find_by_name_and_owner(
    name: str = Query(...),
    owner: str = Query(...),
):
    async with get_postgres_session_maker()() as session:
        row = await template_repo.find_by_name_and_owner(session, name, owner)
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    return _row_to_response(row)
