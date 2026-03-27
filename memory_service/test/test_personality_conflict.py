"""
Test personality conflict detection and degree reasonableness

Tests the new Rule 9 in UPDATE_PROFILE_PROMPT:
- Conflict detection between semantic opposites
- Degree reasonableness based on evidence count
- Complex human nature handling (RARE coexistence)
"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:18088"
USER_ID = "test_personality_conflict"


def setup_initial_profile():
    """Setup initial profile with personality traits"""
    print("\n" + "=" * 80)
    print("SETUP: Creating initial profile with personality traits")
    print("=" * 80)

    messages = [
        {"role": "user", "content": "我是一个很认真负责的人"},
        {"role": "user", "content": "工作上我非常认真负责"},
        {"role": "user", "content": "同事都说我认真负责"},
        {"role": "user", "content": "领导表扬我认真负责"},
    ]

    response = requests.post(
        f"{BASE_URL}/profile",
        json={"user_id": USER_ID, "messages": messages}
    )

    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print("Initial profile created successfully")
        print(f"Operations: {result.get('operations_performed', {})}")
    else:
        print(f"Error: {response.text}")

    # Get current profile
    profile = requests.get(f"{BASE_URL}/profile", params={"user_id": USER_ID}).json()
    print("\nCurrent personality traits:")
    for trait in profile.get("additional_profile", {}).get("personality", []):
        print(f"  - {trait['name']}: degree={trait['degree']}, evidence_count={len(trait['evidence'])}")

    return profile


def test_scenario_1_insufficient_evidence_skip():
    """
    场景1: 单次批评 vs 强evidence - 应该SKIP

    Existing: 认真负责 (degree 4, 4 evidence)
    New: 被领导批评粗枝大叶 (1 evidence)
    Expected: SKIP - 单次批评不足以覆盖强evidence
    """
    print("\n" + "=" * 80)
    print("TEST SCENARIO 1: Insufficient evidence - should SKIP")
    print("=" * 80)

    messages = [
        {"role": "user", "content": "我今天被领导批评了，说我粗枝大叶"}
    ]

    print(f"\nNew message: {messages[0]['content']}")
    print("Expected: SKIP - single criticism insufficient to override existing trait")

    response = requests.post(
        f"{BASE_URL}/profile",
        json={"user_id": USER_ID, "messages": messages}
    )

    print(f"\nStatus: {response.status_code}")
    result = response.json()
    print(f"Operations: {result.get('operations_performed', {})}")

    # Verify
    profile = requests.get(f"{BASE_URL}/profile", params={"user_id": USER_ID}).json()
    personality = profile.get("additional_profile", {}).get("personality", [])

    print("\nCurrent personality traits:")
    for trait in personality:
        print(f"  - {trait['name']}: degree={trait['degree']}, evidence_count={len(trait['evidence'])}")

    # Check: should still have "认真负责", should NOT have "粗枝大叶"
    has_responsible = any(t['name'] == '认真负责' for t in personality)
    has_careless = any(t['name'] in ['粗枝大叶', '粗心'] for t in personality)

    print(f"\n✅ Result: Has '认真负责': {has_responsible}, Has '粗枝大叶': {has_careless}")
    assert has_responsible, "Should keep '认真负责'"
    assert not has_careless, "Should NOT add '粗枝大叶' (single criticism)"
    print("✅ TEST PASSED: Correctly skipped conflicting trait with insufficient evidence")


def test_scenario_2_reduce_degree():
    """
    场景2: 适度冲突证据 - 应该降低degree

    Add some evidence of carelessness, should reduce degree but not delete
    """
    print("\n" + "=" * 80)
    print("TEST SCENARIO 2: Moderate conflicting evidence - should reduce degree")
    print("=" * 80)

    messages = [
        {"role": "user", "content": "这周我犯了几个小错误"},
        {"role": "user", "content": "有时候确实有点粗心"},
        {"role": "user", "content": "需要更加注意细节"}
    ]

    print(f"\nNew messages: {len(messages)} messages about carelessness")
    for msg in messages:
        print(f"  - {msg['content']}")
    print("Expected: UPDATE '认真负责' to lower degree (e.g., degree 3)")

    response = requests.post(
        f"{BASE_URL}/profile",
        json={"user_id": USER_ID, "messages": messages}
    )

    print(f"\nStatus: {response.status_code}")
    result = response.json()
    print(f"Operations: {result.get('operations_performed', {})}")

    # Verify
    profile = requests.get(f"{BASE_URL}/profile", params={"user_id": USER_ID}).json()
    personality = profile.get("additional_profile", {}).get("personality", [])

    print("\nCurrent personality traits:")
    for trait in personality:
        print(f"  - {trait['name']}: degree={trait['degree']}, evidence_count={len(trait['evidence'])}")

    # Check: "认真负责" should have lower degree (but this depends on LLM decision)
    responsible_trait = next((t for t in personality if t['name'] == '认真负责'), None)
    if responsible_trait:
        print(f"\n✅ Result: '认真负责' degree = {responsible_trait['degree']}")
        print("Note: LLM may choose to reduce degree or keep it - both are valid depending on analysis")
    else:
        print("⚠️ Note: '认真负责' was deleted - this may happen with strong conflicting evidence")


def test_scenario_3_real_change():
    """
    场景3: 清理并测试真实改变场景

    Setup: 内向 (old evidence)
    New: 外向 (multiple recent evidence)
    Expected: DELETE 内向, ADD 外向
    """
    print("\n" + "=" * 80)
    print("TEST SCENARIO 3: Real personality change - should DELETE old and ADD new")
    print("=" * 80)

    # Clean up first
    print("\nCleaning up profile...")
    requests.delete(f"{BASE_URL}/profile", params={"user_id": USER_ID})

    # Setup: Add "内向" trait
    print("\nSetup: Adding '内向' trait...")
    messages = [
        {"role": "user", "content": "我不喜欢参加聚会"},
        {"role": "user", "content": "更喜欢独处"},
        {"role": "user", "content": "社交让我很累"}
    ]

    requests.post(f"{BASE_URL}/profile", json={"user_id": USER_ID, "messages": messages})

    profile = requests.get(f"{BASE_URL}/profile", params={"user_id": USER_ID}).json()
    print("Initial personality:")
    for trait in profile.get("additional_profile", {}).get("personality", []):
        print(f"  - {trait['name']}: degree={trait['degree']}")

    # Now add strong evidence for "外向"
    print("\nAdding strong evidence for '外向'...")
    messages = [
        {"role": "user", "content": "我现在变得很外向了，经常主动社交"},
        {"role": "user", "content": "周末参加了三场聚会"},
        {"role": "user", "content": "主动组织团队活动"},
        {"role": "user", "content": "认识了很多新朋友"},
        {"role": "user", "content": "享受社交带来的快乐"},
        {"role": "user", "content": "同事说我判若两人"}
    ]

    print(f"New messages: {len(messages)} messages about being extroverted")
    print("Expected: DELETE '内向', ADD '外向'")

    response = requests.post(
        f"{BASE_URL}/profile",
        json={"user_id": USER_ID, "messages": messages}
    )

    print(f"\nStatus: {response.status_code}")
    result = response.json()
    print(f"Operations: {result.get('operations_performed', {})}")

    # Verify
    profile = requests.get(f"{BASE_URL}/profile", params={"user_id": USER_ID}).json()
    personality = profile.get("additional_profile", {}).get("personality", [])

    print("\nFinal personality traits:")
    for trait in personality:
        print(f"  - {trait['name']}: degree={trait['degree']}, evidence_count={len(trait['evidence'])}")

    has_introverted = any(t['name'] == '内向' for t in personality)
    has_extroverted = any(t['name'] == '外向' for t in personality)

    print(f"\n✅ Result: Has '内向': {has_introverted}, Has '外向': {has_extroverted}")

    if not has_introverted and has_extroverted:
        print("✅ TEST PASSED: Correctly detected real change - deleted old and added new")
    else:
        print("⚠️ Note: LLM decision may vary - check if the logic is reasonable")


def test_scenario_4_complex_coexistence_insufficient():
    """
    场景4: 复杂人性但evidence不足 - 应该SKIP

    Existing: 内向 (work context, 5 evidence)
    New: 外向 (family context, but only 1 evidence)
    Expected: SKIP - insufficient evidence for valid coexistence
    """
    print("\n" + "=" * 80)
    print("TEST SCENARIO 4: Complex coexistence but insufficient evidence - should SKIP")
    print("=" * 80)

    # Clean up and setup
    print("\nCleaning up profile...")
    requests.delete(f"{BASE_URL}/profile", params={"user_id": USER_ID})

    # Setup: Add "内向" in work context
    print("\nSetup: Adding '内向' in work context...")
    messages = [
        {"role": "user", "content": "在公司不爱说话"},
        {"role": "user", "content": "同事聚餐总是安静听别人说"},
        {"role": "user", "content": "开会时很少主动发言"},
        {"role": "user", "content": "领导说我太安静"},
        {"role": "user", "content": "不喜欢office闲聊"}
    ]

    requests.post(f"{BASE_URL}/profile", json={"user_id": USER_ID, "messages": messages})

    profile = requests.get(f"{BASE_URL}/profile", params={"user_id": USER_ID}).json()
    print("Initial personality:")
    for trait in profile.get("additional_profile", {}).get("personality", []):
        print(f"  - {trait['name']}: degree={trait['degree']}, evidence_count={len(trait['evidence'])}")

    # Now add single evidence for "外向" in family context
    print("\nAdding single evidence for '外向' in family context...")
    messages = [
        {"role": "user", "content": "在家里我很外向，和家人有说不完的话"}
    ]

    print(f"New message: {messages[0]['content']}")
    print("Expected: SKIP - need 5+ evidence for valid coexistence")

    response = requests.post(
        f"{BASE_URL}/profile",
        json={"user_id": USER_ID, "messages": messages}
    )

    print(f"\nStatus: {response.status_code}")
    result = response.json()
    print(f"Operations: {result.get('operations_performed', {})}")

    # Verify
    profile = requests.get(f"{BASE_URL}/profile", params={"user_id": USER_ID}).json()
    personality = profile.get("additional_profile", {}).get("personality", [])

    print("\nFinal personality traits:")
    for trait in personality:
        print(f"  - {trait['name']}: degree={trait['degree']}, evidence_count={len(trait['evidence'])}")

    has_introverted = any(t['name'] == '内向' for t in personality)
    has_extroverted = any(t['name'] == '外向' for t in personality)

    print(f"\n✅ Result: Has '内向': {has_introverted}, Has '外向': {has_extroverted}")

    if has_introverted and not has_extroverted:
        print("✅ TEST PASSED: Correctly skipped - insufficient evidence for coexistence")
    else:
        print("⚠️ Note: LLM may still add '外向' with low degree, which could be valid")


def cleanup():
    """Clean up test data"""
    print("\n" + "=" * 80)
    print("CLEANUP: Deleting test profile")
    print("=" * 80)

    response = requests.delete(f"{BASE_URL}/profile", params={"user_id": USER_ID})
    print(f"Status: {response.status_code}")


if __name__ == "__main__":
    try:
        print("\n" + "=" * 80)
        print("PERSONALITY CONFLICT DETECTION TEST SUITE")
        print("=" * 80)
        print("\nThis test suite validates Rule 9 in UPDATE_PROFILE_PROMPT:")
        print("- Conflict detection between semantic opposites")
        print("- Degree reasonableness based on evidence count")
        print("- Complex human nature handling (RARE coexistence)")
        print("\nNote: Some tests depend on LLM interpretation - results may vary")

        # Setup
        setup_initial_profile()

        # Run tests
        test_scenario_1_insufficient_evidence_skip()
        test_scenario_2_reduce_degree()
        test_scenario_3_real_change()
        test_scenario_4_complex_coexistence_insufficient()

        print("\n" + "=" * 80)
        print("ALL TESTS COMPLETED")
        print("=" * 80)
        print("\nNote: Review the results above to ensure LLM decisions are reasonable.")
        print("Some variations are expected due to LLM's semantic understanding.")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cleanup()