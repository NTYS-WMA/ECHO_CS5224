"""
API routes for Prompt Template Management.

Exposes CRUD endpoints for business callers to register, query, and update
prompt templates managed by the AI Generation Service.

Endpoints:
1. POST   /api/v1/templates                  — Register a new template
2. GET    /api/v1/templates                  — List all templates (with filters)
3. GET    /api/v1/templates/{template_id}    — Get a specific template
4. PUT    /api/v1/templates/{template_id}    — Update an existing template
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from ..models.templates import (
    PromptTemplate,
    TemplateListResponse,
    TemplateRegisterRequest,
    TemplateRegisterResponse,
    TemplateUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/templates", tags=["Template Management"])


def get_template_manager():
    """
    Dependency injection placeholder for the TemplateManager.

    The actual instance is set during application startup.
    """
    from ..app import get_app_template_manager

    return get_app_template_manager()


# ------------------------------------------------------------------ #
# 1. Register a new template
# ------------------------------------------------------------------ #


@router.post(
    "",
    response_model=TemplateRegisterResponse,
    status_code=201,
    summary="Register a new prompt template",
    description=(
        "Business callers register a new prompt template. The AI service assigns "
        "a unique template_id and returns it along with the variable schema. "
        "Callers use this template_id in subsequent generation requests."
    ),
)
async def register_template(
    request: TemplateRegisterRequest,
    manager=Depends(get_template_manager),
) -> TemplateRegisterResponse:
    """Register a new prompt template."""
    try:
        template = await manager.register_template(request)
        return TemplateRegisterResponse(
            template_id=template.template_id,
            name=template.name,
            version=template.version,
            variables=template.variables,
            defaults=template.defaults,
            message="Template registered successfully.",
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.exception("Failed to register template: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# ------------------------------------------------------------------ #
# 2. List templates
# ------------------------------------------------------------------ #


@router.get(
    "",
    response_model=TemplateListResponse,
    summary="List available prompt templates",
    description=(
        "Returns a list of all registered prompt templates. Supports optional "
        "filtering by category, owner, or tag."
    ),
)
async def list_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    owner: Optional[str] = Query(None, description="Filter by owner"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    manager=Depends(get_template_manager),
) -> TemplateListResponse:
    """List all available templates with optional filters."""
    items = manager.list_templates(category=category, owner=owner, tag=tag)
    return TemplateListResponse(templates=items, total=len(items))


# ------------------------------------------------------------------ #
# 3. Get a specific template
# ------------------------------------------------------------------ #


@router.get(
    "/{template_id}",
    response_model=PromptTemplate,
    summary="Get a prompt template by ID",
    description=(
        "Returns the full template definition including system prompt, "
        "user prompt template, variable schema, and default parameters."
    ),
)
async def get_template(
    template_id: str,
    manager=Depends(get_template_manager),
) -> PromptTemplate:
    """Retrieve a specific template by ID."""
    template = manager.get_template(template_id)
    if template is None:
        raise HTTPException(
            status_code=404,
            detail=f"Template '{template_id}' not found.",
        )
    return template


# ------------------------------------------------------------------ #
# 4. Update an existing template
# ------------------------------------------------------------------ #


@router.put(
    "/{template_id}",
    response_model=PromptTemplate,
    summary="Update an existing prompt template",
    description=(
        "Business callers can update the content of a template they own. "
        "Only the provided fields are updated; the version is bumped automatically. "
        "The AI service does not directly edit templates — updates come from "
        "the owning business service."
    ),
)
async def update_template(
    template_id: str,
    request: TemplateUpdateRequest,
    manager=Depends(get_template_manager),
) -> PromptTemplate:
    """Update an existing template."""
    try:
        return await manager.update_template(template_id, request)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Failed to update template %s: %s", template_id, str(e))
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
