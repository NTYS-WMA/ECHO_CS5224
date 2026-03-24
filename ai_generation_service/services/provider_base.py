"""
Abstract base class for AI model providers.

All provider implementations (Bedrock, OpenAI-compatible fallback, etc.)
must implement this interface to ensure consistent behavior across the
retry and fallback chain.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ProviderResponse:
    """Standardized response from any AI provider."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int


@dataclass
class EmbeddingResponse:
    """Standardized response from an embedding request."""

    embedding: List[float]
    model: str
    input_tokens: int


class AIProviderBase(ABC):
    """Abstract interface for AI model providers."""

    @abstractmethod
    async def generate(
        self,
        messages: List[dict],
        temperature: float = 0.7,
        max_tokens: int = 512,
        stop_sequences: Optional[List[str]] = None,
    ) -> ProviderResponse:
        """
        Send a chat completion request to the AI provider.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            stop_sequences: Optional stop sequences.

        Returns:
            ProviderResponse with generated content and usage metadata.

        Raises:
            ProviderTimeoutError: If the provider does not respond in time.
            ProviderError: For any other provider-level failure.
        """
        ...

    @abstractmethod
    async def embed(
        self,
        text: str,
    ) -> EmbeddingResponse:
        """
        Generate an embedding vector for the given text.

        Args:
            text: The input text to embed.

        Returns:
            EmbeddingResponse with the embedding vector and usage metadata.

        Raises:
            ProviderTimeoutError: If the provider does not respond in time.
            ProviderError: For any other provider-level failure.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the provider is reachable and healthy."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the human-readable provider name."""
        ...


class ProviderTimeoutError(Exception):
    """Raised when the AI provider does not respond within the timeout."""
    pass


class ProviderError(Exception):
    """Raised for general AI provider failures."""
    pass
