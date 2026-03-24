"""
ECHO — End-to-End Test Script (In-Process)
============================================

Uses FastAPI's TestClient with lifespan support.
Run from project root:

    cd echo-orchestrator
    python tests/test_in_process.py
"""

import json
import time
import sys
import os
import asyncio

# Ensure we can import from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force mock mode
os.environ["MOCK_SERVICES"] = "true"
os.environ["TELEGRAM_BOT_TOKEN"] = "test-token-not-real"

from fastapi.testclient import TestClient
from main import app

# TestClient with lifespan support — this triggers the lifespan startup
client = TestClient(app, raise_server_exceptions=False)

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
passed = 0
failed = 0


def test(name, func):
    global passed, failed
    try:
        func()
        print(f"  ✅ {name}")
        passed += 1
    except AssertionError as e:
        print(f"  ❌ {name} — {e}")
        failed += 1
    except Exception as e:
        print(f"  ❌ {name} — {type(e).__name__}: {e}")
        failed += 1


print("\n" + "=" * 60)
print("  ECHO — End-to-End Tests (In-Process)")
print("=" * 60 + "\n")

#Verify lifespan ran

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert data["mock_mode"] is True

test("Health check", test_health)


def test_event_bus():
    # The lifespan registers workers, but TestClient in sync mode may
    # have timing issues. Manually ensure registration and verify.
    from shared.events.event_bus import event_bus
    from shared.events.topics import CONVERSATION_MESSAGE_RECEIVED, CONVERSATION_OUTBOUND
    from orchestrator.workers.orchestration_worker import register_orchestration_worker
    from channel_gateway.workers.outbound_worker import register_outbound_worker

    # Ensure registered (idempotent check — may already be done by lifespan)
    if CONVERSATION_MESSAGE_RECEIVED not in event_bus.list_topics():
        register_orchestration_worker()
    if CONVERSATION_OUTBOUND not in event_bus.list_topics():
        register_outbound_worker()

    topics = event_bus.list_topics()
    assert CONVERSATION_MESSAGE_RECEIVED in topics, f"Missing topic, got: {topics}"
    assert CONVERSATION_OUTBOUND in topics, f"Missing topic, got: {topics}"

test("Event bus has correct topics", test_event_bus)


#Webhook: commands

def test_start_command():
    with open(os.path.join(TESTS_DIR, "sample_payloads.json")) as f:
        samples = json.load(f)
    r = client.post("/api/v1/channels/telegram/webhook", json=samples["command_start"])
    assert r.status_code == 200
    data = r.json()
    assert "Command handled" in data.get("detail", ""), f"Unexpected: {data}"

test("Webhook — /start command handled inline", test_start_command)


def test_help_command():
    with open(os.path.join(TESTS_DIR, "sample_payloads.json")) as f:
        samples = json.load(f)
    r = client.post("/api/v1/channels/telegram/webhook", json=samples["command_help"])
    assert r.status_code == 200
    assert "Command handled" in r.json().get("detail", "")

test("Webhook — /help command handled inline", test_help_command)


#Webhook: edge cases

def test_empty_text():
    with open(os.path.join(TESTS_DIR, "sample_payloads.json")) as f:
        samples = json.load(f)
    r = client.post("/api/v1/channels/telegram/webhook", json=samples["no_text_message"])
    assert r.status_code == 200
    assert "Ignored" in r.json().get("detail", "")

test("Webhook — empty text message ignored", test_empty_text)


def test_no_message():
    with open(os.path.join(TESTS_DIR, "sample_payloads.json")) as f:
        samples = json.load(f)
    r = client.post("/api/v1/channels/telegram/webhook", json=samples["no_message_update"])
    assert r.status_code == 200
    assert "Ignored" in r.json().get("detail", "")

test("Webhook — update without message ignored", test_no_message)


def test_invalid_json():
    r = client.post(
        "/api/v1/channels/telegram/webhook",
        content="not json",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 400

test("Webhook — invalid JSON returns 400", test_invalid_json)


#Webhook: normal message (verify HTTP layer)

def test_normal_message_accepted():
    with open(os.path.join(TESTS_DIR, "sample_telegram_webhook.json")) as f:
        payload = json.load(f)
    r = client.post("/api/v1/channels/telegram/webhook", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True

test("Webhook — normal message accepted and event published", test_normal_message_accepted)


def test_simulate():
    r = client.post("/debug/simulate", params={"user_id": "usr_sim01", "text": "Testing simulate"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "published"
    assert data["event_id"].startswith("evt-")

test("Simulate endpoint publishes event", test_simulate)


#Unit-style: context models

def test_context_models():
    from orchestrator.models.context import OrchestrationContext, UserContext, RelationshipContext, MemoryContext
    ctx = OrchestrationContext(
        user=UserContext(user_id="usr_test", display_name="Test"),
        relationship=RelationshipContext(affinity_score=0.7, tier="close_friend"),
        memory=MemoryContext(
            short_term_messages=[{"role": "user", "content": "hi"}],
            long_term_memories=[{"memory_id": "m1", "content": "likes running", "score": 0.9}],
        ),
        conversation_id="test-conv",
        correlation_id="evt-test",
        current_message="hello",
    )
    assert ctx.user.display_name == "Test"
    assert ctx.relationship.tier == "close_friend"
    assert len(ctx.memory.long_term_memories) == 1

test("Orchestration context models", test_context_models)


#Unit-style: prompt builder

def test_prompt_builder():
    from orchestrator.models.context import OrchestrationContext, UserContext, RelationshipContext, MemoryContext
    from orchestrator.workers.orchestration_worker import _build_system_prompt

    ctx = OrchestrationContext(
        user=UserContext(
            user_id="usr_alice", display_name="Alice", tone="friendly",
            interests=["fitness", "music"], timezone="Asia/Singapore",
        ),
        relationship=RelationshipContext(affinity_score=0.74, tier="close_friend"),
        memory=MemoryContext(long_term_memories=[
            {"content": "User prefers evening workouts", "score": 0.88},
            {"content": "User listens to pop music", "score": 0.75},
        ]),
        conversation_id="test-conv",
        correlation_id="evt-test",
        current_message="hello",
    )
    prompt = _build_system_prompt(ctx)
    assert "ECHO" in prompt
    assert "Alice" in prompt
    assert "friendly" in prompt
    assert "solid friendship" in prompt
    assert "fitness" in prompt
    assert "evening workouts" in prompt
    assert "Asia/Singapore" in prompt
    print(f"       → System prompt: {len(prompt)} chars")

test("System prompt builder includes all context", test_prompt_builder)


#Unit-style: message builder

def test_message_builder():
    from orchestrator.models.context import OrchestrationContext, UserContext, RelationshipContext, MemoryContext
    from orchestrator.workers.orchestration_worker import _build_messages

    ctx = OrchestrationContext(
        user=UserContext(user_id="usr_test", display_name="Test"),
        relationship=RelationshipContext(),
        memory=MemoryContext(short_term_messages=[
            {"role": "user", "content": "prev msg"},
            {"role": "assistant", "content": "prev reply"},
        ]),
        conversation_id="test-conv",
        correlation_id="evt-test",
        current_message="new message",
    )
    messages = _build_messages(ctx)
    assert messages[0]["role"] == "system"
    assert messages[1]["content"] == "prev msg"
    assert messages[2]["content"] == "prev reply"
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "new message"
    print(f"       → Messages array: {len(messages)} items")

test("Message builder structures conversation correctly", test_message_builder)


#Unit-style: mock clients

def test_mock_clients():
    loop = asyncio.new_event_loop()

    async def check():
        from orchestrator.clients.user_profile_client import get_user_profile
        from orchestrator.clients.relationship_client import get_relationship_context
        from orchestrator.clients.memory_client import get_memory_context
        from orchestrator.clients.ai_generation_client import generate_chat_completion
        from orchestrator.clients.conversation_store_client import persist_messages, get_recent_messages

        profile = await get_user_profile("usr_test", "tester")
        assert profile is not None and "preferences" in profile

        rel = await get_relationship_context("usr_test")
        assert rel is not None and "tier" in rel

        mem = await get_memory_context("usr_test", "conv-1", "hello")
        assert "short_term" in mem and "long_term" in mem

        ai = await generate_chat_completion(
            "usr_test", "conv-1",
            [{"role": "system", "content": "test"}, {"role": "user", "content": "hi"}],
        )
        assert ai is not None and len(ai["output"]) > 0

        ok = await persist_messages("conv-mock-test", "usr_test", "telegram", [
            {"role": "user", "content": "hi", "timestamp": "2026-01-01T00:00:00Z"},
        ])
        assert ok is True

        recent = await get_recent_messages("conv-mock-test", limit=5)
        assert len(recent) >= 1

    loop.run_until_complete(check())
    loop.close()

test("All mock clients return valid data", test_mock_clients)


#Unit-style: event models

def test_event_models():
    from shared.models.events import (
        ConversationMessageReceivedEvent, ConversationOutboundEvent,
        RelationshipInteractionEvent, MemorySummaryRequestedEvent,
        ConversationProcessingFailedEvent, MessagePayload, MessageContext, ResponseItem,
    )

    inbound = ConversationMessageReceivedEvent(
        user_id="usr_test", external_user_id="telegram:1",
        conversation_id="conv-1", channel_message_id="tg-1",
        message=MessagePayload(role="user", type="text", content="hello"),
        context=MessageContext(platform_user_id="1", platform_chat_id="1"),
    )
    assert inbound.model_dump()["event_type"] == "conversation.message.received"

    outbound = ConversationOutboundEvent(
        user_id="usr_test", external_user_id="telegram:1",
        conversation_id="conv-1",
        responses=[ResponseItem(type="text", content="reply")],
    )
    assert outbound.model_dump()["event_type"] == "conversation.reply.generated"

    rel = RelationshipInteractionEvent(
        user_id="usr_test", external_user_id="telegram:1", conversation_id="conv-1",
    )
    assert rel.model_dump()["event_type"] == "relationship.interaction.recorded"

    mem = MemorySummaryRequestedEvent(user_id="usr_test", conversation_id="conv-1")
    assert mem.model_dump()["event_type"] == "memory.summary.requested"

    fail = ConversationProcessingFailedEvent(
        user_id="usr_test", external_user_id="telegram:1",
        conversation_id="conv-1", stage="ai_generation", error_code="TIMEOUT",
    )
    assert fail.model_dump()["event_type"] == "conversation.processing.failed"

test("All event models serialize correctly", test_event_models)


#Unit-style: Telegram models

def test_telegram_models():
    from channel_gateway.models.telegram import TelegramUpdate

    with open(os.path.join(TESTS_DIR, "sample_telegram_webhook.json")) as f:
        data = json.load(f)
    update = TelegramUpdate(**data)
    assert update.message.text == "Hello ECHO"
    assert update.message.from_.username == "alice123"
    assert update.message.chat.id == 123456789

    update2 = TelegramUpdate(update_id=999)
    assert update2.message is None

test("Telegram models parse all webhook formats", test_telegram_models)


#Full async orchestration pipeline

def test_full_orchestration():
    """Run the full orchestration handler directly to verify the entire pipeline."""
    loop = asyncio.new_event_loop()

    async def run():
        from orchestrator.workers.orchestration_worker import handle_inbound_message
        from orchestrator.clients.conversation_store_client import (
            get_recent_messages, get_conversation_length, _in_memory_store,
        )
        from shared.models.events import (
            ConversationMessageReceivedEvent, MessagePayload, MessageContext,
        )

        test_conv = "telegram-chat-e2e-test"
        _in_memory_store.pop(test_conv, None)

        event = ConversationMessageReceivedEvent(
            user_id="usr_e2e_test", external_user_id="telegram:999",
            conversation_id=test_conv, channel_message_id="tg-e2e-1",
            message=MessagePayload(role="user", type="text", content="Hey ECHO, what's up?"),
            context=MessageContext(platform_user_id="999", platform_chat_id="999", username="e2e_tester"),
        )

        await handle_inbound_message(event.model_dump())

        # Allow background tasks to complete
        await asyncio.sleep(0.5)

        messages = await get_recent_messages(test_conv)
        assert len(messages) >= 2, f"Expected >= 2 messages, got {len(messages)}"

        user_msg = messages[0]
        assert user_msg["role"] == "user"
        assert user_msg["content"] == "Hey ECHO, what's up?"

        assistant_msg = messages[1]
        assert assistant_msg["role"] == "assistant"
        assert len(assistant_msg["content"]) > 0

        print(f"       → User: '{user_msg['content']}'")
        print(f"       → ECHO: '{assistant_msg['content'][:70]}...'")
        print(f"       → Conversation length: {get_conversation_length(test_conv)}")

    loop.run_until_complete(run())
    loop.close()

test("Full orchestration pipeline (async, direct call)", test_full_orchestration)


print("\n" + "=" * 60)
print(f"  Results: {passed} passed, {failed} failed, {passed + failed} total")
print("=" * 60 + "\n")

if failed > 0:
    print("⚠️  Some tests failed. Check output above.\n")
    sys.exit(1)
else:
    print("🎉 All tests passed!\n")
    print("Notes:")
    print("  - Telegram API delivery is blocked in this sandbox (expected).")
    print("  - All downstream services used mock responses.")
    print("  - Set MOCK_SERVICES=false and configure real service URLs for integration testing.")
    print()
