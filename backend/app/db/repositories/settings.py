"""Dépôt pour les paramètres système configurables par l'administrateur."""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pymongo.asynchronous.database import AsyncDatabase
from app.core.config import settings


class SettingsRepository:
    def __init__(self, db: AsyncDatabase):
        self.collection = db.settings

    async def get_settings(self) -> Dict[str, Any]:
        doc = await self.collection.find_one({"_id": "system_settings"})
        if not doc:
            doc = {
                "_id": "system_settings",
                "retention_days": settings.RETENTION_DAYS,
                "engines_enabled": settings.ENGINES_ENABLED,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await self.collection.insert_one(doc)
        return doc

    async def update_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        res = await self.collection.find_one_and_update(
            {"_id": "system_settings"},
            {"$set": updates},
            upsert=True,
            return_document=True,
        )
        return res

