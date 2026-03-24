"""
ProfileManager: Core pipeline for UserProfile extraction and updates

Implements the two-stage LLM pipeline:
1. Extract profile information from messages
2. Decide ADD/UPDATE/DELETE operations based on existing data
3. Execute database operations
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from mem0.user_profile.database import PostgresManager, MongoDBManager
from mem0.user_profile.prompts import EXTRACT_PROFILE_PROMPT, UPDATE_PROFILE_PROMPT
from mem0.user_profile.utils import (
    generate_uuid,
    get_current_timestamp,
    map_uuids_to_ids,
    reverse_id_mapping,
    merge_evidence,
    validate_degree,
    format_messages_for_llm,
)
from mem0.user_profile.user_profile_schema import (
    validate_family_relation,
    validate_relation_structure,
    validate_friends_structure,
    validate_others_structure,
    ARRAY_RELATIONS,
    SINGLE_RELATIONS,
)

logger = logging.getLogger(__name__)


class ProfileManager:
    """
    Core pipeline manager for UserProfile

    Handles the complete flow:
    1. Stage 1: LLM extracts profile info from messages
    2. Stage 2: Query existing data and map UUIDs
    3. Stage 3: LLM decides ADD/UPDATE/DELETE operations
    4. Stage 4: Execute database operations
    """

    def __init__(
        self,
        llm: Any,
        postgres: PostgresManager,
        mongodb: MongoDBManager,
    ):
        """
        Initialize ProfileManager

        Args:
            llm: LLM instance for making calls
            postgres: PostgresManager instance
            mongodb: MongoDBManager instance
        """
        self.llm = llm
        self.postgres = postgres
        self.mongodb = mongodb

    def _call_llm(self, prompt: str, response_format=None) -> str:
        """
        Call LLM with prompt

        Args:
            prompt: Prompt string
            response_format: Response format (e.g., {"type": "json_object"})

        Returns:
            LLM response string
        """
        try:
            # Use the LLM's generate_response method
            response = self.llm.generate_response(
                messages=[{"role": "user", "content": prompt}],
                response_format=response_format
            )
            return response
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        Parse JSON response from LLM

        Args:
            response: LLM response string

        Returns:
            Parsed dict or None if parsing fails
        """
        try:
            # Try to extract JSON from markdown code blocks
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                json_str = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                json_str = response[start:end].strip()
            else:
                json_str = response.strip()

            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response was: {response}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing response: {e}")
            return None

    def _add_timestamps_to_evidence(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add timestamps to evidence entries (backend-generated)

        LLM returns evidence without timestamps, we add them here

        Args:
            data: Extracted profile data from LLM

        Returns:
            Data with timestamps added to all evidence
        """
        current_time = get_current_timestamp()

        def process_item(obj):
            if isinstance(obj, dict):
                # If this object has 'evidence' field, add timestamps
                if 'evidence' in obj and isinstance(obj['evidence'], list):
                    for evidence_entry in obj['evidence']:
                        if isinstance(evidence_entry, dict) and 'timestamp' not in evidence_entry:
                            evidence_entry['timestamp'] = current_time

                # Recursively process all values
                return {k: process_item(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [process_item(item) for item in obj]
            else:
                return obj

        return process_item(data)

    def _clean_object_field(self, field_value: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean object fields (social_context, learning_preferences) by removing operation metadata

        Removes: id, event, evidence (these are only for list-based fields like interests/skills/personality)

        Args:
            field_value: The field value from LLM (may contain id, event, evidence)

        Returns:
            Cleaned field value without operation metadata
        """
        def clean_item(obj):
            if isinstance(obj, dict):
                # Remove id, event, evidence from objects
                return {
                    k: clean_item(v)
                    for k, v in obj.items()
                    if k not in ["id", "event", "evidence"]
                }
            elif isinstance(obj, list):
                return [clean_item(item) for item in obj]
            else:
                return obj

        return clean_item(field_value)

    def _deep_merge_social_context(
        self,
        existing: Dict[str, Any],
        new_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Deep merge social_context, preserving existing relationships

        Args:
            existing: Existing social_context from database
            new_data: New social_context from LLM (may contain ADD/UPDATE/DELETE events)

        Returns:
            Merged social_context
        """
        # Start with copy of existing data
        merged = existing.copy() if existing else {}

        # Process family relationships
        if "family" in new_data:
            if "family" not in merged:
                merged["family"] = {}

            for relation_key, relation_value in new_data["family"].items():
                # Validate family relation
                validation = validate_family_relation(relation_key)
                if not validation["valid"]:
                    logger.warning(f"Invalid family relation '{relation_key}': {validation['warning']}")
                    if validation["suggestion"] and validation["suggestion"] != "others":
                        # Auto-correct typo
                        logger.info(f"Auto-correcting '{relation_key}' to '{validation['suggestion']}'")
                        relation_key = validation["suggestion"]
                    else:
                        # Skip invalid relation
                        logger.warning(f"Skipping invalid relation: {relation_key}")
                        continue
                elif validation["warning"]:
                    logger.info(validation["warning"])

                # Check if this is an array relation (brother/sister/daughter/son/etc.)
                is_array_relation = relation_key in ARRAY_RELATIONS

                # Handle event-based operations for single object
                if isinstance(relation_value, dict) and "event" in relation_value:
                    event = relation_value["event"]

                    if event == "ADD":
                        # Add new relationship
                        cleaned = {k: v for k, v in relation_value.items() if k not in ["event", "id"]}
                        if is_array_relation:
                            # For array relations, append to existing array
                            if relation_key not in merged["family"]:
                                merged["family"][relation_key] = []
                            merged["family"][relation_key].append(cleaned)
                        else:
                            # For single relations, direct set
                            merged["family"][relation_key] = cleaned
                        logger.info(f"Added new family relationship: {relation_key}")

                    elif event == "UPDATE":
                        # Update existing relationship
                        cleaned = {k: v for k, v in relation_value.items() if k not in ["event", "id"]}
                        if is_array_relation:
                            # For array relations, update existing item or add if not exists
                            if relation_key not in merged["family"]:
                                merged["family"][relation_key] = []
                            # Try to find existing item by name
                            name_to_update = cleaned.get("name")
                            found = False
                            if name_to_update:
                                for item in merged["family"][relation_key]:
                                    if item.get("name") == name_to_update:
                                        # Merge info
                                        existing_info = item.get("info", [])
                                        new_info = cleaned.get("info", [])
                                        combined_info = existing_info.copy()
                                        for info_item in new_info:
                                            if info_item not in combined_info:
                                                combined_info.append(info_item)
                                        item["info"] = combined_info
                                        found = True
                                        break
                            if not found:
                                # Not found, add as new
                                merged["family"][relation_key].append(cleaned)
                        else:
                            # For single relations
                            if relation_key in merged["family"]:
                                # Merge info arrays
                                existing_info = merged["family"][relation_key].get("info", [])
                                new_info = cleaned.get("info", [])
                                # Combine and deduplicate info
                                combined_info = existing_info.copy()
                                for info_item in new_info:
                                    if info_item not in combined_info:
                                        combined_info.append(info_item)
                                cleaned["info"] = combined_info
                                # Update name if provided
                                if cleaned.get("name") is not None:
                                    merged["family"][relation_key]["name"] = cleaned["name"]
                                else:
                                    # Keep existing name if new name is null
                                    if "name" in merged["family"][relation_key]:
                                        cleaned["name"] = merged["family"][relation_key]["name"]
                                merged["family"][relation_key] = cleaned
                            else:
                                # Relation doesn't exist, treat as ADD
                                merged["family"][relation_key] = cleaned
                        logger.info(f"Updated family relationship: {relation_key}")

                    elif event == "DELETE":
                        # Delete relationship
                        if relation_key in merged["family"]:
                            del merged["family"][relation_key]
                            logger.info(f"Deleted family relationship: {relation_key}")
                # Handle array value (for array relations like brother, sister, daughter)
                elif isinstance(relation_value, list):
                    # Clean each item in the array
                    cleaned_array = []
                    for item in relation_value:
                        if isinstance(item, dict):
                            cleaned_item = {k: v for k, v in item.items() if k not in ["event", "id"]}
                            cleaned_array.append(cleaned_item)
                        else:
                            cleaned_array.append(item)
                    merged["family"][relation_key] = cleaned_array
                    logger.info(f"Set family relationship array: {relation_key} ({len(cleaned_array)} items)")
                else:
                    # No event, single object, direct replacement (backward compatibility)
                    merged["family"][relation_key] = relation_value
                    logger.info(f"Set family relationship (no event): {relation_key}")

        # Process friends (array, direct merge)
        if "friends" in new_data:
            if "friends" not in merged:
                merged["friends"] = []

            # Validate structure
            validation = validate_friends_structure(new_data["friends"])
            if not validation["valid"]:
                logger.warning(f"Invalid friends structure: {validation['errors']}")
            else:
                # Append new friends to existing
                merged["friends"].extend(new_data["friends"])
                logger.info(f"Added {len(new_data['friends'])} friends")

        # Process others (array, direct merge)
        if "others" in new_data:
            if "others" not in merged:
                merged["others"] = []

            # Validate structure
            validation = validate_others_structure(new_data["others"])
            if not validation["valid"]:
                logger.warning(f"Invalid others structure: {validation['errors']}")
            else:
                # Append new others to existing
                merged["others"].extend(new_data["others"])
                logger.info(f"Added {len(new_data['others'])} other relationships")

        return merged

    def extract_profile(self, messages: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        """
        Stage 1: Extract profile information from messages using LLM

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Extracted profile dict with basic_info and additional_profile (with timestamps added)
        """
        try:
            # Format messages for prompt
            formatted_messages = format_messages_for_llm(messages)

            # Build prompt (no current_time parameter anymore)
            prompt = EXTRACT_PROFILE_PROMPT.format(
                messages=formatted_messages
            )

            # Call LLM with JSON response format
            logger.info("Stage 1: Extracting profile information from messages")
            response = self._call_llm(prompt, response_format={"type": "json_object"})

            # Log raw response for debugging
            logger.debug(f"LLM raw response: {response[:500]}")  # First 500 chars

            # Parse response
            extracted_data = self._parse_json_response(response)

            if not extracted_data:
                logger.warning("Failed to extract profile information")
                logger.error(f"Could not parse response: {response[:1000]}")  # First 1000 chars
                return None

            # Add timestamps to evidence (backend-generated)
            extracted_data = self._add_timestamps_to_evidence(extracted_data)

            logger.info(f"Stage 1 complete: Extracted {len(extracted_data.get('additional_profile', {}))} fields")
            return extracted_data

        except Exception as e:
            logger.error(f"Stage 1 failed: {repr(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def query_existing_profile(self, user_id: str) -> Dict[str, Any]:
        """
        Stage 2: Query existing profile data and prepare for LLM

        Args:
            user_id: User ID

        Returns:
            Dict with basic_info and additional_profile (with integer IDs mapped)
        """
        try:
            logger.info(f"Stage 2: Querying existing profile for user {user_id}")

            # Query basic_info from PostgreSQL
            basic_info = self.postgres.get(user_id) or {}

            # Query additional_profile from MongoDB
            additional_profile = self.mongodb.get(user_id) or {}

            # Map UUIDs to integer IDs to prevent LLM hallucinations
            if additional_profile:
                additional_profile, id_mapping = map_uuids_to_ids(additional_profile)
            else:
                id_mapping = {}

            existing_profile = {
                "basic_info": basic_info,
                "additional_profile": additional_profile,
            }

            logger.info(f"Stage 2 complete: Found existing profile with {len(id_mapping)} items")
            return existing_profile, id_mapping

        except Exception as e:
            logger.error(f"Stage 2 failed: {e}")
            return {"basic_info": {}, "additional_profile": {}}, {}

    def decide_operations(
        self,
        extracted_info: Dict[str, Any],
        existing_profile: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Stage 3: LLM decides what operations to perform

        Args:
            extracted_info: Extracted profile information
            existing_profile: Existing profile data (with integer IDs and timestamps for reference)

        Returns:
            Operations dict with ADD/UPDATE/DELETE decisions (timestamps added by backend)
        """
        try:
            logger.info("Stage 3: Deciding operations (ADD/UPDATE/DELETE)")

            # Build prompt
            prompt = UPDATE_PROFILE_PROMPT.format(
                extracted_info=json.dumps(extracted_info, ensure_ascii=False, indent=2),
                existing_profile=json.dumps(existing_profile, ensure_ascii=False, indent=2),
            )

            # Call LLM with JSON response format
            response = self._call_llm(prompt, response_format={"type": "json_object"})

            # Parse response
            operations = self._parse_json_response(response)

            if not operations:
                logger.warning("Failed to decide operations")
                return None

            # Add timestamps to new evidence entries (backend-generated)
            operations = self._add_timestamps_to_evidence(operations)

            logger.info(f"Stage 3 complete: Decided operations")
            return operations

        except Exception as e:
            logger.error(f"Stage 3 failed: {e}")
            return None

    def execute_operations(
        self,
        user_id: str,
        operations: Dict[str, Any],
        id_mapping: Dict[int, str],
    ) -> Dict[str, Any]:
        """
        Stage 4: Execute database operations

        Args:
            user_id: User ID
            operations: Operations dict from Stage 3
            id_mapping: Mapping of integer IDs to UUIDs

        Returns:
            Result dict with success status and details
        """
        try:
            logger.info(f"Stage 4: Executing operations for user {user_id}")

            result = {
                "success": True,
                "basic_info_updated": False,
                "additional_profile_updated": False,
                "operations_performed": {
                    "added": 0,
                    "updated": 0,
                    "deleted": 0,
                },
                "errors": [],
            }

            # Execute basic_info update (simple UPSERT)
            if operations.get("basic_info"):
                try:
                    self.postgres.upsert(user_id, operations["basic_info"])
                    result["basic_info_updated"] = True
                    logger.info("Basic info updated successfully")
                except Exception as e:
                    error_msg = f"Failed to update basic_info: {e}"
                    logger.error(error_msg)
                    result["errors"].append(error_msg)
                    result["success"] = False

            # Execute additional_profile operations
            additional_profile = operations.get("additional_profile", {})

            if additional_profile:
                # Query current additional_profile
                current_profile = self.mongodb.get(user_id) or {}

                # Process each field
                for field_name, field_value in additional_profile.items():
                    # Handle social_context with deep merge
                    if field_name == "social_context" and isinstance(field_value, dict):
                        existing_social_context = current_profile.get("social_context", {})
                        merged_social_context = self._deep_merge_social_context(
                            existing_social_context,
                            field_value
                        )
                        current_profile["social_context"] = merged_social_context
                        result["operations_performed"]["updated"] += 1
                        logger.info("Updated social_context (deep merge)")
                        continue

                    # Handle other object fields (learning_preferences)
                    # These are direct replacements, no ADD/UPDATE/DELETE events
                    if isinstance(field_value, dict) and "preferred_time" in field_value:
                        # Clean object fields: remove id, event, evidence (these are for list-based fields only)
                        cleaned_value = self._clean_object_field(field_value)
                        current_profile[field_name] = cleaned_value
                        result["operations_performed"]["updated"] += 1
                        logger.info(f"Updated {field_name} (object field)")
                        continue

                    # Handle list fields (interests, skills, personality)
                    if not isinstance(field_value, list):
                        continue

                    items = field_value
                    # Get current field data
                    current_field = current_profile.get(field_name, [])

                    # Process each item
                    for item in items:
                        event = item.get("event")
                        item_id = item.get("id")

                        try:
                            if event == "ADD":
                                # Generate new UUID for the item
                                new_id = generate_uuid()
                                item["id"] = new_id

                                # Remove event field before adding
                                item_copy = {k: v for k, v in item.items() if k != "event"}

                                # Add to current field
                                current_field.append(item_copy)
                                result["operations_performed"]["added"] += 1
                                logger.info(f"Added new item to {field_name}: {new_id}")

                            elif event == "UPDATE":
                                # Map integer ID back to UUID
                                if item_id is not None:
                                    int_id = int(item_id) if isinstance(item_id, str) else item_id
                                    if int_id in id_mapping:
                                        uuid = id_mapping[int_id]

                                        # Find and update the item
                                        for existing_item in current_field:
                                            if existing_item.get("id") == uuid:
                                                # Merge evidence
                                                new_evidence = item.get("evidence", [])
                                                existing_evidence = existing_item.get("evidence", [])
                                                merged_evidence = merge_evidence(existing_evidence, new_evidence)

                                                # Update fields
                                                existing_item.update({
                                                    k: v for k, v in item.items()
                                                    if k not in ["id", "event"]
                                                })
                                                existing_item["evidence"] = merged_evidence

                                                # Validate degree
                                                if "degree" in existing_item:
                                                    existing_item["degree"] = validate_degree(existing_item["degree"])

                                                result["operations_performed"]["updated"] += 1
                                                logger.info(f"Updated item in {field_name}: {uuid}")
                                                break

                            elif event == "DELETE":
                                # Map integer ID back to UUID
                                if item_id is not None:
                                    int_id = int(item_id) if isinstance(item_id, str) else item_id
                                    if int_id in id_mapping:
                                        uuid = id_mapping[int_id]

                                        # Remove the item
                                        current_field = [
                                            item for item in current_field
                                            if item.get("id") != uuid
                                        ]
                                        result["operations_performed"]["deleted"] += 1
                                        logger.info(f"Deleted item from {field_name}: {uuid}")

                        except Exception as e:
                            error_msg = f"Failed to {event} item in {field_name}: {e}"
                            logger.error(error_msg)
                            result["errors"].append(error_msg)

                    # Update field in current profile
                    current_profile[field_name] = current_field

                # Upsert entire additional_profile
                try:
                    self.mongodb.upsert(user_id, current_profile)
                    result["additional_profile_updated"] = True
                    logger.info("Additional profile updated successfully")
                except Exception as e:
                    error_msg = f"Failed to update additional_profile: {e}"
                    logger.error(error_msg)
                    result["errors"].append(error_msg)
                    result["success"] = False

            logger.info(f"Stage 4 complete: {result['operations_performed']}")
            return result

        except Exception as e:
            logger.error(f"Stage 4 failed: {e}")
            return {
                "success": False,
                "errors": [str(e)],
            }

    def update_profile(
        self,
        user_id: str,
        messages: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """
        Complete pipeline: Extract, decide, and execute profile updates

        Args:
            user_id: User ID
            messages: Conversation messages

        Returns:
            Result dict with status and details
        """
        try:
            # Stage 1: Extract profile info
            extracted_info = self.extract_profile(messages)
            if not extracted_info:
                return {
                    "success": False,
                    "error": "Failed to extract profile information",
                }

            # Stage 2: Query existing profile
            existing_profile, id_mapping = self.query_existing_profile(user_id)

            # Stage 3: Decide operations
            operations = self.decide_operations(extracted_info, existing_profile)
            if not operations:
                return {
                    "success": False,
                    "error": "Failed to decide operations",
                }

            # Stage 4: Execute operations
            result = self.execute_operations(user_id, operations, id_mapping)

            return result

        except Exception as e:
            logger.error(f"Profile update pipeline failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }
