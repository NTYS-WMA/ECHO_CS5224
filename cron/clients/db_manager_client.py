"""
HTTP client for communicating with the DB Manager service.

The cron service delegates all persistence to the DB Manager via REST.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class DBManagerClient:
    """
    Async HTTP client wrapper for DB Manager's /scheduled-events endpoints.
    """

    def __init__(
        self,
        base_url: str,
        timeout_seconds: int = 10,
        api_key: str = "",
    ):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {}
            if self._api_key:
                headers["X-API-Key"] = self._api_key
            self._client = httpx.AsyncClient(
                timeout=self._timeout, headers=headers
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------ #
    # CRUD operations
    # ------------------------------------------------------------------ #

    async def create_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """POST /scheduled-events — create a new scheduled event."""
        client = await self._get_client()
        url = f"{self._base_url}/scheduled-events"
        resp = await client.post(url, json=data)
        resp.raise_for_status()
        return resp.json()

    async def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """GET /scheduled-events/{id}."""
        client = await self._get_client()
        url = f"{self._base_url}/scheduled-events/{event_id}"
        resp = await client.get(url)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    async def list_events(
        self,
        caller_service: Optional[str] = None,
        status: Optional[str] = None,
        group_key: Optional[str] = None,
        event_name: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """GET /scheduled-events with filters."""
        client = await self._get_client()
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if caller_service:
            params["caller_service"] = caller_service
        if status:
            params["status"] = status
        if group_key:
            params["group_key"] = group_key
        if event_name:
            params["event_name"] = event_name

        url = f"{self._base_url}/scheduled-events"
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    async def poll_due_events(
        self, now: datetime, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """GET /scheduled-events/due/poll — fetch events ready to fire."""
        client = await self._get_client()
        url = f"{self._base_url}/scheduled-events/due/poll"
        params = {"now": now.isoformat(), "limit": limit}
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("events", [])

    async def mark_fired(
        self,
        event_id: str,
        fired_at: datetime,
        next_fire_at: Optional[datetime],
        new_status: str,
    ) -> bool:
        """POST /scheduled-events/{id}/fired — update after dispatching."""
        client = await self._get_client()
        url = f"{self._base_url}/scheduled-events/{event_id}/fired"
        body: Dict[str, Any] = {
            "fired_at": fired_at.isoformat(),
            "new_status": new_status,
        }
        if next_fire_at:
            body["next_fire_at"] = next_fire_at.isoformat()
        resp = await client.post(url, json=body)
        if resp.status_code == 404:
            logger.warning("Event %s not found when marking fired.", event_id)
            return False
        resp.raise_for_status()
        return True

    async def update_event(
        self, event_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """PUT /scheduled-events/{id}."""
        client = await self._get_client()
        url = f"{self._base_url}/scheduled-events/{event_id}"
        resp = await client.put(url, json=updates)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    async def update_status(self, event_id: str, status: str) -> bool:
        """PATCH /scheduled-events/{id}/status."""
        client = await self._get_client()
        url = f"{self._base_url}/scheduled-events/{event_id}/status"
        resp = await client.patch(url, params={"status": status})
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return True

    async def delete_event(self, event_id: str) -> bool:
        """DELETE /scheduled-events/{id}."""
        client = await self._get_client()
        url = f"{self._base_url}/scheduled-events/{event_id}"
        resp = await client.delete(url)
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return True

    async def delete_by_group(self, group_key: str) -> int:
        """DELETE /scheduled-events/by-group/{group_key}."""
        client = await self._get_client()
        url = f"{self._base_url}/scheduled-events/by-group/{group_key}"
        resp = await client.delete(url)
        resp.raise_for_status()
        return resp.json().get("deleted", 0)
