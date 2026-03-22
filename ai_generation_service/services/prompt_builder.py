"""
Prompt builder for the AI Generation Service.

Constructs provider-ready message lists for different generation operations:
- Chat completions: Pass-through with optional system prompt enrichment.
- Summarization: Build a summarization prompt from conversation messages.
- Proactive messages: Build a proactive outreach prompt from relationship context.
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Builds structured prompts for different AI generation operations."""

    # --- Chat Completion ---

    @staticmethod
    def build_chat_completion_messages(messages: List[dict]) -> List[dict]:
        """
        Prepare messages for chat completion.

        For chat completions, the caller (Conversation Orchestrator) already
        provides a fully constructed message list including the system prompt.
        This method passes them through with minimal transformation.

        Args:
            messages: Ordered list of message dicts with 'role' and 'content'.

        Returns:
            Provider-ready message list.
        """
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    # --- Summarization ---

    SUMMARY_SYSTEM_PROMPT = (
        "You are a precise summarization assistant for the ECHO companion platform. "
        "Your task is to distill conversation messages into a compact, factual summary "
        "that captures the user's key preferences, emotional state, and important facts. "
        "The summary will be stored as long-term memory for future personalization. "
        "Be concise, objective, and focus on actionable insights about the user."
    )

    @staticmethod
    def build_summary_messages(
        conversation_messages: List[dict],
        summary_type: str = "memory_compaction",
    ) -> List[dict]:
        """
        Build a summarization prompt from a window of conversation messages.

        Args:
            conversation_messages: The conversation messages to summarize.
            summary_type: The type of summary (e.g., 'memory_compaction').

        Returns:
            Provider-ready message list with system prompt and user instruction.
        """
        # Format the conversation for the summarization prompt
        formatted_conversation = "\n".join(
            f"[{msg.get('role', 'unknown')}]: {msg.get('content', '')}"
            for msg in conversation_messages
        )

        user_instruction = (
            f"Please summarize the following conversation into a compact memory entry.\n"
            f"Summary type: {summary_type}\n\n"
            f"Conversation:\n{formatted_conversation}\n\n"
            f"Provide a concise summary capturing the user's key preferences, "
            f"emotional state, and important facts."
        )

        return [
            {"role": "system", "content": PromptBuilder.SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": user_instruction},
        ]

    # --- Proactive Message Generation ---

    PROACTIVE_SYSTEM_PROMPT = (
        "You are ECHO, a warm and thoughtful AI companion. "
        "You are reaching out to a user you have not heard from in a while. "
        "Your message should feel natural, caring, and not pushy. "
        "Keep it brief and conversational. Do not ask too many questions at once. "
        "Match the tone to the relationship level and the user's known preferences."
    )

    @staticmethod
    def build_proactive_messages(
        relationship_tier: str,
        affinity_score: float,
        days_inactive: int,
        recent_summary: Optional[str] = None,
        timezone: Optional[str] = None,
        tone: str = "friendly",
    ) -> List[dict]:
        """
        Build a proactive outreach prompt from relationship and user context.

        Args:
            relationship_tier: The user's relationship tier.
            affinity_score: The user's affinity score (0-1).
            days_inactive: Days since last interaction.
            recent_summary: Optional recent memory summary.
            timezone: Optional user timezone.
            tone: Desired tone for the message.

        Returns:
            Provider-ready message list.
        """
        context_parts = [
            f"Relationship tier: {relationship_tier}",
            f"Affinity score: {affinity_score:.2f}",
            f"Days since last interaction: {days_inactive}",
            f"Desired tone: {tone}",
        ]

        if timezone:
            context_parts.append(f"User timezone: {timezone}")

        if recent_summary:
            context_parts.append(f"Recent context about the user: {recent_summary}")

        context_block = "\n".join(context_parts)

        user_instruction = (
            f"Based on the following context, compose a short, natural check-in message "
            f"to re-engage this user. The message should feel genuine and not automated.\n\n"
            f"{context_block}\n\n"
            f"Generate only the message text, nothing else."
        )

        return [
            {"role": "system", "content": PromptBuilder.PROACTIVE_SYSTEM_PROMPT},
            {"role": "user", "content": user_instruction},
        ]
