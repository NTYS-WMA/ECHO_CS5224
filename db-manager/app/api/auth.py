from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import Settings, get_settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _ensure_auth_key(expected_key: str | None, provided_key: str | None, key_name: str) -> None:
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{key_name} is not configured on the server.",
        )
    if not provided_key or provided_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )


def require_api_key(
    provided_key: str | None = Security(_api_key_header),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.auth_enabled:
        return
    _ensure_auth_key(settings.api_key, provided_key, "API_KEY")


def require_admin_api_key(
    provided_key: str | None = Security(_api_key_header),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.auth_enabled:
        return
    # Allow fallback to API_KEY when ADMIN_API_KEY is unset.
    expected = settings.admin_api_key or settings.api_key
    _ensure_auth_key(expected, provided_key, "ADMIN_API_KEY")
