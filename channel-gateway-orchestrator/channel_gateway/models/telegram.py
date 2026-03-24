"""
Telegram webhook payload models.

We only model the fields ECHO cares about. Telegram sends many optional fields
that we intentionally ignore (stickers, inline queries, etc.).
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class TelegramUser(BaseModel):
    id: int
    is_bot: bool = False
    first_name: str = ""
    username: str = ""
    language_code: str = "en"


class TelegramChat(BaseModel):
    id: int
    first_name: str = ""
    username: str = ""
    type: str = "private"


class TelegramMessage(BaseModel):
    message_id: int
    date: int  # unix timestamp
    text: str = ""
    media: Optional[dict[str, Any]] = None
    from_: Optional[TelegramUser] = None  # aliased below
    chat: TelegramChat

    model_config = {
        "populate_by_name": True,
    }

    def __init__(self, **data):
        # Handle "from" → "from_" mapping
        if "from" in data:
            data["from_"] = data.pop("from")
        super().__init__(**data)


class TelegramUpdate(BaseModel):
    """Top-level Telegram webhook payload."""
    update_id: int
    message: Optional[TelegramMessage] = None
    # We can extend later for edited_message, callback_query, etc.
