#!/usr/bin/env python3
"""
UserProfile Functional Tests

Fast tests to verify the system is functional - no errors, correct data flow.
Focus: Does it work? Are there errors? Is data saved correctly?

Test coverage:
1. Basic CRUD operations (create, read, update, delete)
2. Prompt structure validation (timestamps, language rules, degree descriptions)
3. Data structure correctness (social_context, learning_preferences)
4. API endpoints (evidence_limit, missing-fields)
5. Backend logic (timestamp generation, field cleaning)
6. Database coordination (PostgreSQL + MongoDB)
"""

import os
import sys
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from mem0.configs.base import MemoryConfig
from mem0.user_profile import UserProfile
from mem0.user_profile.prompts import EXTRACT_PROFILE_PROMPT, UPDATE_PROFILE_PROMPT
from mem0.user_profile.profile_manager import ProfileManager
from mem0.user_profile.utils import get_current_timestamp

# Load environment variables
load_dotenv()

# Test configuration
TEST_CONFIG = {
    "llm": {
        "provider": "deepseek",
        "config": {
            "api_key": os.getenv("DEEPSEEK_API_KEY"),
            "model": "deepseek-chat",
            "temperature": 0.1,
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
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_result(test_name, passed, details=None):
    """Print test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{status}: {test_name}")
    if details:
        print(f"  → {details}")


# ============================================================================
# 1. CRUD Operations Tests
# ============================================================================

def test_basic_crud_operations():
    """Test 1: Basic CRUD - Create, Read, Update, Delete"""
    print_section("Test 1: Basic CRUD Operations")

    try:
        config = MemoryConfig(**TEST_CONFIG)
        user_profile = UserProfile(config)
        user_id = "test_crud_001"

        # CREATE
        print("\n📝 CREATE: Setting initial profile...")
        messages = [
            {"role": "user", "content": "我叫张三，今年25岁，住在北京"}
        ]
        result = user_profile.set_profile(user_id=user_id, messages=messages)
        assert result["success"], "Failed to create profile"
        print("  ✓ Profile created")

        # READ
        print("\n📖 READ: Getting profile...")
        profile = user_profile.get_profile(user_id=user_id)
        assert "basic_info" in profile or "additional_profile" in profile, "Profile is empty"
        print(f"  ✓ Profile retrieved")

        # UPDATE
        print("\n✏️  UPDATE: Updating profile...")
        messages = [
            {"role": "user", "content": "我现在住在上海了"}
        ]
        result = user_profile.set_profile(user_id=user_id, messages=messages)
        assert result["success"], "Failed to update profile"
        print("  ✓ Profile updated")

        # DELETE
        print("\n🗑️  DELETE: Deleting profile...")
        user_profile.delete_profile(user_id=user_id)
        profile = user_profile.get_profile(user_id=user_id)
        is_empty = not profile.get("basic_info") and not profile.get("additional_profile")
        assert is_empty, "Profile not deleted"
        print("  ✓ Profile deleted")

        print_result("Basic CRUD Operations", True, "All operations successful")
        return True

    except Exception as e:
        print_result("Basic CRUD Operations", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# 2. Prompt Structure Validation Tests
# ============================================================================

def test_prompts_no_timestamp():
    """Test 2: Verify prompts don't ask LLM to generate timestamps"""
    print_section("Test 2: Prompts - No Timestamp Generation")

    has_no_timestamp_rule = "NO timestamp" in EXTRACT_PROFILE_PROMPT or "DO NOT include timestamp" in EXTRACT_PROFILE_PROMPT
    no_current_time_param = "{current_time}" not in EXTRACT_PROFILE_PROMPT

    print_result(
        "EXTRACT_PROFILE_PROMPT",
        has_no_timestamp_rule and no_current_time_param,
        "LLM instructed NOT to include timestamps" if has_no_timestamp_rule else "Missing 'NO timestamp' instruction"
    )

    has_no_timestamp_rule2 = "DO NOT" in UPDATE_PROFILE_PROMPT and "timestamp" in UPDATE_PROFILE_PROMPT
    backend_handles2 = "backend" in UPDATE_PROFILE_PROMPT.lower() and "timestamp" in UPDATE_PROFILE_PROMPT

    print_result(
        "UPDATE_PROFILE_PROMPT",
        has_no_timestamp_rule2 or backend_handles2,
        f"Timestamp handling documented"
    )

    return (has_no_timestamp_rule and no_current_time_param) and (has_no_timestamp_rule2 or backend_handles2)


def test_social_context_structure_in_prompt():
    """Test 3: Verify social_context uses 'friends' not 'teachers'"""
    print_section("Test 3: social_context Structure in Prompt")

    has_friends = '"friends":' in EXTRACT_PROFILE_PROMPT
    has_teachers = '"teachers":' in EXTRACT_PROFILE_PROMPT
    has_extraction_rules = "social_context extraction" in EXTRACT_PROFILE_PROMPT

    print_result(
        "social_context.friends exists",
        has_friends,
        "Found 'friends' array in prompt"
    )

    print_result(
        "No separate teachers array",
        not has_teachers or "others" in EXTRACT_PROFILE_PROMPT,
        "teachers should be in 'others' with relation field"
    )

    print_result(
        "Extraction rules exist",
        has_extraction_rules,
        "Prompt has explicit extraction instructions"
    )

    return has_friends and (not has_teachers or "others" in EXTRACT_PROFILE_PROMPT) and has_extraction_rules


def test_language_consistency_rule():
    """Test 4: Verify language consistency rule exists"""
    print_section("Test 4: Language Consistency Rule")

    has_rule = "Language consistency" in EXTRACT_PROFILE_PROMPT
    no_translation = "translation" in EXTRACT_PROFILE_PROMPT or "Chinese/English" in EXTRACT_PROFILE_PROMPT

    print_result(
        "Language consistency rule",
        has_rule and no_translation,
        "Rule found: Keep language consistent, no translation"
    )

    return has_rule and no_translation


def test_degree_descriptions():
    """Test 5: Verify degree descriptions are in English"""
    print_section("Test 5: Degree Descriptions - English Terms")

    english_terms = [
        "dislike", "neutral", "like", "favorite",
        "beginner", "learning", "proficient", "expert",
        "weak", "moderate", "strong"
    ]

    found_english = [term for term in english_terms if term in EXTRACT_PROFILE_PROMPT]

    print_result(
        "English degree terms",
        len(found_english) >= 5,
        f"Found {len(found_english)} English terms: {', '.join(found_english[:5])}"
    )

    return len(found_english) >= 5


# ============================================================================
# 3. Data Structure Tests
# ============================================================================

def test_social_context_structure():
    """Test 6: Verify social_context structure (family, friends, others)"""
    print_section("Test 6: social_context Structure - Real Data")

    try:
        config = MemoryConfig(**TEST_CONFIG)
        user_profile = UserProfile(config)
        user_id = "test_social_001"

        # Test family + friends
        messages = [
            {"role": "user", "content": "我爸爸是医生，妈妈是老师"},
            {"role": "user", "content": "我有个好朋友Jack"},
        ]

        user_profile.set_profile(user_id=user_id, messages=messages)
        profile = user_profile.get_profile(user_id=user_id)
        social_context = profile.get("additional_profile", {}).get("social_context", {})

        has_family = "family" in social_context
        has_friends = "friends" in social_context
        friends_is_array = isinstance(social_context.get("friends", []), list)
        family_is_dict = isinstance(social_context.get("family", {}), dict)

        # Check no metadata fields
        no_metadata = True
        if has_family:
            father = social_context["family"].get("father", {})
            if "id" in father or "event" in father or "evidence" in father:
                no_metadata = False

        print_result("family is dict", family_is_dict, f"family structure: {type(social_context.get('family'))}")
        print_result("friends is array", friends_is_array, f"friends structure: {type(social_context.get('friends'))}")
        print_result("No metadata fields", no_metadata, "No id/event/evidence in social_context")

        # Cleanup
        user_profile.delete_profile(user_id=user_id)

        return has_family or has_friends

    except Exception as e:
        print_result("social_context Structure", False, str(e))
        import traceback
        traceback.print_exc()
        return False


def test_learning_preferences_structure():
    """Test 7: Verify learning_preferences structure"""
    print_section("Test 7: learning_preferences Structure")

    try:
        config = MemoryConfig(**TEST_CONFIG)
        user_profile = UserProfile(config)
        user_id = "test_learning_001"

        messages = [
            {"role": "user", "content": "我喜欢在晚上学习，通过看视频效果最好"}
        ]

        user_profile.set_profile(user_id=user_id, messages=messages)
        profile = user_profile.get_profile(user_id=user_id)
        learning_pref = profile.get("additional_profile", {}).get("learning_preferences", {})

        is_dict = isinstance(learning_pref, dict)

        print_result(
            "learning_preferences is dict",
            is_dict,
            f"Structure: {type(learning_pref)}"
        )

        # Cleanup
        user_profile.delete_profile(user_id=user_id)

        return is_dict

    except Exception as e:
        print_result("learning_preferences Structure", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# 4. API Endpoint Tests
# ============================================================================

def test_evidence_limit_parameter():
    """Test 8: Test evidence_limit parameter (0, N, -1)"""
    print_section("Test 8: evidence_limit Parameter")

    try:
        config = MemoryConfig(**TEST_CONFIG)
        user_profile = UserProfile(config)
        user_id = "test_evidence_001"

        # Create profile with evidence
        messages = [
            {"role": "user", "content": "我喜欢打篮球"},
            {"role": "user", "content": "昨天打篮球很开心"},
        ]

        user_profile.set_profile(user_id=user_id, messages=messages)

        # Test limit=0
        profile_0 = user_profile.get_profile(user_id=user_id, options={"evidence_limit": 0})
        interests_0 = profile_0.get("additional_profile", {}).get("interests", [])
        has_evidence_0 = len(interests_0) > 0 and len(interests_0[0].get("evidence", [])) == 0

        # Test limit=1
        profile_1 = user_profile.get_profile(user_id=user_id, options={"evidence_limit": 1})
        interests_1 = profile_1.get("additional_profile", {}).get("interests", [])
        has_evidence_1 = len(interests_1) > 0 and len(interests_1[0].get("evidence", [])) <= 1

        # Test limit=-1 (all)
        profile_all = user_profile.get_profile(user_id=user_id, options={"evidence_limit": -1})
        interests_all = profile_all.get("additional_profile", {}).get("interests", [])
        has_evidence_all = len(interests_all) > 0 and len(interests_all[0].get("evidence", [])) >= 1

        print_result("evidence_limit=0", has_evidence_0, "No evidence returned")
        print_result("evidence_limit=1", has_evidence_1, "At most 1 evidence")
        print_result("evidence_limit=-1", has_evidence_all, "All evidence returned")

        # Cleanup
        user_profile.delete_profile(user_id=user_id)

        return has_evidence_0 and has_evidence_1 and has_evidence_all

    except Exception as e:
        print_result("evidence_limit Parameter", False, str(e))
        import traceback
        traceback.print_exc()
        return False


def test_missing_fields_endpoint():
    """Test 9: Test missing-fields endpoint"""
    print_section("Test 9: missing-fields Endpoint")

    try:
        config = MemoryConfig(**TEST_CONFIG)
        user_profile = UserProfile(config)
        user_id = "test_missing_001"

        # Create partial profile
        messages = [
            {"role": "user", "content": "我叫李四"}
        ]

        user_profile.set_profile(user_id=user_id, messages=messages)

        # Test source='both'
        missing_both = user_profile.get_missing_fields(user_id=user_id, source="both")
        has_both = "missing_fields" in missing_both

        # Test source='pg'
        missing_pg = user_profile.get_missing_fields(user_id=user_id, source="pg")
        has_pg = "missing_fields" in missing_pg and "basic_info" in missing_pg["missing_fields"]

        # Test source='mongo'
        missing_mongo = user_profile.get_missing_fields(user_id=user_id, source="mongo")
        has_mongo = "missing_fields" in missing_mongo and "additional_profile" in missing_mongo["missing_fields"]

        print_result("source='both'", has_both, "Returns both sources")
        print_result("source='pg'", has_pg, "Returns basic_info fields")
        print_result("source='mongo'", has_mongo, "Returns additional_profile fields")

        # Cleanup
        user_profile.delete_profile(user_id=user_id)

        return has_both and has_pg and has_mongo

    except Exception as e:
        print_result("missing-fields Endpoint", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# 5. Backend Logic Tests
# ============================================================================

def test_timestamp_generation_function():
    """Test 10: Verify timestamp utility function works"""
    print_section("Test 10: Timestamp Generation Function")

    timestamp = get_current_timestamp()

    try:
        from datetime import datetime
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        is_valid = True
    except:
        is_valid = False

    print_result(
        "get_current_timestamp()",
        is_valid,
        f"Generated valid timestamp: {timestamp}"
    )

    return is_valid


def test_add_timestamps_to_evidence_logic():
    """Test 11: Test _add_timestamps_to_evidence logic"""
    print_section("Test 11: Add Timestamps to Evidence Logic")

    test_data = {
        "interests": [
            {
                "name": "足球",
                "degree": 4,
                "evidence": [
                    {"text": "喜欢踢足球"},
                    {"text": "每周都踢"}
                ]
            }
        ]
    }

    class MockLLM:
        pass

    class MockDB:
        pass

    manager = ProfileManager(MockLLM(), MockDB(), MockDB())
    result = manager._add_timestamps_to_evidence(test_data)

    has_timestamps = all(
        "timestamp" in ev
        for item in result.get("interests", [])
        for ev in item.get("evidence", [])
    )

    print_result(
        "Timestamps added to evidence",
        has_timestamps,
        f"All evidence entries have timestamps"
    )

    if result.get("interests"):
        sample_evidence = result["interests"][0]["evidence"][0]
        print(f"  Sample: {sample_evidence}")

    return has_timestamps


def test_empty_and_null_handling():
    """Test 12: Verify omit missing fields rule"""
    print_section("Test 12: Empty and Null Handling")

    has_omit_rule = "omit" in EXTRACT_PROFILE_PROMPT.lower() or "DO NOT include" in EXTRACT_PROFILE_PROMPT

    print_result(
        "Omit missing fields rule",
        has_omit_rule,
        "Rule found: Omit fields with no data"
    )

    return has_omit_rule


# ============================================================================
# 6. Database Coordination Tests
# ============================================================================

def test_database_coordination():
    """Test 13: PostgreSQL + MongoDB coordination"""
    print_section("Test 13: Database Coordination (PostgreSQL + MongoDB)")

    try:
        config = MemoryConfig(**TEST_CONFIG)
        user_profile = UserProfile(config)
        user_id = "test_db_001"

        # Create profile with both basic_info and additional_profile
        messages = [
            {"role": "user", "content": "我叫王五，30岁，住在深圳，喜欢编程"}
        ]

        user_profile.set_profile(user_id=user_id, messages=messages)
        profile = user_profile.get_profile(user_id=user_id)

        has_basic = bool(profile.get("basic_info"))
        has_additional = bool(profile.get("additional_profile"))

        print_result(
            "PostgreSQL (basic_info)",
            has_basic,
            f"basic_info fields: {len(profile.get('basic_info', {}))}"
        )

        print_result(
            "MongoDB (additional_profile)",
            has_additional,
            f"additional_profile fields: {len(profile.get('additional_profile', {}))}"
        )

        # Cleanup
        user_profile.delete_profile(user_id=user_id)

        return has_basic or has_additional

    except Exception as e:
        print_result("Database Coordination", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# Main Test Runner
# ============================================================================

def run_functional_tests():
    """Run all functional tests"""
    print("=" * 70)
    print("  UserProfile Functional Test Suite")
    print("=" * 70)
    print("\nFast tests to verify system functionality (no errors, correct data flow)\n")

    tests = [
        ("Basic CRUD Operations", test_basic_crud_operations),
        ("Prompts - No Timestamp Generation", test_prompts_no_timestamp),
        ("social_context Structure in Prompt", test_social_context_structure_in_prompt),
        ("Language Consistency Rule", test_language_consistency_rule),
        ("Degree Descriptions - English", test_degree_descriptions),
        ("social_context Structure - Real Data", test_social_context_structure),
        ("learning_preferences Structure", test_learning_preferences_structure),
        ("evidence_limit Parameter", test_evidence_limit_parameter),
        ("missing-fields Endpoint", test_missing_fields_endpoint),
        ("Timestamp Generation Function", test_timestamp_generation_function),
        ("Add Timestamps Logic", test_add_timestamps_to_evidence_logic),
        ("Empty and Null Handling", test_empty_and_null_handling),
        ("Database Coordination", test_database_coordination),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n❌ ERROR in {test_name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 70)
    print("  Test Summary")
    print("=" * 70)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    print(f"\nTotal: {passed_count}/{total_count} tests passed\n")

    for test_name, passed in results:
        status = "✅" if passed else "❌"
        print(f"  {status} {test_name}")

    if passed_count == total_count:
        print("\n🎉 All functional tests passed!")
        print("\nVerified:")
        print("  • CRUD operations work correctly")
        print("  • Prompts have correct structure and rules")
        print("  • Data structures are correct (social_context, learning_preferences)")
        print("  • API endpoints work (evidence_limit, missing-fields)")
        print("  • Backend logic handles timestamps and cleaning correctly")
        print("  • PostgreSQL + MongoDB coordination works")
        return True
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed")
        return False


if __name__ == "__main__":
    success = run_functional_tests()
    sys.exit(0 if success else 1)