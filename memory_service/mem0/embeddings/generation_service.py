import logging
from typing import Dict, Literal, Optional, Union

import requests

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase

logger = logging.getLogger(__name__)


class GenerationServiceEmbedding(EmbeddingBase):
    """
    Embedding provider that routes calls through ai_generation_service.
    Uses Amazon Bedrock Titan embed-text-v2 (1024 dims) under the hood.
    """

    def __init__(self, config: Optional[Union[BaseEmbedderConfig, Dict]] = None):
        if isinstance(config, dict):
            known_keys = set(BaseEmbedderConfig().__dict__.keys())
            base_cfg = BaseEmbedderConfig(**{k: v for k, v in config.items() if k in known_keys})
        elif config is None:
            base_cfg = BaseEmbedderConfig()
        else:
            base_cfg = config

        super().__init__(base_cfg)

        raw = config if isinstance(config, dict) else {}
        self._service_url = raw.get("service_url", "http://localhost:8003").rstrip("/")
        self.config.embedding_dims = raw.get("embedding_dims", 1024)

    def embed(self, text: str, memory_action: Optional[Literal["add", "search", "update"]] = None) -> list:
        """
        Get the embedding for the given text via ai_generation_service.

        Args:
            text: The text to embed.
            memory_action: Unused, kept for interface compatibility.

        Returns:
            list: The embedding vector (1024 dims).
        """
        payload = {
            "user_id": "memory-service",
            "input": text,
        }

        try:
            resp = requests.post(
                f"{self._service_url}/api/v1/generation/embeddings",
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["embedding"]
        except Exception as e:
            logger.error(f"GenerationServiceEmbedding: request failed: {e}")
            raise
