from typing import Literal, Optional

from openai import OpenAI

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class QwenEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "text-embedding-v4"
        self.config.embedding_dims = self.config.embedding_dims or 1536

        self.client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.qwen_base_url
        )

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using Qwen.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        response = self.client.embeddings.create(
            model=self.config.model,
            input=text,
            dimensions=self.config.embedding_dims,
            encoding_format="float"
        )
        return response.data[0].embedding