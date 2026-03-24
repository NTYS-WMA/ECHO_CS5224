import os
from typing import Literal, Optional

from volcenginesdkarkruntime import Ark

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class DoubaoEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "doubao-embedding-text-240715"
        self.config.embedding_dims = self.config.embedding_dims or 2560

        self.client = Ark(
            api_key=self.config.api_key,
            base_url=self.config.doubao_base_url
        )

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using Doubao.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        response = self.client.embeddings.create(
            model=self.config.model,
            input=text,
            encoding_format="float"
        )
        return response.data[0].embedding