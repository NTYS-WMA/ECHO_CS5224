"""
Integration tests for MainService cold start feature

Tests the complete cold start flow:
1. fetch_user_summary() HTTP client (stub until MainService implements the endpoint)
2. UserProfile._convert_mainservice_data() data conversion
3. UserProfile.get_profile() cold start integration

Configuration (via environment variables):
- USE_REAL_MAINSERVICE: Set to '1' to test against real MainService (default: mock)
- USE_REAL_POSTGRES: Set to '1' to test against real PostgreSQL (default: mock)
- USE_REAL_MONGODB: Set to '1' to test against real MongoDB (default: mock)

Examples:
    # Use all mocks (default, fast)
    python -m pytest test/test_mainservice_integration.py -v

    # Test real MainService only
    USE_REAL_MAINSERVICE=1 python -m pytest test/test_mainservice_integration.py -v

    # Test all real services
    USE_REAL_MAINSERVICE=1 USE_REAL_POSTGRES=1 USE_REAL_MONGODB=1 python -m pytest test/test_mainservice_integration.py -v
"""

import os
import unittest
from unittest.mock import Mock, patch
from datetime import datetime

from mem0.user_profile.mainservice_client import fetch_user_summary

# ============================================================================
# Test Configuration (set via environment variables)
# ============================================================================

USE_REAL_MAINSERVICE = os.getenv("USE_REAL_MAINSERVICE", "0") == "1"
USE_REAL_POSTGRES = os.getenv("USE_REAL_POSTGRES", "0") == "1"
USE_REAL_MONGODB = os.getenv("USE_REAL_MONGODB", "0") == "1"

MAINSERVICE_BASE_URL = os.getenv("MAINSERVICE_BASE_URL", "http://localhost:8080")
MAINSERVICE_TEST_USER_ID = os.getenv("MAINSERVICE_TEST_USER_ID", "user_12345")

if any([USE_REAL_MAINSERVICE, USE_REAL_POSTGRES, USE_REAL_MONGODB]):
    print(f"\n{'='*70}")
    print("Test Configuration:")
    print(f"  USE_REAL_MAINSERVICE: {USE_REAL_MAINSERVICE} (URL: {MAINSERVICE_BASE_URL if USE_REAL_MAINSERVICE else 'N/A'})")
    print(f"  USE_REAL_POSTGRES:    {USE_REAL_POSTGRES}")
    print(f"  USE_REAL_MONGODB:     {USE_REAL_MONGODB}")
    print(f"{'='*70}\n")


class TestMainServiceClient(unittest.TestCase):
    """Test MainService HTTP client"""

    def setUp(self):
        if USE_REAL_MAINSERVICE:
            self.skipTest("Using real MainService, skip mock tests")
        self.base_url = "http://localhost:8080"
        self.user_id = "user_12345"

    def test_fetch_returns_none_stub(self):
        """Stub always returns None until MainService implements the endpoint"""
        result = fetch_user_summary(self.user_id, self.base_url)
        self.assertIsNone(result)

    def test_fetch_missing_params(self):
        """Test with missing required parameters"""
        result = fetch_user_summary("", self.base_url)
        self.assertIsNone(result)

        result = fetch_user_summary(self.user_id, "")
        self.assertIsNone(result)


class TestDataConversion(unittest.TestCase):
    """Test MainService data to profile format conversion"""

    def setUp(self):
        """Create UserProfile instance for testing conversion logic"""
        from mem0.user_profile.main import UserProfile
        from mem0.configs.base import MemoryConfig

        if USE_REAL_POSTGRES and USE_REAL_MONGODB:
            config = MemoryConfig()
            self.user_profile = UserProfile(config)
        else:
            with patch('mem0.user_profile.main.PostgresManager'), \
                 patch('mem0.user_profile.main.MongoDBManager'), \
                 patch('mem0.user_profile.main.LlmFactory'):
                config = MemoryConfig()
                self.user_profile = UserProfile(config)

    def test_convert_full_data(self):
        """Test conversion with complete data"""
        user_info = {
            "name": "Alice",
            "gender": "female",
            "occupation": "software engineer",
            "company": "Google",
            "education_level": "master",
            "university": "NUS",
            "major": "Computer Science",
            "personality_traits": "curious,diligent,outgoing",
            "interests": "hiking,photography,reading"
        }

        basic_info, additional_profile = self.user_profile._convert_mainservice_data(user_info)

        # Check basic_info
        self.assertEqual(basic_info["name"], "Alice")
        self.assertEqual(basic_info["gender"], "female")
        self.assertEqual(basic_info["occupation"], "software engineer")
        self.assertEqual(basic_info["company"], "Google")
        self.assertEqual(basic_info["education_level"], "master")
        self.assertEqual(basic_info["university"], "NUS")
        self.assertEqual(basic_info["major"], "Computer Science")

        # Check additional_profile
        self.assertIn("personality", additional_profile)
        self.assertEqual(len(additional_profile["personality"]), 3)
        self.assertEqual(additional_profile["personality"][0]["name"], "curious")
        self.assertEqual(additional_profile["personality"][0]["degree"], 3)
        self.assertEqual(
            additional_profile["personality"][0]["evidence"][0]["text"],
            "Initial profile from user registration"
        )

        self.assertIn("interests", additional_profile)
        self.assertEqual(len(additional_profile["interests"]), 3)
        self.assertEqual(additional_profile["interests"][0]["name"], "hiking")
        self.assertEqual(additional_profile["interests"][0]["degree"], 3)

    def test_convert_partial_data(self):
        """Test conversion with only some fields present"""
        user_info = {
            "name": "Bob",
            "occupation": "teacher",
        }

        basic_info, additional_profile = self.user_profile._convert_mainservice_data(user_info)

        self.assertEqual(basic_info["name"], "Bob")
        self.assertEqual(basic_info["occupation"], "teacher")
        self.assertNotIn("gender", basic_info)
        self.assertNotIn("personality", additional_profile)
        self.assertNotIn("interests", additional_profile)

    def test_convert_empty_fields(self):
        """Test handling of empty/null fields"""
        basic_info, additional_profile = self.user_profile._convert_mainservice_data({
            "name": "",
            "personality_traits": "",
            "interests": ""
        })

        self.assertNotIn("name", basic_info)
        self.assertNotIn("personality", additional_profile)
        self.assertNotIn("interests", additional_profile)

        basic_info, additional_profile = self.user_profile._convert_mainservice_data({
            "name": None,
            "personality_traits": None,
            "interests": None
        })

        self.assertNotIn("name", basic_info)
        self.assertNotIn("personality", additional_profile)
        self.assertNotIn("interests", additional_profile)

    def test_convert_whitespace_handling(self):
        """Test trimming whitespace in comma-separated values"""
        user_info = {
            "personality_traits": " curious , diligent , outgoing ",
            "interests": "hiking,  photography  ,reading"
        }

        _, additional_profile = self.user_profile._convert_mainservice_data(user_info)

        self.assertEqual(additional_profile["personality"][0]["name"], "curious")
        self.assertEqual(additional_profile["personality"][1]["name"], "diligent")
        self.assertEqual(additional_profile["interests"][1]["name"], "photography")


class TestColdStartIntegration(unittest.TestCase):
    """Test end-to-end cold start integration (mock tests)"""

    def setUp(self):
        if USE_REAL_MAINSERVICE or USE_REAL_POSTGRES or USE_REAL_MONGODB:
            self.skipTest("Using real services, skip mock integration tests")

    @patch('mem0.user_profile.main.LlmFactory')
    @patch('mem0.user_profile.main.MongoDBManager')
    @patch('mem0.user_profile.main.PostgresManager')
    @patch('mem0.user_profile.main.fetch_user_summary')
    def test_cold_start_user_not_exists(self, mock_fetch, mock_pg, mock_mongo, mock_llm):
        """Test cold start when user doesn't exist"""
        from mem0.user_profile.main import UserProfile
        from mem0.configs.base import MemoryConfig

        mock_fetch.return_value = {
            "name": "Alice",
            "gender": "female",
            "personality_traits": "curious,diligent",
            "interests": "hiking,photography"
        }

        mock_pg_instance = mock_pg.return_value
        mock_pg_instance.get.side_effect = [None, {"name": "Alice", "gender": "female"}]
        mock_pg_instance.upsert.return_value = True

        mock_mongo_instance = mock_mongo.return_value
        mock_mongo_instance.get.side_effect = [None, {}]
        mock_mongo_instance.add_item.return_value = True

        config = MemoryConfig()
        user_profile = UserProfile(config, mainservice_base_url="http://mainservice:8080")

        result = user_profile.get_profile("user_12345")

        mock_fetch.assert_called_once_with("user_12345", "http://mainservice:8080")

        mock_pg_instance.upsert.assert_called_once()
        upsert_args = mock_pg_instance.upsert.call_args[0]
        self.assertEqual(upsert_args[0], "user_12345")
        self.assertEqual(upsert_args[1]["name"], "Alice")
        self.assertEqual(upsert_args[1]["gender"], "female")

        # 2 personality + 2 interests = 4 calls
        self.assertEqual(mock_mongo_instance.add_item.call_count, 4)

        self.assertEqual(result["user_id"], "user_12345")

    @patch('mem0.user_profile.main.LlmFactory')
    @patch('mem0.user_profile.main.MongoDBManager')
    @patch('mem0.user_profile.main.PostgresManager')
    @patch('mem0.user_profile.main.fetch_user_summary')
    def test_cold_start_disabled(self, mock_fetch, mock_pg, mock_mongo, mock_llm):
        """Test that cold start doesn't run when mainservice_base_url is not configured"""
        from mem0.user_profile.main import UserProfile
        from mem0.configs.base import MemoryConfig

        mock_pg_instance = mock_pg.return_value
        mock_pg_instance.get.return_value = None

        mock_mongo_instance = mock_mongo.return_value
        mock_mongo_instance.get.return_value = None

        config = MemoryConfig()
        user_profile = UserProfile(config, mainservice_base_url=None)

        result = user_profile.get_profile("user_12345")

        mock_fetch.assert_not_called()

        self.assertEqual(result["user_id"], "user_12345")
        self.assertEqual(result["basic_info"], {})
        self.assertEqual(result["additional_profile"], {})


class TestRealMainService(unittest.TestCase):
    """Test against real MainService (only runs if USE_REAL_MAINSERVICE=1)"""

    def setUp(self):
        if not USE_REAL_MAINSERVICE:
            self.skipTest("USE_REAL_MAINSERVICE not enabled")

    def test_real_mainservice_connection(self):
        """Test fetching from real MainService"""
        result = fetch_user_summary(MAINSERVICE_TEST_USER_ID, MAINSERVICE_BASE_URL)

        self.assertTrue(
            result is None or isinstance(result, dict),
            f"Expected None or dict, got {type(result)}"
        )

        if result:
            print(f"\nMainService returned data for user_id={MAINSERVICE_TEST_USER_ID}")
            print(f"  Fields: {list(result.keys())}")
        else:
            print(f"\nMainService returned None for user_id={MAINSERVICE_TEST_USER_ID} "
                  f"(endpoint may not be implemented yet)")


class TestRealDatabaseIntegration(unittest.TestCase):
    """Test against real databases (only runs if USE_REAL_POSTGRES=1 and USE_REAL_MONGODB=1)"""

    def setUp(self):
        if not (USE_REAL_POSTGRES and USE_REAL_MONGODB):
            self.skipTest("USE_REAL_POSTGRES and USE_REAL_MONGODB not both enabled")

    def test_real_database_cold_start(self):
        """Test cold start with real databases (requires all services running)"""
        from mem0.user_profile.main import UserProfile
        from mem0.configs.base import MemoryConfig

        config = MemoryConfig()
        user_profile = UserProfile(
            config,
            mainservice_base_url=MAINSERVICE_BASE_URL if USE_REAL_MAINSERVICE else None
        )

        test_user_id = "test_cold_start_" + datetime.now().strftime("%Y%m%d_%H%M%S")

        try:
            profile = user_profile.get_profile(test_user_id)

            self.assertEqual(profile["user_id"], test_user_id)
            print(f"\nCreated test user: {test_user_id}")
            print(f"  basic_info: {profile['basic_info']}")
            print(f"  additional_profile keys: {list(profile['additional_profile'].keys())}")

        finally:
            try:
                user_profile.delete_profile(test_user_id)
                print(f"Cleaned up test user: {test_user_id}")
            except Exception as e:
                print(f"Failed to cleanup test user {test_user_id}: {e}")


if __name__ == '__main__':
    unittest.main()
