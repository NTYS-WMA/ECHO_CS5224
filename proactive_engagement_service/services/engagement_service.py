"""
Core Proactive Engagement Service orchestrating the full proactive scan pipeline.

Pipeline stages:
1. Receive scan trigger (scheduled or manual).
2. Search for proactive candidates via Relationship Service.
3. For each candidate, check eligibility (consent + quiet hours) via User Profile Service.
4. Retrieve recent memory summary via Memory Service for personalization.
5. Request AI-generated proactive message via AI Generation Service.
6. Publish proactive outbound event to conversation.outbound topic.
7. Publish dispatch telemetry event to proactive.dispatch.completed topic.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional

from ..config.settings import Settings
from ..events.publisher import EventPublisher
from ..models.domain import EligibilityCheckResult, ProactiveCandidate
from ..models.events import OutboundResponseItem
from ..models.requests import (
    CandidateSearchFilters,
    ManualTriggerRequest,
    ProactiveScanTriggerEvent,
    TimeContext,
)
from ..models.responses import CandidateItem, DispatchResult, ScanStatusResponse
from ..utils.helpers import generate_event_id, generate_scan_id, get_tier_from_score
from .ai_generation_client import AIGenerationServiceClient
from .eligibility_checker import EligibilityChecker
from .memory_client import MemoryServiceClient
from .relationship_client import RelationshipServiceClient
from .user_profile_client import UserProfileServiceClient

logger = logging.getLogger(__name__)


class ProactiveEngagementService:
    """
    Core service that orchestrates the proactive engagement pipeline.
    """

    def __init__(
        self,
        relationship_client: RelationshipServiceClient,
        user_profile_client: UserProfileServiceClient,
        ai_generation_client: AIGenerationServiceClient,
        memory_client: MemoryServiceClient,
        eligibility_checker: EligibilityChecker,
        event_publisher: EventPublisher,
        settings: Settings,
    ):
        """
        Initialize the ProactiveEngagementService.

        Args:
            relationship_client: Client for the Relationship Service.
            user_profile_client: Client for the User Profile Service.
            ai_generation_client: Client for the AI Generation Service.
            memory_client: Client for the Memory Service.
            eligibility_checker: Eligibility policy checker.
            event_publisher: Event publisher for messaging layer.
            settings: Service configuration.
        """
        self._relationship = relationship_client
        self._user_profile = user_profile_client
        self._ai_generation = ai_generation_client
        self._memory = memory_client
        self._eligibility = eligibility_checker
        self._events = event_publisher
        self._settings = settings

    # ------------------------------------------------------------------ #
    # Scan Trigger Handlers
    # ------------------------------------------------------------------ #

    async def handle_scan_trigger(
        self, event: ProactiveScanTriggerEvent
    ) -> ScanStatusResponse:
        """
        Handle a proactive scan trigger event from the scheduler.

        Args:
            event: The scan trigger event.

        Returns:
            ScanStatusResponse with dispatch statistics.
        """
        scan_id = generate_scan_id()
        correlation_id = event.event_id

        logger.info(
            "Starting proactive scan %s (trigger: %s, mode: %s)",
            scan_id,
            event.event_id,
            event.mode,
        )

        # Determine time context
        window = event.window or {}
        tz = window.get("timezone", "Asia/Singapore")
        current_time = event.timestamp.isoformat()

        # Build filters from defaults
        filters = CandidateSearchFilters(
            min_days_inactive=self._settings.DEFAULT_MIN_DAYS_INACTIVE,
            min_affinity_score=self._settings.DEFAULT_MIN_AFFINITY_SCORE,
            max_batch_size=self._settings.DEFAULT_MAX_BATCH_SIZE,
        )

        return await self._execute_scan(
            scan_id=scan_id,
            filters=filters,
            timezone=tz,
            current_time=current_time,
            correlation_id=correlation_id,
        )

    async def handle_manual_trigger(
        self, request: ManualTriggerRequest
    ) -> ScanStatusResponse:
        """
        Handle a manual proactive scan trigger via the API.

        Args:
            request: The manual trigger request.

        Returns:
            ScanStatusResponse with dispatch statistics.
        """
        scan_id = generate_scan_id()
        correlation_id = request.correlation_id or generate_event_id()

        logger.info("Starting manual proactive scan %s", scan_id)

        filters = request.filters or CandidateSearchFilters(
            min_days_inactive=self._settings.DEFAULT_MIN_DAYS_INACTIVE,
            min_affinity_score=self._settings.DEFAULT_MIN_AFFINITY_SCORE,
            max_batch_size=self._settings.DEFAULT_MAX_BATCH_SIZE,
        )

        current_time = datetime.now(timezone.utc).isoformat()

        return await self._execute_scan(
            scan_id=scan_id,
            filters=filters,
            timezone=request.timezone,
            current_time=current_time,
            correlation_id=correlation_id,
        )

    # ------------------------------------------------------------------ #
    # Core Scan Pipeline
    # ------------------------------------------------------------------ #

    async def _execute_scan(
        self,
        scan_id: str,
        filters: CandidateSearchFilters,
        timezone: str,
        current_time: str,
        correlation_id: str,
    ) -> ScanStatusResponse:
        """
        Execute the full proactive engagement scan pipeline.

        Args:
            scan_id: Unique scan identifier.
            filters: Candidate selection filters.
            timezone: Target timezone.
            current_time: Current time in ISO 8601 format.
            correlation_id: Correlation ID for tracing.

        Returns:
            ScanStatusResponse with dispatch statistics.
        """
        # Stage 1: Search for candidates
        try:
            time_context = TimeContext(timezone=timezone, current_time=current_time)
            candidates = await self._relationship.search_proactive_candidates(
                filters=filters,
                time_context=time_context,
                correlation_id=correlation_id,
            )
        except Exception as e:
            logger.error("Failed to search candidates: %s", str(e))
            return ScanStatusResponse(
                scan_id=scan_id,
                status="failed",
                candidates_scanned=0,
                messages_dispatched=0,
                messages_skipped=0,
            )

        if not candidates:
            logger.info("Scan %s: No candidates found.", scan_id)
            # Publish telemetry even for empty scans
            await self._publish_dispatch_completed(
                correlation_id=correlation_id,
                candidates_scanned=0,
                messages_dispatched=0,
                messages_skipped=0,
            )
            return ScanStatusResponse(
                scan_id=scan_id,
                status="completed",
                candidates_scanned=0,
                messages_dispatched=0,
                messages_skipped=0,
            )

        logger.info("Scan %s: Found %d candidates.", scan_id, len(candidates))

        # Stage 2-6: Process candidates with concurrency control
        semaphore = asyncio.Semaphore(self._settings.MAX_CONCURRENT_DISPATCHES)
        results: List[DispatchResult] = []

        async def process_candidate(candidate: CandidateItem) -> DispatchResult:
            async with semaphore:
                return await self._process_single_candidate(
                    candidate=candidate,
                    current_time=current_time,
                    correlation_id=correlation_id,
                )

        tasks = [process_candidate(c) for c in candidates]
        results = await asyncio.gather(*tasks)

        # Aggregate statistics
        dispatched = sum(1 for r in results if r.dispatched)
        skipped = sum(1 for r in results if not r.dispatched)

        logger.info(
            "Scan %s completed: %d candidates, %d dispatched, %d skipped.",
            scan_id,
            len(candidates),
            dispatched,
            skipped,
        )

        # Publish telemetry event
        await self._publish_dispatch_completed(
            correlation_id=correlation_id,
            candidates_scanned=len(candidates),
            messages_dispatched=dispatched,
            messages_skipped=skipped,
        )

        return ScanStatusResponse(
            scan_id=scan_id,
            status="completed",
            candidates_scanned=len(candidates),
            messages_dispatched=dispatched,
            messages_skipped=skipped,
            results=results,
        )

    # ------------------------------------------------------------------ #
    # Single Candidate Processing
    # ------------------------------------------------------------------ #

    async def _process_single_candidate(
        self,
        candidate: CandidateItem,
        current_time: str,
        correlation_id: str,
    ) -> DispatchResult:
        """
        Process a single proactive engagement candidate through the full pipeline.

        Stages:
        1. Retrieve user consent and preferences from User Profile Service.
        2. Check eligibility (consent + quiet hours).
        3. Retrieve recent memory summary from Memory Service.
        4. Request AI-generated proactive message from AI Generation Service.
        5. Publish proactive outbound event.

        Args:
            candidate: The candidate to process.
            current_time: Current time in ISO 8601 format.
            correlation_id: Correlation ID for tracing.

        Returns:
            DispatchResult indicating success or skip reason.
        """
        user_id = candidate.user_id

        # Stage 1: Get user consent and preferences
        profile_consent = await self._user_profile.get_user_consent_and_preferences(
            user_id
        )
        if profile_consent is None:
            return DispatchResult(
                user_id=user_id,
                dispatched=False,
                skip_reason="profile_unavailable",
            )

        # Stage 2: Check eligibility
        eligibility = self._eligibility.check_eligibility(
            profile_consent=profile_consent,
            current_time_iso=current_time,
        )
        if not eligibility.eligible:
            return DispatchResult(
                user_id=user_id,
                dispatched=False,
                skip_reason=eligibility.skip_reason,
            )

        # Stage 3: Retrieve recent memory summary (best-effort)
        recent_summary = await self._memory.get_recent_summary(user_id)

        # Stage 4: Get channel info for outbound delivery
        channel_info = await self._user_profile.get_user_channel_info(user_id)
        if channel_info is None:
            return DispatchResult(
                user_id=user_id,
                dispatched=False,
                skip_reason="channel_info_unavailable",
            )

        # Stage 5: Request AI-generated proactive message
        tier = get_tier_from_score(candidate.affinity_score)
        generation_result = await self._ai_generation.generate_proactive_message(
            user_id=user_id,
            relationship_tier=tier,
            affinity_score=candidate.affinity_score,
            days_inactive=candidate.days_inactive,
            recent_summary=recent_summary,
            timezone=profile_consent.timezone,
            max_tokens=self._settings.DEFAULT_PROACTIVE_MAX_TOKENS,
            tone=self._settings.DEFAULT_PROACTIVE_TONE,
            correlation_id=correlation_id,
        )

        if generation_result is None:
            return DispatchResult(
                user_id=user_id,
                dispatched=False,
                skip_reason="generation_failed",
            )

        # Extract generated message content
        output = generation_result.get("output", [])
        if not output:
            return DispatchResult(
                user_id=user_id,
                dispatched=False,
                skip_reason="generation_empty",
            )

        message_content = output[0].get("content", "")
        if not message_content.strip():
            return DispatchResult(
                user_id=user_id,
                dispatched=False,
                skip_reason="generation_empty",
            )

        # Stage 6: Publish proactive outbound event
        try:
            await self._events.publish_proactive_outbound(
                event_id=generate_event_id(),
                user_id=user_id,
                channel=channel_info["channel"],
                conversation_id=channel_info["conversation_id"],
                responses=[
                    OutboundResponseItem(type="text", content=message_content)
                ],
                correlation_id=correlation_id,
                metadata={
                    "source": "proactive_engagement",
                    "days_inactive": candidate.days_inactive,
                    "affinity_score": candidate.affinity_score,
                    "tier": tier,
                },
            )
            return DispatchResult(user_id=user_id, dispatched=True)
        except Exception as e:
            logger.error(
                "Failed to publish outbound event for user %s: %s",
                user_id,
                str(e),
            )
            return DispatchResult(
                user_id=user_id,
                dispatched=False,
                skip_reason="publish_failed",
            )

    # ------------------------------------------------------------------ #
    # Telemetry
    # ------------------------------------------------------------------ #

    async def _publish_dispatch_completed(
        self,
        correlation_id: str,
        candidates_scanned: int,
        messages_dispatched: int,
        messages_skipped: int,
    ) -> None:
        """Publish the proactive.dispatch.completed telemetry event."""
        if not self._settings.ENABLE_TELEMETRY_EVENTS:
            return
        try:
            await self._events.publish_dispatch_completed(
                event_id=generate_event_id(),
                correlation_id=correlation_id,
                candidates_scanned=candidates_scanned,
                messages_dispatched=messages_dispatched,
                messages_skipped=messages_skipped,
            )
        except Exception as e:
            logger.error("Failed to publish dispatch completed event: %s", str(e))
