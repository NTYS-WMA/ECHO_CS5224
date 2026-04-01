"""
Tests for the Cron Service v4.0.

Tests cover:
- Domain models (ScheduledEvent, ScheduleEntry)
- Event models (CronTriggeredEvent)
- Utility functions (ID generation, cron parsing, compute_next_run_at)
- Request / Response models
- Configuration (settings, schedule loading)
- API routes (health)
- Scheduler logic (with mocked DB client)
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ================================================================== #
# 1. Domain Model Tests
# ================================================================== #


class TestDomainModels:
    """Test domain models."""

    def test_scheduled_event(self):
        from cron.models.domain import ScheduledEvent

        event = ScheduledEvent(
            id="550e8400-e29b-41d4-a716-446655440000",
            event_name="proactive-reminder",
            event_type="one_time",
            caller_service="proactive-message-service",
            topic="proactive.message.send",
            payload={"user_id": "u123", "message_template": "follow_up"},
            status="active",
        )
        assert event.event_name == "proactive-reminder"
        assert event.event_type == "one_time"
        assert event.caller_service == "proactive-message-service"
        assert event.payload["user_id"] == "u123"
        assert event.status == "active"
        assert event.fire_count == 0

    def test_scheduled_event_recurring(self):
        from cron.models.domain import ScheduledEvent

        event = ScheduledEvent(
            id="test-uuid",
            event_name="relationship-decay",
            event_type="recurring",
            caller_service="cron-service",
            topic="relationship.decay.requested",
            cron_expression="0 3 * * *",
            status="active",
            fire_count=10,
        )
        assert event.event_type == "recurring"
        assert event.cron_expression == "0 3 * * *"
        assert event.fire_count == 10

    def test_scheduled_event_with_group_key(self):
        from cron.models.domain import ScheduledEvent

        event = ScheduledEvent(
            id="test-uuid",
            event_name="proactive-check",
            event_type="one_time",
            caller_service="proactive-service",
            group_key="user_123",
            payload={"conversation_id": "conv_456"},
        )
        assert event.group_key == "user_123"

    def test_legacy_schedule_entry(self):
        from cron.models.domain import ScheduleEntry

        entry = ScheduleEntry(
            name="test-decay",
            cron_expression="0 3 * * *",
            topic="relationship.decay.requested",
        )
        assert entry.name == "test-decay"
        assert entry.enabled is True
        assert entry.payload == {}

    def test_legacy_schedule_entry_interval_validation(self):
        from pydantic import ValidationError
        from cron.models.domain import ScheduleEntry

        with pytest.raises(ValidationError):
            ScheduleEntry(name="invalid", interval_seconds=30, topic="test")


# ================================================================== #
# 2. Event Model Tests
# ================================================================== #


class TestEventModels:
    """Test event models."""

    def test_cron_triggered_event(self):
        from cron.models.events import CronTriggeredEvent

        event = CronTriggeredEvent(
            event_id="evt_001",
            event_type="proactive.message.send",
            scheduled_event_id="uuid-001",
            event_name="proactive-reminder",
            caller_service="proactive-service",
            payload={"user_id": "u123", "template": "follow_up"},
        )
        assert event.event_id == "evt_001"
        assert event.source == "cron-service"
        assert event.schema_version == "4.0"
        assert event.payload["user_id"] == "u123"
        assert event.scheduled_event_id == "uuid-001"

    def test_cron_triggered_event_defaults(self):
        from cron.models.events import CronTriggeredEvent

        event = CronTriggeredEvent(
            event_id="evt_002",
            event_type="test.topic",
            scheduled_event_id="uuid-002",
            event_name="test",
            caller_service="test-service",
        )
        assert event.payload == {}
        assert event.correlation_id is None
        assert event.group_key is None


# ================================================================== #
# 3. Utility Function Tests
# ================================================================== #


class TestUtilities:
    """Test utility functions."""

    def test_generate_event_id(self):
        from cron.utils.helpers import generate_event_id

        eid = generate_event_id()
        assert eid.startswith("evt_")

    def test_generate_ids_unique(self):
        from cron.utils.helpers import generate_event_id

        ids = {generate_event_id() for _ in range(100)}
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

        dt = datetime(2026, 6, 1, 12, 0, 0)
        result = compute_next_run_at(scheduled_at=dt)
        assert result.tzinfo == timezone.utc

    def test_compute_next_run_at_interval(self):
        from cron.utils.helpers import compute_next_run_at

        base = datetime(2026, 3, 22, 10, 0, 0, tzinfo=timezone.utc)
        result = compute_next_run_at(interval_seconds=7200, from_time=base)
        assert result == base + timedelta(seconds=7200)

    def test_compute_next_run_at_cron(self):
        from cron.utils.helpers import compute_next_run_at

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
# 4. Request Model Tests
# ================================================================== #


class TestRequestModels:
    """Test request models."""

    def test_register_event_request(self):
        from cron.models.requests import RegisterEventRequest

        req = RegisterEventRequest(
            event_name="proactive-reminder",
            event_type="one_time",
            caller_service="proactive-service",
            topic="proactive.message.send",
            scheduled_at=datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc),
            payload={"user_id": "u123", "conversation_id": "c456"},
            group_key="user_u123",
        )
        assert req.event_name == "proactive-reminder"
        assert req.payload["user_id"] == "u123"
        assert req.group_key == "user_u123"

    def test_register_recurring_event(self):
        from cron.models.requests import RegisterEventRequest

        req = RegisterEventRequest(
            event_name="daily-check",
            event_type="recurring",
            caller_service="monitoring",
            topic="monitoring.daily",
            cron_expression="0 9 * * *",
        )
        assert req.event_type == "recurring"
        assert req.cron_expression == "0 9 * * *"


# ================================================================== #
# 5. Response Model Tests
# ================================================================== #


class TestResponseModels:
    """Test response models."""

    def test_scheduled_event_response(self):
        from cron.models.responses import ScheduledEventResponse

        resp = ScheduledEventResponse(
            id="uuid-001",
            event_name="test",
            event_type="one_time",
            caller_service="test-service",
            status="active",
        )
        assert resp.id == "uuid-001"
        assert resp.fire_count == 0

    def test_event_list_response(self):
        from cron.models.responses import EventListResponse, ScheduledEventResponse

        resp = EventListResponse(
            events=[
                ScheduledEventResponse(
                    id="1", event_name="e1", event_type="one_time",
                    caller_service="s1", status="active",
                ),
                ScheduledEventResponse(
                    id="2", event_name="e2", event_type="recurring",
                    caller_service="s2", status="active",
                ),
            ],
            total=2,
        )
        assert resp.total == 2
        assert len(resp.events) == 2

    def test_scheduler_status_response(self):
        from cron.models.responses import SchedulerStatusResponse

        resp = SchedulerStatusResponse(
            running=True,
            tick_interval_seconds=30,
            total_events_polled=100,
            total_events_fired=42,
            db_manager_url="http://localhost:18087",
        )
        assert resp.running is True
        assert resp.total_events_fired == 42

    def test_register_event_response(self):
        from cron.models.responses import RegisterEventResponse

        resp = RegisterEventResponse(
            id="uuid-001",
            event_name="test",
            event_type="one_time",
            status="active",
        )
        assert resp.message == "Event registered successfully."

    def test_manual_trigger_response(self):
        from cron.models.responses import ManualTriggerResponse

        resp = ManualTriggerResponse(
            event_id="uuid-001",
            event_name="test",
            topic="test.topic",
            published=True,
        )
        assert resp.published is True
        assert resp.error is None


# ================================================================== #
# 6. Configuration Tests
# ================================================================== #


class TestConfiguration:
    """Test settings and schedule loading."""

    def test_default_schedules(self):
        from cron.config.settings import DEFAULT_SCHEDULES

        assert len(DEFAULT_SCHEDULES) >= 2
        names = [s["name"] for s in DEFAULT_SCHEDULES]
        assert "relationship-decay" in names
        assert "memory-compaction" in names

    def test_schedule_entry_config(self):
        from cron.config.settings import ScheduleEntryConfig

        cfg = ScheduleEntryConfig(
            name="test",
            cron_expression="0 3 * * *",
            topic="test.topic",
        )
        assert cfg.name == "test"
        assert cfg.enabled is True


# ================================================================== #
# 7. Health Route Tests
# ================================================================== #


class TestHealthRoutes:
    """Test health check endpoints."""

    def setup_method(self):
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


# ================================================================== #
# 8. Scheduler Unit Tests (mocked DB client)
# ================================================================== #


class TestSchedulerLogic:
    """Test CronScheduler with mocked DBManagerClient."""

    def test_get_status_initial(self):
        from cron.events.publisher import EventPublisher
        from cron.clients.db_manager_client import DBManagerClient
        from cron.services.scheduler import CronScheduler

        publisher = EventPublisher(broker_url="http://fake:9999", enabled=False)
        db_client = DBManagerClient(base_url="http://fake:18087")
        scheduler = CronScheduler(
            publisher=publisher, db_client=db_client, tick_interval_seconds=60
        )

        status = scheduler.get_status()
        assert status["running"] is False
        assert status["total_events_polled"] == 0
        assert status["total_events_fired"] == 0

    @pytest.mark.asyncio
    async def test_tick_no_due_events(self):
        from cron.events.publisher import EventPublisher
        from cron.clients.db_manager_client import DBManagerClient
        from cron.services.scheduler import CronScheduler

        publisher = EventPublisher(broker_url="http://fake:9999", enabled=False)
        db_client = DBManagerClient(base_url="http://fake:18087")
        db_client.poll_due_events = AsyncMock(return_value=[])

        scheduler = CronScheduler(
            publisher=publisher, db_client=db_client, tick_interval_seconds=60
        )
        await scheduler._tick()

        assert scheduler._total_polled == 0
        assert scheduler._total_fired == 0

    @pytest.mark.asyncio
    async def test_tick_fires_due_event(self):
        from cron.events.publisher import EventPublisher
        from cron.clients.db_manager_client import DBManagerClient
        from cron.services.scheduler import CronScheduler

        publisher = EventPublisher(broker_url="http://fake:9999", enabled=False)
        publisher.publish = AsyncMock(return_value=True)

        db_client = DBManagerClient(base_url="http://fake:18087")
        now = datetime.now(timezone.utc)
        db_client.poll_due_events = AsyncMock(return_value=[
            {
                "id": "evt-uuid-1",
                "event_name": "test-event",
                "event_type": "one_time",
                "caller_service": "test-service",
                "topic": "test.topic",
                "callback_url": None,
                "payload": {"key": "value"},
                "fire_count": 0,
                "max_fires": None,
                "cron_expression": None,
                "interval_seconds": None,
                "correlation_id": None,
                "group_key": None,
            }
        ])
        db_client.mark_fired = AsyncMock(return_value=True)

        scheduler = CronScheduler(
            publisher=publisher, db_client=db_client, tick_interval_seconds=60
        )
        await scheduler._tick()

        assert scheduler._total_polled == 1
        assert scheduler._total_fired == 1
        db_client.mark_fired.assert_called_once()
        # One-time event should be marked as completed
        call_args = db_client.mark_fired.call_args
        assert call_args.kwargs["new_status"] == "completed"
        assert call_args.kwargs["next_fire_at"] is None

    @pytest.mark.asyncio
    async def test_tick_fires_recurring_event(self):
        from cron.events.publisher import EventPublisher
        from cron.clients.db_manager_client import DBManagerClient
        from cron.services.scheduler import CronScheduler

        publisher = EventPublisher(broker_url="http://fake:9999", enabled=False)
        publisher.publish = AsyncMock(return_value=True)

        db_client = DBManagerClient(base_url="http://fake:18087")
        db_client.poll_due_events = AsyncMock(return_value=[
            {
                "id": "evt-uuid-2",
                "event_name": "recurring-test",
                "event_type": "recurring",
                "caller_service": "test-service",
                "topic": "test.recurring",
                "callback_url": None,
                "payload": {},
                "fire_count": 5,
                "max_fires": None,
                "cron_expression": "0 9 * * *",
                "interval_seconds": None,
                "correlation_id": None,
                "group_key": None,
            }
        ])
        db_client.mark_fired = AsyncMock(return_value=True)

        scheduler = CronScheduler(
            publisher=publisher, db_client=db_client, tick_interval_seconds=60
        )
        await scheduler._tick()

        call_args = db_client.mark_fired.call_args
        assert call_args.kwargs["new_status"] == "active"
        assert call_args.kwargs["next_fire_at"] is not None

    @pytest.mark.asyncio
    async def test_recurring_event_max_fires_reached(self):
        from cron.events.publisher import EventPublisher
        from cron.clients.db_manager_client import DBManagerClient
        from cron.services.scheduler import CronScheduler

        publisher = EventPublisher(broker_url="http://fake:9999", enabled=False)
        publisher.publish = AsyncMock(return_value=True)

        db_client = DBManagerClient(base_url="http://fake:18087")
        db_client.poll_due_events = AsyncMock(return_value=[
            {
                "id": "evt-uuid-3",
                "event_name": "limited-recurring",
                "event_type": "recurring",
                "caller_service": "test-service",
                "topic": "test.limited",
                "callback_url": None,
                "payload": {},
                "fire_count": 9,  # Will become 10 after fire
                "max_fires": 10,
                "cron_expression": "0 9 * * *",
                "interval_seconds": None,
                "correlation_id": None,
                "group_key": None,
            }
        ])
        db_client.mark_fired = AsyncMock(return_value=True)

        scheduler = CronScheduler(
            publisher=publisher, db_client=db_client, tick_interval_seconds=60
        )
        await scheduler._tick()

        call_args = db_client.mark_fired.call_args
        assert call_args.kwargs["new_status"] == "completed"

    @pytest.mark.asyncio
    async def test_register_defaults_skips_existing(self):
        from cron.config.settings import ScheduleEntryConfig
        from cron.events.publisher import EventPublisher
        from cron.clients.db_manager_client import DBManagerClient
        from cron.services.scheduler import CronScheduler

        publisher = EventPublisher(broker_url="http://fake:9999", enabled=False)
        db_client = DBManagerClient(base_url="http://fake:18087")
        db_client.list_events = AsyncMock(return_value={"total": 1, "events": [{}]})
        db_client.create_event = AsyncMock()

        scheduler = CronScheduler(
            publisher=publisher, db_client=db_client, tick_interval_seconds=60
        )

        configs = [
            ScheduleEntryConfig(
                name="relationship-decay",
                cron_expression="0 3 * * *",
                topic="relationship.decay.requested",
            ),
        ]
        await scheduler.register_defaults(configs)

        db_client.create_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_defaults_creates_new(self):
        from cron.config.settings import ScheduleEntryConfig
        from cron.events.publisher import EventPublisher
        from cron.clients.db_manager_client import DBManagerClient
        from cron.services.scheduler import CronScheduler

        publisher = EventPublisher(broker_url="http://fake:9999", enabled=False)
        db_client = DBManagerClient(base_url="http://fake:18087")
        db_client.list_events = AsyncMock(return_value={"total": 0, "events": []})
        db_client.create_event = AsyncMock(return_value={"id": "new-uuid"})

        scheduler = CronScheduler(
            publisher=publisher, db_client=db_client, tick_interval_seconds=60
        )

        configs = [
            ScheduleEntryConfig(
                name="memory-compaction",
                cron_expression="0 4 * * 0",
                topic="memory.compaction.requested",
            ),
        ]
        await scheduler.register_defaults(configs)

        db_client.create_event.assert_called_once()
