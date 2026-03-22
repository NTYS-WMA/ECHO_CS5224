"""
Unit tests for the AI Generation Service API routes.

Uses a mock provider to test request/response contracts without
requiring an actual AI provider connection.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from ..app import create_app
from ..services.generation_service import GenerationService


# ------------------------------------------------------------------ #
# Sample request payloads
# ------------------------------------------------------------------ #

CHAT_COMPLETION_PAYLOAD = {
    "user_id": "usr_9f2a7c41",
    "conversation_id": "telegram-chat-123456789",
    "messages": [
        {"role": "system", "content": "You are ECHO, a warm and concise companion."},
        {"role": "user", "content": "Hello ECHO"},
    ],
    "generation_config": {"temperature": 0.7, "max_tokens": 200},
    "correlation_id": "evt-001",
}

SUMMARY_PAYLOAD = {
    "user_id": "usr_9f2a7c41",
    "conversation_id": "telegram-chat-123456789",
    "messages_window": {
        "from_message_id": "msg-601",
        "to_message_id": "msg-645",
    },
    "summary_type": "memory_compaction",
    "correlation_id": "evt-022",
}

PROACTIVE_MESSAGE_PAYLOAD = {
    "user_id": "usr_9f2a7c41",
    "relationship": {
        "tier": "close_friend",
        "affinity_score": 0.74,
        "days_inactive": 3,
    },
    "context": {
        "recent_summary": "User enjoys evening workouts and friendly check-ins",
        "timezone": "Asia/Singapore",
    },
    "constraints": {"max_tokens": 120, "tone": "friendly"},
    "correlation_id": "evt-6001",
}


# ------------------------------------------------------------------ #
# Tests
# ------------------------------------------------------------------ #


class TestHealthRoutes:
    """Test health check endpoints."""

    def setup_method(self):
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_health_check(self):
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_readiness_check(self):
        response = self.client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"


class TestRequestValidation:
    """
    Test request payload validation.

    These tests verify that FastAPI's request validation rejects
    incomplete payloads with 422 status codes. Since validation
    happens before the dependency injection of GenerationService,
    we mock the service dependency to avoid the RuntimeError.
    """

    def setup_method(self):
        self.app = create_app()
        # Override the dependency to return a mock service
        mock_service = MagicMock(spec=GenerationService)

        from ..routes.generation_routes import get_generation_service

        self.app.dependency_overrides[get_generation_service] = lambda: mock_service
        self.client = TestClient(self.app)

    def teardown_method(self):
        self.app.dependency_overrides.clear()

    def test_chat_completion_missing_messages(self):
        payload = {
            "user_id": "usr_test",
            "conversation_id": "conv-1",
        }
        response = self.client.post(
            "/api/v1/generation/chat-completions", json=payload
        )
        assert response.status_code == 422

    def test_summary_missing_window(self):
        payload = {
            "user_id": "usr_test",
            "conversation_id": "conv-1",
            "summary_type": "memory_compaction",
        }
        response = self.client.post("/api/v1/generation/summaries", json=payload)
        assert response.status_code == 422

    def test_proactive_missing_relationship(self):
        payload = {
            "user_id": "usr_test",
        }
        response = self.client.post(
            "/api/v1/generation/proactive-messages", json=payload
        )
        assert response.status_code == 422

    def test_chat_completion_valid_payload_shape(self):
        """Verify a valid payload passes request validation (not 422)."""
        from ..models.requests import ChatCompletionRequest
        # Validate that the payload can be parsed into the request model
        req = ChatCompletionRequest(**CHAT_COMPLETION_PAYLOAD)
        assert req.user_id == "usr_9f2a7c41"
        assert len(req.messages) == 2

    def test_proactive_valid_payload_shape(self):
        """Verify a valid proactive payload passes request validation."""
        from ..models.requests import ProactiveMessageRequest
        req = ProactiveMessageRequest(**PROACTIVE_MESSAGE_PAYLOAD)
        assert req.user_id == "usr_9f2a7c41"
        assert req.relationship.tier == "close_friend"
