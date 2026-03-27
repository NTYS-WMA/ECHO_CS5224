"""
MongoDB Manager for UserProfile additional_profile storage
"""

import logging
from typing import Dict, Any, Optional, List

try:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError
except ImportError:
    raise ImportError("The 'pymongo' library is required. Please install it using 'pip install pymongo'.")

logger = logging.getLogger(__name__)


class MongoDBManager:
    """
    MongoDB manager for UserProfile additional_profile storage

    Manages connection and CRUD operations for user_additional_profile collection
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize MongoDB connection

        Args:
            config: Configuration dict with connection parameters
                - uri: MongoDB connection URI
                - database: Database name
                - collection: Collection name (default: user_additional_profile)
        """
        self.config = config
        self.uri = config['uri']
        self.database_name = config['database']
        self.collection_name = config.get('collection', 'user_additional_profile')

        self.client = None
        self.db = None
        self.collection = None
        self._initialize_connection()

    def _initialize_connection(self):
        """Initialize MongoDB connection"""
        try:
            self.client = MongoClient(self.uri)
            self.db = self.client[self.database_name]
            self.collection = self.db[self.collection_name]

            # Test connection
            self.client.admin.command('ping')
            logger.info(f"MongoDB connected successfully to {self.database_name}.{self.collection_name}")
        except PyMongoError as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    def create_collection(self):
        """
        Create collection and indexes if not exist

        Creates indexes on:
        - user_id (unique)
        - interests.id
        - skills.id
        - personality.id
        """
        try:
            # Create collection if not exists
            if self.collection_name not in self.db.list_collection_names():
                self.db.create_collection(self.collection_name)
                logger.info(f"Collection '{self.collection_name}' created")

            # Create indexes
            self.collection.create_index("user_id", unique=True)
            self.collection.create_index("interests.id")
            self.collection.create_index("skills.id")
            self.collection.create_index("personality.id")

            logger.info(f"Indexes created for collection '{self.collection_name}'")
        except PyMongoError as e:
            logger.error(f"Failed to create collection or indexes: {e}")
            raise

    def upsert(self, user_id: str, additional_profile: Dict[str, Any]) -> bool:
        """
        Insert or update user additional_profile

        Args:
            user_id: User ID
            additional_profile: Additional profile dict with interests, skills, etc.

        Returns:
            True if successful
        """
        try:
            document = {
                "user_id": user_id,
                **additional_profile
            }

            result = self.collection.replace_one(
                {"user_id": user_id},
                document,
                upsert=True
            )

            if result.upserted_id or result.modified_count > 0:
                logger.info(f"Successfully upserted additional_profile for user {user_id}")
                return True
            else:
                logger.warning(f"No changes made to additional_profile for user {user_id}")
                return True  # No changes needed, still successful
        except PyMongoError as e:
            logger.error(f"Failed to upsert additional_profile for user {user_id}: {e}")
            raise

    def get(self, user_id: str, options: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Get user additional_profile by user_id

        Args:
            user_id: User ID
            options: Query options
                - fields: List of field names to return (e.g., ['interests', 'skills'])
                - evidence_limit: Control evidence return behavior:
                    * 0: Remove all evidence (return empty arrays)
                    * Positive N: Return latest N evidence items (sorted by timestamp desc)
                    * -1: Return all evidence
                    * Not specified: Use default behavior
                - If None, return all fields

        Returns:
            Dict with additional_profile or None if not found
        """
        try:
            # Build projection
            if options and 'fields' in options:
                # Only include specified fields (cannot mix inclusion and exclusion except for _id)
                fields = options['fields']
                projection = {"_id": 0}  # Only exclude _id
                for field in fields:
                    projection[field] = 1
            else:
                # Exclude _id and user_id from result
                projection = {"_id": 0, "user_id": 0}

            result = self.collection.find_one(
                {"user_id": user_id},
                projection
            )

            # Apply evidence_limit if specified
            if result and options and 'evidence_limit' in options:
                evidence_limit = options['evidence_limit']
                if evidence_limit == 0:
                    # 0 means remove all evidence
                    result = self._remove_evidence(result)
                elif evidence_limit > 0:
                    # Positive number means limit to N items
                    result = self._limit_evidence(result, evidence_limit)
                # -1 means return all evidence (no processing needed)

            return result
        except PyMongoError as e:
            logger.error(f"Failed to get additional_profile for user {user_id}: {e}")
            raise

    def _remove_evidence(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove all evidence from profile data

        Args:
            profile: Profile data dictionary

        Returns:
            Profile with evidence removed (empty arrays)
        """
        # Fields that contain evidence arrays
        evidence_fields = ['interests', 'skills', 'personality', 'social_context', 'learning_preferences']

        for field in evidence_fields:
            if field in profile and isinstance(profile[field], list):
                for item in profile[field]:
                    if isinstance(item, dict) and 'evidence' in item:
                        item['evidence'] = []

        return profile

    def _limit_evidence(self, profile: Dict[str, Any], limit: int) -> Dict[str, Any]:
        """
        Limit evidence items in profile data

        Args:
            profile: Profile data dictionary
            limit: Maximum number of evidence items per entry

        Returns:
            Profile with limited evidence (sorted by timestamp descending)
        """
        # Fields that contain evidence arrays
        evidence_fields = ['interests', 'skills', 'personality', 'social_context', 'learning_preferences']

        for field in evidence_fields:
            if field in profile and isinstance(profile[field], list):
                for item in profile[field]:
                    if isinstance(item, dict) and 'evidence' in item and isinstance(item['evidence'], list):
                        # Sort by timestamp descending (most recent first) and limit
                        sorted_evidence = sorted(
                            item['evidence'],
                            key=lambda x: x.get('timestamp', ''),
                            reverse=True
                        )
                        item['evidence'] = sorted_evidence[:limit]

        return profile

    def update_field(self, user_id: str, field_name: str, field_data: List[Dict[str, Any]]) -> bool:
        """
        Update a specific field (interests, skills, etc.) for a user

        Args:
            user_id: User ID
            field_name: Field name (e.g., 'interests', 'skills')
            field_data: List of items for this field

        Returns:
            True if successful
        """
        try:
            result = self.collection.update_one(
                {"user_id": user_id},
                {"$set": {field_name: field_data}},
                upsert=True
            )

            if result.modified_count > 0 or result.upserted_id:
                logger.info(f"Successfully updated field '{field_name}' for user {user_id}")
                return True
            else:
                logger.warning(f"No changes made to field '{field_name}' for user {user_id}")
                return True
        except PyMongoError as e:
            logger.error(f"Failed to update field '{field_name}' for user {user_id}: {e}")
            raise

    def add_item(self, user_id: str, field_name: str, item: Dict[str, Any]) -> bool:
        """
        Add an item to a field array (e.g., add new interest)

        Args:
            user_id: User ID
            field_name: Field name (e.g., 'interests')
            item: Item to add (must have 'id' field)

        Returns:
            True if successful
        """
        try:
            result = self.collection.update_one(
                {"user_id": user_id},
                {"$push": {field_name: item}},
                upsert=True
            )

            if result.modified_count > 0 or result.upserted_id:
                logger.info(f"Successfully added item to '{field_name}' for user {user_id}")
                return True
            else:
                logger.warning(f"No changes made when adding to '{field_name}' for user {user_id}")
                return False
        except PyMongoError as e:
            logger.error(f"Failed to add item to '{field_name}' for user {user_id}: {e}")
            raise

    def update_item(self, user_id: str, field_name: str, item_id: str, updated_item: Dict[str, Any]) -> bool:
        """
        Update an item in a field array by item_id

        Args:
            user_id: User ID
            field_name: Field name (e.g., 'interests')
            item_id: Item ID to update
            updated_item: Updated item data

        Returns:
            True if successful
        """
        try:
            # Build update fields (exclude id from update)
            update_fields = {}
            for key, value in updated_item.items():
                if key != 'id':
                    update_fields[f"{field_name}.$.{key}"] = value

            result = self.collection.update_one(
                {"user_id": user_id, f"{field_name}.id": item_id},
                {"$set": update_fields}
            )

            if result.modified_count > 0:
                logger.info(f"Successfully updated item {item_id} in '{field_name}' for user {user_id}")
                return True
            else:
                logger.warning(f"No item found to update: {item_id} in '{field_name}' for user {user_id}")
                return False
        except PyMongoError as e:
            logger.error(f"Failed to update item in '{field_name}' for user {user_id}: {e}")
            raise

    def delete_item(self, user_id: str, field_name: str, item_id: str) -> bool:
        """
        Delete an item from a field array by item_id

        Args:
            user_id: User ID
            field_name: Field name (e.g., 'interests')
            item_id: Item ID to delete

        Returns:
            True if successful
        """
        try:
            result = self.collection.update_one(
                {"user_id": user_id},
                {"$pull": {field_name: {"id": item_id}}}
            )

            if result.modified_count > 0:
                logger.info(f"Successfully deleted item {item_id} from '{field_name}' for user {user_id}")
                return True
            else:
                logger.warning(f"No item found to delete: {item_id} in '{field_name}' for user {user_id}")
                return False
        except PyMongoError as e:
            logger.error(f"Failed to delete item from '{field_name}' for user {user_id}: {e}")
            raise

    def delete(self, user_id: str) -> bool:
        """
        Delete user additional_profile

        Args:
            user_id: User ID

        Returns:
            True if deleted successfully
        """
        try:
            result = self.collection.delete_one({"user_id": user_id})

            if result.deleted_count > 0:
                logger.info(f"Successfully deleted additional_profile for user {user_id}")
                return True
            else:
                logger.warning(f"No additional_profile found to delete for user {user_id}")
                return False
        except PyMongoError as e:
            logger.error(f"Failed to delete additional_profile for user {user_id}: {e}")
            raise

    def get_missing_fields(self, user_id: str) -> list:
        """
        Get list of missing additional_profile fields for a user

        Args:
            user_id: User ID

        Returns:
            List of missing field names (fields that don't exist or are empty arrays)
        """
        # Define all expected additional_profile fields
        ALL_FIELDS = [
            'interests', 'skills', 'personality', 'social_context', 'learning_preferences'
        ]

        try:
            # Get current additional_profile
            profile = self.get(user_id)

            if not profile:
                # User doesn't exist, all fields are missing
                return ALL_FIELDS

            # Find missing fields (not exist or empty arrays)
            missing_fields = []
            for field in ALL_FIELDS:
                value = profile.get(field)
                # Field is missing if it doesn't exist or is an empty list/dict
                if value is None or (isinstance(value, (list, dict)) and len(value) == 0):
                    missing_fields.append(field)

            return missing_fields
        except PyMongoError as e:
            logger.error(f"Failed to get missing fields for user {user_id}: {e}")
            raise

    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")
