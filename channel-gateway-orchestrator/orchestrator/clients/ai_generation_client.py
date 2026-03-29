"""
Client for the AI Generation Service.

POST /api/v1/generation/execute  (template_id: tpl_chat_completion, messages mode)

Falls back to a simple echo-style mock when MOCK_SERVICES=true.
"""

import asyncio
import logging
import uuid
from typing import Any, Optional

import httpx

from shared.config.settings import settings

logger = logging.getLogger(__name__)

_http_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            base_url=settings.ai_generation_service_url,
            timeout=60.0,  # LLM calls via Bedrock can be slow
        )
    return _http_client


#Mock Response

def _mock_chat_completion(messages: list[dict]) -> dict[str, Any]:
    """Generate a simple mock response based on the last user message."""
    # Find last user message
    user_msg = ""
    user_name = "there"
    for m in reversed(messages):
        if m.get("role") == "user":
            user_msg = m.get("content", "")
            break

    # Extract display name from system prompt if present
    for m in messages:
        if m.get("role") == "system":
            break

    mock_reply = f"Hey {user_name}! I heard you say: \"{user_msg}\". I'm ECHO (running in mock mode)."

    return {
        "response_id": f"gen-mock-{uuid.uuid4().hex[:6]}",
        "template_id": "tpl_chat_completion",
        "output": [
            {
                "type": "text",
                "content": mock_reply,
            }
        ],
        "model": "mock-model",
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
        },
    }


#Public API

async def generate_chat_completion(
    user_id: str,
    conversation_id: str,
    messages: list[dict[str, str]],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    correlation_id: str = "",
) -> Optional[dict[str, Any]]:
    """
    Request a chat completion from the AI Generation Service.

    Args:
        user_id: Internal user ID
        conversation_id: Conversation thread ID
        messages: List of {"role": "system"/"user"/"assistant", "content": "..."}
        temperature: Generation temperature (default from settings)
        max_tokens: Max output tokens (default from settings)
        correlation_id: Event correlation ID for tracing

    Returns:
        Response dict with 'output', 'model', 'usage' keys, or None on failure.
    """
    if settings.mock_services:
        logger.debug("[MOCK] Generating mock chat completion for %s", user_id)
        return _mock_chat_completion(messages)

    payload = {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "template_id": "tpl_chat_completion",
        "messages": messages,
        "generation_config": {
            "temperature": temperature or settings.ai_temperature,
            "max_tokens": max_tokens or settings.ai_max_tokens,
        },
        "correlation_id": correlation_id,
    }

    max_attempts = 3
    backoff = 3.0  # seconds; doubles each retry

    for attempt in range(1, max_attempts + 1):
        try:
            client = _get_client()
            resp = await client.post("/api/v1/generation/execute", json=payload)
            resp.raise_for_status()
            result = resp.json()
            logger.info(
                "AI generation complete for %s — model=%s tokens_in=%d tokens_out=%d",
                user_id,
                result.get("model", "?"),
                result.get("usage", {}).get("input_tokens", 0),
                result.get("usage", {}).get("output_tokens", 0),
            )
            return result
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 500 and attempt < max_attempts:
                wait = backoff * (2 ** (attempt - 1))  # 3s, 6s
                logger.warning(
                    "AI generation 500 for %s (attempt %d/%d) — retrying in %.0fs",
                    user_id, attempt, max_attempts, wait,
                )
                await asyncio.sleep(wait)
            else:
                logger.exception("AI generation failed for %s after %d attempt(s)", user_id, attempt)
                return None
        except Exception:
            logger.exception("AI generation failed for %s", user_id)
            return None
