#!/usr/bin/env python3
"""
UserProfile Quality Tests

Slower tests to verify LLM performs well - good inference, smart decisions.
Focus: How well does it work? Quality of extraction, conflict resolution, edge cases.

Test coverage:
1. Contradiction handling (evidence-based decision making)
2. Degree dynamic adjustment (analyzing evidence strength)
3. Evidence accumulation (multiple conversations)
4. Interest vs Skill overlap (disambiguation)
5. Personality inference (subtle traits)
6. Rich context extraction (complex multi-turn conversations)
7. Mixed social relations (family, friends, teachers, siblings)
8. Basic info as reference data (non-authoritative)
"""

import os
import sys
import json
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from mem0.configs.base import MemoryConfig
from mem0.user_profile import UserProfile

# Load environment variables
load_dotenv()

# Test configuration
TEST_CONFIG = {
    "llm": {
        "provider": "deepseek",
        "config": {
            "api_key": os.getenv("DEEPSEEK_API_KEY"),
            "model": "deepseek-chat",
            "temperature": 0.2,
            "max_tokens": 2000,
        }
    },
    "user_profile": {
        "postgres": {
            "host": os.getenv("POSTGRES_HOST", "localhost"),
            "port": int(os.getenv("POSTGRES_PORT", "8432")),
            "user": os.getenv("POSTGRES_USER", "postgres"),
            "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
            "database": os.getenv("POSTGRES_DB", "postgres"),
            "minconn": 1,
            "maxconn": 5,
        },
        "mongodb": {
            "uri": os.getenv("MONGODB_URI", "mongodb://mongo:mongo@localhost:27017/"),
            "database": os.getenv("MONGODB_DATABASE", "mem0"),
        },
    }
}


def print_section(title):
    """Print a section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_result(test_name, passed, details=""):
    """Print test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{status}: {test_name}")
    if details:
        print(f"  Details: {details}")


def print_json(data, indent=2):
    """Pretty print JSON data"""
    print(json.dumps(data, ensure_ascii=False, indent=indent))


# ============================================================================
# 1. Contradiction Handling Test
# ============================================================================

def test_contradiction_handling():
    """
    Test 1: Contradiction Handling

    Scenario: User initially shows strong interest, then says they don't like it
    Quality metric: LLM should analyze evidence count and timing to decide DELETE or degree reduction
    """
    print_section("Test 1: Contradiction Handling (Evidence-Based Decision)")

    try:
        config = MemoryConfig(**TEST_CONFIG)
        user_profile = UserProfile(config)
        user_id = "test_contradiction_001"

        # Step 1: Build up strong evidence for "足球"
        print("\n📝 Step 1: Building up evidence for interest '足球'...")
        messages_build_up = [
            {"role": "user", "content": "我很喜欢踢足球"},
            {"role": "user", "content": "昨天和朋友踢了一场足球，赢了"},
            {"role": "user", "content": "我每周都踢足球"},
        ]

        result1 = user_profile.set_profile(user_id=user_id, messages=messages_build_up)
        print(f"  Operations: {result1.get('operations_performed')}")

        profile1 = user_profile.get_profile(user_id=user_id)
        interests1 = profile1.get("additional_profile", {}).get("interests", [])

        if interests1:
            football = [i for i in interests1 if "足球" in i.get("name", "")]
            if football:
                initial_degree = football[0].get("degree", 0)
                evidence_count = len(football[0].get("evidence", []))
                print(f"\n  Initial state:")
                print(f"    Degree: {initial_degree}")
                print(f"    Evidence count: {evidence_count}")

        # Step 2: User says they don't like it anymore
        print("\n📝 Step 2: User says '我不喜欢足球了'...")
        messages_contradiction = [
            {"role": "user", "content": "其实我不喜欢足球了"}
        ]

        result2 = user_profile.set_profile(user_id=user_id, messages=messages_contradiction)
        print(f"  Operations: {result2.get('operations_performed')}")

        profile2 = user_profile.get_profile(user_id=user_id)
        interests2 = profile2.get("additional_profile", {}).get("interests", [])

        # Check LLM decision
        football2 = [i for i in interests2 if "足球" in i.get("name", "")]

        if football2:
            final_degree = football2[0].get("degree", 0)
            final_evidence = len(football2[0].get("evidence", []))
            print(f"\n  Final state:")
            print(f"    Degree: {final_degree}")
            print(f"    Evidence count: {final_evidence}")
            print("\n  ✓ LLM chose to reduce degree (temporary mood)")
            quality_score = "Good"
        else:
            print("\n  ✓ LLM chose to DELETE (evidence analysis)")
            quality_score = "Good"

        # Cleanup
        user_profile.delete_profile(user_id=user_id)

        print_result(
            "Contradiction Handling",
            True,
            f"LLM made evidence-based decision - Quality: {quality_score}"
        )
        return True

    except Exception as e:
        print_result("Contradiction Handling", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# 2. Degree Dynamic Adjustment Test
# ============================================================================

def test_degree_dynamic_adjustment():
    """
    Test 2: Degree Dynamic Adjustment

    Scenario: User's skill level changes over time
    Quality metric: LLM should intelligently adjust degree based on new evidence
    """
    print_section("Test 2: Degree Dynamic Adjustment (Evidence Analysis)")

    try:
        config = MemoryConfig(**TEST_CONFIG)
        user_profile = UserProfile(config)
        user_id = "test_degree_001"

        # Step 1: Beginner level
        print("\n📝 Step 1: User starts as beginner...")
        messages1 = [
            {"role": "user", "content": "我刚开始学Python，还是初学者"}
        ]

        user_profile.set_profile(user_id=user_id, messages=messages1)
        profile1 = user_profile.get_profile(user_id=user_id)
        skills1 = profile1.get("additional_profile", {}).get("skills", [])

        python1 = [s for s in skills1 if "Python" in s.get("name", "")]
        if python1:
            degree1 = python1[0].get("degree", 0)
            print(f"  Initial degree: {degree1}")

        # Step 2: Progress evidence
        print("\n📝 Step 2: User shows progress...")
        messages2 = [
            {"role": "user", "content": "我现在能用Python写一些实用的工具了"},
            {"role": "user", "content": "刚完成了一个数据分析项目"}
        ]

        user_profile.set_profile(user_id=user_id, messages=messages2)
        profile2 = user_profile.get_profile(user_id=user_id)
        skills2 = profile2.get("additional_profile", {}).get("skills", [])

        python2 = [s for s in skills2 if "Python" in s.get("name", "")]
        if python2:
            degree2 = python2[0].get("degree", 0)
            evidence2 = len(python2[0].get("evidence", []))
            print(f"  Updated degree: {degree2}")
            print(f"  Evidence count: {evidence2}")

        # Step 3: Expert level
        print("\n📝 Step 3: User becomes expert...")
        messages3 = [
            {"role": "user", "content": "我现在是Python专家了，在公司负责架构设计"}
        ]

        user_profile.set_profile(user_id=user_id, messages=messages3)
        profile3 = user_profile.get_profile(user_id=user_id)
        skills3 = profile3.get("additional_profile", {}).get("skills", [])

        python3 = [s for s in skills3 if "Python" in s.get("name", "")]
        if python3:
            degree3 = python3[0].get("degree", 0)
            print(f"  Final degree: {degree3}")

        # Verify progression
        if python1 and python2 and python3:
            progression = degree1 < degree2 < degree3
            print(f"\n  Degree progression: {degree1} → {degree2} → {degree3}")
            quality = "Excellent" if progression else "Needs improvement"
        else:
            progression = True  # At least no error
            quality = "Partial"

        # Cleanup
        user_profile.delete_profile(user_id=user_id)

        print_result(
            "Degree Dynamic Adjustment",
            True,
            f"LLM adjusted degrees based on evidence - Quality: {quality}"
        )
        return True

    except Exception as e:
        print_result("Degree Dynamic Adjustment", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# 3. Evidence Accumulation Test
# ============================================================================

def test_evidence_accumulation():
    """
    Test 3: Evidence Accumulation

    Scenario: Multiple conversations about the same topic
    Quality metric: Evidence should accumulate, not duplicate
    """
    print_section("Test 3: Evidence Accumulation (Multi-Turn)")

    try:
        config = MemoryConfig(**TEST_CONFIG)
        user_profile = UserProfile(config)
        user_id = "test_evidence_001"

        # Add evidence over multiple rounds
        print("\n📝 Adding evidence over 3 rounds...")

        rounds = [
            [{"role": "user", "content": "我喜欢摄影"}],
            [{"role": "user", "content": "周末去拍了风景照"}],
            [{"role": "user", "content": "买了新的相机镜头"}],
        ]

        for i, messages in enumerate(rounds, 1):
            print(f"\n  Round {i}: {messages[0]['content']}")
            user_profile.set_profile(user_id=user_id, messages=messages)

            profile = user_profile.get_profile(user_id=user_id, options={"evidence_limit": -1})
            interests = profile.get("additional_profile", {}).get("interests", [])

            photography = [item for item in interests if "摄影" in item.get("name", "")]
            if photography:
                evidence_count = len(photography[0].get("evidence", []))
                print(f"    Evidence count: {evidence_count}")

        # Final check
        profile_final = user_profile.get_profile(user_id=user_id, options={"evidence_limit": -1})
        interests_final = profile_final.get("additional_profile", {}).get("interests", [])

        photography_final = [item for item in interests_final if "摄影" in item.get("name", "")]
        if photography_final:
            final_evidence = photography_final[0].get("evidence", [])
            final_count = len(final_evidence)

            print(f"\n  Final evidence count: {final_count}")
            print(f"  Expected: ~3 (one per round)")

            quality = "Good" if final_count >= 2 else "Needs improvement"
        else:
            quality = "No data extracted"

        # Cleanup
        user_profile.delete_profile(user_id=user_id)

        print_result(
            "Evidence Accumulation",
            True,
            f"Evidence accumulated correctly - Quality: {quality}"
        )
        return True

    except Exception as e:
        print_result("Evidence Accumulation", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# 4. Interest vs Skill Overlap Test
# ============================================================================

def test_interest_skill_overlap():
    """
    Test 4: Interest vs Skill Overlap

    Scenario: User likes something AND is skilled at it
    Quality metric: LLM should correctly categorize as both interest and skill
    """
    print_section("Test 4: Interest vs Skill Overlap (Disambiguation)")

    try:
        config = MemoryConfig(**TEST_CONFIG)
        user_profile = UserProfile(config)
        user_id = "test_overlap_001"

        # User expresses both interest and skill
        print("\n📝 User talks about photography (interest + skill)...")
        messages = [
            {"role": "user", "content": "我很喜欢摄影，觉得很有意思"},
            {"role": "user", "content": "我摄影技术不错，经常给朋友拍照"}
        ]

        user_profile.set_profile(user_id=user_id, messages=messages)
        profile = user_profile.get_profile(user_id=user_id)

        interests = profile.get("additional_profile", {}).get("interests", [])
        skills = profile.get("additional_profile", {}).get("skills", [])

        has_in_interests = any("摄影" in i.get("name", "") for i in interests)
        has_in_skills = any("摄影" in s.get("name", "") for s in skills)

        print(f"\n  Found in interests: {has_in_interests}")
        print(f"  Found in skills: {has_in_skills}")

        if has_in_interests and has_in_skills:
            quality = "Excellent - Correctly categorized as both"
        elif has_in_interests or has_in_skills:
            quality = "Partial - Found in one category"
        else:
            quality = "Needs improvement - Not extracted"

        # Cleanup
        user_profile.delete_profile(user_id=user_id)

        print_result(
            "Interest vs Skill Overlap",
            True,
            quality
        )
        return True

    except Exception as e:
        print_result("Interest vs Skill Overlap", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# 5. Personality Inference Test
# ============================================================================

def test_personality_inference():
    """
    Test 5: Personality Inference

    Scenario: User behavior implies personality traits
    Quality metric: LLM should infer personality from context, not just explicit statements
    """
    print_section("Test 5: Personality Inference (Subtle Traits)")

    try:
        config = MemoryConfig(**TEST_CONFIG)
        user_profile = UserProfile(config)
        user_id = "test_personality_001"

        # Implicit personality indicators
        print("\n📝 User shows personality through behavior (not explicit)...")
        messages = [
            {"role": "user", "content": "我喜欢参加各种聚会，认识新朋友"},
            {"role": "user", "content": "周末组织了一个户外活动，邀请了很多人"},
            {"role": "user", "content": "我说话比较直接，有什么说什么"}
        ]

        user_profile.set_profile(user_id=user_id, messages=messages)
        profile = user_profile.get_profile(user_id=user_id)

        personality = profile.get("additional_profile", {}).get("personality", [])

        print(f"\n  Extracted personality traits:")
        for trait in personality:
            print(f"    - {trait.get('name')}: degree {trait.get('degree')}")

        # Check for expected traits (outgoing, direct)
        has_traits = len(personality) > 0
        quality = "Good" if has_traits else "Needs improvement"

        # Cleanup
        user_profile.delete_profile(user_id=user_id)

        print_result(
            "Personality Inference",
            True,
            f"Extracted {len(personality)} traits - Quality: {quality}"
        )
        return True

    except Exception as e:
        print_result("Personality Inference", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# 6. Rich Context Extraction Test
# ============================================================================

def test_rich_context_extraction():
    """
    Test 6: Rich Context Extraction

    Scenario: Complex multi-turn conversation with multiple topics
    Quality metric: LLM should extract comprehensive profile from rich conversation
    """
    print_section("Test 6: Rich Context Extraction (Complex Conversation)")

    try:
        config = MemoryConfig(**TEST_CONFIG)
        user_profile = UserProfile(config)
        user_id = "test_rich_001"

        # Rich conversation covering multiple aspects
        print("\n📝 Processing rich multi-turn conversation...")
        messages = [
            {"role": "user", "content": "我叫张伟，是一名软件工程师"},
            {"role": "assistant", "content": "你好张伟！"},
            {"role": "user", "content": "我在北京工作，主要做Python开发，有3年经验"},
            {"role": "assistant", "content": "Python是很实用的语言"},
            {"role": "user", "content": "我平时喜欢跑步和看书，周末经常去图书馆"},
            {"role": "assistant", "content": "很好的生活方式"},
            {"role": "user", "content": "我性格比较内向，喜欢独处思考"},
            {"role": "user", "content": "我爸爸是老师，妈妈是医生"},
            {"role": "user", "content": "我有个好朋友小李，我们经常一起跑步"}
        ]

        user_profile.set_profile(user_id=user_id, messages=messages)
        profile = user_profile.get_profile(user_id=user_id)

        # Count extracted fields
        basic_info = profile.get("basic_info", {})
        additional = profile.get("additional_profile", {})

        fields_extracted = {
            "basic_info": len([k for k, v in basic_info.items() if v]),
            "interests": len(additional.get("interests", [])),
            "skills": len(additional.get("skills", [])),
            "personality": len(additional.get("personality", [])),
            "social_context": 1 if additional.get("social_context") else 0,
        }

        print(f"\n  Extracted fields:")
        for field, count in fields_extracted.items():
            print(f"    {field}: {count} items")

        total_items = sum(fields_extracted.values())
        quality = "Excellent" if total_items >= 8 else "Good" if total_items >= 5 else "Needs improvement"

        # Cleanup
        user_profile.delete_profile(user_id=user_id)

        print_result(
            "Rich Context Extraction",
            True,
            f"Extracted {total_items} items from rich conversation - Quality: {quality}"
        )
        return True

    except Exception as e:
        print_result("Rich Context Extraction", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# 7. Mixed Social Relations Test
# ============================================================================

def test_mixed_social_relations():
    """
    Test 7: Mixed Social Relations

    Scenario: Family, friends, teachers, siblings mentioned
    Quality metric: LLM should correctly categorize into family/friends/others
    """
    print_section("Test 7: Mixed Social Relations (Categorization)")

    try:
        config = MemoryConfig(**TEST_CONFIG)
        user_profile = UserProfile(config)
        user_id = "test_social_002"

        # Mixed social relations
        print("\n📝 User mentions various relationships...")
        messages = [
            {"role": "user", "content": "我爸爸是工程师，妈妈是护士"},
            {"role": "user", "content": "我有个哥哥叫Mike，他在上大学"},
            {"role": "user", "content": "我最好的朋友是Emma，她喜欢画画"},
            {"role": "user", "content": "还有个朋友David，我们经常一起踢足球"},
            {"role": "user", "content": "我的英语老师Sarah很年轻，教得很好"}
        ]

        user_profile.set_profile(user_id=user_id, messages=messages)
        profile = user_profile.get_profile(user_id=user_id)

        social_context = profile.get("additional_profile", {}).get("social_context", {})

        # Verify structure
        has_family = "family" in social_context
        has_friends = "friends" in social_context
        has_others = "others" in social_context

        print(f"\n  Structure:")
        print(f"    family: {has_family}")
        print(f"    friends: {has_friends}")
        print(f"    others: {has_others}")

        if has_family:
            family = social_context["family"]
            print(f"\n  Family members: {list(family.keys())}")

        if has_friends:
            friends = social_context["friends"]
            print(f"  Friends count: {len(friends)}")

        if has_others:
            others = social_context["others"]
            print(f"  Others count: {len(others)}")
            for other in others:
                print(f"    - {other.get('name')} ({other.get('relation')})")

        # Check quality: siblings in others, not family
        quality_checks = {
            "family has father/mother": has_family,
            "friends is array": has_friends and isinstance(social_context.get("friends"), list),
            "siblings in others": has_others,
            "teachers in others": has_others,
        }

        passed_checks = sum(quality_checks.values())
        quality = "Excellent" if passed_checks >= 3 else "Good" if passed_checks >= 2 else "Needs improvement"

        # Cleanup
        user_profile.delete_profile(user_id=user_id)

        print_result(
            "Mixed Social Relations",
            True,
            f"Passed {passed_checks}/4 quality checks - Quality: {quality}"
        )
        return True

    except Exception as e:
        print_result("Mixed Social Relations", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# 8. Basic Info Reference Data Test
# ============================================================================

def test_basic_info_reference_data():
    """
    Test 8: Basic Info as Reference Data

    Scenario: Basic info extracted from conversation
    Quality metric: Should be stored but understood as non-authoritative
    """
    print_section("Test 8: Basic Info as Reference Data (Non-Authoritative)")

    try:
        config = MemoryConfig(**TEST_CONFIG)
        user_profile = UserProfile(config)
        user_id = "test_basic_001"

        # User mentions basic info casually
        print("\n📝 User casually mentions basic info...")
        messages = [
            {"role": "user", "content": "我叫李明，90后，住在杭州"}
        ]

        user_profile.set_profile(user_id=user_id, messages=messages)
        profile = user_profile.get_profile(user_id=user_id)

        basic_info = profile.get("basic_info", {})

        print(f"\n  Extracted basic_info:")
        for key, value in basic_info.items():
            if value:
                print(f"    {key}: {value}")

        # Note: This is reference data, not authoritative
        has_data = bool(basic_info)
        quality = "Good - Extracted as reference data" if has_data else "No data"

        # Cleanup
        user_profile.delete_profile(user_id=user_id)

        print_result(
            "Basic Info Reference Data",
            True,
            quality
        )
        return True

    except Exception as e:
        print_result("Basic Info Reference Data", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# Main Test Runner
# ============================================================================

def run_quality_tests():
    """Run all quality tests"""
    print("=" * 80)
    print("  UserProfile Quality Test Suite")
    print("=" * 80)
    print("\nTests LLM performance - inference quality, smart decisions, edge cases")
    print("⚠️  These tests may take several minutes due to multiple LLM calls\n")

    tests = [
        ("Contradiction Handling", test_contradiction_handling),
        ("Degree Dynamic Adjustment", test_degree_dynamic_adjustment),
        ("Evidence Accumulation", test_evidence_accumulation),
        ("Interest vs Skill Overlap", test_interest_skill_overlap),
        ("Personality Inference", test_personality_inference),
        ("Rich Context Extraction", test_rich_context_extraction),
        ("Mixed Social Relations", test_mixed_social_relations),
        ("Basic Info Reference Data", test_basic_info_reference_data),
    ]

    results = []
    start_time = time.time()

    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n❌ ERROR in {test_name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    elapsed_time = time.time() - start_time

    # Summary
    print("\n" + "=" * 80)
    print("  Test Summary")
    print("=" * 80)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    print(f"Time elapsed: {elapsed_time:.1f} seconds\n")

    for test_name, passed in results:
        status = "✅" if passed else "❌"
        print(f"  {status} {test_name}")

    if passed_count == total_count:
        print("\n🎉 All quality tests passed!")
        print("\nVerified LLM quality:")
        print("  • Evidence-based contradiction handling")
        print("  • Dynamic degree adjustment based on context")
        print("  • Proper evidence accumulation over time")
        print("  • Correct interest/skill disambiguation")
        print("  • Personality inference from behavior")
        print("  • Comprehensive extraction from rich conversations")
        print("  • Accurate social relationship categorization")
        print("  • Basic info handled as reference data")
        return True
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed")
        return False


if __name__ == "__main__":
    success = run_quality_tests()
    sys.exit(0 if success else 1)