import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _parse_dt(value: Any) -> datetime:
    """Convert a value to a datetime object. Accepts datetime or ISO string."""
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


class TemplateRepository:
    """PostgreSQL repository for prompt templates."""

    async def get_all(self, session: AsyncSession) -> list[dict[str, Any]]:
        query = text(
            """
            SELECT template_id, name, description, version, owner, category,
                   system_prompt, user_prompt_template, variables, defaults,
                   tags, created_at, updated_at
            FROM prompt_templates
            ORDER BY updated_at DESC
            """
        )
        result = await session.execute(query)
        return [dict(row) for row in result.mappings()]

    async def get_by_id(self, session: AsyncSession, template_id: str) -> dict[str, Any] | None:
        query = text(
            """
            SELECT template_id, name, description, version, owner, category,
                   system_prompt, user_prompt_template, variables, defaults,
                   tags, created_at, updated_at
            FROM prompt_templates
            WHERE template_id = :template_id
            """
        )
        result = await session.execute(query, {"template_id": template_id})
        row = result.mappings().first()
        return dict(row) if row else None

    async def find_by_name_and_owner(
        self, session: AsyncSession, name: str, owner: str
    ) -> dict[str, Any] | None:
        query = text(
            """
            SELECT template_id, name, description, version, owner, category,
                   system_prompt, user_prompt_template, variables, defaults,
                   tags, created_at, updated_at
            FROM prompt_templates
            WHERE name = :name AND owner = :owner
            """
        )
        result = await session.execute(query, {"name": name, "owner": owner})
        row = result.mappings().first()
        return dict(row) if row else None

    async def upsert(self, session: AsyncSession, template: dict[str, Any]) -> None:
        query = text(
            """
            INSERT INTO prompt_templates
                (template_id, name, description, version, owner, category,
                 system_prompt, user_prompt_template, variables, defaults,
                 tags, created_at, updated_at)
            VALUES
                (:template_id, :name, :description, :version, :owner, :category,
                 :system_prompt, :user_prompt_template,
                 CAST(:variables AS jsonb), CAST(:defaults AS jsonb),
                 CAST(:tags AS jsonb), :created_at, :updated_at)
            ON CONFLICT (template_id) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                version = EXCLUDED.version,
                owner = EXCLUDED.owner,
                category = EXCLUDED.category,
                system_prompt = EXCLUDED.system_prompt,
                user_prompt_template = EXCLUDED.user_prompt_template,
                variables = EXCLUDED.variables,
                defaults = EXCLUDED.defaults,
                tags = EXCLUDED.tags,
                updated_at = EXCLUDED.updated_at
            """
        )
        await session.execute(
            query,
            {
                "template_id": template["template_id"],
                "name": template["name"],
                "description": template.get("description", ""),
                "version": template.get("version", "1.0.0"),
                "owner": template["owner"],
                "category": template.get("category", "general"),
                "system_prompt": template["system_prompt"],
                "user_prompt_template": template["user_prompt_template"],
                "variables": json.dumps(template.get("variables", {}), ensure_ascii=False),
                "defaults": json.dumps(template["defaults"], ensure_ascii=False) if template.get("defaults") else None,
                "tags": json.dumps(template.get("tags", []), ensure_ascii=False),
                "created_at": _parse_dt(template["created_at"]),
                "updated_at": _parse_dt(template["updated_at"]),
            },
        )

    async def delete(self, session: AsyncSession, template_id: str) -> bool:
        query = text("DELETE FROM prompt_templates WHERE template_id = :template_id")
        result = await session.execute(query, {"template_id": template_id})
        return result.rowcount > 0

    async def list_by_filters(
        self,
        session: AsyncSession,
        category: str | None = None,
        owner: str | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: dict[str, Any] = {}

        if category:
            conditions.append("category = :category")
            params["category"] = category
        if owner:
            conditions.append("owner = :owner")
            params["owner"] = owner
        if tag:
            conditions.append("tags @> CAST(:tag AS jsonb)")
            params["tag"] = json.dumps([tag])

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = text(
            f"""
            SELECT template_id, name, description, version, owner, category,
                   system_prompt, user_prompt_template, variables, defaults,
                   tags, created_at, updated_at
            FROM prompt_templates
            WHERE {where_clause}
            ORDER BY updated_at DESC
            """
        )
        result = await session.execute(query, params)
        return [dict(row) for row in result.mappings()]
