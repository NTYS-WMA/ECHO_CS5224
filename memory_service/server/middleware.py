"""
Request/Response Logging Middleware

Provides detailed logging for all HTTP requests and responses.
Log level controlled by LOG_LEVEL environment variable.
"""

import json
import logging
from time import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log HTTP requests and responses.

    Logging behavior:
    - INFO level: Log request method, path, status code, and duration
    - DEBUG level: Additionally log query params, request body, and response preview
    """

    def __init__(self, app: ASGIApp, log_level: str = "INFO"):
        super().__init__(app)
        self.log_level = log_level.upper()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log details"""
        start_time = time()

        # Log request info
        self._log_request(request)

        # Process request
        response = await call_next(request)

        # Log response info
        duration = time() - start_time
        self._log_response(request, response, duration)

        return response

    def _log_request(self, request: Request):
        """Log incoming request details"""
        logger.info(f"→ {request.method} {request.url.path}")

        if self.log_level == "DEBUG":
            # Log query parameters
            if request.query_params:
                logger.debug(f"  Query params: {dict(request.query_params)}")

            # Note: Request body logging is handled in endpoint for POST/PUT
            # because reading body here would consume it

    def _log_response(self, request: Request, response: Response, duration: float):
        """Log response details"""
        logger.info(
            f"← {request.method} {request.url.path} "
            f"- Status: {response.status_code} "
            f"- Duration: {duration:.3f}s"
        )


def log_request_body(body_data: dict, endpoint_name: str):
    """
    Helper function to log request body in endpoints.

    Args:
        body_data: Parsed request body (dict)
        endpoint_name: Name of the endpoint for context
    """
    if logger.level <= logging.DEBUG:
        # Truncate or summarize large data
        if "messages" in body_data:
            msg_count = len(body_data.get("messages", []))
            first_msg = body_data["messages"][0] if msg_count > 0 else None
            logger.debug(
                f"  [{endpoint_name}] Request body: "
                f"{{user_id: {body_data.get('user_id', 'N/A')}, "
                f"messages: {msg_count} items, "
                f"first: '{first_msg.get('content', '')[:50] if first_msg else ''}...'}}"
            )
        else:
            # For non-message data, log full JSON (truncated)
            body_str = json.dumps(body_data, ensure_ascii=False)
            logger.debug(f"  [{endpoint_name}] Request body: {body_str[:200]}")


def log_response_data(response_data: dict, endpoint_name: str):
    """
    Helper function to log response data in endpoints.

    Args:
        response_data: Response data (dict)
        endpoint_name: Name of the endpoint for context
    """
    if logger.level <= logging.DEBUG:
        # Summarize response
        if "basic_info" in response_data or "additional_profile" in response_data:
            # Profile response
            basic_fields = len(response_data.get("basic_info", {}))
            additional_fields = len(response_data.get("additional_profile", {}))
            logger.debug(
                f"  [{endpoint_name}] Response: "
                f"{{basic_info: {basic_fields} fields, "
                f"additional_profile: {additional_fields} fields}}"
            )
        elif "success" in response_data:
            # Operation result
            logger.debug(
                f"  [{endpoint_name}] Response: "
                f"{{success: {response_data.get('success')}, "
                f"operations: {response_data.get('operations_performed', {})}}}"
            )
        elif "missing_fields" in response_data:
            # Missing fields response
            missing = response_data.get("missing_fields", {})
            logger.debug(
                f"  [{endpoint_name}] Response: "
                f"{{missing_fields: {list(missing.keys())}}}"
            )
        else:
            # Generic response
            response_str = json.dumps(response_data, ensure_ascii=False)
            logger.debug(f"  [{endpoint_name}] Response: {response_str[:200]}")