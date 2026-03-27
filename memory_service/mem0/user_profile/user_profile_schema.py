"""
User Profile Schema Definition and Validation

This module defines the schema for user profile data structures,
including allowed family relations, field formats, and validation logic.

Current persona: General adult users (ages 14-40)
- Core: spouse, father, mother, son, daughter
- Common: brother, sister, grandparents
- Extended: grandchildren, in-laws
"""

import logging
from typing import Dict, List, Any, Union

logger = logging.getLogger(__name__)

# ============================================================================
# Family Relations Definition
# ============================================================================

FAMILY_RELATIONS = {
    # Core relations (most important for adults)
    "core": [
        "spouse",
        "father",
        "mother",
        "son",
        "daughter",
    ],

    # Common relations
    "common": [
        "brother",
        "sister",
        "grandfather_paternal",
        "grandmother_paternal",
        "grandfather_maternal",
        "grandmother_maternal",
    ],

    # Extended relations
    "extended": [
        "grandson",
        "granddaughter",
        "father_in_law",
        "mother_in_law",
    ]
}

# All allowed family relations (flat list)
ALL_FAMILY_RELATIONS = (
    FAMILY_RELATIONS["core"] +
    FAMILY_RELATIONS["common"] +
    FAMILY_RELATIONS["extended"]
)

# Relations that can have multiple members (array type)
ARRAY_RELATIONS = [
    "brother",
    "sister",
    "son",
    "daughter",
    "grandson",
    "granddaughter",
]

# Relations that have exactly one member (object type)
SINGLE_RELATIONS = [
    "spouse",
    "father",
    "mother",
    "grandfather_paternal",
    "grandmother_paternal",
    "grandfather_maternal",
    "grandmother_maternal",
    "father_in_law",
    "mother_in_law",
]

# Note: collateral relatives (uncle, aunt, cousin) are NOT in family relations.
# They should be placed in social_context.others with an explicit 'relation' field
# to distinguish e.g. paternal uncle vs maternal uncle.

# ============================================================================
# Validation Functions
# ============================================================================

def validate_family_relation(relation_key: str) -> Dict[str, Any]:
    """
    Validate whether a family relation key is allowed.

    Args:
        relation_key: Relation field name (e.g. "father", "spouse")

    Returns:
        {
            "valid": bool,
            "suggestion": str | None,  # suggested correct key if invalid
            "warning": str | None
        }
    """
    # Check against allowed list
    if relation_key in ALL_FAMILY_RELATIONS:
        return {"valid": True, "suggestion": None, "warning": None}

    # Detect common incorrect usages
    common_mistakes = {
        "wife": "spouse",
        "husband": "spouse",
        "sibling": "brother or sister",
        "parent": "father or mother",
        "child": "son or daughter",
        "grandparent": "grandfather_* or grandmother_*",
        "uncle": "others",   # collateral relative → others
        "aunt": "others",    # collateral relative → others
        "cousin": "others",  # collateral relative → others
    }

    if relation_key in common_mistakes:
        suggestion = common_mistakes[relation_key]
        if suggestion == "others":
            return {
                "valid": False,
                "suggestion": suggestion,
                "warning": f"Invalid relation '{relation_key}' for family. "
                          f"Collateral relatives should be in 'social_context.others' with explicit 'relation' field."
            }
        else:
            return {
                "valid": False,
                "suggestion": suggestion,
                "warning": f"Invalid relation '{relation_key}', use '{suggestion}' instead"
            }

    # Detect common typos
    typo_suggestions = {
        "fatehr": "father",
        "motehr": "mother",
        "borther": "brother",
        "sisiter": "sister",
        "daugther": "daughter",
        "spose": "spouse",
        "granfather": "grandfather",
        "grandmohter": "grandmother",
    }

    if relation_key in typo_suggestions:
        return {
            "valid": False,
            "suggestion": typo_suggestions[relation_key],
            "warning": f"Possible typo: '{relation_key}' -> '{typo_suggestions[relation_key]}'"
        }

    # Not in allowed list
    return {
        "valid": False,
        "suggestion": None,
        "warning": f"Unknown family relation: '{relation_key}'. "
                  f"Should use allowed_relations or put in 'social_context.others'."
    }


def validate_relation_structure(relation_key: str, value: Union[Dict, List]) -> Dict[str, Any]:
    """
    Validate the data structure of a relation entry.

    Args:
        relation_key: Relation field name (e.g. "father", "brother")
        value: Relation data (object or array depending on relation type)

    Returns:
        {
            "valid": bool,
            "errors": [str]
        }
    """
    errors = []

    if relation_key in ARRAY_RELATIONS:
        if not isinstance(value, list):
            errors.append(f"'{relation_key}' should be an array, got {type(value).__name__}")
        else:
            for idx, item in enumerate(value):
                errors.extend(_validate_relation_item(relation_key, item, idx))
    else:
        # Should be a single object
        if isinstance(value, list):
            errors.append(f"'{relation_key}' should be an object, got array")
        else:
            errors.extend(_validate_relation_item(relation_key, value))

    return {"valid": len(errors) == 0, "errors": errors}


def _validate_relation_item(relation_key: str, item: Dict, index: int = None) -> List[str]:
    """
    Validate a single relation item's fields.

    Args:
        relation_key: Relation field name
        item: Relation data object
        index: Array index if this item is part of an array relation

    Returns:
        List of error strings
    """
    errors = []
    prefix = f"{relation_key}[{index}]" if index is not None else relation_key

    # Check required fields
    if "name" not in item:
        errors.append(f"{prefix}: missing 'name' field")
    if "info" not in item:
        errors.append(f"{prefix}: missing 'info' field")

    # Check field types
    if "name" in item:
        if item["name"] is not None and not isinstance(item["name"], str):
            errors.append(f"{prefix}.name: should be string or null, got {type(item['name']).__name__}")

    if "info" in item:
        if not isinstance(item["info"], list):
            errors.append(f"{prefix}.info: should be array, got {type(item['info']).__name__}")
        else:
            for i, info_item in enumerate(item["info"]):
                if not isinstance(info_item, str):
                    errors.append(f"{prefix}.info[{i}]: should be string, got {type(info_item).__name__}")

    # Check for unexpected fields (family members should only have name and info)
    allowed_fields = {"name", "info"}
    extra_fields = set(item.keys()) - allowed_fields
    if extra_fields:
        errors.append(f"{prefix}: unexpected fields {extra_fields}")

    return errors


def validate_friends_structure(friends: List) -> Dict[str, Any]:
    """
    Validate the data structure of the friends list.

    Args:
        friends: List of friend entries

    Returns:
        {
            "valid": bool,
            "errors": [str]
        }
    """
    errors = []

    if not isinstance(friends, list):
        errors.append(f"friends should be an array, got {type(friends).__name__}")
        return {"valid": False, "errors": errors}

    for idx, friend in enumerate(friends):
        if not isinstance(friend, dict):
            errors.append(f"friends[{idx}]: should be an object, got {type(friend).__name__}")
            continue

        if "name" not in friend:
            errors.append(f"friends[{idx}]: missing 'name' field")
        if "info" not in friend:
            errors.append(f"friends[{idx}]: missing 'info' field")

        if "name" in friend:
            if friend["name"] is not None and not isinstance(friend["name"], str):
                errors.append(f"friends[{idx}].name: should be string or null")

        if "info" in friend:
            if not isinstance(friend["info"], list):
                errors.append(f"friends[{idx}].info: should be array")

        allowed_fields = {"name", "info"}
        extra_fields = set(friend.keys()) - allowed_fields
        if extra_fields:
            errors.append(f"friends[{idx}]: unexpected fields {extra_fields}")

    return {"valid": len(errors) == 0, "errors": errors}


def validate_others_structure(others: List) -> Dict[str, Any]:
    """
    Validate the data structure of the others list (collateral relatives, teachers, colleagues, etc.).

    Args:
        others: List of other-relation entries

    Returns:
        {
            "valid": bool,
            "errors": [str]
        }
    """
    errors = []

    if not isinstance(others, list):
        errors.append(f"others should be an array, got {type(others).__name__}")
        return {"valid": False, "errors": errors}

    for idx, other in enumerate(others):
        if not isinstance(other, dict):
            errors.append(f"others[{idx}]: should be an object, got {type(other).__name__}")
            continue

        if "name" not in other:
            errors.append(f"others[{idx}]: missing 'name' field")
        if "relation" not in other:
            errors.append(f"others[{idx}]: missing 'relation' field")
        if "info" not in other:
            errors.append(f"others[{idx}]: missing 'info' field")

        if "name" in other:
            if other["name"] is not None and not isinstance(other["name"], str):
                errors.append(f"others[{idx}].name: should be string or null")

        if "relation" in other:
            if not isinstance(other["relation"], str):
                errors.append(f"others[{idx}].relation: should be string")

        if "info" in other:
            if not isinstance(other["info"], list):
                errors.append(f"others[{idx}].info: should be array")

        allowed_fields = {"name", "relation", "info"}
        extra_fields = set(other.keys()) - allowed_fields
        if extra_fields:
            errors.append(f"others[{idx}]: unexpected fields {extra_fields}")

    return {"valid": len(errors) == 0, "errors": errors}
