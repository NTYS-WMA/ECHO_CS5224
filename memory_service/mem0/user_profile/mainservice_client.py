"""
MainService HTTP Client for Cold Start Integration

Fetches initial user profile data from MainService during first-time user access.

NOTE: The MainService API endpoint is not yet implemented. This client returns None
until the endpoint is available. Update fetch_user_summary() once the API is defined.

Expected response schema (to be confirmed with MainService team):
    {
        "user_id": "...",
        "name": "...",
        "gender": "male|female|unknown",
        "occupation": "...",
        "company": "...",
        "personality_traits": "trait1,trait2,...",  // comma-separated
        "interests": "interest1,interest2,..."       // comma-separated
    }
"""

import logging
from typing import Optional, Dict, Any
import requests

logger = logging.getLogger(__name__)


def fetch_user_summary(user_id: str, base_url: str) -> Optional[Dict[str, Any]]:
    """
    Fetch user summary from MainService API.

    Args:
        user_id: User ID
        base_url: MainService base URL (e.g., "http://mainservice:8080")

    Returns:
        Dict with user data if successful, None if failed or not yet implemented.

    TODO: Implement once MainService defines the GET /user/{user_id}/summary endpoint.
    """
    if not user_id or not base_url:
        logger.warning("Missing user_id or base_url for MainService request")
        return None

    # TODO: Remove this stub once MainService implements the endpoint
    logger.warning(
        f"MainService cold-start is not yet implemented. "
        f"Skipping cold start for user_id={user_id}."
    )
    return None

    # ---- Implementation template (uncomment when API is available) ----
    # url = f"{base_url.rstrip('/')}/user/{user_id}/summary"
    # try:
    #     logger.info(f"Fetching user summary from MainService: {url}")
    #     response = requests.get(url, timeout=1.0)
    #     response.raise_for_status()
    #     data = response.json()
    #     if not data.get("success"):
    #         logger.warning(f"MainService returned success=False: {data.get('message')}")
    #         return None
    #     if "data" not in data:
    #         logger.warning(f"MainService response missing 'data' field: {data}")
    #         return None
    #     logger.info(f"Successfully fetched user summary for user_id={user_id}")
    #     return data["data"]
    # except requests.Timeout:
    #     logger.warning(f"MainService request timeout (1s) for user_id={user_id}, url={url}")
    #     return None
    # except requests.RequestException as e:
    #     logger.warning(f"MainService request failed for user_id={user_id}: {e}")
    #     return None
    # except ValueError as e:
    #     logger.warning(f"Failed to parse MainService JSON response: {e}")
    #     return None
    # except Exception as e:
    #     logger.error(f"Unexpected error fetching from MainService: {e}")
    #     return None
