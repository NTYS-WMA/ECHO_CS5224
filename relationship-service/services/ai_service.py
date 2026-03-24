"""
AI Service — single-turn completion for session scoring.

Delegates to the team's AI Generation Service via HTTP.

Endpoint: POST /api/v1/generation/execute  (host:8003)
Template:  tpl_sentiment_analysis — variables: {"text": <prompt>}

"""
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config import get_settings

settings = get_settings()

_EXECUTE_URL = f"{settings.ai_generation_service_url}/api/v1/generation/execute"
_TEMPLATE_ID = "tpl_sentiment_analysis"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def complete(prompt: str, max_tokens: int = 256) -> str:
    """Single-turn completion via the AI Generation Service. Returns raw text."""
    payload = {
        "user_id": "relationship-service",
        "template_id": _TEMPLATE_ID,
        "variables": {"text": prompt},
        "generation_config": {"max_tokens": max_tokens},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(_EXECUTE_URL, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["output"][0]["content"].strip()
