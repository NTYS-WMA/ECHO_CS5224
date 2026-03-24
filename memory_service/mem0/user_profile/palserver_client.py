"""
PalServer HTTP Client for Cold Start Integration

Fetches initial user profile data from PalServer during first-time user access.
"""

import logging
from typing import Optional, Dict, Any
import requests

logger = logging.getLogger(__name__)


def fetch_child_summary(child_id: str, base_url: str) -> Optional[Dict[str, Any]]:
    """
    Fetch child summary from PalServer API

    Args:
        child_id: Child ID (session_id in PalServer)
        base_url: PalServer base URL (e.g., "http://localhost:8099/pal")

    Returns:
        Dict with child data if successful, None if failed

    Example response:
        {
            "success": True,
            "code": "CHILD_INFO_RETRIEVED",
            "message": "孩子信息获取成功",
            "data": {
                "id": 12345,
                "childName": "小明",
                "age": 8,
                "gender": 1,
                "personalityTraits": "开朗,善良,勇敢",
                "hobbies": "篮球,音乐,阅读",
                ...
            }
        }
    """
    if not child_id or not base_url:
        logger.warning("Missing child_id or base_url for PalServer request")
        return None

    # Build URL
    url = f"{base_url.rstrip('/')}/child/{child_id}/summary"

    try:
        # Make HTTP request with 1 second timeout (cluster internal network)
        logger.info(f"Fetching child summary from PalServer: {url}")
        response = requests.get(url, timeout=1.0)

        # Check HTTP status
        response.raise_for_status()

        # Parse JSON
        data = response.json()

        # Validate response structure
        if not data.get("success"):
            logger.warning(f"PalServer returned success=False: {data.get('message')}")
            return None

        if "data" not in data:
            logger.warning(f"PalServer response missing 'data' field: {data}")
            return None

        logger.info(f"Successfully fetched child summary for child_id={child_id}")
        return data["data"]

    except requests.Timeout:
        logger.warning(f"PalServer request timeout (1s) for child_id={child_id}, url={url}")
        return None

    except requests.RequestException as e:
        logger.warning(f"PalServer request failed for child_id={child_id}: {e}")
        return None

    except ValueError as e:
        logger.warning(f"Failed to parse PalServer JSON response: {e}")
        return None

    except Exception as e:
        logger.error(f"Unexpected error fetching from PalServer: {e}")
        return None
