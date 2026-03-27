#!/usr/bin/env python3
"""
Independent test file for connecting to Dify API
Can be run standalone to test Dify connection with configurable API key and URL
"""
import os
import json
import time
import logging
from typing import Dict, Any, Optional
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DifyConnector:
    """
    Dify API connection wrapper with configurable API key and URL
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize Dify connector

        Args:
            api_key: Dify API key (if not provided, uses DIFY_API_KEY env var)
            base_url: Dify base URL (if not provided, uses DIFY_BASE_URL env var or default)
        """
        self.api_key = api_key or os.getenv('DIFY_API_KEY')
        self.base_url = base_url or os.getenv('DIFY_BASE_URL', 'https://api.dify.ai')

        if not self.api_key:
            raise ValueError("Dify API key is required. Set DIFY_API_KEY env var or pass api_key parameter")

        # Remove trailing slash from base_url if present
        self.base_url = self.base_url.rstrip('/')

        # Initialize HTTP client with proper headers
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'User-Agent': 'MyMem0-DifyTest/1.0'
            },
            timeout=30.0
        )

        logger.info(f"Initialized Dify connector with base URL: {self.base_url}")

    def test_connection(self) -> Dict[str, Any]:
        """
        Test basic connection to Dify API

        Returns:
            Dict containing connection test results
        """
        # Common Dify API endpoints to try
        endpoints_to_try = [
            '/v1/apps',
            '/api/v1/apps',
            '/console/api/apps',
            '/v1/info',
            '/api/v1/info',
            '/',
            '/health'
        ]

        for endpoint in endpoints_to_try:
            try:
                logger.info(f"🔍 Trying endpoint: {endpoint}")
                response = self.client.get(endpoint)

                if response.status_code == 200:
                    data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                    logger.info(f"✅ Connection successful via {endpoint}")
                    return {
                        'success': True,
                        'status_code': response.status_code,
                        'response_time_ms': response.elapsed.total_seconds() * 1000,
                        'endpoint': endpoint,
                        'data': data
                    }
                else:
                    logger.warning(f"⚠️ Endpoint {endpoint} returned {response.status_code}")

            except httpx.HTTPStatusError as e:
                logger.warning(f"⚠️ HTTP error on {endpoint}: {e.response.status_code}")
                continue
            except httpx.RequestError as e:
                logger.error(f"❌ Request error on {endpoint}: {str(e)}")
                return {
                    'success': False,
                    'error': 'REQUEST_ERROR',
                    'message': str(e)
                }
            except Exception as e:
                logger.warning(f"⚠️ Error on {endpoint}: {str(e)}")
                continue

        logger.error("❌ All endpoints failed")
        return {
            'success': False,
            'error': 'ALL_ENDPOINTS_FAILED',
            'message': 'No working endpoint found'
        }

    def list_apps(self) -> Dict[str, Any]:
        """
        List available apps in Dify

        Returns:
            Dict containing apps list or error info
        """
        try:
            response = self.client.get('/v1/apps')
            response.raise_for_status()

            data = response.json()
            logger.info(f"📱 Found {len(data.get('data', []))} apps")
            return {
                'success': True,
                'apps': data.get('data', []),
                'total': len(data.get('data', []))
            }

        except Exception as e:
            logger.error(f"❌ Failed to list apps: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def send_chat_message(self, app_id: str, message: str, user_id: str = "test_user") -> Dict[str, Any]:
        """
        Send a chat message to a Dify app

        Args:
            app_id: The Dify app ID
            message: Message to send
            user_id: User identifier

        Returns:
            Dict containing response or error info
        """
        try:
            payload = {
                "inputs": {},
                "query": message,
                "user": user_id,
                "response_mode": "blocking"
            }

            response = self.client.post(f'/v1/chat-messages', json=payload)
            response.raise_for_status()

            data = response.json()
            logger.info(f"💬 Chat message sent successfully to app {app_id}")
            return {
                'success': True,
                'response': data
            }

        except Exception as e:
            logger.error(f"❌ Failed to send chat message: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_conversation_history(self, app_id: str, user_id: str = "test_user") -> Dict[str, Any]:
        """
        Get conversation history for a user

        Args:
            app_id: The Dify app ID
            user_id: User identifier

        Returns:
            Dict containing conversation history or error info
        """
        try:
            params = {
                'user': user_id,
                'limit': 20
            }

            response = self.client.get(f'/v1/conversations', params=params)
            response.raise_for_status()

            data = response.json()
            logger.info(f"📝 Retrieved conversation history for user {user_id}")
            return {
                'success': True,
                'conversations': data.get('data', []),
                'total': len(data.get('data', []))
            }

        except Exception as e:
            logger.error(f"❌ Failed to get conversation history: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def close(self):
        """Close the HTTP client"""
        self.client.close()
        logger.info("🔌 Connection closed")

def load_config_from_file(config_file: str = "dify_config.json") -> Dict[str, str]:
    """
    Load configuration from JSON file

    Args:
        config_file: Path to config file

    Returns:
        Dict containing config values
    """
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            logger.info(f"📄 Loaded config from {config_file}")
            return config
        except Exception as e:
            logger.warning(f"⚠️ Failed to load config from {config_file}: {e}")

    return {}

def create_sample_config():
    """Create a sample configuration file"""
    sample_config = {
        "api_key": "your-dify-api-key-here",
        "base_url": "https://api.dify.ai",
        "test_app_id": "your-app-id-here"
    }

    with open("dify_config.json.sample", 'w') as f:
        json.dump(sample_config, f, indent=2)

    logger.info("📝 Created sample config file: dify_config.json.sample")

def run_comprehensive_test(connector: DifyConnector, app_id: Optional[str] = None):
    """
    Run a comprehensive test suite

    Args:
        connector: DifyConnector instance
        app_id: Optional app ID for chat testing
    """
    logger.info("🚀 Starting comprehensive Dify API test")

    # Test 1: Basic connection
    logger.info("\n🔍 Test 1: Basic Connection")
    connection_result = connector.test_connection()
    if not connection_result['success']:
        logger.error("❌ Basic connection failed, stopping tests")
        return

    # Test 2: List apps
    logger.info("\n📱 Test 2: List Apps")
    apps_result = connector.list_apps()

    if apps_result['success'] and apps_result['apps']:
        logger.info(f"Available apps:")
        for app in apps_result['apps'][:3]:  # Show first 3 apps
            logger.info(f"  - {app.get('name', 'Unknown')} (ID: {app.get('id', 'Unknown')})")

        # Use first app if no app_id provided
        if not app_id and apps_result['apps']:
            app_id = apps_result['apps'][0].get('id')
            logger.info(f"Using first app for testing: {app_id}")

    # Test 3: Chat message (if app_id available)
    if app_id:
        logger.info(f"\n💬 Test 3: Send Chat Message to app {app_id}")
        chat_result = connector.send_chat_message(
            app_id=app_id,
            message="Hello, this is a test message from the connection test script.",
            user_id="test_user_123"
        )

        if chat_result['success']:
            logger.info("✅ Chat message sent successfully")
        else:
            logger.warning(f"⚠️ Chat test failed: {chat_result['error']}")

        # Test 4: Get conversation history
        logger.info(f"\n📝 Test 4: Get Conversation History")
        history_result = connector.get_conversation_history(
            app_id=app_id,
            user_id="test_user_123"
        )

        if history_result['success']:
            logger.info(f"✅ Retrieved {history_result['total']} conversations")
        else:
            logger.warning(f"⚠️ History test failed: {history_result['error']}")
    else:
        logger.warning("⚠️ No app ID available, skipping chat and history tests")

    logger.info("\n🎉 Comprehensive test completed!")

def auto_discover_local_dify() -> Optional[str]:
    """
    Try to auto-discover local Dify instance

    Returns:
        URL if found, None otherwise
    """
    common_ports = [80, 3000, 5000, 5001, 8000, 8080, 9000]

    for port in common_ports:
        try:
            test_url = f"http://localhost:{port}"
            logger.info(f"🔍 Testing {test_url}...")

            with httpx.Client(timeout=5.0) as client:
                response = client.get(test_url)
                if response.status_code == 200:
                    logger.info(f"✅ Found service at {test_url}")
                    return test_url
        except:
            continue

    logger.warning("⚠️ No local Dify instance found on common ports")
    return None

def main():
    """Main function to run the test"""
    logger.info("🔧 Dify Connection Test Script")
    logger.info("=" * 50)

    # Load config from file if exists
    config = load_config_from_file()

    # Get configuration from various sources (priority: args > config file > env vars)
    api_key = config.get('api_key') or os.getenv('DIFY_API_KEY')
    base_url = config.get('base_url') or os.getenv('DIFY_BASE_URL')
    test_app_id = config.get('test_app_id') or os.getenv('DIFY_TEST_APP_ID')

    # Auto-discover if no base_url configured
    if not base_url:
        logger.info("🔍 No base URL configured, trying to auto-discover local Dify...")
        discovered_url = auto_discover_local_dify()
        if discovered_url:
            base_url = discovered_url
        else:
            base_url = 'https://api.dify.ai'  # fallback to cloud

    # Create sample config if no API key found
    if not api_key:
        logger.warning("⚠️ No API key found!")
        logger.info("💡 Creating sample config file...")
        create_sample_config()
        logger.info("📖 Please:")
        logger.info("   1. Copy dify_config.json.sample to dify_config.json")
        logger.info("   2. Fill in your actual Dify API key and settings")
        logger.info("   3. Or set DIFY_API_KEY environment variable")
        logger.info("   4. Run this script again")
        return

    try:
        # Initialize connector
        connector = DifyConnector(api_key=api_key, base_url=base_url)

        # Run tests
        run_comprehensive_test(connector, test_app_id)

    except Exception as e:
        logger.error(f"❌ Test failed with error: {str(e)}")

    finally:
        # Clean up
        if 'connector' in locals():
            connector.close()

if __name__ == "__main__":
    main()