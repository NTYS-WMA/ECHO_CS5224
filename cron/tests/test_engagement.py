"""
Tests for the Cron Service v3.0.

Tests cover:
- Domain models (ScheduleEntry)
- Event models (CronTriggeredEvent)
- Utility functions (ID generation, cron parsing, compute_next_run_at)
- Configuration (settings, schedule loading)
- API routes (health, schedules, scheduler status)
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


# ================================================================== #
# 1. Domain Model Tests
# ================================================================== #


class TestDomainModels:
    """Test domain models."""

    def test_schedule_entry_cron(self):
        from cron.models.domain import ScheduleEntry

        entry = ScheduleEntry(
            name="test-decay",
            cron_expression="0 3 * * *",
            topic="relationship.decay.requested",
        )
        assert entry.name == "test-decay"
        assert entry.cron_expression == "0 3 * * *"
        assert entry.topic == "relationship.decay.requested"
        assert entry.enabled is True
        assert entry.payload == {}
        assert entry.next_fire_at is None
        assert entry.last_fired_at is None

    def test_schedule_entry_interval(self):
        from cron.models.domain import ScheduleEntry

        entry = ScheduleEntry(
            name="test-interval",
            interval_seconds=3600,
            topic="test.ping",
            payload={"key": "value"},
        )
        assert entry.interval_seconds == 3600
        assert entry.payload == {"key": "value"}

    def test_schedule_entry_disabled(self):
        from cron.models.domain import ScheduleEntry

        entry = ScheduleEntry(
            name="disabled",
            cron_expression="0 0 * * *",
            topic="test.disabled",
            enabled=False,
        )
        assert entry.enabled is False

    def test_schedule_entry_with_fire_times(self):
        from cron.models.domain import ScheduleEntry

        now = datetime.now(timezone.utc)
        entry = ScheduleEntry(
            name="test",
            cron_expression="0 9 * * *",
            topic="test.topic",
            next_fire_at=now + timedelta(hours=1),
            last_fired_at=now - timedelta(hours=23),
        )
        assert entry.next_fire_at > now
        assert entry.last_fired_at < now

    def test_schedule_entry_interval_min_validation(self):
        from pydantic import ValidationError
        from cron.models.domain import ScheduleEntry

        with pytest.raises(ValidationError):
            ScheduleEntry(
                name="invalid",
                interval_seconds=30,  # min is 60
                topic="test",
            )


# ================================================================== #
# 2. Event Model Tests
# ================================================================== #


class TestEventModels:
    """Test event models."""

    def test_cron_triggered_event(self):
        from cron.models.events import CronTriggeredEvent

        event = CronTriggeredEvent(
            event_id="evt_001",
            event_type="relationship.decay.requested",
            schedule_name="relationship-decay",
            payload={"scope": "all"},
        )
        assert event.event_id == "evt_001"
        assert event.event_type == "relationship.decay.requested"
        assert event.source == "cron-service"
        assert event.schema_version == "3.0"
        assert event.schedule_name == "relationship-decay"
        assert event.payload == {"scope": "all"}
        assert event.timestamp is not None

    def test_cron_triggered_event_defaults(self):
        from cron.models.events import CronTriggeredEvent

        event = CronTriggeredEvent(
            event_id="evt_002",
            event_type="test.topic",
            schedule_name="test",
        )
        assert event.payload == {}
        assert event.correlation_id is None


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
# 4. Response Model Tests
# ================================================================== #


class TestResponseModels:
    """Test response models."""

    def test_schedule_entry_response(self):
        from cron.models.responses import ScheduleEntryResponse

        resp = ScheduleEntryResponse(
            name="test",
            cron_expression="0 3 * * *",
            topic="test.topic",
            enabled=True,
        )
        assert resp.name == "test"
        assert resp.topic == "test.topic"

    def test_schedule_list_response(self):
        from cron.models.responses import ScheduleEntryResponse, ScheduleListResponse

        resp = ScheduleListResponse(
            schedules=[
                ScheduleEntryResponse(
                    name="s1",
                    cron_expression="0 3 * * *",
                    topic="t1",
                    enabled=True,
                ),
                ScheduleEntryResponse(
                    name="s2",
                    interval_seconds=3600,
                    topic="t2",
                    enabled=False,
                ),
            ],
            total=2,
        )
        assert resp.total == 2
        assert len(resp.schedules) == 2

    def test_scheduler_status_response(self):
        from cron.models.responses import SchedulerStatusResponse

        resp = SchedulerStatusResponse(
            running=True,
            tick_interval_seconds=30,
            total_schedules=3,
            active_schedules=2,
        )
        assert resp.running is True
        assert resp.total_schedules == 3

    def test_manual_trigger_response(self):
        from cron.models.responses import ManualTriggerResponse

        resp = ManualTriggerResponse(
            schedule_name="test",
            topic="test.topic",
            published=True,
        )
        assert resp.published is True
        assert resp.error is None


# ================================================================== #
# 5. Configuration Tests
# ================================================================== #


class TestConfiguration:
    """Test settings and schedule loading."""

    def test_default_schedules(self):
        from cron.config.settings import DEFAULT_SCHEDULES

        assert len(DEFAULT_SCHEDULES) >= 2
        names = [s["name"] for s in DEFAULT_SCHEDULES]
        assert "relationship-decay" in names

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
# 6. API Route Tests (via TestClient)
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


class TestSchedulerIntegration:
    """Test CronScheduler without real broker."""

    def test_load_schedules(self):
        from cron.config.settings import ScheduleEntryConfig
        from cron.events.publisher import EventPublisher
        from cron.services.scheduler import CronScheduler

        publisher = EventPublisher(
            broker_url="http://fake:9999",
            enabled=False,
        )
        scheduler = CronScheduler(publisher=publisher, tick_interval_seconds=60)

        configs = [
            ScheduleEntryConfig(
                name="test-decay",
                cron_expression="0 3 * * *",
                topic="relationship.decay.requested",
            ),
            ScheduleEntryConfig(
                name="test-compact",
                cron_expression="0 4 * * 0",
                topic="memory.compaction.requested",
                enabled=False,
            ),
        ]
        scheduler.load_schedules(configs)

        entries = scheduler.get_schedules()
        assert len(entries) == 2

        decay = scheduler.get_schedule("test-decay")
        assert decay is not None
        assert decay.topic == "relationship.decay.requested"
        assert decay.next_fire_at is not None
        assert decay.enabled is True

        compact = scheduler.get_schedule("test-compact")
        assert compact is not None
        assert compact.enabled is False

    def test_get_status(self):
        from cron.events.publisher import EventPublisher
        from cron.services.scheduler import CronScheduler

        publisher = EventPublisher(broker_url="http://fake:9999", enabled=False)
        scheduler = CronScheduler(publisher=publisher)

        status = scheduler.get_status()
        assert status["running"] is False
        assert status["total_schedules"] == 0
        assert status["active_schedules"] == 0

    def test_get_schedule_not_found(self):
        from cron.events.publisher import EventPublisher
        from cron.services.scheduler import CronScheduler

        publisher = EventPublisher(broker_url="http://fake:9999", enabled=False)
        scheduler = CronScheduler(publisher=publisher)

        assert scheduler.get_schedule("nonexistent") is None
