"""Dépôt d'accès aux données pour la collection 'users'."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from pymongo.asynchronous.database import AsyncDatabase
from app.core.config import settings
from app.core.security import hash_password


class UserRepository:
    def __init__(self, db: AsyncDatabase):
        self.collection = db.users

    async def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one({"username": username})

    async def get_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one({"_id": user_id})

    async def create(self, username: str, password: str, role: str) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        user_doc = {
            "_id": str(uuid.uuid4()),
            "username": username,
            "password_hash": hash_password(password),
            "role": role,
            "active": True,
            "created_at": now,
            "last_login": None,
            "failed_attempts": 0,
            "locked_until": None,
        }
        await self.collection.insert_one(user_doc)
        return user_doc

    async def list_users(self, skip: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        cursor = self.collection.find({}).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def update(self, user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        result = await self.collection.find_one_and_update(
            {"_id": user_id},
            {"$set": updates},
            return_document=True,
        )
        return result

    async def record_login_attempt(self, username: str, success: bool) -> Tuple[bool, int]:
        """Met à jour les compteurs de tentative dans MongoDB.

        Retourne un tuple (just_locked, total_failed_attempts).
        """
        user = await self.get_by_username(username)
        if not user:
            return False, 0

        now = datetime.now(timezone.utc)
        if success:
            await self.collection.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "last_login": now.isoformat(),
                        "failed_attempts": 0,
                        "locked_until": None,
                    }
                },
            )
            return False, 0
        else:
            attempts = user.get("failed_attempts", 0) + 1
            just_locked = False
            updates: Dict[str, Any] = {"failed_attempts": attempts}
            if attempts >= settings.MAX_LOGIN_ATTEMPTS:
                locked_until = now + timedelta(minutes=settings.LOCKOUT_MINUTES)
                updates["locked_until"] = locked_until.isoformat()
                just_locked = True

            await self.collection.update_one({"_id": user["_id"]}, {"$set": updates})
            return just_locked, attempts

    async def is_locked(self, user: Dict[str, Any]) -> bool:
        locked_until_str = user.get("locked_until")
        if not locked_until_str:
            return False
        locked_until = datetime.fromisoformat(locked_until_str)
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < locked_until
