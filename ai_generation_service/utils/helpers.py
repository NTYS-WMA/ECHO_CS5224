"""
Utility helpers for the AI Generation Service.
"""

import re
import uuid
from datetime import datetime, timezone


def generate_event_id() -> str:
    """Generate a unique event ID prefixed with 'evt-'."""
    return f"evt-{uuid.uuid4().hex[:12]}"


def generate_response_id() -> str:
    """Generate a unique generation response ID prefixed with 'gen-'."""
    return f"gen-{uuid.uuid4().hex[:12]}"


def generate_template_id(name: str) -> str:
    """
    Generate a unique template ID from a human-readable name.

    Converts the name to snake_case and appends a short UUID suffix
    to ensure uniqueness.

    Args:
        name: Human-readable template name.

    Returns:
        A template ID like 'tpl_custom_greeting_a1b2c3'.
    """
    # Convert to lowercase, replace non-alphanumeric with underscore
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    # Truncate slug to keep ID reasonable
    slug = slug[:40]
    suffix = uuid.uuid4().hex[:6]
    return f"tpl_{slug}_{suffix}"


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)
