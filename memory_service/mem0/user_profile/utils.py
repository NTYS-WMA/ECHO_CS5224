"""
Utility functions for UserProfile module
"""

import uuid
from datetime import datetime
from typing import Dict, List, Any


def generate_uuid() -> str:
    """Generate a UUID string"""
    return str(uuid.uuid4())


def get_current_timestamp() -> str:
    """Get current timestamp in ISO format"""
    return datetime.now().isoformat()


def map_uuids_to_ids(data: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[int, str]]:
    """
    Map UUIDs to integer IDs to prevent LLM hallucinations

    Args:
        data: Profile data with UUID ids

    Returns:
        tuple: (data_with_int_ids, id_mapping)
            - data_with_int_ids: Data with integer IDs (0, 1, 2, ...)
            - id_mapping: {int_id: uuid_string}
    """
    id_mapping = {}
    counter = 0

    def replace_ids(obj):
        nonlocal counter
        if isinstance(obj, dict):
            if 'id' in obj and obj['id']:
                # Map UUID to integer
                id_mapping[counter] = obj['id']
                obj['id'] = str(counter)
                counter += 1
            return {k: replace_ids(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [replace_ids(item) for item in obj]
        else:
            return obj

    data_with_int_ids = replace_ids(data.copy())
    return data_with_int_ids, id_mapping


def reverse_id_mapping(data: Dict[str, Any], id_mapping: Dict[int, str]) -> Dict[str, Any]:
    """
    Reverse integer IDs back to UUIDs

    Args:
        data: Data with integer IDs
        id_mapping: {int_id: uuid_string}

    Returns:
        Data with UUID ids restored
    """
    def restore_ids(obj):
        if isinstance(obj, dict):
            if 'id' in obj and obj['id'] is not None:
                int_id = int(obj['id']) if isinstance(obj['id'], str) else obj['id']
                if int_id in id_mapping:
                    obj['id'] = id_mapping[int_id]
            return {k: restore_ids(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [restore_ids(item) for item in obj]
        else:
            return obj

    return restore_ids(data.copy())


def merge_evidence(existing_evidence: List[Dict], new_evidence: List[Dict], max_count: int = 5) -> List[Dict]:
    """
    Merge existing and new evidence, keeping the most recent and relevant ones

    Args:
        existing_evidence: Existing evidence list
        new_evidence: New evidence to add
        max_count: Maximum number of evidence to keep

    Returns:
        Merged evidence list
    """
    # Combine all evidence
    all_evidence = existing_evidence + new_evidence

    # Sort by timestamp (newest first)
    all_evidence.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

    # Keep only the most recent max_count items
    return all_evidence[:max_count]


def validate_degree(degree: int, min_val: int = 1, max_val: int = 5) -> int:
    """
    Validate and clamp degree value to valid range

    Args:
        degree: Degree value to validate
        min_val: Minimum valid value (default 1)
        max_val: Maximum valid value (default 5)

    Returns:
        Clamped degree value
    """
    if degree < min_val:
        return min_val
    if degree > max_val:
        return max_val
    return degree


def format_messages_for_llm(messages: List[Dict[str, str]]) -> str:
    """
    Format messages list for LLM prompt

    Args:
        messages: List of message dicts with 'role' and 'content'

    Returns:
        Formatted string
    """
    formatted = []
    for msg in messages:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        formatted.append(f"{role.capitalize()}: {content}")
    return "\n".join(formatted)
