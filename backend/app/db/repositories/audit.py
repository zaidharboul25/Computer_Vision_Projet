"""Dépôt d'accès aux données pour la collection 'audit_log' (Phase 4).

RÈGLE DE SÉCURITÉ (§12) :
Toutes les actions d'audit sont enregistrées de façon immuable.
Aucun secret (mot de passe, jeton JWT, clé d'API) n'est consigné dans les logs.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid
from pymongo import DESCENDING
from pymongo.asynchronous.database import AsyncDatabase


class AuditRepository:
    def __init__(self, db: AsyncDatabase):
        self.collection = db.audit_log

    async def log_action(
        self,
        action: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Enregistre une action d'audit assainie."""
        clean_details = dict(details or {})
        # Nettoyage des clés sensibles
        for sensitive_key in ["password", "token", "jwt", "secret", "authorization"]:
            clean_details.pop(sensitive_key, None)

        now = datetime.now(timezone.utc)
        doc = {
            "_id": str(uuid.uuid4()),
            "action": action,
            "user_id": user_id,
            "username": username,
            "at": now,
            "details": clean_details,
        }
        await self.collection.insert_one(doc)
        return doc

    async def list_logs(
        self,
        skip: int = 0,
        limit: int = 100,
        action: Optional[str] = None,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Liste paginée et filtrée des journaux d'audit (pour admin et auditor)."""
        query: Dict[str, Any] = {}
        if action:
            query["action"] = action
        if user_id:
            query["user_id"] = user_id
        if username:
            query["username"] = username
        if date_from or date_to:
            date_filter = {}
            if date_from:
                date_filter["$gte"] = date_from
            if date_to:
                date_filter["$lte"] = date_to
            query["at"] = date_filter

        total = await self.collection.count_documents(query)
        cursor = self.collection.find(query).sort("at", DESCENDING).skip(skip).limit(limit)
        items = await cursor.to_list(length=limit)
        return items, total
