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
                hometown, current_city, timezone, language, school_name, grade, class_name
            )
            VALUES (
                :user_id, :name, :nickname, :english_name, :birthday, :gender, :nationality,
                :hometown, :current_city, :timezone, :language, :school_name, :grade, :class_name
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
                school_name = EXCLUDED.school_name,
                grade = EXCLUDED.grade,
                class_name = EXCLUDED.class_name,
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
            "school_name": basic_info.get("school_name"),
            "grade": basic_info.get("grade"),
            "class_name": basic_info.get("class_name"),
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

