"""
Core generation service orchestrating AI provider calls with retry and fallback.

This service is the central business logic layer of the AI Generation Service.
It handles:
- Chat completion requests from the Conversation Orchestrator.
- Summary generation requests from the Memory Service.
- Proactive message generation requests from the Proactive Engagement Service.
- Retry logic with exponential backoff.
- Fallback to a secondary provider on primary failure.
- Event publishing for telemetry and failure monitoring.
"""

import asyncio
import logging
from typing import List, Optional

from ..config.settings import Settings
from ..events.publisher import EventPublisher
from ..models.requests import (
    ChatCompletionRequest,
    ProactiveMessageRequest,
    SummaryGenerationRequest,
)
from ..models.responses import (
    ChatCompletionResponse,
    ErrorResponse,
    OutputItem,
    ProactiveMessageResponse,
    SummaryGenerationResponse,
    UsageInfo,
)
from ..utils.helpers import generate_event_id, generate_response_id
from .conversation_store_client import ConversationStoreClient
from .prompt_builder import PromptBuilder
from .provider_base import AIProviderBase, ProviderError, ProviderTimeoutError

logger = logging.getLogger(__name__)


class GenerationService:
    """
    Core service that processes generation requests with retry and fallback.
    """

    def __init__(
        self,
        primary_provider: AIProviderBase,
        fallback_provider: Optional[AIProviderBase],
        event_publisher: EventPublisher,
        conversation_store: ConversationStoreClient,
        settings: Settings,
    ):
        """
        Initialize the GenerationService.

        Args:
            primary_provider: The primary AI provider (e.g., Bedrock/Claude).
            fallback_provider: Optional fallback AI provider.
            event_publisher: Event publisher for telemetry and failure events.
            conversation_store: Client for retrieving conversation messages.
            settings: Service configuration.
        """
        self._primary = primary_provider
        self._fallback = fallback_provider
        self._events = event_publisher
        self._conversation_store = conversation_store
        self._settings = settings

    # ------------------------------------------------------------------ #
    # Chat Completion
    # ------------------------------------------------------------------ #

    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """
        Handle a chat completion request from the Conversation Orchestrator.

        Args:
            request: The chat completion request.

        Returns:
            ChatCompletionResponse with generated text and usage info.

        Raises:
            GenerationError: If all providers fail after retries.
        """
        messages = PromptBuilder.build_chat_completion_messages(
            [m.model_dump() for m in request.messages]
        )

        temperature = (
            request.generation_config.temperature
            if request.generation_config and request.generation_config.temperature is not None
            else self._settings.DEFAULT_TEMPERATURE
        )
        max_tokens = (
            request.generation_config.max_tokens
            if request.generation_config and request.generation_config.max_tokens is not None
            else self._settings.DEFAULT_MAX_TOKENS
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

        # Publish telemetry event
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

    # ------------------------------------------------------------------ #
    # Summary Generation
    # ------------------------------------------------------------------ #

    async def generate_summary(
        self, request: SummaryGenerationRequest
    ) -> SummaryGenerationResponse:
        """
        Handle a summary generation request from the Memory Service.

        Retrieves the conversation messages from the Conversation Persistence
        Store, builds a summarization prompt, and invokes the AI provider.

        Args:
            request: The summary generation request.

        Returns:
            SummaryGenerationResponse with the generated summary.

        Raises:
            GenerationError: If all providers fail after retries.
        """
        # Retrieve conversation messages for the specified window
        # TO BE UPDATED: Error handling for conversation store failures
        try:
            conversation_messages = (
                await self._conversation_store.get_messages_by_window(
                    conversation_id=request.conversation_id,
                    from_message_id=request.messages_window.from_message_id,
                    to_message_id=request.messages_window.to_message_id,
                )
            )
        except Exception as e:
            logger.error(
                "Failed to retrieve conversation messages for summarization: %s",
                str(e),
            )
            # If we cannot retrieve messages, we cannot summarize.
            raise GenerationError(
                error_code="CONVERSATION_STORE_UNAVAILABLE",
                message=f"Failed to retrieve conversation messages: {str(e)}",
                retryable=True,
            )

        messages = PromptBuilder.build_summary_messages(
            conversation_messages=conversation_messages,
            summary_type=request.summary_type,
        )

        provider_response = await self._invoke_with_retry_and_fallback(
            messages=messages,
            temperature=self._settings.SUMMARY_TEMPERATURE,
            max_tokens=self._settings.SUMMARY_MAX_TOKENS,
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

        # Publish telemetry event
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

    # ------------------------------------------------------------------ #
    # Proactive Message Generation
    # ------------------------------------------------------------------ #

    async def generate_proactive_message(
        self, request: ProactiveMessageRequest
    ) -> ProactiveMessageResponse:
        """
        Handle a proactive message generation request from the Proactive
        Engagement Service.

        Args:
            request: The proactive message generation request.

        Returns:
            ProactiveMessageResponse with the generated outreach message.

        Raises:
            GenerationError: If all providers fail after retries.
        """
        messages = PromptBuilder.build_proactive_messages(
            relationship_tier=request.relationship.tier,
            affinity_score=request.relationship.affinity_score,
            days_inactive=request.relationship.days_inactive,
            recent_summary=(
                request.context.recent_summary if request.context else None
            ),
            timezone=request.context.timezone if request.context else None,
            tone=(
                request.constraints.tone
                if request.constraints and request.constraints.tone
                else "friendly"
            ),
        )

        max_tokens = (
            request.constraints.max_tokens
            if request.constraints and request.constraints.max_tokens
            else self._settings.PROACTIVE_MAX_TOKENS
        )

        provider_response = await self._invoke_with_retry_and_fallback(
            messages=messages,
            temperature=self._settings.PROACTIVE_TEMPERATURE,
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

        # Publish telemetry event
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

    # ------------------------------------------------------------------ #
    # Retry and Fallback Logic
    # ------------------------------------------------------------------ #

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

        Args:
            messages: Provider-ready message list.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens.
            stop_sequences: Optional stop sequences.
            operation: Operation name for logging and events.
            user_id: User ID for event publishing.
            correlation_id: Correlation ID for tracing.

        Returns:
            ProviderResponse from whichever provider succeeds.

        Raises:
            GenerationError: If all attempts fail.
        """
        last_error = None
        fallback_attempted = False

        # Try primary provider with retries
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
                    backoff = self._settings.RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                    await asyncio.sleep(backoff)
            except ProviderError as e:
                last_error = e
                logger.warning(
                    "Primary provider error on attempt %d: %s", attempt, str(e)
                )
                if attempt < self._settings.MAX_RETRY_ATTEMPTS:
                    backoff = self._settings.RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                    await asyncio.sleep(backoff)

        # Try fallback provider if configured
        if self._fallback and (
            (isinstance(last_error, ProviderTimeoutError) and self._settings.FALLBACK_ON_TIMEOUT)
            or (isinstance(last_error, ProviderError) and self._settings.FALLBACK_ON_PROVIDER_ERROR)
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

        # All attempts exhausted — publish failure event and raise
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

    # ------------------------------------------------------------------ #
    # Event Publishing Helpers
    # ------------------------------------------------------------------ #

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
    """Raised when all generation attempts fail."""

    def __init__(self, error_code: str, message: str, retryable: bool):
        super().__init__(message)
        self.error_code = error_code
        self.retryable = retryable
