"""
Core generation service — the AI execution engine.

This service is the central execution layer of the AI Generation Service.
It does NOT contain business logic or prompt construction. Instead it:
- Accepts template-rendered messages from the TemplateRenderer.
- Invokes AI providers with retry and fallback.
- Publishes telemetry events.

The prompt assembly responsibility is split:
- **Business callers** assemble the core prompt content (variables).
- **TemplateRenderer** renders templates with those variables.
- **GenerationService** executes the rendered prompt against AI providers.

Supported invocation patterns:
1. Template-based: template_id + variables -> render -> execute
2. Multi-turn chat: template_id + messages -> merge system prompt -> execute
3. Embedding: text -> embed via provider
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from ..config.settings import Settings
from ..events.publisher import EventPublisher
from ..models.requests import (
    ChatCompletionRequest,
    EmbeddingRequest,
    ProactiveMessageRequest,
    SummaryGenerationRequest,
    TemplateGenerationRequest,
)
from ..models.responses import (
    ChatCompletionResponse,
    EmbeddingResponse,
    GenerationResponse,
    OutputItem,
    ProactiveMessageResponse,
    SummaryGenerationResponse,
    UsageInfo,
)
from ..utils.helpers import generate_event_id, generate_response_id
from .provider_base import AIProviderBase, ProviderError, ProviderTimeoutError
from .template_renderer import TemplateRenderer, TemplateRenderError

logger = logging.getLogger(__name__)

# Default template IDs for legacy endpoints.
# These correspond to preset templates in the prompt_templates/ directory.
DEFAULT_CHAT_TEMPLATE = "tpl_chat_completion"
DEFAULT_SUMMARY_TEMPLATE = "tpl_memory_compaction"
DEFAULT_PROACTIVE_TEMPLATE = "tpl_proactive_outreach"


class GenerationService:
    """
    Core AI execution engine with retry, fallback, and telemetry.
    """

    def __init__(
        self,
        primary_provider: AIProviderBase,
        fallback_provider: Optional[AIProviderBase],
        event_publisher: EventPublisher,
        template_renderer: TemplateRenderer,
        settings: Settings,
    ):
        """
        Initialize the GenerationService.

        Args:
            primary_provider: The primary AI provider (e.g., Bedrock/Claude).
            fallback_provider: Optional fallback AI provider.
            event_publisher: Event publisher for telemetry and failure events.
            template_renderer: Renderer for prompt templates.
            settings: Service configuration.
        """
        self._primary = primary_provider
        self._fallback = fallback_provider
        self._events = event_publisher
        self._renderer = template_renderer
        self._settings = settings

    # ================================================================== #
    # PRIMARY INTERFACE: Template-based generation
    # ================================================================== #

    async def execute(
        self, request: TemplateGenerationRequest
    ) -> GenerationResponse:
        """
        Execute a generation request using a prompt template.

        This is the primary generation interface. The caller specifies a
        template_id and provides variables (or messages for multi-turn chat).
        The service renders the template and executes it.

        Args:
            request: The template-based generation request.

        Returns:
            GenerationResponse with generated text and usage info.

        Raises:
            GenerationError: If rendering or all provider attempts fail.
        """
        template_id = request.template_id

        try:
            # Determine rendering mode
            if request.messages:
                # Multi-turn chat mode: merge template system prompt with messages
                messages, defaults = self._renderer.render_with_messages(
                    template_id=template_id,
                    messages=[m.model_dump() for m in request.messages],
                )
            else:
                # Variable-based mode: render template with variables
                messages, defaults = self._renderer.render(
                    template_id=template_id,
                    variables=request.variables,
                )
        except TemplateRenderError as e:
            raise GenerationError(
                error_code="TEMPLATE_RENDER_ERROR",
                message=str(e),
                retryable=False,
            )

        # Resolve generation parameters: caller config > template defaults > service defaults
        temperature = self._resolve_param(
            request.generation_config.temperature if request.generation_config else None,
            defaults.temperature if defaults else None,
            self._settings.DEFAULT_TEMPERATURE,
        )
        max_tokens = self._resolve_param(
            request.generation_config.max_tokens if request.generation_config else None,
            defaults.max_tokens if defaults else None,
            self._settings.DEFAULT_MAX_TOKENS,
        )
        stop_sequences = (
            request.generation_config.stop_sequences
            if request.generation_config
            else (defaults.stop_sequences if defaults else None)
        )

        provider_response = await self._invoke_with_retry_and_fallback(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stop_sequences=stop_sequences,
            operation=f"execute:{template_id}",
            user_id=request.user_id,
            correlation_id=request.correlation_id,
        )

        response = GenerationResponse(
            response_id=generate_response_id(),
            template_id=template_id,
            output=[OutputItem(type="text", content=provider_response.content)],
            model=provider_response.model,
            usage=UsageInfo(
                input_tokens=provider_response.input_tokens,
                output_tokens=provider_response.output_tokens,
            ),
        )

        await self._publish_completed_event(
            operation=f"execute:{template_id}",
            user_id=request.user_id,
            model=provider_response.model,
            usage={
                "input_tokens": provider_response.input_tokens,
                "output_tokens": provider_response.output_tokens,
            },
            correlation_id=request.correlation_id,
        )

        return response

    # ================================================================== #
    # EMBEDDING INTERFACE
    # ================================================================== #

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """
        Generate an embedding vector for the given input text.

        This endpoint is parallel to execute() and uses the same primary
        provider's embedding capability (e.g., Amazon Titan Embeddings).

        Args:
            request: The embedding request with input text.

        Returns:
            EmbeddingResponse with the embedding vector and usage info.

        Raises:
            GenerationError: If the provider fails after retries.
        """
        last_error = None

        for attempt in range(1, self._settings.MAX_RETRY_ATTEMPTS + 1):
            try:
                logger.info(
                    "Invoking primary provider '%s' for embedding (attempt %d/%d)",
                    self._primary.provider_name,
                    attempt,
                    self._settings.MAX_RETRY_ATTEMPTS,
                )
                provider_response = await self._primary.embed(text=request.input)

                response = EmbeddingResponse(
                    response_id=generate_response_id(),
                    embedding=provider_response.embedding,
                    dimension=len(provider_response.embedding),
                    model=provider_response.model,
                    usage=UsageInfo(
                        input_tokens=provider_response.input_tokens,
                        output_tokens=0,
                    ),
                )

                await self._publish_completed_event(
                    operation="embedding",
                    user_id=request.user_id,
                    model=provider_response.model,
                    usage={"input_tokens": provider_response.input_tokens, "output_tokens": 0},
                    correlation_id=request.correlation_id,
                )

                return response

            except ProviderTimeoutError as e:
                last_error = e
                logger.warning("Embedding provider timeout on attempt %d: %s", attempt, str(e))
                if attempt < self._settings.MAX_RETRY_ATTEMPTS:
                    backoff = self._settings.RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                    await asyncio.sleep(backoff)
            except ProviderError as e:
                last_error = e
                logger.warning("Embedding provider error on attempt %d: %s", attempt, str(e))
                if attempt < self._settings.MAX_RETRY_ATTEMPTS:
                    backoff = self._settings.RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                    await asyncio.sleep(backoff)

        # Try fallback if configured
        if self._fallback and (
            (isinstance(last_error, ProviderTimeoutError) and self._settings.FALLBACK_ON_TIMEOUT)
            or (isinstance(last_error, ProviderError) and self._settings.FALLBACK_ON_PROVIDER_ERROR)
        ):
            try:
                logger.info("Falling back to provider '%s' for embedding", self._fallback.provider_name)
                provider_response = await self._fallback.embed(text=request.input)

                response = EmbeddingResponse(
                    response_id=generate_response_id(),
                    embedding=provider_response.embedding,
                    dimension=len(provider_response.embedding),
                    model=provider_response.model,
                    usage=UsageInfo(
                        input_tokens=provider_response.input_tokens,
                        output_tokens=0,
                    ),
                )

                await self._publish_completed_event(
                    operation="embedding",
                    user_id=request.user_id,
                    model=provider_response.model,
                    usage={"input_tokens": provider_response.input_tokens, "output_tokens": 0},
                    correlation_id=request.correlation_id,
                )

                return response

            except (ProviderTimeoutError, ProviderError) as e:
                last_error = e
                logger.error("Fallback embedding also failed: %s", str(e))

        error_code = (
            "PROVIDER_TIMEOUT"
            if isinstance(last_error, ProviderTimeoutError)
            else "PROVIDER_ERROR"
        )

        await self._publish_failed_event(
            operation="embedding",
            user_id=request.user_id,
            error_code=error_code,
            retryable=isinstance(last_error, ProviderTimeoutError),
            fallback_attempted=self._fallback is not None,
            correlation_id=request.correlation_id,
        )

        raise GenerationError(
            error_code=error_code,
            message=str(last_error),
            retryable=isinstance(last_error, ProviderTimeoutError),
        )

    # ================================================================== #
    # LEGACY INTERFACES (backward compatibility)
    # ================================================================== #

    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """
        Handle a chat completion request (legacy endpoint).

        Maps to the template-based execution engine using the chat template.
        """
        template_id = request.template_id or DEFAULT_CHAT_TEMPLATE

        try:
            messages, defaults = self._renderer.render_with_messages(
                template_id=template_id,
                messages=[m.model_dump() for m in request.messages],
            )
        except TemplateRenderError as e:
            raise GenerationError(
                error_code="TEMPLATE_RENDER_ERROR",
                message=str(e),
                retryable=False,
            )

        temperature = self._resolve_param(
            request.generation_config.temperature if request.generation_config else None,
            defaults.temperature if defaults else None,
            self._settings.DEFAULT_TEMPERATURE,
        )
        max_tokens = self._resolve_param(
            request.generation_config.max_tokens if request.generation_config else None,
            defaults.max_tokens if defaults else None,
            self._settings.DEFAULT_MAX_TOKENS,
        )
        stop_sequences = (
            request.generation_config.stop_sequences
            if request.generation_config
            else None
        )

        provider_response = await self._invoke_with_retry_and_fallback(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stop_sequences=stop_sequences,
            operation="chat_completion",
            user_id=request.user_id,
            correlation_id=request.correlation_id,
        )

        response = ChatCompletionResponse(
            response_id=generate_response_id(),
            output=[OutputItem(type="text", content=provider_response.content)],
            model=provider_response.model,
            usage=UsageInfo(
                input_tokens=provider_response.input_tokens,
                output_tokens=provider_response.output_tokens,
            ),
        )

        await self._publish_completed_event(
            operation="chat_completion",
            user_id=request.user_id,
            model=provider_response.model,
            usage={
                "input_tokens": provider_response.input_tokens,
                "output_tokens": provider_response.output_tokens,
            },
            correlation_id=request.correlation_id,
        )

        return response

    async def generate_summary(
        self, request: SummaryGenerationRequest
    ) -> SummaryGenerationResponse:
        """
        Handle a summary generation request (legacy endpoint).

        NOTE: This legacy endpoint no longer fetches conversation messages
        internally. The caller (Memory Service) must provide the conversation
        content via the messages_window identifiers, and the actual message
        retrieval is the caller's responsibility. This method now constructs
        the summary prompt from the request metadata and delegates to the
        template-based execution engine.
        """
        # Build user prompt from request metadata.
        # The caller is responsible for providing conversation content via
        # the unified /execute endpoint. This legacy path constructs a
        # prompt from the available request fields.
        user_prompt = (
            f"Please summarize the conversation into a compact memory entry.\n"
            f"Summary type: {request.summary_type}\n"
            f"Conversation ID: {request.conversation_id}\n"
            f"Message range: {request.messages_window.from_message_id} "
            f"to {request.messages_window.to_message_id}\n\n"
            f"Provide a concise summary capturing the user's key preferences, "
            f"emotional state, and important facts."
        )

        template_id = request.template_id or DEFAULT_SUMMARY_TEMPLATE

        try:
            messages, defaults = self._renderer.render(
                template_id=template_id,
                variables={"user_prompt": user_prompt},
            )
        except TemplateRenderError as e:
            raise GenerationError(
                error_code="TEMPLATE_RENDER_ERROR",
                message=str(e),
                retryable=False,
            )

        temperature = self._resolve_param(
            None,
            defaults.temperature if defaults else None,
            self._settings.DEFAULT_TEMPERATURE,
        )
        max_tokens = self._resolve_param(
            None,
            defaults.max_tokens if defaults else None,
            self._settings.DEFAULT_MAX_TOKENS,
        )

        provider_response = await self._invoke_with_retry_and_fallback(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stop_sequences=None,
            operation="summary_generation",
            user_id=request.user_id,
            correlation_id=request.correlation_id,
        )

        response = SummaryGenerationResponse(
            content=provider_response.content,
            model=provider_response.model,
            usage=UsageInfo(
                input_tokens=provider_response.input_tokens,
                output_tokens=provider_response.output_tokens,
            ),
        )

        await self._publish_completed_event(
            operation="summary_generation",
            user_id=request.user_id,
            model=provider_response.model,
            usage={
                "input_tokens": provider_response.input_tokens,
                "output_tokens": provider_response.output_tokens,
            },
            correlation_id=request.correlation_id,
        )

        return response

    async def generate_proactive_message(
        self, request: ProactiveMessageRequest
    ) -> ProactiveMessageResponse:
        """
        Handle a proactive message generation request (legacy endpoint).

        Assembles the context block and maps to template-based execution.
        """
        # Build context block — this is the business-layer assembly that
        # will eventually move to the Cron Service caller
        context_parts = [
            f"Relationship tier: {request.relationship.tier}",
            f"Affinity score: {request.relationship.affinity_score:.2f}",
            f"Days since last interaction: {request.relationship.days_inactive}",
            f"Desired tone: {request.constraints.tone if request.constraints and request.constraints.tone else 'friendly'}",
        ]
        if request.context and request.context.timezone:
            context_parts.append(f"User timezone: {request.context.timezone}")
        if request.context and request.context.recent_summary:
            context_parts.append(
                f"Recent context about the user: {request.context.recent_summary}"
            )
        context_block = "\n".join(context_parts)

        # Assemble the full user prompt (business-layer responsibility)
        user_prompt = (
            f"Based on the following context, compose a short, natural check-in "
            f"message to re-engage this user. The message should feel genuine "
            f"and not automated.\n\n{context_block}\n\n"
            f"Generate only the message text, nothing else."
        )

        template_id = request.template_id or DEFAULT_PROACTIVE_TEMPLATE

        try:
            messages, defaults = self._renderer.render(
                template_id=template_id,
                variables={"user_prompt": user_prompt},
            )
        except TemplateRenderError as e:
            raise GenerationError(
                error_code="TEMPLATE_RENDER_ERROR",
                message=str(e),
                retryable=False,
            )

        max_tokens = self._resolve_param(
            request.constraints.max_tokens if request.constraints else None,
            defaults.max_tokens if defaults else None,
            self._settings.DEFAULT_MAX_TOKENS,
        )
        temperature = self._resolve_param(
            None,
            defaults.temperature if defaults else None,
            self._settings.DEFAULT_TEMPERATURE,
        )

        provider_response = await self._invoke_with_retry_and_fallback(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stop_sequences=None,
            operation="proactive_message",
            user_id=request.user_id,
            correlation_id=request.correlation_id,
        )

        response = ProactiveMessageResponse(
            response_id=generate_response_id(),
            output=[OutputItem(type="text", content=provider_response.content)],
            model=provider_response.model,
            usage=UsageInfo(
                input_tokens=provider_response.input_tokens,
                output_tokens=provider_response.output_tokens,
            ),
        )

        await self._publish_completed_event(
            operation="proactive_message",
            user_id=request.user_id,
            model=provider_response.model,
            usage={
                "input_tokens": provider_response.input_tokens,
                "output_tokens": provider_response.output_tokens,
            },
            correlation_id=request.correlation_id,
        )

        return response

    # ================================================================== #
    # Retry and Fallback Logic
    # ================================================================== #

    async def _invoke_with_retry_and_fallback(
        self,
        messages: List[dict],
        temperature: float,
        max_tokens: int,
        stop_sequences: Optional[List[str]],
        operation: str,
        user_id: str,
        correlation_id: Optional[str],
    ):
        """
        Invoke the primary provider with retry, then fall back if configured.

        Returns:
            ProviderResponse from whichever provider succeeds.

        Raises:
            GenerationError: If all attempts fail.
        """
        last_error = None
        fallback_attempted = False

        for attempt in range(1, self._settings.MAX_RETRY_ATTEMPTS + 1):
            try:
                logger.info(
                    "Invoking primary provider '%s' for %s (attempt %d/%d)",
                    self._primary.provider_name,
                    operation,
                    attempt,
                    self._settings.MAX_RETRY_ATTEMPTS,
                )
                return await self._primary.generate(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stop_sequences=stop_sequences,
                )
            except ProviderTimeoutError as e:
                last_error = e
                logger.warning(
                    "Primary provider timeout on attempt %d: %s", attempt, str(e)
                )
                if attempt < self._settings.MAX_RETRY_ATTEMPTS:
                    backoff = self._settings.RETRY_BACKOFF_BASE_SECONDS * (
                        2 ** (attempt - 1)
                    )
                    await asyncio.sleep(backoff)
            except ProviderError as e:
                last_error = e
                logger.warning(
                    "Primary provider error on attempt %d: %s", attempt, str(e)
                )
                if attempt < self._settings.MAX_RETRY_ATTEMPTS:
                    backoff = self._settings.RETRY_BACKOFF_BASE_SECONDS * (
                        2 ** (attempt - 1)
                    )
                    await asyncio.sleep(backoff)

        if self._fallback and (
            (
                isinstance(last_error, ProviderTimeoutError)
                and self._settings.FALLBACK_ON_TIMEOUT
            )
            or (
                isinstance(last_error, ProviderError)
                and self._settings.FALLBACK_ON_PROVIDER_ERROR
            )
        ):
            fallback_attempted = True
            try:
                logger.info(
                    "Falling back to provider '%s' for %s",
                    self._fallback.provider_name,
                    operation,
                )
                return await self._fallback.generate(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stop_sequences=stop_sequences,
                )
            except (ProviderTimeoutError, ProviderError) as e:
                last_error = e
                logger.error("Fallback provider also failed: %s", str(e))

        error_code = (
            "PROVIDER_TIMEOUT"
            if isinstance(last_error, ProviderTimeoutError)
            else "PROVIDER_ERROR"
        )

        await self._publish_failed_event(
            operation=operation,
            user_id=user_id,
            error_code=error_code,
            retryable=isinstance(last_error, ProviderTimeoutError),
            fallback_attempted=fallback_attempted,
            correlation_id=correlation_id,
        )

        raise GenerationError(
            error_code=error_code,
            message=str(last_error),
            retryable=isinstance(last_error, ProviderTimeoutError),
        )

    # ================================================================== #
    # Parameter Resolution
    # ================================================================== #

    @staticmethod
    def _resolve_param(caller_value, template_default, service_default):
        """
        Resolve a generation parameter using the priority chain:
        caller config > template default > service default.
        """
        if caller_value is not None:
            return caller_value
        if template_default is not None:
            return template_default
        return service_default

    # ================================================================== #
    # Event Publishing Helpers
    # ================================================================== #

    async def _publish_completed_event(
        self,
        operation: str,
        user_id: str,
        model: str,
        usage: Optional[dict],
        correlation_id: Optional[str],
    ) -> None:
        """Publish a telemetry event for a successful generation."""
        if not self._settings.ENABLE_TELEMETRY_EVENTS:
            return
        try:
            await self._events.publish_generation_completed(
                event_id=generate_event_id(),
                user_id=user_id,
                operation=operation,
                model=model,
                usage=usage,
                correlation_id=correlation_id,
            )
        except Exception as e:
            logger.error("Failed to publish completed event: %s", str(e))

    async def _publish_failed_event(
        self,
        operation: str,
        user_id: str,
        error_code: str,
        retryable: bool,
        fallback_attempted: bool,
        correlation_id: Optional[str],
    ) -> None:
        """Publish a failure event for monitoring and alerting."""
        try:
            await self._events.publish_generation_failed(
                event_id=generate_event_id(),
                user_id=user_id,
                operation=operation,
                error_code=error_code,
                retryable=retryable,
                fallback_attempted=fallback_attempted,
                correlation_id=correlation_id,
            )
        except Exception as e:
            logger.error("Failed to publish failure event: %s", str(e))


class GenerationError(Exception):
    """Raised when generation fails (rendering, provider, or exhausted retries)."""

    def __init__(self, error_code: str, message: str, retryable: bool):
        super().__init__(message)
        self.error_code = error_code
        self.retryable = retryable
