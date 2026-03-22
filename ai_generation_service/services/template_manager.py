"""
Prompt Template Manager — storage, registration, query, and update.

The TemplateManager is responsible for:
- Loading preset templates from the prompt_templates/ directory on startup.
- Registering new templates submitted by business callers.
- Updating existing templates (content only, not direct editing of prompt logic).
- Querying templates by ID, category, owner, or tags.
- Persisting template metadata to a JSON index file for durability.

Templates are stored as individual JSON files in the prompt_templates/ directory.
A metadata index (template_index.json) tracks all registered templates.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

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

    Templates are loaded from disk on initialization and cached in memory.
    Mutations (register, update) are persisted back to disk.
    """

    def __init__(self, templates_dir: str):
        """
        Initialize the TemplateManager.

        Args:
            templates_dir: Absolute path to the prompt_templates/ directory.
        """
        self._templates_dir = Path(templates_dir)
        self._templates: Dict[str, PromptTemplate] = {}
        self._index_path = self._templates_dir / "template_index.json"

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def load_templates(self) -> int:
        """
        Load all template JSON files from the templates directory.

        Returns:
            Number of templates loaded.
        """
        if not self._templates_dir.exists():
            logger.warning(
                "Templates directory does not exist: %s", self._templates_dir
            )
            return 0

        loaded = 0
        for filepath in sorted(self._templates_dir.glob("*.json")):
            if filepath.name == "template_index.json":
                continue
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                template = PromptTemplate(**data)
                self._templates[template.template_id] = template
                loaded += 1
                logger.info(
                    "Loaded template: %s (%s)", template.template_id, template.name
                )
            except Exception as e:
                logger.error("Failed to load template from %s: %s", filepath, str(e))

        logger.info("Loaded %d templates from %s", loaded, self._templates_dir)
        self._save_index()
        return loaded

    # ------------------------------------------------------------------ #
    # Query Operations
    # ------------------------------------------------------------------ #

    def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        """
        Retrieve a template by ID.

        Args:
            template_id: The unique template identifier.

        Returns:
            The PromptTemplate if found, else None.
        """
        return self._templates.get(template_id)

    def list_templates(
        self,
        category: Optional[str] = None,
        owner: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[TemplateListItem]:
        """
        List templates with optional filtering.

        Args:
            category: Filter by category.
            owner: Filter by owner.
            tag: Filter by tag.

        Returns:
            List of TemplateListItem summaries.
        """
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

    def register_template(self, request: TemplateRegisterRequest) -> PromptTemplate:
        """
        Register a new template.

        Assigns a unique template_id, persists to disk, and returns the
        full template with its ID and variable schema.

        Args:
            request: The registration request from the business caller.

        Returns:
            The newly created PromptTemplate.

        Raises:
            ValueError: If a template with the same name and owner already exists.
        """
        # Check for duplicate name+owner
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

        self._templates[template_id] = template
        self._persist_template(template)
        self._save_index()

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

    def update_template(
        self, template_id: str, request: TemplateUpdateRequest
    ) -> PromptTemplate:
        """
        Update an existing template.

        Only the fields provided in the request are updated. The version
        is bumped and updated_at is refreshed automatically.

        Args:
            template_id: The template to update.
            request: The update request with partial fields.

        Returns:
            The updated PromptTemplate.

        Raises:
            KeyError: If the template does not exist.
        """
        template = self._templates.get(template_id)
        if template is None:
            raise KeyError(f"Template '{template_id}' not found.")

        # Apply partial updates
        update_data = request.model_dump(exclude_unset=True)
        template_data = template.model_dump()

        for key, value in update_data.items():
            if value is not None:
                template_data[key] = value

        # Bump version
        template_data["version"] = self._bump_version(template_data["version"])
        template_data["updated_at"] = datetime.now(timezone.utc)

        updated_template = PromptTemplate(**template_data)
        self._templates[template_id] = updated_template
        self._persist_template(updated_template)
        self._save_index()

        logger.info(
            "Updated template: %s to version %s",
            template_id,
            updated_template.version,
        )
        return updated_template

    # ------------------------------------------------------------------ #
    # Internal Helpers
    # ------------------------------------------------------------------ #

    def _persist_template(self, template: PromptTemplate) -> None:
        """Write a template to its JSON file on disk."""
        # Derive filename from template_id
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", template.template_id)
        filepath = self._templates_dir / f"{safe_name}.json"
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(
                    template.model_dump(mode="json"),
                    f,
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                )
            logger.debug("Persisted template to %s", filepath)
        except Exception as e:
            logger.error("Failed to persist template %s: %s", template.template_id, str(e))

    def _save_index(self) -> None:
        """Save the template index file for quick lookups."""
        index = {}
        for tid, tpl in self._templates.items():
            index[tid] = {
                "name": tpl.name,
                "owner": tpl.owner,
                "category": tpl.category,
                "version": tpl.version,
                "tags": tpl.tags,
                "updated_at": tpl.updated_at.isoformat(),
            }
        try:
            with open(self._index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to save template index: %s", str(e))

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
