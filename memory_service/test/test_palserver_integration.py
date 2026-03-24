"""
Integration tests for PalServer cold start feature

Tests the complete cold start flow:
1. fetch_child_summary() HTTP client
2. UserProfile._convert_palserver_data() data conversion
3. UserProfile.get_profile() cold start integration

Configuration (via environment variables):
- USE_REAL_PALSERVER: Set to '1' to test against real PalServer (default: mock)
- USE_REAL_POSTGRES: Set to '1' to test against real PostgreSQL (default: mock)
- USE_REAL_MONGODB: Set to '1' to test against real MongoDB (default: mock)

Examples:
    # Use all mocks (default, fast)
    python -m pytest test/test_palserver_integration.py -v

    # Test real PalServer only
    USE_REAL_PALSERVER=1 python -m pytest test/test_palserver_integration.py -v

    # Test all real services
    USE_REAL_PALSERVER=1 USE_REAL_POSTGRES=1 USE_REAL_MONGODB=1 python -m pytest test/test_palserver_integration.py -v
"""

import os
import unittest
from unittest.mock import Mock, patch
from datetime import datetime

from mem0.user_profile.palserver_client import fetch_child_summary

# ============================================================================
# Test Configuration (set via environment variables)
# ============================================================================

# Whether to use real services instead of mocks
USE_REAL_PALSERVER = os.getenv("USE_REAL_PALSERVER", "0") == "1"
USE_REAL_POSTGRES = os.getenv("USE_REAL_POSTGRES", "0") == "1"
USE_REAL_MONGODB = os.getenv("USE_REAL_MONGODB", "0") == "1"

# PalServer configuration (only used if USE_REAL_PALSERVER=1)
PALSERVER_BASE_URL = os.getenv("PALSERVER_BASE_URL", "http://localhost:8099/pal")
PALSERVER_TEST_CHILD_ID = os.getenv("PALSERVER_TEST_CHILD_ID", "12345")

# Print configuration at import time
if any([USE_REAL_PALSERVER, USE_REAL_POSTGRES, USE_REAL_MONGODB]):
    print(f"\n{'='*70}")
    print("Test Configuration:")
    print(f"  USE_REAL_PALSERVER: {USE_REAL_PALSERVER} (URL: {PALSERVER_BASE_URL if USE_REAL_PALSERVER else 'N/A'})")
    print(f"  USE_REAL_POSTGRES:  {USE_REAL_POSTGRES}")
    print(f"  USE_REAL_MONGODB:   {USE_REAL_MONGODB}")
    print(f"{'='*70}\n")


class TestPalServerClient(unittest.TestCase):
    """Test PalServer HTTP client (mock tests, skipped if USE_REAL_PALSERVER=1)"""

    def setUp(self):
        if USE_REAL_PALSERVER:
            self.skipTest("Using real PalServer, skip mock tests")
        self.base_url = "http://localhost:8099/pal"
        self.child_id = "12345"

    @patch('mem0.user_profile.palserver_client.requests.get')
    def test_fetch_success(self, mock_get):
        """Test successful fetch from PalServer"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "code": "CHILD_INFO_RETRIEVED",
            "message": "孩子信息获取成功",
            "data": {
                "id": 12345,
                "childName": "小明",
                "age": 8,
                "gender": 1,
                "personalityTraits": "开朗,善良,勇敢",
                "hobbies": "篮球,音乐,阅读"
            }
        }
        mock_get.return_value = mock_response

        result = fetch_child_summary(self.child_id, self.base_url)

        self.assertIsNotNone(result)
        self.assertEqual(result["id"], 12345)
        self.assertEqual(result["childName"], "小明")
        mock_get.assert_called_once_with(
            f"{self.base_url}/child/{self.child_id}/summary",
            timeout=1.0
        )

    @patch('mem0.user_profile.palserver_client.requests.get')
    def test_fetch_timeout(self, mock_get):
        """Test timeout handling (1 second)"""
        import requests
        mock_get.side_effect = requests.Timeout("Connection timeout")

        result = fetch_child_summary(self.child_id, self.base_url)

        self.assertIsNone(result)

    @patch('mem0.user_profile.palserver_client.requests.get')
    def test_fetch_http_error(self, mock_get):
        """Test HTTP error handling (404, 500, etc.)"""
        import requests
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        result = fetch_child_summary(self.child_id, self.base_url)

        self.assertIsNone(result)

    @patch('mem0.user_profile.palserver_client.requests.get')
    def test_fetch_success_false(self, mock_get):
        """Test when PalServer returns success=False"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": False,
            "message": "Child not found"
        }
        mock_get.return_value = mock_response

        result = fetch_child_summary(self.child_id, self.base_url)

        self.assertIsNone(result)

    @patch('mem0.user_profile.palserver_client.requests.get')
    def test_fetch_missing_data_field(self, mock_get):
        """Test when response is missing 'data' field"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "message": "OK"
            # Missing 'data' field
        }
        mock_get.return_value = mock_response

        result = fetch_child_summary(self.child_id, self.base_url)

        self.assertIsNone(result)

    def test_fetch_missing_params(self):
        """Test with missing required parameters"""
        result = fetch_child_summary("", self.base_url)
        self.assertIsNone(result)

        result = fetch_child_summary(self.child_id, "")
        self.assertIsNone(result)


class TestDataConversion(unittest.TestCase):
    """Test PalServer data to MyMem0 format conversion"""

    def setUp(self):
        """Create UserProfile instance for testing conversion logic"""
        from mem0.user_profile.main import UserProfile
        from mem0.configs.base import MemoryConfig

        # Use real databases if configured, otherwise mock
        if USE_REAL_POSTGRES and USE_REAL_MONGODB:
            # Use real databases
            config = MemoryConfig()
            self.user_profile = UserProfile(config)
        else:
            # Use mocks (default for fast tests)
            with patch('mem0.user_profile.main.PostgresManager'), \
                 patch('mem0.user_profile.main.MongoDBManager'), \
                 patch('mem0.user_profile.main.LlmFactory'):
                config = MemoryConfig()
                self.user_profile = UserProfile(config)

    def test_convert_full_data(self):
        """Test conversion with complete data"""
        child_info = {
            "id": 12345,
            "childName": "小明",
            "age": 8,
            "gender": 1,
            "personalityTraits": "开朗,善良,勇敢",
            "hobbies": "篮球,音乐,阅读"
        }

        basic_info, additional_profile = self.user_profile._convert_palserver_data(child_info)

        # Check basic_info
        self.assertEqual(basic_info["nickname"], "小明")
        self.assertEqual(basic_info["gender"], "male")
        self.assertNotIn("age", basic_info)  # Age should be ignored

        # Check additional_profile
        self.assertIn("personality", additional_profile)
        self.assertEqual(len(additional_profile["personality"]), 3)
        self.assertEqual(additional_profile["personality"][0]["name"], "开朗")
        self.assertEqual(additional_profile["personality"][0]["degree"], 3)
        self.assertEqual(
            additional_profile["personality"][0]["evidence"][0]["text"],
            "Initial profile from user registration"
        )

        self.assertIn("interests", additional_profile)
        self.assertEqual(len(additional_profile["interests"]), 3)
        self.assertEqual(additional_profile["interests"][0]["name"], "篮球")
        self.assertEqual(additional_profile["interests"][0]["degree"], 3)

    def test_convert_gender_mapping(self):
        """Test gender value mapping (1->male, 2->female, other->unknown)"""
        # Test male
        basic_info, _ = self.user_profile._convert_palserver_data({"gender": 1})
        self.assertEqual(basic_info["gender"], "male")

        # Test female
        basic_info, _ = self.user_profile._convert_palserver_data({"gender": 2})
        self.assertEqual(basic_info["gender"], "female")

        # Test unknown
        basic_info, _ = self.user_profile._convert_palserver_data({"gender": 99})
        self.assertEqual(basic_info["gender"], "unknown")

        # Test None (should not set gender)
        basic_info, _ = self.user_profile._convert_palserver_data({"gender": None})
        self.assertNotIn("gender", basic_info)

    def test_convert_empty_fields(self):
        """Test handling of empty/null fields"""
        # Test empty strings
        basic_info, additional_profile = self.user_profile._convert_palserver_data({
            "childName": "",
            "personalityTraits": "",
            "hobbies": ""
        })

        self.assertNotIn("nickname", basic_info)
        self.assertNotIn("personality", additional_profile)
        self.assertNotIn("interests", additional_profile)

        # Test None values
        basic_info, additional_profile = self.user_profile._convert_palserver_data({
            "childName": None,
            "personalityTraits": None,
            "hobbies": None
        })

        self.assertNotIn("nickname", basic_info)
        self.assertNotIn("personality", additional_profile)
        self.assertNotIn("interests", additional_profile)

    def test_convert_whitespace_handling(self):
        """Test trimming whitespace in comma-separated values"""
        child_info = {
            "personalityTraits": " 开朗 , 善良 , 勇敢 ",
            "hobbies": "篮球,  音乐  ,阅读"
        }

        _, additional_profile = self.user_profile._convert_palserver_data(child_info)

        # Check trimmed values
        self.assertEqual(additional_profile["personality"][0]["name"], "开朗")
        self.assertEqual(additional_profile["personality"][1]["name"], "善良")
        self.assertEqual(additional_profile["interests"][1]["name"], "音乐")


class TestColdStartIntegration(unittest.TestCase):
    """Test end-to-end cold start integration (mock tests, skipped if using real services)"""

    def setUp(self):
        if USE_REAL_PALSERVER or USE_REAL_POSTGRES or USE_REAL_MONGODB:
            self.skipTest("Using real services, skip mock integration tests (use TestRealDatabaseIntegration instead)")

    @patch('mem0.user_profile.main.LlmFactory')
    @patch('mem0.user_profile.main.MongoDBManager')
    @patch('mem0.user_profile.main.PostgresManager')
    @patch('mem0.user_profile.main.fetch_child_summary')  # Patch where it's imported, not where it's defined
    def test_cold_start_user_not_exists(self, mock_fetch, mock_pg, mock_mongo, mock_llm):
        """Test cold start when user doesn't exist"""
        from mem0.user_profile.main import UserProfile
        from mem0.configs.base import MemoryConfig

        # Mock PalServer response
        mock_fetch.return_value = {
            "id": 12345,
            "childName": "小明",
            "gender": 1,
            "personalityTraits": "开朗,善良",
            "hobbies": "篮球,音乐"
        }

        # Mock database managers
        mock_pg_instance = mock_pg.return_value
        mock_pg_instance.get.side_effect = [None, {"nickname": "小明", "gender": "male"}]  # First None, then data after cold start
        mock_pg_instance.upsert.return_value = True

        mock_mongo_instance = mock_mongo.return_value
        mock_mongo_instance.get.side_effect = [None, {}]  # First None, then empty dict after cold start
        mock_mongo_instance.add_item.return_value = True

        # Initialize UserProfile with PalServer URL
        config = MemoryConfig()
        user_profile = UserProfile(config, palserver_base_url="http://localhost:8099/pal")

        # Call get_profile (should trigger cold start)
        result = user_profile.get_profile("12345")

        # Verify fetch_child_summary was called with correct params
        mock_fetch.assert_called_once_with("12345", "http://localhost:8099/pal")

        # Verify postgres.upsert was called with converted data
        mock_pg_instance.upsert.assert_called_once()
        upsert_call_args = mock_pg_instance.upsert.call_args
        self.assertEqual(upsert_call_args[0][0], "12345")  # user_id
        self.assertEqual(upsert_call_args[0][1]["nickname"], "小明")
        self.assertEqual(upsert_call_args[0][1]["gender"], "male")

        # Verify mongodb.add_item was called (2 personality + 2 interests = 4 calls)
        self.assertEqual(mock_mongo_instance.add_item.call_count, 4)

        # Verify result contains user_id
        self.assertEqual(result["user_id"], "12345")

    @patch('mem0.user_profile.main.LlmFactory')
    @patch('mem0.user_profile.main.MongoDBManager')
    @patch('mem0.user_profile.main.PostgresManager')
    @patch('mem0.user_profile.main.fetch_child_summary')  # Patch where it's imported
    def test_cold_start_disabled(self, mock_fetch, mock_pg, mock_mongo, mock_llm):
        """Test that cold start doesn't run when PalServer URL is not configured"""
        from mem0.user_profile.main import UserProfile
        from mem0.configs.base import MemoryConfig

        # Mock database returns None
        mock_pg_instance = mock_pg.return_value
        mock_pg_instance.get.return_value = None

        mock_mongo_instance = mock_mongo.return_value
        mock_mongo_instance.get.return_value = None

        # Initialize without palserver_base_url
        config = MemoryConfig()
        user_profile = UserProfile(config, palserver_base_url=None)

        # Call get_profile
        result = user_profile.get_profile("12345")

        # Verify fetch_child_summary was NOT called (cold start disabled)
        mock_fetch.assert_not_called()

        # Verify result is empty
        self.assertEqual(result["user_id"], "12345")
        self.assertEqual(result["basic_info"], {})
        self.assertEqual(result["additional_profile"], {})


class TestRealPalServer(unittest.TestCase):
    """Test against real PalServer (only runs if USE_REAL_PALSERVER=1)"""

    def setUp(self):
        if not USE_REAL_PALSERVER:
            self.skipTest("USE_REAL_PALSERVER not enabled")

    def test_real_palserver_connection(self):
        """Test fetching from real PalServer"""
        result = fetch_child_summary(PALSERVER_TEST_CHILD_ID, PALSERVER_BASE_URL)

        # Allow None (child not found) or dict (child found)
        self.assertTrue(
            result is None or isinstance(result, dict),
            f"Expected None or dict, got {type(result)}"
        )

        # If data returned, validate structure
        if result:
            print(f"\n✓ PalServer returned data for child_id={PALSERVER_TEST_CHILD_ID}")
            print(f"  Fields: {list(result.keys())}")

            # Check expected fields exist (optional, may be None)
            possible_fields = ["id", "childName", "age", "gender", "personalityTraits", "hobbies"]
            for field in possible_fields:
                if field in result:
                    print(f"  - {field}: {result[field]}")
        else:
            print(f"\n⚠ PalServer returned None for child_id={PALSERVER_TEST_CHILD_ID} (child may not exist)")


class TestRealDatabaseIntegration(unittest.TestCase):
    """Test against real databases (only runs if USE_REAL_POSTGRES=1 and USE_REAL_MONGODB=1)"""

    def setUp(self):
        if not (USE_REAL_POSTGRES and USE_REAL_MONGODB):
            self.skipTest("USE_REAL_POSTGRES and USE_REAL_MONGODB not both enabled")

    def test_real_database_cold_start(self):
        """Test cold start with real databases (requires all services running)"""
        from mem0.user_profile.main import UserProfile
        from mem0.configs.base import MemoryConfig

        # Initialize with real databases
        config = MemoryConfig()
        user_profile = UserProfile(config, palserver_base_url=PALSERVER_BASE_URL if USE_REAL_PALSERVER else None)

        # Use a test user ID that won't conflict
        test_user_id = "test_cold_start_" + datetime.now().strftime("%Y%m%d_%H%M%S")

        try:
            # Get profile (should be empty initially)
            profile = user_profile.get_profile(test_user_id)

            self.assertEqual(profile["user_id"], test_user_id)
            print(f"\n✓ Created test user: {test_user_id}")
            print(f"  basic_info: {profile['basic_info']}")
            print(f"  additional_profile keys: {list(profile['additional_profile'].keys())}")

        finally:
            # Cleanup: delete test user
            try:
                user_profile.delete_profile(test_user_id)
                print(f"✓ Cleaned up test user: {test_user_id}")
            except Exception as e:
                print(f"⚠ Failed to cleanup test user {test_user_id}: {e}")


if __name__ == '__main__':
    unittest.main()
