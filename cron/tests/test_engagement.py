"""
Tests for the Cron Service v2.0.

Tests cover:
- Domain models and validation
- Utility functions (ID generation, cron parsing, next_run_at)
- Task CRUD API routes (via TestClient)
- Scheduler routes
- Health routes
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

# ================================================================== #
# 1. Domain Model Tests
# ================================================================== #


class TestDomainModels:
    """Test domain models and enums."""

    def test_task_status_values(self):
        from cron.models.domain import TaskStatus

        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.SCHEDULED == "scheduled"
        assert TaskStatus.EXECUTING == "executing"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.CANCELLED == "cancelled"
        assert TaskStatus.PAUSED == "paused"

    def test_task_type_values(self):
        from cron.models.domain import TaskType

        assert TaskType.ONE_TIME == "one_time"
        assert TaskType.RECURRING == "recurring"

    def test_schedule_config_one_time(self):
        from cron.models.domain import ScheduleConfig

        dt = datetime(2026, 4, 1, 9, 0, 0, tzinfo=timezone.utc)
        config = ScheduleConfig(scheduled_at=dt)
        assert config.scheduled_at == dt
        assert config.cron_expression is None
        assert config.interval_seconds is None
        assert config.timezone == "UTC"

    def test_schedule_config_recurring_cron(self):
        from cron.models.domain import ScheduleConfig

        config = ScheduleConfig(cron_expression="0 9 * * *")
        assert config.cron_expression == "0 9 * * *"
        assert config.scheduled_at is None

    def test_schedule_config_recurring_interval(self):
        from cron.models.domain import ScheduleConfig

        config = ScheduleConfig(interval_seconds=3600)
        assert config.interval_seconds == 3600

    def test_schedule_config_interval_min_validation(self):
        from pydantic import ValidationError
        from cron.models.domain import ScheduleConfig

        with pytest.raises(ValidationError):
            ScheduleConfig(interval_seconds=30)  # min is 60

    def test_task_payload_text(self):
        from cron.models.domain import TaskPayload

        payload = TaskPayload(message_type="text", content="Hello!")
        assert payload.message_type == "text"
        assert payload.content == "Hello!"
        assert payload.template_id is None

    def test_task_payload_template(self):
        from cron.models.domain import TaskPayload

        payload = TaskPayload(
            message_type="template",
            template_id="tpl_abc123",
            template_variables={"name": "Alice"},
        )
        assert payload.message_type == "template"
        assert payload.template_id == "tpl_abc123"

    def test_scheduled_task_creation(self):
        from cron.models.domain import (
            ScheduleConfig,
            ScheduledTask,
            TaskPayload,
            TaskStatus,
            TaskType,
        )

        now = datetime.now(timezone.utc)
        task = ScheduledTask(
            task_id="task_test123",
            owner_service="test-service",
            task_type=TaskType.ONE_TIME,
            status=TaskStatus.SCHEDULED,
            channel="telegram",
            user_id="usr_001",
            payload=TaskPayload(message_type="text", content="Hi"),
            schedule_config=ScheduleConfig(scheduled_at=now + timedelta(hours=1)),
            next_run_at=now + timedelta(hours=1),
            created_at=now,
            updated_at=now,
        )
        assert task.task_id == "task_test123"
        assert task.retry_count == 0
        assert task.max_retries == 3


# ================================================================== #
# 2. Utility Function Tests
# ================================================================== #


class TestUtilities:
    """Test utility functions."""

    def test_generate_task_id(self):
        from cron.utils.helpers import generate_task_id

        tid = generate_task_id()
        assert tid.startswith("task_")
        assert len(tid) == 17  # task_ + 12 hex chars

    def test_generate_event_id(self):
        from cron.utils.helpers import generate_event_id

        eid = generate_event_id()
        assert eid.startswith("evt_")

    def test_generate_poll_id(self):
        from cron.utils.helpers import generate_poll_id

        pid = generate_poll_id()
        assert pid.startswith("poll_")

    def test_generate_ids_unique(self):
        from cron.utils.helpers import generate_task_id

        ids = {generate_task_id() for _ in range(100)}
        assert len(ids) == 100

    def test_utc_now(self):
        from cron.utils.helpers import utc_now

        now = utc_now()
        assert now.tzinfo is not None

    def test_compute_next_run_at_scheduled(self):
        from cron.utils.helpers import compute_next_run_at

        dt = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = compute_next_run_at(scheduled_at=dt)
        assert result == dt

    def test_compute_next_run_at_scheduled_naive(self):
        from cron.utils.helpers import compute_next_run_at

        dt = datetime(2026, 6, 1, 12, 0, 0)  # naive
        result = compute_next_run_at(scheduled_at=dt)
        assert result.tzinfo == timezone.utc

    def test_compute_next_run_at_interval(self):
        from cron.utils.helpers import compute_next_run_at

        base = datetime(2026, 3, 22, 10, 0, 0, tzinfo=timezone.utc)
        result = compute_next_run_at(interval_seconds=7200, from_time=base)
        assert result == base + timedelta(seconds=7200)

    def test_compute_next_run_at_cron(self):
        from cron.utils.helpers import compute_next_run_at

        # "0 9 * * *" = every day at 09:00
        base = datetime(2026, 3, 22, 10, 0, 0, tzinfo=timezone.utc)
        result = compute_next_run_at(cron_expression="0 9 * * *", from_time=base)
        assert result is not None
        assert result.hour == 9
        assert result.minute == 0
        assert result > base

    def test_compute_next_run_at_none(self):
        from cron.utils.helpers import compute_next_run_at

        result = compute_next_run_at()
        assert result is None

    def test_compute_next_run_at_invalid_cron(self):
        from cron.utils.helpers import compute_next_run_at

        result = compute_next_run_at(cron_expression="invalid")
        assert result is None


# ================================================================== #
# 3. Request / Response Model Tests
# ================================================================== #


class TestRequestModels:
    """Test request model validation."""

    def test_register_task_request_valid(self):
        from cron.models.requests import RegisterTaskRequest
        from cron.models.domain import (
            ScheduleConfig,
            TaskPayload,
            TaskType,
        )

        req = RegisterTaskRequest(
            owner_service="test-service",
            task_type=TaskType.ONE_TIME,
            channel="telegram",
            user_id="usr_001",
            payload=TaskPayload(message_type="text", content="Hello"),
            schedule_config=ScheduleConfig(
                scheduled_at=datetime(2026, 4, 1, 9, 0, 0, tzinfo=timezone.utc)
            ),
        )
        assert req.max_retries == 3  # default

    def test_register_task_request_recurring(self):
        from cron.models.requests import RegisterTaskRequest
        from cron.models.domain import (
            ScheduleConfig,
            TaskPayload,
            TaskType,
        )

        req = RegisterTaskRequest(
            owner_service="relationship-service",
            task_type=TaskType.RECURRING,
            channel="whatsapp",
            user_id="usr_002",
            payload=TaskPayload(
                message_type="template",
                template_id="tpl_proactive",
                template_variables={"name": "Bob"},
            ),
            schedule_config=ScheduleConfig(cron_expression="0 9 * * 1-5"),
        )
        assert req.task_type == TaskType.RECURRING

    def test_update_task_request_partial(self):
        from cron.models.requests import UpdateTaskRequest
        from cron.models.domain import TaskPayload

        req = UpdateTaskRequest(
            payload=TaskPayload(message_type="text", content="Updated message"),
        )
        assert req.payload is not None
        assert req.schedule_config is None
        assert req.max_retries is None

    def test_manual_poll_trigger_defaults(self):
        from cron.models.requests import ManualPollTriggerRequest

        req = ManualPollTriggerRequest()
        assert req.max_tasks == 100


class TestResponseModels:
    """Test response model construction."""

    def test_task_response_from_domain(self):
        from cron.models.domain import (
            ScheduleConfig,
            ScheduledTask,
            TaskPayload,
            TaskStatus,
            TaskType,
        )
        from cron.models.responses import TaskResponse

        now = datetime.now(timezone.utc)
        task = ScheduledTask(
            task_id="task_abc",
            owner_service="test",
            task_type=TaskType.ONE_TIME,
            status=TaskStatus.SCHEDULED,
            channel="web",
            user_id="usr_x",
            payload=TaskPayload(message_type="text", content="Hi"),
            schedule_config=ScheduleConfig(scheduled_at=now + timedelta(hours=1)),
            next_run_at=now + timedelta(hours=1),
            created_at=now,
            updated_at=now,
        )
        resp = TaskResponse.from_domain(task)
        assert resp.task_id == "task_abc"
        assert resp.status == TaskStatus.SCHEDULED

    def test_poll_cycle_response(self):
        from cron.models.responses import (
            PollCycleResponse,
            PollExecutionResult,
        )

        resp = PollCycleResponse(
            poll_id="poll_test",
            tasks_found=5,
            tasks_dispatched=3,
            tasks_failed=2,
            results=[
                PollExecutionResult(task_id="t1", success=True),
                PollExecutionResult(task_id="t2", success=False, error="timeout"),
            ],
            duration_ms=123.45,
        )
        assert resp.tasks_found == 5
        assert len(resp.results) == 2

    def test_task_deleted_response(self):
        from cron.models.responses import TaskDeletedResponse

        resp = TaskDeletedResponse(task_id="task_del")
        assert resp.status == "cancelled"
        assert "cancelled" in resp.message.lower()


# ================================================================== #
# 4. Event Model Tests
# ================================================================== #


class TestEventModels:
    """Test event model construction."""

    def test_task_dispatched_event(self):
        from cron.models.events import TaskDispatchedEvent

        event = TaskDispatchedEvent(
            event_id="evt_001",
            task_id="task_001",
            user_id="usr_001",
            channel="telegram",
            owner_service="test",
        )
        assert event.event_type == "proactive.task.dispatched"
        assert event.schema_version == "2.0"

    def test_task_failed_event(self):
        from cron.models.events import TaskFailedEvent

        event = TaskFailedEvent(
            event_id="evt_002",
            task_id="task_002",
            user_id="usr_002",
            owner_service="test",
            error="Connection refused",
            retry_count=3,
        )
        assert event.event_type == "proactive.task.failed"
        assert event.retry_count == 3

    def test_outbound_message_payload(self):
        from cron.models.events import OutboundMessagePayload

        payload = OutboundMessagePayload(
            event_id="evt_003",
            task_id="task_003",
            user_id="usr_003",
            channel="whatsapp",
            content="Hello from ECHO!",
        )
        assert payload.event_type == "conversation.outbound"
        assert payload.message_type == "text"


# ================================================================== #
# 5. API Route Tests (via TestClient)
# ================================================================== #


class TestHealthRoutes:
    """Test health check endpoints."""

    def setup_method(self):
        """Create a minimal test app with only health routes."""
        from fastapi import FastAPI
        from cron.routes.health_routes import router

        self.app = FastAPI()
        self.app.include_router(router)
        self.client = TestClient(self.app)

    def test_health(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_readiness(self):
        resp = self.client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"


class TestTaskRouteValidation:
    """Test task route request validation (without actual DB Service)."""

    def setup_method(self):
        """Create a test app with task routes and a mock TaskService."""
        from fastapi import FastAPI
        from cron.routes.task_routes import router, get_task_service
        from cron.services.task_service import TaskService
        from cron.services.db_client import DatabaseServiceClient

        self.app = FastAPI()
        self.app.include_router(router)

        # Create a TaskService with a dummy DB client (won't actually call)
        self.mock_db = DatabaseServiceClient(base_url="http://fake:9999")
        self.mock_service = TaskService(db_client=self.mock_db)

        # Override dependency
        self.app.dependency_overrides[get_task_service] = lambda: self.mock_service
        self.client = TestClient(self.app)

    def test_register_task_validation_missing_fields(self):
        """Missing required fields should return 422."""
        resp = self.client.post("/api/v1/tasks", json={})
        assert resp.status_code == 422

    def test_register_task_validation_valid_body(self):
        """Valid body should not return 422 (may fail at DB level)."""
        body = {
            "owner_service": "test",
            "task_type": "one_time",
            "channel": "telegram",
            "user_id": "usr_001",
            "payload": {"message_type": "text", "content": "Hello"},
            "schedule_config": {
                "scheduled_at": "2026-04-01T09:00:00Z",
            },
        }
        resp = self.client.post("/api/v1/tasks", json=body)
        # Should pass validation (422 would mean validation failed)
        # May get 400 because DB client fails, which is expected
        assert resp.status_code != 422

    def test_list_tasks_default_params(self):
        """List tasks should accept default params (DB may fail)."""
        resp = self.client.get("/api/v1/tasks")
        # Returns 200 with empty list since DB client returns ([], 0) on error
        assert resp.status_code == 200

    def test_get_task_not_found(self):
        """Get non-existent task should return 404."""
        resp = self.client.get("/api/v1/tasks/nonexistent_id")
        assert resp.status_code == 404

    def test_delete_task_not_found(self):
        """Delete non-existent task should return 404."""
        resp = self.client.delete("/api/v1/tasks/nonexistent_id")
        assert resp.status_code == 404

    def test_update_task_not_found(self):
        """Update non-existent task should return 404."""
        resp = self.client.put(
            "/api/v1/tasks/nonexistent_id",
            json={"max_retries": 5},
        )
        assert resp.status_code == 404

    def test_pause_task_not_found(self):
        """Pause non-existent task should return 400."""
        resp = self.client.post("/api/v1/tasks/nonexistent_id/pause")
        assert resp.status_code == 400

    def test_resume_task_not_found(self):
        """Resume non-existent task should return 400."""
        resp = self.client.post("/api/v1/tasks/nonexistent_id/resume")
        assert resp.status_code == 400
