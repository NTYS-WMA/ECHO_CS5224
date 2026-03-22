"""
Utility helpers for the AI Generation Service.
"""

import uuid
from datetime import datetime, timezone


def generate_event_id() -> str:
    """Generate a unique event ID prefixed with 'evt-'."""
    return f"evt-{uuid.uuid4().hex[:12]}"


def generate_response_id() -> str:
    """Generate a unique generation response ID prefixed with 'gen-'."""
    return f"gen-{uuid.uuid4().hex[:12]}"


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)
