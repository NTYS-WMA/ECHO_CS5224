"""
User Profile Schema Definition and Validation

This module defines the schema for user profile data structures,
including allowed family relations, field formats, and validation logic.

用户画像调整指南
================

当前用户画像：小孩
- Core: father, mother
- Common: brother, sister, grandparents
- Extended: spouse, children, grandchildren

如果未来调整为成年人用户画像，需要修改：
1. 本文件的 FAMILY_RELATIONS 定义
2. extraction_rules.yaml 中的 allowed_relations
3. prompts.py 中的示例（如果有）
4. DEV_GUIDE_UserProfile.md 文档

成年人用户画像的分类示例：
- Core: spouse
- Common: father, mother, son, daughter
- Extended: brother, sister, grandparents, grandchildren
"""

import logging
from typing import Dict, List, Any, Union

logger = logging.getLogger(__name__)

# ============================================================================
# Family Relations Definition
# ============================================================================

FAMILY_RELATIONS = {
    # 核心关系（当前用户画像：小孩）
    "core": [
        "father",          # 父亲
        "mother",          # 母亲
    ],

    # 常见关系（当前用户画像：小孩）
    "common": [
        "brother",                    # 兄弟（可多个）
        "sister",                     # 姐妹（可多个）
        "grandfather_paternal",       # 爷爷
        "grandmother_paternal",       # 奶奶
        "grandfather_maternal",       # 外公
        "grandmother_maternal",       # 外婆
    ],

    # 扩展关系（当前用户画像：小孩，不太常见）
    "extended": [
        "spouse",          # 配偶（如果是成年人场景）
        "son",             # 儿子（可多个）
        "daughter",        # 女儿（可多个）
        "grandson",        # 孙子（可多个）
        "granddaughter",   # 孙女（可多个）
    ]
}

# 所有允许的 family 关系（扁平化列表）
ALL_FAMILY_RELATIONS = (
    FAMILY_RELATIONS["core"] +
    FAMILY_RELATIONS["common"] +
    FAMILY_RELATIONS["extended"]
)

# 可多个的关系（数组类型）
ARRAY_RELATIONS = [
    "brother",
    "sister",
    "son",
    "daughter",
    "grandson",
    "granddaughter"
]

# 单个的关系（对象类型）
SINGLE_RELATIONS = [
    "father",
    "mother",
    "spouse",
    "grandfather_paternal",
    "grandmother_paternal",
    "grandfather_maternal",
    "grandmother_maternal"
]

# 注：以下关系已移除，应放到 social_context.others：
# - uncle (叔叔/舅舅/姑父等) - 旁系亲属
# - aunt (阿姨/姑姑/舅妈等) - 旁系亲属
# - cousin (表兄弟姐妹/堂兄弟姐妹) - 旁系亲属
# 原因：这些关系需要 relation 字段来精确描述（如"姑姑" vs "阿姨"）

# ============================================================================
# Validation Functions
# ============================================================================

def validate_family_relation(relation_key: str) -> Dict[str, Any]:
    """
    验证 family 关系字段名是否有效

    Args:
        relation_key: 关系字段名（如 "father", "mother"）

    Returns:
        {
            "valid": bool,              # 是否有效
            "suggestion": str | None,   # 建议使用的字段名
            "warning": str | None       # 警告信息
        }
    """
    # 检查是否在允许列表中
    if relation_key in ALL_FAMILY_RELATIONS:
        return {"valid": True, "suggestion": None, "warning": None}

    # 检测常见错误用法
    common_mistakes = {
        "wife": "spouse",
        "husband": "spouse",
        "sibling": "brother or sister",
        "parent": "father or mother",
        "child": "son or daughter",
        "grandparent": "grandfather_* or grandmother_*",
        "uncle": "others",  # 旁系亲属应放到 others
        "aunt": "others",   # 旁系亲属应放到 others
        "cousin": "others", # 旁系亲属应放到 others
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

    # 检测常见 typo
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
            "warning": f"Possible typo: '{relation_key}' → '{typo_suggestions[relation_key]}'"
        }

    # 不在允许列表中
    return {
        "valid": False,
        "suggestion": None,
        "warning": f"Unknown family relation: '{relation_key}'. "
                  f"Should use allowed_relations or put in 'social_context.others'."
    }


def validate_relation_structure(relation_key: str, value: Union[Dict, List]) -> Dict[str, Any]:
    """
    验证关系的数据结构是否正确

    Args:
        relation_key: 关系字段名（如 "father", "brother"）
        value: 关系数据（对象或数组）

    Returns:
        {
            "valid": bool,      # 是否有效
            "errors": [str]     # 错误列表
        }
    """
    errors = []

    # 检查是否应该是数组
    if relation_key in ARRAY_RELATIONS:
        if not isinstance(value, list):
            errors.append(f"'{relation_key}' should be an array, got {type(value).__name__}")
        else:
            for idx, item in enumerate(value):
                errors.extend(_validate_relation_item(relation_key, item, idx))
    else:
        # 应该是单个对象
        if isinstance(value, list):
            errors.append(f"'{relation_key}' should be an object, got array")
        else:
            errors.extend(_validate_relation_item(relation_key, value))

    return {"valid": len(errors) == 0, "errors": errors}


def _validate_relation_item(relation_key: str, item: Dict, index: int = None) -> List[str]:
    """
    验证单个关系项的字段

    Args:
        relation_key: 关系字段名
        item: 关系数据对象
        index: 如果是数组中的项，索引号

    Returns:
        错误列表
    """
    errors = []
    prefix = f"{relation_key}[{index}]" if index is not None else relation_key

    # 检查必需字段
    if "name" not in item:
        errors.append(f"{prefix}: missing 'name' field")
    if "info" not in item:
        errors.append(f"{prefix}: missing 'info' field")

    # 检查字段类型
    if "name" in item:
        if item["name"] is not None and not isinstance(item["name"], str):
            errors.append(f"{prefix}.name: should be string or null, got {type(item['name']).__name__}")

    if "info" in item:
        if not isinstance(item["info"], list):
            errors.append(f"{prefix}.info: should be array, got {type(item['info']).__name__}")
        else:
            # 检查 info 数组中的每个元素是否为字符串
            for i, info_item in enumerate(item["info"]):
                if not isinstance(info_item, str):
                    errors.append(f"{prefix}.info[{i}]: should be string, got {type(info_item).__name__}")

    # 检查是否有多余字段（family 成员只应有 name 和 info）
    allowed_fields = {"name", "info"}
    extra_fields = set(item.keys()) - allowed_fields
    if extra_fields:
        errors.append(f"{prefix}: unexpected fields {extra_fields}")

    return errors


def validate_friends_structure(friends: List) -> Dict[str, Any]:
    """
    验证 friends 的数据结构

    Args:
        friends: 朋友列表

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

        # 检查必需字段
        if "name" not in friend:
            errors.append(f"friends[{idx}]: missing 'name' field")
        if "info" not in friend:
            errors.append(f"friends[{idx}]: missing 'info' field")

        # 检查字段类型
        if "name" in friend:
            if friend["name"] is not None and not isinstance(friend["name"], str):
                errors.append(f"friends[{idx}].name: should be string or null")

        if "info" in friend:
            if not isinstance(friend["info"], list):
                errors.append(f"friends[{idx}].info: should be array")

        # 检查是否有多余字段
        allowed_fields = {"name", "info"}
        extra_fields = set(friend.keys()) - allowed_fields
        if extra_fields:
            errors.append(f"friends[{idx}]: unexpected fields {extra_fields}")

    return {"valid": len(errors) == 0, "errors": errors}


def validate_others_structure(others: List) -> Dict[str, Any]:
    """
    验证 others 的数据结构

    Args:
        others: 其他关系列表

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

        # 检查必需字段
        if "name" not in other:
            errors.append(f"others[{idx}]: missing 'name' field")
        if "relation" not in other:
            errors.append(f"others[{idx}]: missing 'relation' field")
        if "info" not in other:
            errors.append(f"others[{idx}]: missing 'info' field")

        # 检查字段类型
        if "name" in other:
            if other["name"] is not None and not isinstance(other["name"], str):
                errors.append(f"others[{idx}].name: should be string or null")

        if "relation" in other:
            if not isinstance(other["relation"], str):
                errors.append(f"others[{idx}].relation: should be string")

        if "info" in other:
            if not isinstance(other["info"], list):
                errors.append(f"others[{idx}].info: should be array")

        # 检查是否有多余字段
        allowed_fields = {"name", "relation", "info"}
        extra_fields = set(other.keys()) - allowed_fields
        if extra_fields:
            errors.append(f"others[{idx}]: unexpected fields {extra_fields}")

    return {"valid": len(errors) == 0, "errors": errors}
