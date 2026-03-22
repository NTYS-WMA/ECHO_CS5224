"""
Fallback AI provider using an OpenAI-compatible API endpoint.

This provider is used when the primary Bedrock provider fails or times out.
It supports any OpenAI-compatible API (e.g., Azure OpenAI, self-hosted vLLM,
or other third-party endpoints).

TO BE UPDATED: Configure the fallback provider endpoint and API key
via environment variables once the fallback strategy is finalized.
"""

import logging
from typing import List, Optional

import httpx

from .provider_base import (
    AIProviderBase,
    ProviderError,
    ProviderResponse,
    ProviderTimeoutError,
)

logger = logging.getLogger(__name__)


class FallbackProvider(AIProviderBase):
    """
    Fallback AI provider using an OpenAI-compatible chat completions API.
    """

    def __init__(
        self,
        api_base_url: str,
        api_key: str,
        model_id: str,
        timeout_seconds: int = 30,
    ):
        """
        Initialize the fallback provider.

        Args:
            api_base_url: Base URL of the OpenAI-compatible API.
            api_key: API key for authentication.
            model_id: Model identifier to use.
            timeout_seconds: Request timeout in seconds.
        """
        self._api_base_url = api_base_url.rstrip("/")
        self._api_key = api_key
        self._model_id = model_id
        self._timeout_seconds = timeout_seconds

    async def generate(
        self,
        messages: List[dict],
        temperature: float = 0.7,
        max_tokens: int = 512,
        stop_sequences: Optional[List[str]] = None,
    ) -> ProviderResponse:
        """
        Send a chat completion request to the OpenAI-compatible fallback API.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            stop_sequences: Optional stop sequences.

        Returns:
            ProviderResponse with generated content and usage metadata.
        """
        url = f"{self._api_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if stop_sequences:
            payload["stop"] = stop_sequences

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

            # Parse OpenAI-compatible response
            choice = data.get("choices", [{}])[0]
            content = choice.get("message", {}).get("content", "")
            usage = data.get("usage", {})

            return ProviderResponse(
                content=content,
                model=data.get("model", self._model_id),
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
            )

        except httpx.TimeoutException:
            logger.error(
                "Fallback provider timed out after %ds", self._timeout_seconds
            )
            raise ProviderTimeoutError(
                f"Fallback provider timed out after {self._timeout_seconds}s"
            )
        except httpx.HTTPStatusError as e:
            logger.error("Fallback provider HTTP error: %s", str(e))
            raise ProviderError(f"Fallback provider HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.error("Fallback provider error: %s", str(e))
            raise ProviderError(f"Fallback provider error: {str(e)}")

    async def health_check(self) -> bool:
        """Check if the fallback API is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self._api_base_url}/models")
                return response.status_code == 200
        except Exception:
            return False

    @property
    def provider_name(self) -> str:
        return "fallback_openai_compatible"
