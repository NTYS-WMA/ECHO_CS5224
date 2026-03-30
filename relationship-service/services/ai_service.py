"""
AI Service — single-turn completion for session scoring.

Delegates to the team's AI Generation Service via HTTP.

On first call, registers a passthrough template (tpl_relationship_scoring)
that lets relationship_manager.py supply its own fully-crafted prompt.
The template is idempotent — a 409 on registration is treated as success,
and the existing template_id is fetched from the template list.

Endpoint: POST /api/v1/generation/execute  (host:8003)
Template:  tpl_relationship_scoring — variable: {"full_prompt": <prompt>}
"""
import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_BASE_URL = settings.ai_generation_service_url
_EXECUTE_URL = f"{_BASE_URL}/api/v1/generation/execute"
_TEMPLATES_URL = f"{_BASE_URL}/api/v1/templates"
_TEMPLATE_NAME = "Relationship Scoring"
_TEMPLATE_OWNER = "relationship-service"

_TEMPLATE_PAYLOAD = {
    "name": _TEMPLATE_NAME,
    "description": (
        "Passthrough template for the Relationship Service. "
        "The caller supplies the complete scoring prompt including instructions and conversation."
    ),
    "owner": _TEMPLATE_OWNER,
    "category": "analysis",
    "version": "1.0.0",
    "system_prompt": "You are a precise JSON-output assistant. Follow the instructions in the user message exactly.",
    "user_prompt_template": "{{full_prompt}}",
    "variables": {
        "full_prompt": {
            "type": "string",
            "required": True,
            "description": "Complete scoring prompt assembled by the relationship service.",
        }
    },
    "defaults": {"temperature": 0.2, "max_tokens": 1024},
    "tags": ["analysis", "relationship", "scoring"],
}

_template_id: str | None = None


async def _ensure_template_registered() -> str:
    """
    Register tpl_relationship_scoring if not already present.
    Returns the assigned template_id.
    409 means already registered — fetch the id from the template list.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(_TEMPLATES_URL, json=_TEMPLATE_PAYLOAD)

        if response.status_code == 201:
            template_id = response.json()["template_id"]
            logger.info("Registered relationship scoring template: %s", template_id)
            return template_id

        if response.status_code == 409:
            # Already registered — look it up by owner
            list_response = await client.get(
                _TEMPLATES_URL, params={"owner": _TEMPLATE_OWNER}
            )
            list_response.raise_for_status()
            templates = list_response.json().get("templates", [])
            for t in templates:
                if t["name"] == _TEMPLATE_NAME:
                    logger.info("Found existing relationship scoring template: %s", t["template_id"])
                    return t["template_id"]

        raise RuntimeError(
            f"Failed to register or retrieve relationship scoring template: {response.status_code}"
        )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def complete(prompt: str, max_tokens: int = 1024) -> str:
    """Single-turn completion via the AI Generation Service. Returns raw text."""
    global _template_id
    if not _template_id:
        _template_id = await _ensure_template_registered()

    payload = {
        "user_id": "relationship-service",
        "template_id": _template_id,
        "variables": {"full_prompt": prompt},
        "generation_config": {"max_tokens": max_tokens},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(_EXECUTE_URL, json=payload)
        if response.status_code == 400:
            # Template may have been lost (AI service restarted). Force re-registration on next retry.
            _template_id = None
        response.raise_for_status()
        data = response.json()
        return data["output"][0]["content"].strip()
