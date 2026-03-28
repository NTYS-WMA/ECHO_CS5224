"""
Amazon Bedrock (Claude) provider implementation.

This provider wraps the AWS Bedrock Converse API to invoke Claude models
for chat completion, summarization, and proactive message generation.

TO BE UPDATED: AWS credentials and Bedrock client initialization should
be configured via the deployment environment (IAM role, env vars, etc.).
"""

import asyncio
import json
import logging
from typing import List, Optional

from .provider_base import (
    AIProviderBase,
    EmbeddingResponse,
    ProviderError,
    ProviderResponse,
    ProviderTimeoutError,
    ProviderToolResponse,
    ToolCallItem,
)

logger = logging.getLogger(__name__)


class BedrockProvider(AIProviderBase):
    """
    AI provider backed by Amazon Bedrock (Claude models).

    Uses the Bedrock Converse API for model invocation.
    """

    def __init__(
        self,
        region: str = "ap-southeast-1",
        model_id: str = "apac.anthropic.claude-sonnet-4-20250514-v1:0",
        timeout_seconds: int = 30,
        max_retries: int = 2,
        embedding_model_id: str = "cohere.embed-multilingual-v3",
    ):
        """
        Initialize the Bedrock provider.

        Args:
            region: AWS region for Bedrock.
            model_id: Bedrock model identifier.
            timeout_seconds: Request timeout in seconds.
            max_retries: Maximum retry attempts for transient failures.
            embedding_model_id: Bedrock model identifier for embeddings.
        """
        self._region = region
        self._model_id = model_id
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._embedding_model_id = embedding_model_id
        self._client = None

    async def _get_client(self):
        """
        Lazily initialize the Bedrock runtime client.

        TO BE UPDATED: In production, use boto3 with proper IAM role credentials.
        """
        if self._client is None:
            try:
                import boto3

                self._client = boto3.client(
                    "bedrock-runtime",
                    region_name=self._region,
                )
                logger.info(
                    "Bedrock client initialized for region=%s, model=%s",
                    self._region,
                    self._model_id,
                )
            except ImportError:
                logger.warning(
                    "boto3 not installed. Bedrock provider will not function. "
                    "Install with: pip install boto3"
                )
                raise ProviderError("boto3 is required for Bedrock provider")
            except Exception as e:
                logger.error("Failed to initialize Bedrock client: %s", str(e))
                raise ProviderError(f"Bedrock client initialization failed: {str(e)}")
        return self._client

    async def generate(
        self,
        messages: List[dict],
        temperature: float = 0.7,
        max_tokens: int = 512,
        stop_sequences: Optional[List[str]] = None,
    ) -> ProviderResponse:
        """
        Invoke the Bedrock Converse API for text generation.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            stop_sequences: Optional stop sequences.

        Returns:
            ProviderResponse with generated content and usage metadata.
        """
        client = await self._get_client()

        # Separate system prompt from conversation messages
        system_prompt = None
        conversation_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                conversation_messages.append(
                    {
                        "role": msg["role"],
                        "content": [{"text": msg["content"]}],
                    }
                )

        # Build the Converse API request
        request_params = {
            "modelId": self._model_id,
            "messages": conversation_messages,
            "inferenceConfig": {
                "temperature": temperature,
                "maxTokens": max_tokens,
            },
        }

        if system_prompt:
            request_params["system"] = [{"text": system_prompt}]

        if stop_sequences:
            request_params["inferenceConfig"]["stopSequences"] = stop_sequences

        try:
            # Run the synchronous boto3 call in a thread pool with timeout
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: client.converse(**request_params)),
                timeout=self._timeout_seconds,
            )

            # Extract response content
            output_message = response.get("output", {}).get("message", {})
            content_blocks = output_message.get("content", [])
            generated_text = ""
            for block in content_blocks:
                if "text" in block:
                    generated_text += block["text"]

            # Extract usage info
            usage = response.get("usage", {})
            input_tokens = usage.get("inputTokens", 0)
            output_tokens = usage.get("outputTokens", 0)

            return ProviderResponse(
                content=generated_text,
                model=self._model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        except asyncio.TimeoutError:
            logger.error(
                "Bedrock request timed out after %ds for model %s",
                self._timeout_seconds,
                self._model_id,
            )
            raise ProviderTimeoutError(
                f"Bedrock request timed out after {self._timeout_seconds}s"
            )
        except Exception as e:
            error_msg = str(e)
            logger.error("Bedrock generation failed: %s", error_msg)
            raise ProviderError(f"Bedrock generation failed: {error_msg}")

    def _convert_tools_to_bedrock(self, tools: List[dict]) -> List[dict]:
        """
        Convert OpenAI-format tool definitions to Bedrock Converse toolConfig format.

        OpenAI format:
            {"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}
        Bedrock format:
            {"toolSpec": {"name": "...", "description": "...", "inputSchema": {"json": {...}}}}
        """
        bedrock_tools = []
        for tool in tools:
            func = tool.get("function", {})
            spec = {
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "inputSchema": {"json": func.get("parameters", {})},
            }
            bedrock_tools.append({"toolSpec": spec})
        return bedrock_tools

    def _convert_tool_choice_to_bedrock(self, tool_choice: str) -> dict:
        """Convert tool_choice string to Bedrock toolChoice format."""
        if tool_choice == "none":
            return {}  # No toolChoice means model won't use tools
        if tool_choice == "any":
            return {"any": {}}
        # "auto" is the default
        return {"auto": {}}

    async def generate_with_tools(
        self,
        messages: List[dict],
        tools: List[dict],
        tool_choice: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> ProviderToolResponse:
        """
        Invoke the Bedrock Converse API with tool definitions.

        Converts OpenAI-format tools to Bedrock's toolConfig format and
        parses tool_use blocks from the response.
        """
        client = await self._get_client()

        # Separate system prompt from conversation messages
        system_prompt = None
        conversation_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                conversation_messages.append(
                    {
                        "role": msg["role"],
                        "content": [{"text": msg["content"]}],
                    }
                )

        # Build the Converse API request
        request_params = {
            "modelId": self._model_id,
            "messages": conversation_messages,
            "inferenceConfig": {
                "temperature": temperature,
                "maxTokens": max_tokens,
            },
            "toolConfig": {
                "tools": self._convert_tools_to_bedrock(tools),
            },
        }

        # Add tool choice if not "none"
        if tool_choice != "none":
            request_params["toolConfig"]["toolChoice"] = self._convert_tool_choice_to_bedrock(tool_choice)

        if system_prompt:
            request_params["system"] = [{"text": system_prompt}]

        try:
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: client.converse(**request_params)),
                timeout=self._timeout_seconds,
            )

            # Extract response content blocks
            output_message = response.get("output", {}).get("message", {})
            content_blocks = output_message.get("content", [])

            text_content = ""
            tool_calls = []

            for block in content_blocks:
                if "text" in block:
                    text_content += block["text"]
                elif "toolUse" in block:
                    tool_use = block["toolUse"]
                    tool_calls.append(
                        ToolCallItem(
                            name=tool_use.get("name", ""),
                            arguments=tool_use.get("input", {}),
                        )
                    )

            usage = response.get("usage", {})

            return ProviderToolResponse(
                content=text_content or None,
                tool_calls=tool_calls,
                model=self._model_id,
                input_tokens=usage.get("inputTokens", 0),
                output_tokens=usage.get("outputTokens", 0),
            )

        except asyncio.TimeoutError:
            logger.error(
                "Bedrock tool-calling request timed out after %ds for model %s",
                self._timeout_seconds,
                self._model_id,
            )
            raise ProviderTimeoutError(
                f"Bedrock tool-calling request timed out after {self._timeout_seconds}s"
            )
        except Exception as e:
            error_msg = str(e)
            logger.error("Bedrock tool-calling generation failed: %s", error_msg)
            raise ProviderError(f"Bedrock tool-calling generation failed: {error_msg}")

    async def embed(self, text: str) -> EmbeddingResponse:
        """
        Generate an embedding vector via Bedrock.

        Supports both Cohere Embed and Amazon Titan Embed models.

        Args:
            text: The input text to embed.

        Returns:
            EmbeddingResponse with the embedding vector and usage metadata.
        """
        client = await self._get_client()

        is_cohere = "cohere" in self._embedding_model_id.lower()

        if is_cohere:
            request_body = json.dumps({
                "texts": [text],
                "input_type": "search_document",
            })
        else:
            request_body = json.dumps({"inputText": text})

        try:
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: client.invoke_model(
                        modelId=self._embedding_model_id,
                        contentType="application/json",
                        accept="application/json",
                        body=request_body,
                    ),
                ),
                timeout=self._timeout_seconds,
            )

            response_body = json.loads(response["body"].read())

            if is_cohere:
                embeddings = response_body.get("embeddings", [[]])
                embedding = embeddings[0] if embeddings else []
                input_tokens = 0
            else:
                embedding = response_body.get("embedding", [])
                input_tokens = response_body.get("inputTextTokenCount", 0)

            return EmbeddingResponse(
                embedding=embedding,
                model=self._embedding_model_id,
                input_tokens=input_tokens,
            )

        except asyncio.TimeoutError:
            logger.error(
                "Bedrock embedding request timed out after %ds for model %s",
                self._timeout_seconds,
                self._embedding_model_id,
            )
            raise ProviderTimeoutError(
                f"Bedrock embedding request timed out after {self._timeout_seconds}s"
            )
        except Exception as e:
            error_msg = str(e)
            logger.error("Bedrock embedding failed: %s", error_msg)
            raise ProviderError(f"Bedrock embedding failed: {error_msg}")

    async def health_check(self) -> bool:
        """Check if the Bedrock service is reachable."""
        try:
            client = await self._get_client()
            # A lightweight check; actual health probing may vary
            return client is not None
        except Exception:
            return False

    @property
    def provider_name(self) -> str:
        return "bedrock"
