"""
Utility helpers for the Proactive Engagement Service.
"""

import uuid
from datetime import datetime, timezone, timedelta


def generate_event_id() -> str:
    """Generate a unique event ID prefixed with 'evt-'."""
    return f"evt-{uuid.uuid4().hex[:12]}"


def generate_scan_id() -> str:
    """Generate a unique scan ID prefixed with 'scan-'."""
    return f"scan-{uuid.uuid4().hex[:12]}"


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def is_within_quiet_hours(
    current_time_str: str,
    quiet_start: str,
    quiet_end: str,
    user_timezone: str,
) -> bool:
    """
    Check if the current time falls within the user's quiet hours.

    Quiet hours may span midnight (e.g., 22:00 to 07:00).

    Args:
        current_time_str: Current time in ISO 8601 format.
        quiet_start: Quiet hours start time in HH:MM format.
        quiet_end: Quiet hours end time in HH:MM format.
        user_timezone: User timezone (IANA format).

    Returns:
        True if the current time is within quiet hours.
    """
    try:
        # Parse the current time
        # We need to check the user's local time against quiet hours
        from zoneinfo import ZoneInfo

        current_utc = datetime.fromisoformat(current_time_str.replace("Z", "+00:00"))
        user_tz = ZoneInfo(user_timezone)
        current_local = current_utc.astimezone(user_tz)

        # Parse quiet hours
        quiet_start_parts = quiet_start.split(":")
        quiet_end_parts = quiet_end.split(":")
        start_hour, start_min = int(quiet_start_parts[0]), int(quiet_start_parts[1])
        end_hour, end_min = int(quiet_end_parts[0]), int(quiet_end_parts[1])

        current_minutes = current_local.hour * 60 + current_local.minute
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min

        if start_minutes <= end_minutes:
            # Quiet hours do not span midnight (e.g., 01:00 to 06:00)
            return start_minutes <= current_minutes < end_minutes
        else:
            # Quiet hours span midnight (e.g., 22:00 to 07:00)
            return current_minutes >= start_minutes or current_minutes < end_minutes

    except Exception:
        # If we cannot determine quiet hours, default to not quiet
        return False


def get_tier_from_score(affinity_score: float) -> str:
    """
    Map an affinity score to a relationship tier.

    Score ranges:
        0.00 - 0.30: acquaintance
        0.31 - 0.60: friend
        0.61 - 0.80: close_friend
        0.81 - 1.00: best_friend

    Args:
        affinity_score: Affinity score on a 0-1 scale.

    Returns:
        Relationship tier string.
    """
    if affinity_score <= 0.30:
        return "acquaintance"
    elif affinity_score <= 0.60:
        return "friend"
    elif affinity_score <= 0.80:
        return "close_friend"
    else:
        return "best_friend"
