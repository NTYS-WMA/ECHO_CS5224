import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.db.mongo import get_mongo_db
from app.db.postgres import get_pg_session
from app.repositories.profile_repository import ProfileRepository

router = APIRouter()


class Message(BaseModel):
    role: str
    content: str


class ProfileUpdateRequest(BaseModel):
    messages: List[Message]
    user_id: str


class ProfileUpdateResponse(BaseModel):
    success: bool
    basic_info_updated: bool = False
    additional_profile_updated: bool = False
    operations_performed: Dict[str, int] = Field(default_factory=lambda: {"added": 0, "updated": 0, "deleted": 0})
    errors: List[str] = Field(default_factory=list)


class BasicInfo(BaseModel):
    name: Optional[str] = None
    nickname: Optional[str] = None
    english_name: Optional[str] = None
    birthday: Optional[str] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    hometown: Optional[str] = None
    current_city: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    occupation: Optional[str] = None
    company: Optional[str] = None
    education_level: Optional[str] = None
    university: Optional[str] = None
    major: Optional[str] = None


class InterestItem(BaseModel):
    id: str
    name: str
    degree: int
    evidence: List[Dict[str, Any]]


class SkillItem(BaseModel):
    id: str
    name: str
    degree: int
    evidence: List[Dict[str, Any]]


class PersonalityItem(BaseModel):
    id: str
    name: str
    degree: int
    evidence: List[Dict[str, Any]]


class SocialContext(BaseModel):
    family: Dict[str, Any] = Field(default_factory=dict)
    friends: List[Dict[str, Any]] = Field(default_factory=list)
    others: List[Dict[str, Any]] = Field(default_factory=list)


class LearningPreferences(BaseModel):
    preferred_time: Optional[str] = None
    preferred_style: Optional[str] = None
    difficulty_level: Optional[str] = None


class AdditionalProfile(BaseModel):
    interests: List[InterestItem] = Field(default_factory=list)
    skills: List[SkillItem] = Field(default_factory=list)
    personality: List[PersonalityItem] = Field(default_factory=list)
    social_context: SocialContext = Field(default_factory=SocialContext)
    learning_preferences: LearningPreferences = Field(default_factory=LearningPreferences)


class UserProfile(BaseModel):
    user_id: str
    basic_info: BasicInfo = Field(default_factory=BasicInfo)
    additional_profile: AdditionalProfile = Field(default_factory=AdditionalProfile)


class MissingFieldsResponse(BaseModel):
    user_id: str
    missing_fields: Dict[str, List[str]]


class BasicInfoUpdateRequest(BaseModel):
    data: BasicInfo


class AdditionalProfileUpdateRequest(BaseModel):
    data: Dict[str, Any]


profile_repo = ProfileRepository()
BASIC_INFO_FIELDS = [
    "name",
    "nickname",
    "english_name",
    "birthday",
    "gender",
    "nationality",
    "hometown",
    "current_city",
    "timezone",
    "language",
    "occupation",
    "company",
    "education_level",
    "university",
    "major",
]
ADDITIONAL_FIELDS = ["interests", "skills", "personality", "social_context", "learning_preferences"]


def _model_fields(model_cls: type[BaseModel]) -> list[str]:
    if hasattr(model_cls, "model_fields"):
        return list(model_cls.model_fields.keys())
    return list(model_cls.__fields__.keys())


def _model_dump(model: BaseModel, exclude_none: bool = False) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=exclude_none)
    return model.dict(exclude_none=exclude_none)


def _messages_text(messages: List[Message]) -> str:
    return "\n".join([m.content for m in messages if m.content]).strip()


def _extract_basic_info(messages: List[Message]) -> dict[str, Any]:
    text = _messages_text(messages)
    lowered = text.lower()
    basic: dict[str, Any] = {}

    patterns = {
        "name": [r"my name is\s+([A-Za-z\s\-']+)", r"i am\s+([A-Za-z\s\-']+)"],
        "nickname": [r"you can call me\s+([A-Za-z\s\-']+)"],
        "hometown": [r"i'm from\s+([A-Za-z\s\-']+)", r"i am from\s+([A-Za-z\s\-']+)"],
        "current_city": [r"i live in\s+([A-Za-z\s\-']+)", r"based in\s+([A-Za-z\s\-']+)"],
        "occupation": [r"i work as\s+a[n]?\s+([A-Za-z\s\-']+)", r"i am a[n]?\s+([A-Za-z\s\-']+)"],
        "company": [r"i work at\s+([A-Za-z0-9\s\-'.&]+)"],
        "major": [r"major(ed)? in\s+([A-Za-z\s\-']+)"],
        "university": [r"stud(y|ied) at\s+([A-Za-z0-9\s\-'.&]+)", r"graduated from\s+([A-Za-z0-9\s\-'.&]+)"],
        "language": [r"i speak\s+([A-Za-z\s,]+)"],
        "timezone": [r"timezone\s+is\s+([A-Za-z_\-/+0-9:]+)"],
        "birthday": [r"birthday\s+is\s+([0-9]{4}-[0-9]{2}-[0-9]{2})"],
    }

    for field, field_patterns in patterns.items():
        for p in field_patterns:
            match = re.search(p, lowered)
            if match:
                value = match.group(match.lastindex or 1).strip()
                basic[field] = value.title() if field in {"name", "nickname", "hometown", "current_city", "occupation", "major"} else value
                break

    if "male" in lowered:
        basic["gender"] = "male"
    elif "female" in lowered:
        basic["gender"] = "female"

    for level in ["phd", "doctor", "master", "bachelor", "high school"]:
        if level in lowered:
            basic["education_level"] = "phd" if level in {"phd", "doctor"} else level
            break

    return basic


def _extract_additional_profile(messages: List[Message]) -> dict[str, Any]:
    additional: dict[str, Any] = {
        "interests": [],
        "skills": [],
        "personality": [],
    }

    for msg in messages:
        if not msg.content:
            continue

        content = msg.content.strip()
        lowered = content.lower()
        evidence = [{"text": content}]

        interest_match = re.search(r"i like\s+([a-z\s,]+)", lowered)
        if interest_match:
            interests = [i.strip() for i in interest_match.group(1).split(",") if i.strip()]
            for it in interests:
                additional["interests"].append(
                    {
                        "id": f"interest-{it.replace(' ', '-')}",
                        "name": it,
                        "degree": 3,
                        "evidence": evidence,
                    }
                )

        skill_match = re.search(r"i (?:am good at|can|know)\s+([a-z\s,]+)", lowered)
        if skill_match:
            skills = [s.strip() for s in skill_match.group(1).split(",") if s.strip()]
            for sk in skills:
                additional["skills"].append(
                    {
                        "id": f"skill-{sk.replace(' ', '-')}",
                        "name": sk,
                        "degree": 3,
                        "evidence": evidence,
                    }
                )

        for trait in ["curious", "patient", "outgoing", "introvert", "extrovert", "diligent", "creative"]:
            if trait in lowered:
                additional["personality"].append(
                    {
                        "id": f"personality-{trait}",
                        "name": trait,
                        "degree": 3,
                        "evidence": evidence,
                    }
                )

        if "prefer to study" in lowered:
            learning_preferences = additional.get("learning_preferences")
            if not isinstance(learning_preferences, dict):
                learning_preferences = {}
            learning_preferences["preferred_style"] = content
            additional["learning_preferences"] = learning_preferences

    return additional


def _merge_additional(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing or {})

    for array_field in ["interests", "skills", "personality"]:
        by_id: dict[str, dict[str, Any]] = {}
        for item in merged.get(array_field, []) or []:
            if isinstance(item, dict) and item.get("id"):
                by_id[item["id"]] = item
        for item in incoming.get(array_field, []) or []:
            if isinstance(item, dict) and item.get("id"):
                by_id[item["id"]] = item
        merged[array_field] = list(by_id.values())

    existing_sc = merged.get("social_context") if isinstance(merged.get("social_context"), dict) else {}
    incoming_sc = incoming.get("social_context") if isinstance(incoming.get("social_context"), dict) else {}
    merged["social_context"] = {**existing_sc, **incoming_sc}

    existing_lp = merged.get("learning_preferences") if isinstance(merged.get("learning_preferences"), dict) else {}
    incoming_lp = incoming.get("learning_preferences") if isinstance(incoming.get("learning_preferences"), dict) else {}
    merged["learning_preferences"] = {**existing_lp, **incoming_lp}

    merged["user_id"] = merged.get("user_id") or incoming.get("user_id")
    return merged


@router.post("/profile", response_model=ProfileUpdateResponse)
async def update_profile(request: ProfileUpdateRequest):
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")

    basic_info = _extract_basic_info(request.messages)
    additional = _extract_additional_profile(request.messages)

    basic_info_updated = bool(basic_info)
    additional_profile_updated = any(
        bool(additional.get(field)) for field in ADDITIONAL_FIELDS
    )

    async with get_pg_session() as session:
        if basic_info_updated:
            await profile_repo.upsert_basic_profile(session, request.user_id, basic_info)
        await session.commit()

    mongo_db = get_mongo_db()
    collection_name = "user_additional_profile"
    existing_doc = await profile_repo.get_additional_profile(mongo_db, collection_name, request.user_id)
    merged_additional = _merge_additional(existing_doc, {"user_id": request.user_id, **additional})
    if additional_profile_updated:
        await profile_repo.upsert_additional_profile(mongo_db, collection_name, request.user_id, merged_additional)

    added_count = len(additional.get("interests", [])) + len(additional.get("skills", [])) + len(additional.get("personality", []))
    return ProfileUpdateResponse(
        success=True,
        basic_info_updated=basic_info_updated,
        additional_profile_updated=additional_profile_updated,
        operations_performed={"added": added_count, "updated": 0, "deleted": 0},
        errors=[],
    )


@router.get("/profile", response_model=UserProfile)
async def get_profile(
    user_id: str = Query(..., description="User ID"),
    fields: Optional[str] = Query("all", description="Comma-separated field names like interests,skills; return all if not specified"),
    evidence_limit: int = Query(5, description="Evidence count control: 0=no evidence, N=latest N items, -1=all"),
):
    async with get_pg_session() as session:
        basic_info = await profile_repo.get_basic_profile(session, user_id)

    mongo_db = get_mongo_db()
    additional_profile_doc = await profile_repo.get_additional_profile(mongo_db, "user_additional_profile", user_id)

    basic_info_model = BasicInfo()
    if basic_info:
        for field in _model_fields(BasicInfo):
            if field in basic_info:
                setattr(basic_info_model, field, basic_info[field])

    additional_profile_model = AdditionalProfile()
    if additional_profile_doc:
        doc = dict(additional_profile_doc)

        if fields and fields != "all":
            selected_fields = {f.strip() for f in fields.split(",") if f.strip()}
            doc = {k: v for k, v in doc.items() if k in selected_fields or k == "user_id"}

        if evidence_limit >= 0:
            for field_name in ["interests", "skills", "personality"]:
                items = doc.get(field_name)
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict) and isinstance(item.get("evidence"), list):
                            if evidence_limit == 0:
                                item["evidence"] = []
                            else:
                                item["evidence"] = item["evidence"][:evidence_limit]

        for field in _model_fields(AdditionalProfile):
            if field in doc:
                setattr(additional_profile_model, field, doc[field])

    return UserProfile(
        user_id=user_id,
        basic_info=basic_info_model,
        additional_profile=additional_profile_model,
    )


@router.get("/profile/missing-fields", response_model=MissingFieldsResponse)
async def get_missing_fields(
    user_id: str = Query(..., description="User ID"),
    source: str = Query("both", description="pg (basic info) / mongo (additional profile) / both"),
):
    if source not in ["pg", "mongo", "both"]:
        raise HTTPException(status_code=400, detail="source must be one of: pg, mongo, both")

    missing_basic: list[str] = []
    missing_additional: list[str] = []

    if source in ["pg", "both"]:
        async with get_pg_session() as session:
            basic_info = await profile_repo.get_basic_profile(session, user_id)

        if not basic_info:
            missing_basic = BASIC_INFO_FIELDS.copy()
        else:
            for field in BASIC_INFO_FIELDS:
                if not basic_info.get(field):
                    missing_basic.append(field)

    if source in ["mongo", "both"]:
        mongo_db = get_mongo_db()
        additional_profile = await profile_repo.get_additional_profile(mongo_db, "user_additional_profile", user_id)

        if not additional_profile:
            missing_additional = ADDITIONAL_FIELDS.copy()
        else:
            for field in ADDITIONAL_FIELDS:
                value = additional_profile.get(field)
                if value is None:
                    missing_additional.append(field)
                    continue
                if isinstance(value, (list, dict)) and len(value) == 0:
                    missing_additional.append(field)

    return MissingFieldsResponse(
        user_id=user_id,
        missing_fields={
            "basic_info": missing_basic,
            "additional_profile": missing_additional,
        },
    )


@router.put("/profile/basic-info")
async def update_basic_info(
    user_id: str = Query(..., description="User ID"),
    request: BasicInfoUpdateRequest = ...,
):
    payload = _model_dump(request.data, exclude_none=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No basic_info fields provided")

    async with get_pg_session() as session:
        await profile_repo.upsert_basic_profile(session, user_id, payload)
        await session.commit()

    return {"success": True, "user_id": user_id, "updated_fields": list(payload.keys())}


@router.put("/profile/additional-profile")
async def update_additional_profile(
    user_id: str = Query(..., description="User ID"),
    request: AdditionalProfileUpdateRequest = ...,
):
    if not request.data:
        raise HTTPException(status_code=400, detail="No additional_profile fields provided")

    mongo_db = get_mongo_db()
    collection_name = "user_additional_profile"
    existing_doc = await profile_repo.get_additional_profile(mongo_db, collection_name, user_id)
    merged = _merge_additional(existing_doc, {"user_id": user_id, **request.data})
    await profile_repo.upsert_additional_profile(mongo_db, collection_name, user_id, merged)

    return {"success": True, "user_id": user_id, "updated_fields": list(request.data.keys())}


@router.delete("/profile")
async def delete_profile(user_id: str = Query(..., description="User ID")):
    async with get_pg_session() as session:
        deleted_basic = await profile_repo.delete_basic_profile(session, user_id)
        await session.commit()

    mongo_db = get_mongo_db()
    deleted_additional = await profile_repo.delete_additional_profile(
        mongo_db, "user_additional_profile", user_id
    )

    return {
        "success": True,
        "user_id": user_id,
        "basic_info_deleted": bool(deleted_basic),
        "additional_profile_deleted": bool(deleted_additional),
    }


@router.delete("/profile/additional-profile/{field_name}/{item_id}")
async def delete_additional_profile_item(
    field_name: str,
    item_id: str,
    user_id: str = Query(..., description="User ID"),
):
    if field_name not in {"interests", "skills", "personality"}:
        raise HTTPException(status_code=400, detail="Unsupported array field for item delete")

    mongo_db = get_mongo_db()
    deleted = await profile_repo.delete_additional_profile_item(
        mongo_db,
        "user_additional_profile",
        user_id,
        field_name,
        item_id,
    )
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Profile item not found")
    return {"success": True, "user_id": user_id, "field": field_name, "item_id": item_id}


@router.delete("/profile/additional-profile/{field_name}")
async def delete_additional_profile_field(
    field_name: str,
    user_id: str = Query(..., description="User ID"),
):
    if field_name not in set(ADDITIONAL_FIELDS):
        raise HTTPException(status_code=400, detail="Unsupported additional profile field")

    mongo_db = get_mongo_db()
    deleted = await profile_repo.delete_additional_profile_field(
        mongo_db,
        "user_additional_profile",
        user_id,
        field_name,
    )
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Profile field not found")
    return {"success": True, "user_id": user_id, "field": field_name}
