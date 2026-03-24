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
from mem0.user_profile.palserver_client import fetch_child_summary
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
                {"role": "user", "content": "我叫张三，住在北京"},
                {"role": "assistant", "content": "你好张三！"}
            ]
        )

        # Get profile
        profile = user_profile.get_profile(user_id="user123")
    """

    def __init__(self, config: MemoryConfig, palserver_base_url: Optional[str] = None):
        """
        Initialize UserProfile

        Args:
            config: MemoryConfig instance with user_profile settings
            palserver_base_url: PalServer base URL for cold start (optional)
                Example: "http://localhost:8099/pal"

        Architecture Note:
            - basic_info (PostgreSQL): Conversation-extracted reference data, NON-authoritative
              * Exception: Cold start data from PalServer is imported here (see discuss/40-cold_start_implementation.md)
            - additional_profile (MongoDB): Core value - interests, skills, personality
            - See discuss/19-manual_data_decision.md for architectural decisions
        """
        self.config = config
        self.palserver_base_url = palserver_base_url

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
                    {"role": "user", "content": "我叫李明，今年30岁"},
                    {"role": "assistant", "content": "你好李明！"},
                    {"role": "user", "content": "我喜欢踢足球"}
                ]
            manual_data: Optional dict of manually provided basic_info that takes priority
                Example: {"name": "李明", "birthday": "1990-01-01"}

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
                    "name": "张三",
                    "current_city": "北京",
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

            # Cold start: If user doesn't exist and PalServer is configured, try importing
            if not basic_info and not additional_profile and self.palserver_base_url:
                logger.info(f"User {user_id} not found, attempting cold start from PalServer")
                if self._cold_start_from_palserver(user_id):
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

    def _cold_start_from_palserver(self, user_id: str) -> bool:
        """
        Attempt to import initial profile data from PalServer (cold start)

        This method is called when a user's profile doesn't exist in MyMem0.
        It fetches initial data from PalServer and stores it in both databases.

        Args:
            user_id: User ID (child_id in PalServer)

        Returns:
            True if data was successfully imported, False otherwise

        Note:
            This is a special case where basic_info receives data from an external
            source rather than conversation extraction. See discuss/40-cold_start_implementation.md
            for architectural justification.
        """
        try:
            # Fetch data from PalServer
            child_info = fetch_child_summary(user_id, self.palserver_base_url)

            if not child_info:
                logger.info(f"No data found in PalServer for user {user_id}")
                return False

            # Convert PalServer data to MyMem0 format
            basic_info, additional_profile = self._convert_palserver_data(child_info)

            # Store basic_info in PostgreSQL (if any)
            if basic_info:
                self.postgres.upsert(user_id, basic_info)
                logger.info(f"Imported basic_info from PalServer for user {user_id}: {list(basic_info.keys())}")

            # Store additional_profile in MongoDB (if any)
            if additional_profile:
                # Import personality items
                if "personality" in additional_profile:
                    for item in additional_profile["personality"]:
                        self.mongodb.add_item(user_id, "personality", item)
                    logger.info(f"Imported {len(additional_profile['personality'])} personality traits from PalServer")

                # Import interest items
                if "interests" in additional_profile:
                    for item in additional_profile["interests"]:
                        self.mongodb.add_item(user_id, "interests", item)
                    logger.info(f"Imported {len(additional_profile['interests'])} interests from PalServer")

            logger.info(f"Cold start completed successfully for user {user_id}")
            return True

        except Exception as e:
            logger.warning(f"Cold start from PalServer failed for user {user_id}: {e}")
            return False

    def _convert_palserver_data(self, child_info: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Convert PalServer child data to MyMem0 profile format

        Args:
            child_info: Child data from PalServer API

        Returns:
            Tuple of (basic_info, additional_profile) dicts

        Example:
            Input:
                {
                    "childName": "小明",
                    "gender": 1,
                    "personalityTraits": "开朗,善良,勇敢",
                    "hobbies": "篮球,音乐,阅读"
                }

            Output:
                (
                    {"nickname": "小明", "gender": "male"},
                    {
                        "personality": [
                            {"name": "开朗", "degree": 3, "evidence": [...]},
                            ...
                        ],
                        "interests": [
                            {"name": "篮球", "degree": 3, "evidence": [...]},
                            ...
                        ]
                    }
                )
        """
        basic_info = {}
        additional_profile = {}

        # Convert childName to nickname
        if child_info.get("childName"):
            basic_info["nickname"] = child_info["childName"]

        # Convert gender (1->male, 2->female, other->unknown)
        gender_value = child_info.get("gender")
        if gender_value == 1:
            basic_info["gender"] = "male"
        elif gender_value == 2:
            basic_info["gender"] = "female"
        elif gender_value is not None:
            basic_info["gender"] = "unknown"

        # Evidence timestamp (same for all items)
        timestamp = datetime.now().isoformat()

        # Convert personalityTraits to personality items
        personality_traits = child_info.get("personalityTraits")
        if personality_traits and isinstance(personality_traits, str):
            traits = [t.strip() for t in personality_traits.split(",") if t.strip()]
            if traits:
                additional_profile["personality"] = [
                    {
                        "name": trait,
                        "degree": 3,  # Default medium degree
                        "evidence": [
                            {
                                "text": "Initial profile from user registration",
                                "timestamp": timestamp
                            }
                        ]
                    }
                    for trait in traits
                ]

        # Convert hobbies to interests items
        hobbies = child_info.get("hobbies")
        if hobbies and isinstance(hobbies, str):
            hobby_list = [h.strip() for h in hobbies.split(",") if h.strip()]
            if hobby_list:
                additional_profile["interests"] = [
                    {
                        "name": hobby,
                        "degree": 3,  # Default medium degree
                        "evidence": [
                            {
                                "text": "Initial profile from user registration",
                                "timestamp": timestamp
                            }
                        ]
                    }
                    for hobby in hobby_list
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
