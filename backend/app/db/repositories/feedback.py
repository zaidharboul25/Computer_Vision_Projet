"""Dépôt MongoDB pour la collection 'feedback' (Phase 4).

RÈGLE D'HISTORIQUE EN AJOUT SEUL (§6.5, AC-07) :
Chaque décision humaine est persistée comme un enregistrement immuable distinct.
La décision courante d'une région est la plus récente selon l'ordre (created_at DESC, _id DESC).
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from pymongo import DESCENDING, ReturnDocument
from app.db.mongo import get_database


class FeedbackRepository:
    @staticmethod
    async def add_feedback(
        region_id: str,
        inspection_id: str,
        decision: str,
        reviewed_by: str,
        rejection_reason: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Ajoute une décision de validation humaine (opération en ajout seul avec séquence atomique)."""
        db = get_database()
        feedback_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # Compteur atomique par région pour ordre chronologique déterministe absolu
        counter = await db.counters.find_one_and_update(
            {"_id": f"region_feedback_{region_id}"},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        seq = counter["seq"] if counter else 1

        doc = {
            "_id": feedback_id,
            "id": feedback_id,
            "region_id": region_id,
            "inspection_id": inspection_id,
            "seq": seq,
            "decision": decision,
            "rejection_reason": rejection_reason,
            "comment": comment,
            "reviewed_by": reviewed_by,
            "created_at": now,
            "quality_checked": False,
        }

        await db.feedback.insert_one(doc)
        return doc

    @staticmethod
    async def get_history_by_region(region_id: str) -> List[Dict[str, Any]]:
        """Récupère l'historique complet des revues pour une région, du plus récent au plus ancien."""
        db = get_database()
        cursor = db.feedback.find({"region_id": region_id}).sort([
            ("seq", DESCENDING),
            ("created_at", DESCENDING),
            ("_id", DESCENDING),
        ])
        return await cursor.to_list(length=500)

    @staticmethod
    async def get_latest_by_region(region_id: str) -> Optional[Dict[str, Any]]:
        """Récupère la décision humaine courante (la plus récente) d'une région."""
        db = get_database()
        return await db.feedback.find_one(
            {"region_id": region_id},
            sort=[("seq", DESCENDING), ("created_at", DESCENDING), ("_id", DESCENDING)],
        )

    @staticmethod
    async def get_latest_decisions_map(region_ids: List[str]) -> Dict[str, str]:
        """Agrège la décision courante pour une liste d'identifiants de régions."""
        if not region_ids:
            return {}
        db = get_database()
        pipeline = [
            {"$match": {"region_id": {"$in": region_ids}}},
            {"$sort": {"seq": -1, "created_at": -1, "_id": -1}},
            {
                "$group": {
                    "_id": "$region_id",
                    "latest_decision": {"$first": "$decision"},
                }
            },
        ]
        cursor = await db.feedback.aggregate(pipeline)
        results = await cursor.to_list(length=len(region_ids))
        return {r["_id"]: r["latest_decision"] for r in results}

    @staticmethod
    async def list_feedback_for_export(skip: int = 0, limit: int = 1000) -> List[Dict[str, Any]]:
        """Jointure feedback + regions pour l'export d'annotation future (Exigence E)."""
        db = get_database()
        pipeline = [
            {"$sort": {"created_at": -1}},
            {"$skip": skip},
            {"$limit": limit},
            {
                "$lookup": {
                    "from": "regions",
                    "localField": "region_id",
                    "foreignField": "id",
                    "as": "region_info",
                }
            },
        ]
        cursor = await db.feedback.aggregate(pipeline)
        docs = await cursor.to_list(length=limit)
        items = []
        for d in docs:
            reg = d["region_info"][0] if d.get("region_info") else {}
            items.append({
                "id": str(d["_id"]),
                "region_id": str(d.get("region_id")),
                "inspection_id": str(d.get("inspection_id")),
                "decision": d.get("decision"),
                "rejection_reason": d.get("rejection_reason"),
                "comment": d.get("comment"),
                "bbox": reg.get("bbox", [0.0, 0.0, 0.0, 0.0]),
                "classification": reg.get("classification"),
                "reviewed_by": str(d.get("reviewed_by")),
                "created_at": d.get("created_at"),
                "quality_checked": bool(d.get("quality_checked", False)),
            })
        return items
