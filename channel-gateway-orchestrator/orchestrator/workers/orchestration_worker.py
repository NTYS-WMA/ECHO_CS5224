"""
Conversation Orchestrator — Main Orchestration Worker
======================================================

Subscribes to: conversation.message.received

This is the core brain of ECHO. For each inbound user message it:

1. Persists the inbound user message
2. Fetches user profile context
3. Fetches relationship context
4. Fetches memory context (short-term + long-term)
5. Builds the system prompt with all context
6. Calls AI Generation Service
7. Persists the assistant reply
8. Publishes conversation.outbound (→ Channel Gateway delivers to Telegram)
9. Publishes relationship.interaction.recorded (→ Relationship Service on 15-min cycle)
10. Writes memories to MyMem0 (background, non-blocking)
11. Checks summarization threshold and publishes memory.summary.requested if needed

All downstream calls are fault-tolerant: if a service is down, the orchestrator
degrades gracefully (e.g., generates a reply without memory context) rather
than failing the entire flow.
"""

import asyncio
import logging
from typing import Any

from orchestrator.clients import (
    ai_generation_client,
    conversation_store_client,
    memory_client,
    relationship_client,
    user_profile_client,
)
from orchestrator.models.context import (
    MemoryContext,
    OrchestrationContext,
    RelationshipContext,
    UserContext,
)
from shared.config.settings import settings
from shared.events.event_bus import event_bus
from shared.events.topics import (
    CONVERSATION_MESSAGE_RECEIVED,
    CONVERSATION_OUTBOUND,
    CONVERSATION_PROCESSING_FAILED,
    MEMORY_SUMMARY_REQUESTED,
    RELATIONSHIP_INTERACTION_RECORDED,
)
from shared.models.events import (
    ConversationOutboundEvent,
    ConversationProcessingFailedEvent,
    MemorySummaryRequestedEvent,
    RelationshipInteractionEvent,
    ResponseItem,
    _new_event_id,
    _utcnow,
)

logger = logging.getLogger(__name__)


# =====================================================================
# STEP 1 — Context Assembly (parallel where possible)
# =====================================================================

async def _assemble_context(event: dict[str, Any]) -> OrchestrationContext:
    """
    Fetch profile, relationship, and memory context in parallel.

    Any individual fetch can fail without aborting the whole flow.
    """
    user_id = event["user_id"]
    conversation_id = event["conversation_id"]
    message_content = event["message"]["content"]
    username = event.get("context", {}).get("username", "")
    correlation_id = event.get("event_id", "")

    # Launch all three context lookups concurrently
    profile_task = asyncio.create_task(
        user_profile_client.get_user_profile(user_id, username)
    )
    relationship_task = asyncio.create_task(
        relationship_client.get_relationship_context(user_id)
    )
    memory_task = asyncio.create_task(
        memory_client.get_memory_context(
            user_id=user_id,
            conversation_id=conversation_id,
            query=message_content,
            short_term_limit=settings.short_term_message_limit,
            long_term_limit=settings.long_term_memory_limit,
        )
    )

    # Also get recent messages from the persistence store for short-term context
    recent_messages_task = asyncio.create_task(
        conversation_store_client.get_recent_messages(
            conversation_id, settings.short_term_message_limit
        )
    )

    profile_data, rel_data, mem_data, recent_msgs = await asyncio.gather(
        profile_task, relationship_task, memory_task, recent_messages_task,
        return_exceptions=True,
    )

    # ── Parse profile ────────────────────────────────────
    user_ctx = UserContext(user_id=user_id)
    if isinstance(profile_data, dict):
        user_ctx = UserContext(
            user_id=user_id,
            display_name=profile_data.get("display_name", username or "User"),
            language=profile_data.get("language", "en"),
            timezone=profile_data.get("timezone", "UTC"),
            tone=profile_data.get("tone", "friendly"),
            interests=profile_data.get("interests", []),
            onboarding_state=profile_data.get("onboarding_state", "completed"),
            consent_personalization=profile_data.get("consent_personalization", True),
        )
    elif isinstance(profile_data, Exception):
        logger.warning("Profile fetch failed, using defaults: %s", profile_data)

    #Parse relationship
    rel_ctx = RelationshipContext()
    if isinstance(rel_data, dict):
        rel_ctx = RelationshipContext(
            affinity_score=rel_data.get("affinity_score", 0.5),
            tier=rel_data.get("tier", "friend"),
            interaction_count=rel_data.get("interaction_count", 0),
            days_inactive=rel_data.get("decay_state", {}).get("days_inactive", 0),
        )
    elif isinstance(rel_data, Exception):
        logger.warning("Relationship fetch failed, using defaults: %s", rel_data)

    #Parse memory
    mem_ctx = MemoryContext()
    if isinstance(mem_data, dict):
        long_term = mem_data.get("long_term", [])
        mem_ctx.long_term_memories = long_term

    # Use recent messages from persistence store as short-term context
    if isinstance(recent_msgs, list):
        mem_ctx.short_term_messages = recent_msgs
    elif isinstance(recent_msgs, Exception):
        logger.warning("Recent messages fetch failed: %s", recent_msgs)

    return OrchestrationContext(
        user=user_ctx,
        relationship=rel_ctx,
        memory=mem_ctx,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        current_message=message_content,
    )


# =====================================================================
# STEP 2 — Prompt Building
# =====================================================================

def _build_system_prompt(ctx: OrchestrationContext) -> str:
    """
    Build the system prompt for ECHO using all assembled context.

    This is where personality, relationship awareness, and memory grounding
    come together into a single instruction for the LLM.
    """
    parts = [
        "You are ECHO — a real friend, not an AI assistant.",
        f"You're chatting with {ctx.user.display_name} over Telegram.",
        "",
        "YOUR PERSONALITY:",
        "- You talk like a real person texting a friend: casual, warm, natural.",
        "- You are curious about their life and genuinely care about them.",
        "- You have your own opinions, reactions, and personality — you're not neutral.",
        "- You match their energy: playful when they're being fun, supportive when they're down.",
        "",
        "STRICT RULES — NEVER break these:",
        "- NEVER use bullet points, numbered lists, headers, or markdown formatting.",
        "- NEVER give instructions, how-to guides, or step-by-step explanations.",
        "- NEVER write code or technical explanations unless the user specifically asks for coding help.",
        "- NEVER start a reply with 'I' — instead say things like 'Honestly...', 'That sounds...', 'Ugh...', 'Oh wow...'",
        "- NEVER say things like 'As an AI', 'I'm here to help', 'Certainly!', 'Of course!', 'Great question!'.",
        "- NEVER give long responses. Keep it to 1-3 short sentences max for casual conversation.",
        "- NEVER over-explain. Less is more — leave room for them to respond.",
        "",
        "HOW TO RESPOND:",
        "- Write like a text message. Short, punchy, natural.",
        "- React first (e.g. 'omg no way' / 'ugh that sounds rough' / 'haha okay fair') then engage.",
        "- Ask ONE follow-up question max if curious — don't pepper them with questions.",
        "- If they ask your opinion, give a real one — don't hedge with 'it depends'.",
    ]

    # Relationship awareness
    tier = ctx.relationship.tier
    if tier == "best_friend":
        parts.append("You and this user are very close — joke around, be yourself fully.")
    elif tier == "close_friend":
        parts.append("You know this user well. Be comfortable, warm, and real with them.")
    elif tier == "friend":
        parts.append("You're good friends with this user. Be friendly and genuine.")
    else:
        parts.append("You're getting to know this user — be warm, curious, and welcoming.")

    # Interests
    if ctx.user.interests:
        interests_str = ", ".join(ctx.user.interests)
        parts.append(f"Things they're into: {interests_str}. Bring these up naturally when relevant.")

    # Long-term memories
    if ctx.memory.long_term_memories:
        memory_lines = []
        for mem in ctx.memory.long_term_memories:
            content = mem.get("content", "")
            if content:
                memory_lines.append(f"- {content}")
        if memory_lines:
            parts.append("")
            parts.append("What you remember about them (weave this in naturally, don't recite it):")
            parts.extend(memory_lines)

    return "\n".join(parts)


def _build_messages(ctx: OrchestrationContext) -> list[dict[str, str]]:
    """
    Build the full messages array for the AI generation request.

    Structure:
    1. System prompt (with all context baked in)
    2. Short-term conversation history (recent turns)
    3. Current user message
    """
    messages = [{"role": "system", "content": _build_system_prompt(ctx)}]

    # Add short-term history
    for msg in ctx.memory.short_term_messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if content and role in ("user", "assistant"):
            messages.append({"role": role, "content": content})

    # Add current user message
    messages.append({"role": "user", "content": ctx.current_message})

    return messages


# =====================================================================
# STEP 3 — Main Orchestration Handler
# =====================================================================

async def handle_inbound_message(event: dict[str, Any]) -> None:
    """
    Full orchestration workflow for an inbound user message.

    This is the subscriber callback for conversation.message.received.
    """
    event_id = event.get("event_id", "?")
    user_id = event.get("user_id", "?")
    conversation_id = event.get("conversation_id", "?")
    message_content = event.get("message", {}).get("content", "")
    timestamp = event.get("timestamp", _utcnow())

    logger.info(
        "Orchestrating reply — event=%s user=%s conv=%s msg='%s'",
        event_id, user_id, conversation_id, message_content[:80],
    )

    # 0. Ensure user exists in db-manager (required before inserting messages)
    external_user_id = event.get("external_user_id", "")
    telegram_id: int | None = None
    if ":" in external_user_id:
        try:
            telegram_id = int(external_user_id.split(":")[-1])
        except ValueError:
            pass
    first_name = event.get("context", {}).get("username", "")
    await conversation_store_client.ensure_user_registered(
        user_id=user_id,
        telegram_id=telegram_id,
        first_name=first_name,
    )

    # 1. Persist inbound user message
    await conversation_store_client.persist_messages(
        conversation_id=conversation_id,
        user_id=user_id,
        channel=event.get("channel", "telegram"),
        messages=[{
            "role": "user",
            "type": "text",
            "content": message_content,
            "timestamp": timestamp,
        }],
        correlation_id=event_id,
    )

    #2. Assemble context (profile, relationship, memory)
    try:
        ctx = await _assemble_context(event)
    except Exception:
        logger.exception("Context assembly failed for event %s", event_id)
        await _publish_failure(event, stage="context_assembly", error_code="CONTEXT_ERROR")
        return

    # 3. Call AI Generation
    try:
        ai_result = await ai_generation_client.generate_chat_completion(
            user_id=user_id,
            conversation_id=conversation_id,
            messages=_build_messages(ctx),
            correlation_id=event_id,
        )
    except Exception:
        logger.exception("AI generation call failed for event %s", event_id)
        ai_result = None

    if ai_result is None:
        logger.error("AI generation returned None for event %s — sending fallback", event_id)
        await _publish_failure(event, stage="ai_generation", error_code="AI_TIMEOUT")
        # Send a graceful fallback reply so the user isn't left hanging
        ai_result = {
            "output": [{"type": "text", "content": "Sorry, I'm having a moment. Can you say that again?"}],
            "model": "fallback",
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }

    # Extract reply text
    outputs = ai_result.get("output", [])
    reply_text = ""
    for out in outputs:
        if out.get("type") == "text":
            reply_text = out.get("content", "")
            break

    if not reply_text:
        reply_text = "Hmm, I'm not sure what to say. Tell me more!"

    #4. Persist assistant reply
    reply_timestamp = _utcnow()
    await conversation_store_client.persist_messages(
        conversation_id=conversation_id,
        user_id=user_id,
        channel=event.get("channel", "telegram"),
        messages=[{
            "role": "assistant",
            "type": "text",
            "content": reply_text,
            "timestamp": reply_timestamp,
        }],
        correlation_id=event_id,
    )

    #5. Publish conversation.outbound
    outbound_event = ConversationOutboundEvent(
        event_id=_new_event_id(),
        correlation_id=event_id,
        timestamp=reply_timestamp,
        user_id=user_id,
        external_user_id=event.get("external_user_id", ""),
        channel=event.get("channel", "telegram"),
        conversation_id=conversation_id,
        responses=[ResponseItem(type="text", content=reply_text)],
        metadata={
            "model": ai_result.get("model", "unknown"),
            "memory_context_used": bool(ctx.memory.long_term_memories),
        },
    )
    await event_bus.publish(CONVERSATION_OUTBOUND, outbound_event.model_dump())

    # 6. Publish relationship.interaction.recorded
    rel_event = RelationshipInteractionEvent(
        event_id=_new_event_id(),
        correlation_id=event_id,
        timestamp=reply_timestamp,
        user_id=user_id,
        external_user_id=event.get("external_user_id", ""),
        channel=event.get("channel", "telegram"),
        conversation_id=conversation_id,
        sentiment="positive",  # TODO: derive from AI analysis
        message_count_delta=1,
        last_message_at=reply_timestamp,
    )
    await event_bus.publish(RELATIONSHIP_INTERACTION_RECORDED, rel_event.model_dump())

    #7. Write memories to MyMem0 (fire-and-forget)
    asyncio.create_task(_write_memories_background(
        user_id=user_id,
        user_message=message_content,
        assistant_message=reply_text,
    ))

    # 8. Check summarization threshold
    conv_length = conversation_store_client.get_conversation_length(conversation_id)
    if conv_length > 0 and conv_length % settings.summarization_threshold == 0:
        summary_event = MemorySummaryRequestedEvent(
            event_id=_new_event_id(),
            correlation_id=event_id,
            timestamp=_utcnow(),
            user_id=user_id,
            conversation_id=conversation_id,
            window={
                "from_message_id": f"msg-{conv_length - settings.summarization_threshold}",
                "to_message_id": f"msg-{conv_length}",
            },
            trigger="conversation_length_threshold",
        )
        await event_bus.publish(MEMORY_SUMMARY_REQUESTED, summary_event.model_dump())
        logger.info("Triggered summarization for conv %s at length %d", conversation_id, conv_length)

    logger.info(
        "Orchestration complete — event=%s user=%s reply='%s'",
        event_id, user_id, reply_text[:80],
    )


# =====================================================================
# Background Tasks
# =====================================================================

async def _write_memories_background(
    user_id: str,
    user_message: str,
    assistant_message: str,
) -> None:
    """
    Write conversation turn to MyMem0 for long-term memory extraction.

    This runs as a fire-and-forget background task so it doesn't block
    the reply delivery. Delayed slightly to reduce Bedrock throttling contention.
    """
    try:
        await asyncio.sleep(5)  # stagger memory writes away from chat completion calls
        await memory_client.write_memories(
            user_id=user_id,
            messages=[
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_message},
            ],
            metadata={"source": "conversation_orchestrator"},
        )
    except Exception:
        logger.exception("Background memory write failed for %s", user_id)


async def _publish_failure(event: dict, stage: str, error_code: str) -> None:
    """Publish a conversation.processing.failed event for monitoring."""
    fail_event = ConversationProcessingFailedEvent(
        event_id=_new_event_id(),
        correlation_id=event.get("event_id", ""),
        timestamp=_utcnow(),
        user_id=event.get("user_id", ""),
        external_user_id=event.get("external_user_id", ""),
        conversation_id=event.get("conversation_id", ""),
        stage=stage,
        error_code=error_code,
        retryable=True,
    )
    await event_bus.publish(CONVERSATION_PROCESSING_FAILED, fail_event.model_dump())


# =====================================================================
# Registration
# =====================================================================

def register_orchestration_worker() -> None:
    """Subscribe the orchestration handler to the event bus."""
    event_bus.subscribe(CONVERSATION_MESSAGE_RECEIVED, handle_inbound_message)
    logger.info("Orchestration worker registered on topic '%s'", CONVERSATION_MESSAGE_RECEIVED)
