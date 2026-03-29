"""
Relationship Manager — session-level affinity scoring for the Relationship Service.

Scores are stored on a 0–1 scale and map to four tiers:
    0.00–0.30  Acquaintance   0.31–0.60  Friend
    0.61–0.80  Close Friend   0.81–1.00  Best Friend

Scoring is session-based. A session ends when a user has been silent for
SESSION_TIMEOUT_MINUTES. The scheduler calls run_session_scoring() every 15 minutes.
Inactivity decay runs daily via run_inactivity_decay().

Public API
──────────
  get_relationship_context()   → GET /api/v1/relationships/{user_id}/context
  set_relationship_score()     → PATCH /api/v1/relationships/{user_id}/score
  run_session_scoring()        → cron, every 15 min
  run_inactivity_decay()       → cron, daily
  apply_inactivity_decay()     → per-user, called by run_inactivity_decay
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import managers.db_manager as db_manager
import services.ai_service as ai_service

logger = logging.getLogger(__name__)

SESSION_TIMEOUT_MINUTES = 30

_TIERS = [
    (0.80, "best_friend"),
    (0.60, "close_friend"),
    (0.30, "friend"),
    (0.0,  "acquaintance"),
]

_SESSION_SCORE_PROMPT = (
    "You are a relationship analyst for ECHO, a personal AI companion.\n"
    "Read the completed conversation session below and assess the overall "
    "relationship signal between the user and ECHO.\n\n"
    "Return ONLY a compact JSON object with exactly these four fields "
    "(no markdown, no explanation):\n"
    '  "sentiment":  "positive" | "negative" | "neutral"\n'
    '  "intensity":  "strong" | "weak"\n'
    '  "delta":      float between -0.05 and +0.03\n'
    '  "reasoning":  one sentence explaining your score\n\n'
    "Scoring guide (affinity score is on a 0–1 scale):\n"
    "  Strong positive  (+0.02 to +0.03): user opened up, shared personal info, "
    "expressed gratitude, affection, or trust.\n"
    "  Weak positive    (+0.003 to +0.01): casual friendly chat, light humour, "
    "sustained engagement.\n"
    "  Neutral          (+0.0 to +0.002): transactional or very short exchange.\n"
    "  Weak negative    (-0.01 to -0.02): mild frustration or disengagement.\n"
    "  Strong negative  (-0.03 to -0.05): rudeness, insults, hostility, or "
    "explicit requests to stop.\n\n"
    "Notes: venting or sharing a problem signals trust — lean positive. "
    "Dry humour without hostility is not negative. "
    "Very short sessions (1–2 messages) should score near 0 unless clearly emotional. "
    "Messages marked '[proactive, no reply from user]' mean ECHO reached out but was ignored — "
    "treat each ignored proactive as a mild negative signal (-0.005 to -0.015 depending on context).\n\n"
    "CONVERSATION:\n{conversation}\n\nJSON:"
)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _get_tier(score: float) -> str:
    for threshold, tier in _TIERS:
        if score > threshold:
            return tier
    return "acquaintance"


def _format_conversation(messages: list[dict]) -> str:
    lines = []
    for i, m in enumerate(messages):
        if m["role"] == "assistant" and m.get("is_proactive"):
            m_time = datetime.fromisoformat(m["created_at"])
            has_reply = any(
                n["role"] == "user" and datetime.fromisoformat(n["created_at"]) > m_time
                for n in messages[i + 1:]
            )
            if has_reply:
                lines.append(f"ECHO [proactive]: {m['content']}")
            else:
                lines.append(f"ECHO [proactive, no reply from user]: {m['content']}")
        else:
            lines.append(f"{m['role'].upper()}: {m['content']}")
    return "\n".join(lines)


def _parse_score_response(raw: str) -> dict:
    try:
        if "```" in raw:
            raw = raw.split("```")[1].strip()
            if raw.lower().startswith("json"):
                raw = raw[4:].strip()
        result = json.loads(raw)
        delta = max(-0.05, min(0.03, float(result.get("delta", 0.0))))
        sentiment = result.get("sentiment", "neutral")
        if sentiment not in ("positive", "negative", "neutral"):
            sentiment = "neutral"
        intensity = result.get("intensity", "weak")
        if intensity not in ("strong", "weak"):
            intensity = "weak"
        return {
            "sentiment": sentiment,
            "intensity": intensity,
            "delta": delta,
            "reasoning": result.get("reasoning", ""),
        }
    except Exception:
        return {"sentiment": "neutral", "intensity": "weak", "delta": 0.0, "reasoning": "parse error"}


def _publish_score_event(
    user_id: str,
    previous_score: float,
    new_score: float,
    delta: float,
    reason: str,
) -> None:
    """Emit relationship.score.updated event (structured log for now)."""
    previous_tier = _get_tier(previous_score)
    new_tier = _get_tier(new_score)
    if previous_tier != new_tier:
        logger.info(
            "relationship.score.updated [TIER CHANGE] user=%s %s → %s (%.4f → %.4f) reason=%s",
            user_id, previous_tier, new_tier, previous_score, new_score, reason,
        )
    else:
        logger.debug(
            "relationship.score.updated user=%s tier=%s %.4f → %.4f (delta=%.4f) reason=%s",
            user_id, new_tier, previous_score, new_score, delta, reason,
        )


# ─── Public API ───────────────────────────────────────────────────────────────


async def get_relationship_context(user_id: str) -> Optional[dict]:
    """Return relationship context for a user. Auto-creates score record on first access."""
    rel = await db_manager.get_relationship_score(user_id)
    if not rel:
        user = await db_manager.get_user_by_id(user_id)
        if user is None:
            return None
        rel = await db_manager.create_relationship_score(user_id)
        logger.info("Created default relationship score for new user %s", user_id)

    user = await db_manager.get_user_by_id(user_id)
    now = datetime.now(timezone.utc)
    last_interaction_str = user.get("last_active_at") if user else None
    if last_interaction_str:
        last_interaction = datetime.fromisoformat(last_interaction_str)
        if last_interaction.tzinfo is None:
            last_interaction = last_interaction.replace(tzinfo=timezone.utc)
    else:
        last_interaction = None
    days_inactive = max(0, (now - last_interaction).days) if last_interaction else 0

    return {
        "user_id": user_id,
        "affinity_score": round(rel["score"], 4),
        "tier": _get_tier(rel["score"]),
        "interaction_count": rel["total_interactions"],
        "last_interaction_at": last_interaction.isoformat() if last_interaction else None,
        "decay_state": {
            "last_decay_at": rel.get("last_decay_at"),
            "days_inactive": days_inactive,
        },
        "updated_at": rel.get("last_updated"),
    }


async def set_relationship_score(
    user_id: str,
    new_score: float,
) -> Optional[dict]:
    """Directly set affinity score for a user (admin use). Returns None if no record exists."""
    rel = await db_manager.get_relationship_score(user_id)
    if rel is None:
        return None

    previous_score = rel["score"]
    clamped = max(0.0, min(1.0, new_score))

    await db_manager.set_score_absolute(user_id, clamped, current_rel=rel)
    await db_manager.insert_score_history(
        user_id=user_id,
        delta=clamped - previous_score,
        new_score=clamped,
        reason="manual_update",
    )
    _publish_score_event(user_id, previous_score, clamped, clamped - previous_score, "manual_update")

    return {
        "user_id": user_id,
        "previous_score": round(previous_score, 4),
        "new_score": round(clamped, 4),
        "previous_tier": _get_tier(previous_score),
        "new_tier": _get_tier(clamped),
    }


async def run_session_scoring() -> None:
    """Score all ended conversation sessions. Called by cron every 15 min."""
    rows = await db_manager.get_users_with_ended_sessions(inactive_minutes=SESSION_TIMEOUT_MINUTES)
    if not rows:
        return

    logger.info("Session scoring: %d user(s) eligible.", len(rows))
    for row in rows:
        last_scored_at_str = row.get("last_scored_at")
        last_scored_at = datetime.fromisoformat(last_scored_at_str) if last_scored_at_str else None
        await _score_conversation_session(row["id"], last_scored_at)


async def _score_conversation_session(
    user_id: str,
    last_scored_at: Optional[datetime],
) -> float:
    messages = await db_manager.get_messages_since_datetime(user_id, since=last_scored_at)
    user_messages = [m for m in messages if m["role"] == "user"]

    if not user_messages:
        logger.debug("No user messages to score for user %s — stamping and skipping.", user_id)
        await db_manager.stamp_last_scored_at(user_id)
        rel = await db_manager.get_relationship_score(user_id)
        return rel["score"] if rel else 0.10

    prompt = _SESSION_SCORE_PROMPT.format(conversation=_format_conversation(messages))

    try:
        raw = await ai_service.complete(prompt, max_tokens=1024)
        result = _parse_score_response(raw)
        delta = result["delta"]
        is_positive = result["sentiment"] != "negative"
        logger.info(
            "Session scored for user %s: %s/%s → delta=%.4f | %s",
            user_id, result["sentiment"], result["intensity"], delta, result["reasoning"],
        )
    except Exception as exc:
        logger.warning("Session scoring failed for user %s: %s — applying 0.0 delta.", user_id, exc)
        result = {"sentiment": None, "intensity": None, "delta": 0.0, "reasoning": "api_error"}
        delta = 0.0
        is_positive = True

    rel = await db_manager.get_relationship_score(user_id)
    previous_score = rel["score"] if rel else 0.10

    new_score = await db_manager.update_relationship_score(
        user_id=user_id,
        delta=delta,
        is_positive=is_positive,
    )
    await db_manager.stamp_last_scored_at(user_id)
    await db_manager.insert_score_history(
        user_id=user_id,
        delta=delta,
        new_score=new_score,
        reason="session_scored",
        sentiment=result.get("sentiment"),
        intensity=result.get("intensity"),
        reasoning=result.get("reasoning"),
    )
    _publish_score_event(user_id, previous_score, new_score, delta, reason="session_scored")
    return new_score


async def run_inactivity_decay(inactive_hours: int = 24) -> None:
    """Apply passive score decay to all users inactive for at least `inactive_hours`. Called daily."""
    inactive_users = await db_manager.get_inactive_users(inactive_hours=inactive_hours)
    for user in inactive_users:
        new_score = await apply_inactivity_decay(user["id"], days_inactive=1)
        logger.debug("Decay applied for user %s → score=%.4f", user["id"], new_score)


async def apply_inactivity_decay(
    user_id: str,
    days_inactive: int,
) -> float:
    """Apply -0.005 per day of inactivity for a single user."""
    rel = await db_manager.get_relationship_score(user_id)
    previous_score = rel["score"] if rel else 0.10
    delta = -(0.005 * days_inactive)
    new_score = await db_manager.update_relationship_score(
        user_id=user_id,
        delta=delta,
        is_positive=False,
        is_decay=True,
    )
    await db_manager.insert_score_history(
        user_id=user_id,
        delta=delta,
        new_score=new_score,
        reason="inactivity_decay",
    )
    _publish_score_event(user_id, previous_score, new_score, delta, reason="inactivity_decay")
    return new_score
