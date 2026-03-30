"""
Prompt Template Manager — storage, registration, query, and update.

The TemplateManager is responsible for:
- Loading preset templates from the prompt_templates/ directory on startup.
- Syncing preset templates to the database (via db-manager) for durability.
- Loading all templates from the database on startup (including dynamically registered ones).
- Registering new templates submitted by business callers (persisted to DB).
- Updating existing templates (persisted to DB).
- Querying templates by ID, category, owner, or tags.

Templates are persisted in the database via the db-manager service so they
survive container restarts.  Preset JSON files in prompt_templates/ serve as
seed data that is upserted into the DB on every startup.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import httpx

from ..models.templates import (
    PromptTemplate,
    TemplateDefaults,
    TemplateListItem,
    TemplateRegisterRequest,
    TemplateUpdateRequest,
    TemplateVariableSchema,
)
from ..utils.helpers import generate_template_id

logger = logging.getLogger(__name__)


class TemplateManager:
    """
    Manages the lifecycle of prompt templates.

    Templates are loaded from the database on initialization and cached in memory.
    Preset templates (JSON files) are synced to the DB on startup.
    Mutations (register, update) are persisted to the DB via db-manager.
    """

    def __init__(self, templates_dir: str, db_manager_url: str, db_manager_api_key: Optional[str] = None):
        self._templates_dir = Path(templates_dir)
        self._templates: Dict[str, PromptTemplate] = {}
        self._db_manager_url = db_manager_url.rstrip("/")
        self._headers: dict[str, str] = {}
        if db_manager_api_key:
            self._headers["X-API-Key"] = db_manager_api_key

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    async def load_templates(self) -> int:
        """
        Load preset templates from disk, sync them to DB, then load all
        templates from DB into memory cache.

        Returns:
            Number of templates loaded into memory.
        """
        # Step 1: Load preset templates from JSON files and sync to DB
        await self._sync_presets_to_db()

        # Step 2: Load all templates from DB (presets + dynamically registered)
        await self._load_from_db()

        logger.info("Loaded %d templates into memory", len(self._templates))
        return len(self._templates)

    # ------------------------------------------------------------------ #
    # Query Operations
    # ------------------------------------------------------------------ #

    def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        return self._templates.get(template_id)

    def list_templates(
        self,
        category: Optional[str] = None,
        owner: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[TemplateListItem]:
        results = []
        for tpl in self._templates.values():
            if category and tpl.category != category:
                continue
            if owner and tpl.owner != owner:
                continue
            if tag and tag not in tpl.tags:
                continue
            results.append(
                TemplateListItem(
                    template_id=tpl.template_id,
                    name=tpl.name,
                    description=tpl.description,
                    version=tpl.version,
                    owner=tpl.owner,
                    category=tpl.category,
                    tags=tpl.tags,
                    updated_at=tpl.updated_at,
                )
            )
        return results

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #

    async def register_template(self, request: TemplateRegisterRequest) -> PromptTemplate:
        # Check for duplicate name+owner in memory cache
        for tpl in self._templates.values():
            if tpl.name == request.name and tpl.owner == request.owner:
                raise ValueError(
                    f"Template with name '{request.name}' already exists "
                    f"for owner '{request.owner}'. Use update instead."
                )

        now = datetime.now(timezone.utc)
        template_id = generate_template_id(request.name)

        template = PromptTemplate(
            template_id=template_id,
            name=request.name,
            description=request.description,
            version="1.0.0",
            owner=request.owner,
            category=request.category,
            system_prompt=request.system_prompt,
            user_prompt_template=request.user_prompt_template,
            variables=request.variables,
            defaults=request.defaults,
            tags=request.tags,
            created_at=now,
            updated_at=now,
        )

        # Persist to DB first
        await self._persist_template_to_db(template)

        # Update in-memory cache
        self._templates[template_id] = template

        logger.info(
            "Registered new template: %s (%s) by %s",
            template_id,
            request.name,
            request.owner,
        )
        return template

    # ------------------------------------------------------------------ #
    # Update
    # ------------------------------------------------------------------ #

    async def update_template(
        self, template_id: str, request: TemplateUpdateRequest
    ) -> PromptTemplate:
        template = self._templates.get(template_id)
        if template is None:
            raise KeyError(f"Template '{template_id}' not found.")

        update_data = request.model_dump(exclude_unset=True)
        template_data = template.model_dump()

        for key, value in update_data.items():
            if value is not None:
                template_data[key] = value

        template_data["version"] = self._bump_version(template_data["version"])
        template_data["updated_at"] = datetime.now(timezone.utc)

        updated_template = PromptTemplate(**template_data)

        # Persist to DB first
        await self._persist_template_to_db(updated_template)

        # Update in-memory cache
        self._templates[template_id] = updated_template

        logger.info(
            "Updated template: %s to version %s",
            template_id,
            updated_template.version,
        )
        return updated_template

    # ------------------------------------------------------------------ #
    # DB Persistence Helpers
    # ------------------------------------------------------------------ #

    async def _persist_template_to_db(self, template: PromptTemplate) -> None:
        """Upsert a template to the database via db-manager."""
        payload = template.model_dump(mode="json")
        # Ensure datetime fields are ISO strings
        for field in ("created_at", "updated_at"):
            if isinstance(payload.get(field), datetime):
                payload[field] = payload[field].isoformat()

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.put(
                    f"{self._db_manager_url}/templates",
                    json=payload,
                    headers=self._headers,
                )
                r.raise_for_status()
            logger.debug("Persisted template %s to DB", template.template_id)
        except Exception as e:
            logger.error("Failed to persist template %s to DB: %s", template.template_id, str(e))
            raise

    async def _load_from_db(self) -> None:
        """Load all templates from DB into the in-memory cache."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(
                    f"{self._db_manager_url}/templates/all",
                    headers=self._headers,
                )
                r.raise_for_status()
            data = r.json()
            for item in data.get("templates", []):
                try:
                    template = self._dict_to_template(item)
                    self._templates[template.template_id] = template
                except Exception as e:
                    logger.error("Failed to parse template from DB: %s", str(e))
        except Exception as e:
            logger.error("Failed to load templates from DB: %s", str(e))

    async def _sync_presets_to_db(self) -> None:
        """Load preset JSON files from disk and upsert them into the DB."""
        if not self._templates_dir.exists():
            logger.warning("Templates directory does not exist: %s", self._templates_dir)
            return

        for filepath in sorted(self._templates_dir.glob("*.json")):
            if filepath.name == "template_index.json":
                continue
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                template = PromptTemplate(**data)
                await self._persist_template_to_db(template)
                logger.info("Synced preset template to DB: %s (%s)", template.template_id, template.name)
            except Exception as e:
                logger.error("Failed to sync preset template %s to DB: %s", filepath.name, str(e))

    # ------------------------------------------------------------------ #
    # Conversion Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _dict_to_template(data: dict) -> PromptTemplate:
        """Convert a dict (from DB API response) into a PromptTemplate."""
        # Parse nested variable schemas
        variables = {}
        raw_vars = data.get("variables") or {}
        for var_name, var_schema in raw_vars.items():
            if isinstance(var_schema, dict):
                variables[var_name] = TemplateVariableSchema(**var_schema)
            else:
                variables[var_name] = var_schema

        defaults = None
        if data.get("defaults"):
            defaults = TemplateDefaults(**data["defaults"])

        return PromptTemplate(
            template_id=data["template_id"],
            name=data["name"],
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            owner=data["owner"],
            category=data.get("category", "general"),
            system_prompt=data["system_prompt"],
            user_prompt_template=data["user_prompt_template"],
            variables=variables,
            defaults=defaults,
            tags=data.get("tags", []),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )

    @staticmethod
    def _bump_version(version: str) -> str:
        """Bump the patch version of a semantic version string."""
        parts = version.split(".")
        if len(parts) == 3:
            try:
                parts[2] = str(int(parts[2]) + 1)
                return ".".join(parts)
            except ValueError:
                pass
        return version + ".1"
