"""
ECHO — End-to-End Test Script
===============================

Run with:  python -m tests.test_flow

This starts the FastAPI app on port 8000, then fires a series of HTTP
requests to test the full pipeline (Channel Gateway → Event Bus →
Orchestrator → mock clients → Event Bus → Outbound Worker).

Requires MOCK_SERVICES=true (the default) so no external services are needed.
Telegram delivery will fail for simulated chats — that's expected.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000"
TESTS_DIR = Path(__file__).parent


async def run_tests():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:

        print("\n" + "=" * 60)
        print("  ECHO — End-to-End Flow Tests")
        print("=" * 60)

        #1. Health check
        print("\n[1] Health check...")
        resp = await client.get("/health")
        assert resp.status_code == 200, f"Health check failed: {resp.status_code}"
        data = resp.json()
        assert data["status"] == "healthy"
        print(f"    ✅ {data}")

        #2. Event bus debug
        print("\n[2] Event bus topics...")
        resp = await client.get("/debug/event-bus")
        assert resp.status_code == 200
        print(f"    ✅ Topics: {resp.json()['topics']}")

        #3. Telegram webhook — normal message
        print("\n[3] Telegram webhook — normal message...")
        with open(TESTS_DIR / "sample_telegram_webhook.json") as f:
            payload = json.load(f)
        resp = await client.post("/api/v1/channels/telegram/webhook", json=payload)
        assert resp.status_code == 200, f"Webhook failed: {resp.text}"
        print(f"    ✅ Response: {resp.json()}")

        # Give the async pipeline a moment to process
        await asyncio.sleep(1.5)

        #4. Check conversation store
        print("\n[4] Conversation store state...")
        resp = await client.get("/debug/conversations")
        assert resp.status_code == 200
        convs = resp.json()
        print(f"    ✅ Conversations tracked: {len(convs)}")
        for conv_id, info in convs.items():
            print(f"       {conv_id}: {info['message_count']} messages")
            if info.get("last_message"):
                print(f"         Last: [{info['last_message']['role']}] {info['last_message']['content'][:60]}")

        #5. Telegram webhook — /start command
        print("\n[5] Telegram webhook — /start command...")
        with open(TESTS_DIR / "sample_payloads.json") as f:
            samples = json.load(f)
        resp = await client.post("/api/v1/channels/telegram/webhook", json=samples["command_start"])
        assert resp.status_code == 200
        data = resp.json()
        print(f"    ✅ Response: {data}")
        assert "Command handled" in data.get("detail", ""), "Command should be handled inline"

        #6. Telegram webhook — /help command
        print("\n[6] Telegram webhook — /help command...")
        resp = await client.post("/api/v1/channels/telegram/webhook", json=samples["command_help"])
        assert resp.status_code == 200
        print(f"    ✅ Response: {resp.json()}")

        #7. Simulate endpoint (bypass Telegram)
        print("\n[7] Simulate endpoint — direct orchestration test...")
        resp = await client.post("/debug/simulate", params={"user_id": "usr_sim001", "text": "What do you think about running?"})
        assert resp.status_code == 200
        data = resp.json()
        print(f"    ✅ Event published: {data['event_id']}")

        await asyncio.sleep(1.5)

        #8. Check conversations again (should have more)
        print("\n[8] Final conversation store state...")
        resp = await client.get("/debug/conversations")
        convs = resp.json()
        for conv_id, info in convs.items():
            print(f"    📝 {conv_id}: {info['message_count']} messages")

        #9. No-text message (should be ignored)
        print("\n[9] Telegram webhook — empty text (should be ignored)...")
        resp = await client.post("/api/v1/channels/telegram/webhook", json=samples["no_text_message"])
        assert resp.status_code == 200
        data = resp.json()
        print(f"    ✅ Response: {data}")
        assert "Ignored" in data.get("detail", "")

        #10. No-message update (should be ignored)
        print("\n[10] Telegram webhook — no message field (should be ignored)...")
        resp = await client.post("/api/v1/channels/telegram/webhook", json=samples["no_message_update"])
        assert resp.status_code == 200
        data = resp.json()
        print(f"    ✅ Response: {data}")
        assert "Ignored" in data.get("detail", "")

        #11. Multi-turn conversation
        print("\n[11] Multi-turn conversation (same user, 2 messages)...")
        resp1 = await client.post("/api/v1/channels/telegram/webhook", json=samples["multi_turn_message_1"])
        assert resp1.status_code == 200
        await asyncio.sleep(1.5)

        resp2 = await client.post("/api/v1/channels/telegram/webhook", json=samples["multi_turn_message_2"])
        assert resp2.status_code == 200
        await asyncio.sleep(1.5)

        resp = await client.get("/debug/conversations")
        convs = resp.json()
        alice_conv = convs.get("telegram-chat-123456789", {})
        print(f"    ✅ Alice's conversation now has {alice_conv.get('message_count', 0)} messages")

        #Done
        print("\n" + "=" * 60)
        print("  ✅ All tests passed!")
        print("=" * 60)
        print("\nNote: Telegram delivery calls may have failed for simulated/")
        print("test chat IDs — that's expected. Check logs for full trace.\n")


if __name__ == "__main__":
    asyncio.run(run_tests())
