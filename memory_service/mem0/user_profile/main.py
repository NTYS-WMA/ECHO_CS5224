"""
UserProfile: Main class for user profile management

Provides high-level API for extracting and managing user profiles from conversations.
"""

import logging
from typing import Dict, Any, List, Optional

from datetime import datetime

from mem0.configs.base import MemoryConfig
from mem0.user_profile.database import PostgresManager, MongoDBManager
from mem0.user_profile.profile_manager import ProfileManager
from mem0.user_profile.mainservice_client import fetch_user_summary
from mem0.utils.factory import LlmFactory

logger = logging.getLogger(__name__)


class UserProfile:
    """
    UserProfile main class

    Provides API for:
    - Extracting user profile from conversation messages
    - Updating user profile with evidence-based approach
    - Retrieving user profile data

    Usage:
        from mem0 import Memory
        from mem0.user_profile import UserProfile

        # Initialize with the same config as Memory
        config = MemoryConfig()
        user_profile = UserProfile(config)

        # Update profile from messages
        result = user_profile.set_profile(
            user_id="user123",
            messages=[
                {"role": "user", "content": "I'm Alice, living in Singapore"},
                {"role": "assistant", "content": "Nice to meet you, Alice!"}
            ]
        )

        # Get profile
        profile = user_profile.get_profile(user_id="user123")
    """

    def __init__(self, config: MemoryConfig, mainservice_base_url: Optional[str] = None):
        """
        Initialize UserProfile

        Args:
            config: MemoryConfig instance with user_profile settings
            mainservice_base_url: MainService base URL for cold start (optional)
                Example: "http://mainservice:8080"
                Leave None to disable cold start.

        Architecture Note:
            - basic_info (PostgreSQL): Conversation-extracted reference data, NON-authoritative
              * Exception: Cold start data from MainService is imported here
            - additional_profile (MongoDB): Core value - interests, skills, personality
        """
        self.config = config
        self.mainservice_base_url = mainservice_base_url

        # Initialize database managers
        self.postgres = PostgresManager(config.user_profile.postgres)
        self.mongodb = MongoDBManager(config.user_profile.mongodb)

        # Initialize LLM (shared with Memory module)
        self.llm = LlmFactory.create(
            config.llm.provider,
            config.llm.config,
        )

        # Initialize ProfileManager
        self.profile_manager = ProfileManager(
            llm=self.llm,
            postgres=self.postgres,
            mongodb=self.mongodb,
        )

        logger.info("UserProfile initialized successfully")

    def set_profile(
        self,
        user_id: str,
        messages: List[Dict[str, str]],
        manual_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Extract and update user profile from conversation messages

        This method runs the complete pipeline:
        1. Extract profile information from messages using LLM
        2. Query existing profile data
        3. Decide ADD/UPDATE/DELETE operations using LLM
        4. Execute database operations

        Args:
            user_id: User ID (required)
            messages: List of message dicts with 'role' and 'content'
                Example:
                [
                    {"role": "user", "content": "I'm Alice, 28, working as a data scientist"},
                    {"role": "assistant", "content": "Nice to meet you, Alice!"},
                    {"role": "user", "content": "I love hiking on weekends"}
                ]
            manual_data: Optional dict of manually provided basic_info that takes priority
                Example: {"name": "Alice", "birthday": "1995-06-15"}

        Returns:
            Result dict with status and details:
            {
                "success": True,
                "basic_info_updated": True,
                "additional_profile_updated": True,
                "operations_performed": {
                    "added": 2,
                    "updated": 1,
                    "deleted": 0
                },
                "errors": []
            }

        Raises:
            ValueError: If user_id is not provided or messages is empty
        """
        # Validate input
        if not user_id:
            raise ValueError("user_id is required")

        if not messages or not isinstance(messages, list):
            raise ValueError("messages must be a non-empty list")

        # Run pipeline
        try:
            result = self.profile_manager.update_profile(user_id, messages)
            return result
        except Exception as e:
            logger.error(f"Failed to set profile for user {user_id}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def get_profile(
        self,
        user_id: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get user profile data

        Args:
            user_id: User ID (required)
            options: Query options (optional)
                - fields: List of field names to return from additional_profile
                  Example: {"fields": ["interests", "skills"]}
                  If None, returns all fields
                - evidence_limit: Control evidence return behavior (default 5):
                  * 0: Remove all evidence (return empty arrays)
                  * Positive N: Return latest N evidence items
                  * -1: Return all evidence
                  Example: {"evidence_limit": 0}, {"evidence_limit": 10}, {"evidence_limit": -1}

        Returns:
            Profile dict with basic_info and additional_profile:
            {
                "user_id": "user123",
                "basic_info": {
                    "name": "Alice",
                    "current_city": "Singapore",
                    ...
                },
                "additional_profile": {
                    "interests": [...],
                    "skills": [...],
                    ...
                }
            }

        Raises:
            ValueError: If user_id is not provided
        """
        # Validate input
        if not user_id:
            raise ValueError("user_id is required")

        try:
            # Apply default evidence_limit if not specified
            if options is None:
                options = {}
            if 'evidence_limit' not in options:
                options['evidence_limit'] = 5  # Default to 5

            # Query basic_info
            basic_info = self.postgres.get(user_id) or {}

            # Query additional_profile with options
            additional_profile = self.mongodb.get(user_id, options) or {}

            # Cold start: If user doesn't exist and MainService is configured, try importing
            if not basic_info and not additional_profile and self.mainservice_base_url:
                logger.info(f"User {user_id} not found, attempting cold start from MainService")
                if self._cold_start_from_mainservice(user_id):
                    # Re-query after cold start
                    basic_info = self.postgres.get(user_id) or {}
                    additional_profile = self.mongodb.get(user_id, options) or {}

            return {
                "user_id": user_id,
                "basic_info": basic_info,
                "additional_profile": additional_profile,
            }
        except Exception as e:
            logger.error(f"Failed to get profile for user {user_id}: {e}")
            raise

    def get_missing_fields(self, user_id: str, source: str = "both") -> Dict[str, Any]:
        """
        Get missing fields in user profile

        Args:
            user_id: User ID (required)
            source: Which source to check - "pg", "mongo", or "both" (default)

        Returns:
            Result dict with missing fields:
            {
                "user_id": "user123",
                "missing_fields": {
                    "basic_info": ["hometown", "gender", "birthday"],
                    "additional_profile": ["personality", "learning_preferences"]
                }
            }

        Raises:
            ValueError: If user_id is not provided or source is invalid
        """
        # Validate input
        if not user_id:
            raise ValueError("user_id is required")

        if source not in ["pg", "mongo", "both"]:
            raise ValueError("source must be 'pg', 'mongo', or 'both'")

        try:
            result = {
                "user_id": user_id,
                "missing_fields": {}
            }

            # Check PostgreSQL basic_info
            if source in ["pg", "both"]:
                missing_basic = self.postgres.get_missing_fields(user_id)
                result["missing_fields"]["basic_info"] = missing_basic

            # Check MongoDB additional_profile
            if source in ["mongo", "both"]:
                missing_additional = self.mongodb.get_missing_fields(user_id)
                result["missing_fields"]["additional_profile"] = missing_additional

            return result
        except Exception as e:
            logger.error(f"Failed to get missing fields for user {user_id}: {e}")
            raise

    def delete_profile(self, user_id: str) -> Dict[str, Any]:
        """
        Delete user profile completely

        Args:
            user_id: User ID (required)

        Returns:
            Result dict:
            {
                "success": True,
                "basic_info_deleted": True,
                "additional_profile_deleted": True
            }

        Raises:
            ValueError: If user_id is not provided
        """
        # Validate input
        if not user_id:
            raise ValueError("user_id is required")

        try:
            # Delete from PostgreSQL
            basic_info_deleted = self.postgres.delete(user_id)

            # Delete from MongoDB
            additional_profile_deleted = self.mongodb.delete(user_id)

            return {
                "success": True,
                "basic_info_deleted": basic_info_deleted,
                "additional_profile_deleted": additional_profile_deleted,
            }
        except Exception as e:
            logger.error(f"Failed to delete profile for user {user_id}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def initialize_databases(self):
        """
        Initialize database tables/collections

        Creates:
        - PostgreSQL: user_profile.user_profile table
        - MongoDB: user_additional_profile collection with indexes

        This is typically called once during setup.
        """
        try:
            logger.info("Initializing UserProfile databases...")

            # Initialize PostgreSQL table
            self.postgres.create_table()
            logger.info("PostgreSQL table created")

            # Initialize MongoDB collection
            self.mongodb.create_collection()
            logger.info("MongoDB collection created")

            logger.info("UserProfile databases initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize databases: {e}")
            raise

    def _cold_start_from_mainservice(self, user_id: str) -> bool:
        """
        Attempt to import initial profile data from MainService (cold start).

        Called when a user's profile doesn't exist yet. Fetches initial data from
        MainService and stores it in both databases.

        Args:
            user_id: User ID

        Returns:
            True if data was successfully imported, False otherwise.

        Note:
            This is a special case where basic_info receives data from an external
            source rather than conversation extraction.
        """
        try:
            user_info = fetch_user_summary(user_id, self.mainservice_base_url)

            if not user_info:
                logger.info(f"No data found in MainService for user {user_id}")
                return False

            basic_info, additional_profile = self._convert_mainservice_data(user_info)

            if basic_info:
                self.postgres.upsert(user_id, basic_info)
                logger.info(f"Imported basic_info from MainService for user {user_id}: {list(basic_info.keys())}")

            if additional_profile:
                if "personality" in additional_profile:
                    for item in additional_profile["personality"]:
                        self.mongodb.add_item(user_id, "personality", item)
                    logger.info(f"Imported {len(additional_profile['personality'])} personality traits from MainService")

                if "interests" in additional_profile:
                    for item in additional_profile["interests"]:
                        self.mongodb.add_item(user_id, "interests", item)
                    logger.info(f"Imported {len(additional_profile['interests'])} interests from MainService")

            logger.info(f"Cold start completed successfully for user {user_id}")
            return True

        except Exception as e:
            logger.warning(f"Cold start from MainService failed for user {user_id}: {e}")
            return False

    def _convert_mainservice_data(self, user_info: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Convert MainService user data to profile format.

        Args:
            user_info: User data from MainService API

        Returns:
            Tuple of (basic_info, additional_profile) dicts

        Example:
            Input:
                {
                    "name": "Alice",
                    "gender": "female",
                    "occupation": "software engineer",
                    "company": "Google",
                    "personality_traits": "curious,diligent",
                    "interests": "hiking,photography"
                }

            Output:
                (
                    {"name": "Alice", "gender": "female", "occupation": "software engineer", "company": "Google"},
                    {
                        "personality": [{"name": "curious", "degree": 3, "evidence": [...]}, ...],
                        "interests": [{"name": "hiking", "degree": 3, "evidence": [...]}, ...]
                    }
                )

        TODO: Update field mapping once MainService finalizes its response schema.
        """
        basic_info = {}
        additional_profile = {}

        # Map basic fields
        for field in ("name", "nickname", "gender", "occupation", "company",
                      "education_level", "university", "major", "current_city"):
            if user_info.get(field):
                basic_info[field] = user_info[field]

        # Evidence timestamp (same for all items in a cold-start batch)
        timestamp = datetime.now().isoformat()

        # Convert personality_traits (comma-separated string) to personality items
        personality_traits = user_info.get("personality_traits")
        if personality_traits and isinstance(personality_traits, str):
            traits = [t.strip() for t in personality_traits.split(",") if t.strip()]
            if traits:
                additional_profile["personality"] = [
                    {
                        "name": trait,
                        "degree": 3,  # Default medium degree
                        "evidence": [{"text": "Initial profile from user registration", "timestamp": timestamp}]
                    }
                    for trait in traits
                ]

        # Convert interests (comma-separated string) to interest items
        interests = user_info.get("interests")
        if interests and isinstance(interests, str):
            interest_list = [i.strip() for i in interests.split(",") if i.strip()]
            if interest_list:
                additional_profile["interests"] = [
                    {
                        "name": interest,
                        "degree": 3,  # Default medium degree
                        "evidence": [{"text": "Initial profile from user registration", "timestamp": timestamp}]
                    }
                    for interest in interest_list
                ]

        return basic_info, additional_profile

    def close(self):
        """Close database connections"""
        try:
            self.postgres.close()
            self.mongodb.close()
            logger.info("UserProfile connections closed")
        except Exception as e:
            logger.error(f"Failed to close connections: {e}")
            raise
