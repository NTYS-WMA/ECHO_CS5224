from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.repositories.profile_repository import ProfileRepository
from app.db.postgres import get_pg_session
from app.db.mongo import get_mongo_db

router = APIRouter()

# Pydantic models
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
    operations_performed: Dict[str, int] = {"added": 0, "updated": 0, "deleted": 0}
    errors: List[str] = []

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
    school_name: Optional[str] = None
    grade: Optional[str] = None
    class_name: Optional[str] = None

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
    family: Dict[str, Any] = {}
    friends: List[Dict[str, Any]] = []
    others: List[Dict[str, Any]] = []

class LearningPreferences(BaseModel):
    preferred_time: Optional[str] = None
    preferred_style: Optional[str] = None
    difficulty_level: Optional[str] = None

class AdditionalProfile(BaseModel):
    interests: List[InterestItem] = []
    skills: List[SkillItem] = []
    personality: List[PersonalityItem] = []
    social_context: SocialContext = SocialContext()
    learning_preferences: LearningPreferences = LearningPreferences()

class UserProfile(BaseModel):
    user_id: str
    basic_info: BasicInfo = BasicInfo()
    additional_profile: AdditionalProfile = AdditionalProfile()

class MissingFieldsResponse(BaseModel):
    user_id: str
    missing_fields: Dict[str, List[str]]

# Repository instance
profile_repo = ProfileRepository()

@router.post("/profile", response_model=ProfileUpdateResponse)
async def update_profile(request: ProfileUpdateRequest):
    """Extract and update user profile"""
    # TODO: Implement LLM-based profile extraction
    # For now, return mock response
    return ProfileUpdateResponse(
        success=True,
        basic_info_updated=True,
        additional_profile_updated=True,
        operations_performed={"added": 2, "updated": 0, "deleted": 0},
        errors=[]
    )

@router.get("/profile", response_model=UserProfile)
async def get_profile(
    user_id: str = Query(..., description="User ID"),
    fields: Optional[str] = Query("all", description="Comma-separated field names like interests,skills; return all if not specified"),
    evidence_limit: int = Query(5, description="Evidence count control: 0=no evidence, N=latest N items, -1=all")
):
    """Get user profile"""
    async with get_pg_session() as session:
        basic_info = await profile_repo.get_basic_profile(session, user_id)
    
    mongo_db = get_mongo_db()
    additional_profile_doc = await mongo_db.user_additional_profile.find_one({"user_id": user_id})
    
    # Parse basic_info
    basic_info_model = BasicInfo()
    if basic_info:
        for field in BasicInfo.__fields__:
            if field in basic_info:
                setattr(basic_info_model, field, basic_info[field])
    
    # Parse additional_profile
    additional_profile = AdditionalProfile()
    if additional_profile_doc:
        # TODO: Parse interests, skills, personality, social_context, learning_preferences
        pass
    
    return UserProfile(
        user_id=user_id,
        basic_info=basic_info_model,
        additional_profile=additional_profile
    )

@router.get("/profile/missing-fields", response_model=MissingFieldsResponse)
async def get_missing_fields(
    user_id: str = Query(..., description="User ID"),
    source: str = Query("both", description="pg (basic info) / mongo (additional profile) / both")
):
    """Query missing fields"""
    missing_basic = []
    missing_additional = []
    
    if source in ["pg", "both"]:
        async with get_pg_session() as session:
            basic_info = await profile_repo.get_basic_profile(session, user_id)
            if not basic_info:
                missing_basic = ["name", "nickname", "english_name", "birthday", "gender", 
                               "nationality", "hometown", "current_city", "timezone", 
                               "language", "school_name", "grade", "class_name"]
            else:
                # Check which fields are null/empty
                for field in ["name", "nickname", "english_name", "birthday", "gender", 
                            "nationality", "hometown", "current_city", "timezone", 
                            "language", "school_name", "grade", "class_name"]:
                    if not basic_info.get(field):
                        missing_basic.append(field)
    
    if source in ["mongo", "both"]:
        mongo_db = get_mongo_db()
        additional_profile = await mongo_db.user_additional_profile.find_one({"user_id": user_id})
        if not additional_profile:
            missing_additional = ["interests", "skills", "personality", "social_context", "learning_preferences"]
        else:
            # TODO: Check missing fields in additional profile
            pass
    
    return MissingFieldsResponse(
        user_id=user_id,
        missing_fields={
            "basic_info": missing_basic,
            "additional_profile": missing_additional
        }
    )