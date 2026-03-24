"""
Utility functions for the Cron Service v3.0.

Provides ID generation, cron expression parsing, and next-fire-time
computation for schedule entries.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional


def generate_event_id() -> str:
    """Generate a unique event identifier."""
    return f"evt_{uuid.uuid4().hex[:12]}"


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def compute_next_run_at(
    scheduled_at: Optional[datetime] = None,
    cron_expression: Optional[str] = None,
    interval_seconds: Optional[int] = None,
    from_time: Optional[datetime] = None,
) -> Optional[datetime]:
    """
    Compute the next fire time for a schedule entry.

    Priority:
    1. scheduled_at — used as-is (for one-shot schedules).
    2. interval_seconds — add interval to from_time (or now).
    3. cron_expression — parse and compute next match.

    Returns:
        Next fire datetime (UTC), or None if cannot be determined.
    """
    if scheduled_at is not None:
        if scheduled_at.tzinfo is None:
            return scheduled_at.replace(tzinfo=timezone.utc)
        return scheduled_at.astimezone(timezone.utc)

    base = from_time or datetime.now(timezone.utc)

    if interval_seconds is not None and interval_seconds > 0:
        return base + timedelta(seconds=interval_seconds)

    if cron_expression is not None:
        return _next_cron_match(cron_expression, base)

    return None


def _expand_cron_field(spec: str, min_val: int, max_val: int) -> list:
    """Expand a cron field spec into a sorted list of integers."""
    values = set()
    for part in spec.split(","):
        if "/" in part:
            base_part, step_str = part.split("/", 1)
            step = int(step_str)
            if base_part == "*":
                start = min_val
            elif "-" in base_part:
                start = int(base_part.split("-")[0])
            else:
                start = int(base_part)
            for v in range(start, max_val + 1, step):
                values.add(v)
        elif part == "*":
            values.update(range(min_val, max_val + 1))
        elif "-" in part:
            lo, hi = part.split("-", 1)
            values.update(range(int(lo), int(hi) + 1))
        else:
            values.add(int(part))
    return sorted(v for v in values if min_val <= v <= max_val)


def _next_cron_match(expression: str, from_time: datetime) -> Optional[datetime]:
    """
    Compute the next datetime matching a 5-field cron expression.

    Supports: minute hour day_of_month month day_of_week
    Supports: *, specific values, ranges (1-5), steps (*/15), lists (1,3,5)

    This is a simplified implementation suitable for development.
    For production, consider using the ``croniter`` library.
    """
    try:
        fields = expression.strip().split()
        if len(fields) != 5:
            return None

        minute_spec, hour_spec, dom_spec, month_spec, dow_spec = fields

        minutes = _expand_cron_field(minute_spec, 0, 59)
        hours = _expand_cron_field(hour_spec, 0, 23)
        doms = _expand_cron_field(dom_spec, 1, 31)
        months = _expand_cron_field(month_spec, 1, 12)
        dows_cron = _expand_cron_field(dow_spec, 0, 6)  # cron: 0=Sunday

        if not all([minutes, hours, doms, months, dows_cron]):
            return None

        # Convert cron day-of-week (0=Sun) to Python weekday (0=Mon)
        python_dows = set()
        for d in dows_cron:
            python_dows.add((d - 1) % 7)

        candidate = from_time.replace(second=0, microsecond=0) + timedelta(minutes=1)
        if candidate.tzinfo is None:
            candidate = candidate.replace(tzinfo=timezone.utc)

        end_search = from_time + timedelta(days=400)

        while candidate < end_search:
            if (
                candidate.month in months
                and candidate.day in doms
                and candidate.weekday() in python_dows
                and candidate.hour in hours
                and candidate.minute in minutes
            ):
                return candidate.replace(tzinfo=timezone.utc)
            if candidate - from_time < timedelta(hours=48):
                candidate += timedelta(minutes=1)
            else:
                candidate += timedelta(hours=1)

        return None

    except (ValueError, IndexError):
        return None
