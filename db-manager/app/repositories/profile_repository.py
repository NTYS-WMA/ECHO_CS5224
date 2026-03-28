from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ProfileRepository:
    """Storage operations for user basic_info (PostgreSQL) and additional_profile (MongoDB)."""

    async def get_basic_profile(self, session: AsyncSession, user_id: str) -> dict[str, Any] | None:
        query = text(
            """
            SELECT *
            FROM user_profile.user_profile
            WHERE user_id = :user_id
            """
        )
        result = await session.execute(query, {"user_id": user_id})
        row = result.mappings().first()
        return dict(row) if row else None

    async def upsert_basic_profile(self, session: AsyncSession, user_id: str, basic_info: dict[str, Any]) -> None:
        query = text(
            """
            INSERT INTO user_profile.user_profile (
                user_id, name, nickname, english_name, birthday, gender, nationality,
                hometown, current_city, timezone, language, occupation, company,
                education_level, university, major
            )
            VALUES (
                :user_id, :name, :nickname, :english_name, :birthday, :gender, :nationality,
                :hometown, :current_city, :timezone, :language, :occupation, :company,
                :education_level, :university, :major
            )
            ON CONFLICT (user_id) DO UPDATE SET
                name = EXCLUDED.name,
                nickname = EXCLUDED.nickname,
                english_name = EXCLUDED.english_name,
                birthday = EXCLUDED.birthday,
                gender = EXCLUDED.gender,
                nationality = EXCLUDED.nationality,
                hometown = EXCLUDED.hometown,
                current_city = EXCLUDED.current_city,
                timezone = EXCLUDED.timezone,
                language = EXCLUDED.language,
                occupation = EXCLUDED.occupation,
                company = EXCLUDED.company,
                education_level = EXCLUDED.education_level,
                university = EXCLUDED.university,
                major = EXCLUDED.major,
                updated_at = NOW()
            """
        )
        payload = {
            "user_id": user_id,
            "name": basic_info.get("name"),
            "nickname": basic_info.get("nickname"),
            "english_name": basic_info.get("english_name"),
            "birthday": basic_info.get("birthday"),
            "gender": basic_info.get("gender"),
            "nationality": basic_info.get("nationality"),
            "hometown": basic_info.get("hometown"),
            "current_city": basic_info.get("current_city"),
            "timezone": basic_info.get("timezone"),
            "language": basic_info.get("language"),
            "occupation": basic_info.get("occupation"),
            "company": basic_info.get("company"),
            "education_level": basic_info.get("education_level"),
            "university": basic_info.get("university"),
            "major": basic_info.get("major"),
        }
        await session.execute(query, payload)

    async def get_additional_profile(
        self, mongo_db: AsyncIOMotorDatabase, collection_name: str, user_id: str
    ) -> dict[str, Any] | None:
        return await mongo_db[collection_name].find_one({"user_id": user_id}, {"_id": 0})

    async def upsert_additional_profile(
        self, mongo_db: AsyncIOMotorDatabase, collection_name: str, user_id: str, additional: dict[str, Any]
    ) -> None:
        await mongo_db[collection_name].update_one(
            {"user_id": user_id},
            {"$set": {"user_id": user_id, **additional}},
            upsert=True,
        )

    async def delete_basic_profile(self, session: AsyncSession, user_id: str) -> int:
        query = text(
            """
            DELETE FROM user_profile.user_profile
            WHERE user_id = :user_id
            """
        )
        result = await session.execute(query, {"user_id": user_id})
        return result.rowcount or 0

    async def delete_additional_profile(
        self, mongo_db: AsyncIOMotorDatabase, collection_name: str, user_id: str
    ) -> int:
        result = await mongo_db[collection_name].delete_one({"user_id": user_id})
        return result.deleted_count

    async def set_additional_profile_field(
        self,
        mongo_db: AsyncIOMotorDatabase,
        collection_name: str,
        user_id: str,
        field_name: str,
        value: Any,
    ) -> int:
        result = await mongo_db[collection_name].update_one(
            {"user_id": user_id},
            {"$set": {"user_id": user_id, field_name: value}},
            upsert=True,
        )
        return (result.modified_count or 0) + (1 if result.upserted_id else 0)

    async def delete_additional_profile_field(
        self,
        mongo_db: AsyncIOMotorDatabase,
        collection_name: str,
        user_id: str,
        field_name: str,
    ) -> int:
        result = await mongo_db[collection_name].update_one(
            {"user_id": user_id},
            {"$unset": {field_name: ""}},
        )
        return result.modified_count

    async def delete_additional_profile_item(
        self,
        mongo_db: AsyncIOMotorDatabase,
        collection_name: str,
        user_id: str,
        field_name: str,
        item_id: str,
    ) -> int:
        result = await mongo_db[collection_name].update_one(
            {"user_id": user_id},
            {"$pull": {field_name: {"id": item_id}}},
        )
        return result.modified_count
