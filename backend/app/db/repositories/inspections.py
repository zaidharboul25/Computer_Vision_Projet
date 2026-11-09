"""Dépôt MongoDB pour la gestion des inspections (Phase 3).

Garantit la traçabilité des états de traitement, la mise à jour temps réel
de la progression des moteurs (§6.2, AC-08) et le nettoyage des inspections orphelines.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from pymongo import ASCENDING, DESCENDING
from app.db.mongo import get_database
from app.schemas.inspection import ImageMeta


class InspectionRepository:
    @staticmethod
    async def create_inspection(
        inspection_id: str,
        created_by: str,
        image_meta: ImageMeta,
        enabled_engines: List[str],
        is_demo: bool = False,
    ) -> Dict[str, Any]:
        """Crée un enregistrement d'inspection à l'état 'pending'."""
        db = get_database()
        now = datetime.now(timezone.utc)

        engines_map = {}
        for eng in enabled_engines:
            engines_map[eng] = {
                "status": "pending",
                "version": None,
                "error": None,
                "latency_ms": None,
            }

        doc = {
            "_id": inspection_id,
            "id": inspection_id,
            "status": "pending",
            "partial": False,
            "created_by": created_by,
            "created_at": now,
            "completed_at": None,
            "image_meta": image_meta.model_dump(),
            "domain_check": None,
            "warnings": list(image_meta.warnings) if hasattr(image_meta, "warnings") else [],
            "engines": engines_map,
            "regions_count": 0,
            "heatmap_meta": None,
            "error_message": None,
            "is_demo": is_demo,
        }

        await db.inspections.insert_one(doc)
        return doc

    @staticmethod
    async def get_by_id(inspection_id: str) -> Optional[Dict[str, Any]]:
        """Récupère une inspection par son identifiant unique."""
        db = get_database()
        return await db.inspections.find_one({"_id": inspection_id})

    @staticmethod
    async def update_engine_progress(
        inspection_id: str,
        engine_name: str,
        status: str,
        version: Optional[str] = None,
        error: Optional[str] = None,
        latency_ms: Optional[Dict[str, float]] = None,
    ) -> None:
        """Met à jour l'état et la latence d'un moteur spécifique en cours d'exécution."""
        db = get_database()
        update_fields = {
            f"engines.{engine_name}.status": status,
        }
        if version is not None:
            update_fields[f"engines.{engine_name}.version"] = version
        if error is not None:
            update_fields[f"engines.{engine_name}.error"] = error
        if latency_ms is not None:
            update_fields[f"engines.{engine_name}.latency_ms"] = latency_ms

        await db.inspections.update_one(
            {"_id": inspection_id},
            {"$set": update_fields},
        )

    @staticmethod
    async def update_status(
        inspection_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        """Met à jour le statut global d'une inspection."""
        db = get_database()
        update_doc: Dict[str, Any] = {"status": status}
        if error_message:
            update_doc["error_message"] = error_message
        await db.inspections.update_one({"_id": inspection_id}, {"$set": update_doc})

    @staticmethod
    async def complete_inspection(
        inspection_id: str,
        status: str,
        partial: bool,
        regions_count: int,
        heatmap_meta: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        domain_check: Optional[Dict[str, Any]] = None,
        warnings: Optional[List[str]] = None,
    ) -> None:
        """Finalise l'inspection en enregistrant les métadonnées de sortie."""
        db = get_database()
        now = datetime.now(timezone.utc)
        update_fields: Dict[str, Any] = {
            "status": status,
            "partial": partial,
            "regions_count": regions_count,
            "completed_at": now,
        }
        if heatmap_meta is not None:
            update_fields["heatmap_meta"] = heatmap_meta
        if error_message is not None:
            update_fields["error_message"] = error_message
        if domain_check is not None:
            update_fields["domain_check"] = domain_check
        if warnings is not None:
            update_fields["warnings"] = warnings
            update_fields["image_meta.warnings"] = warnings

        await db.inspections.update_one({"_id": inspection_id}, {"$set": update_fields})

    @staticmethod
    async def list_inspections(
        username: str,
        can_view_all: bool,
        skip: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
        created_by: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        id_filter: Optional[str] = None,
        review_status: Optional[str] = None,
        model: Optional[str] = None,
        include_demo: bool = True,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Liste paginée avec filtres et contrôle de visibilité par rôle (AC-08)."""
        import re
        db = get_database()
        query: Dict[str, Any] = {}

        # Si l'utilisateur n'a pas le droit de voir tout (ex: opérateur), filtrer strictement sur ses inspections
        if not can_view_all:
            query["created_by"] = username
        elif created_by:
            query["created_by"] = created_by

        if not include_demo:
            query["is_demo"] = {"$ne": True}

        if id_filter:
            clean_id = id_filter.strip()
            query["id"] = {"$regex": f"^{re.escape(clean_id)}", "$options": "i"}

        if status:
            query["status"] = status

        if review_status:
            reviewed_ids = await db.feedback.distinct("inspection_id")
            if review_status == "reviewed":
                query["id"] = {"$in": reviewed_ids}
            elif review_status == "unreviewed":
                query["id"] = {"$nin": reviewed_ids}
            else:
                query["review_status"] = review_status

        if model:
            query[f"engines.{model}"] = {"$exists": True}

        if date_from or date_to:
            date_filter = {}
            if date_from:
                date_filter["$gte"] = date_from
            if date_to:
                date_filter["$lte"] = date_to
            query["created_at"] = date_filter

        total = await db.inspections.count_documents(query)
        cursor = db.inspections.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
        items = await cursor.to_list(length=limit)
        return items, total

    @staticmethod
    async def get_summary_stats(include_demo: bool = True) -> Dict[str, Any]:
        """Calcule uniquement des décomptes depuis MongoDB pour le tableau de bord (§14.2, Exigence C)."""
        db = get_database()
        base_match: Dict[str, Any] = {}
        if not include_demo:
            base_match["is_demo"] = {"$ne": True}

        # 1. Inspections par statut
        pipe_insp = [
            {"$match": base_match},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        cursor_insp = await db.inspections.aggregate(pipe_insp)
        insp_counts = await cursor_insp.to_list(10)
        insp_stats = {"pending": 0, "running": 0, "done": 0, "error": 0, "total": 0}
        for item in insp_counts:
            st = item["_id"]
            cnt = item["count"]
            insp_stats["total"] += cnt
            if st in insp_stats:
                insp_stats[st] = cnt

        # 2. Régions par moteur
        pipe_reg = [
            {"$group": {"_id": "$engine", "count": {"$sum": 1}}},
        ]
        cursor_reg = await db.regions.aggregate(pipe_reg)
        reg_counts = await cursor_reg.to_list(10)
        reg_stats = {"yolo": 0, "patchcore": 0, "total": 0}
        for item in reg_counts:
            eng = item["_id"]
            cnt = item["count"]
            reg_stats["total"] += cnt
            if eng in reg_stats:
                reg_stats[eng] = cnt

        # 3. Décisions courantes par statut de revue
        pipe_reviews = [
            {"$sort": {"seq": -1, "created_at": -1, "_id": -1}},
            {"$group": {"_id": "$region_id", "latest_decision": {"$first": "$decision"}}},
            {"$group": {"_id": "$latest_decision", "count": {"$sum": 1}}},
        ]
        cursor_reviews = await db.feedback.aggregate(pipe_reviews)
        review_counts = await cursor_reviews.to_list(10)
        rev_stats = {"confirmed": 0, "rejected": 0, "uncertain": 0, "unreviewed": 0, "total": reg_stats["total"]}
        reviewed_total = 0
        for item in review_counts:
            dec = item["_id"]
            cnt = item["count"]
            reviewed_total += cnt
            if dec in rev_stats:
                rev_stats[dec] = cnt
        rev_stats["unreviewed"] = max(0, reg_stats["total"] - reviewed_total)

        # 4. Dernières inspections
        cursor_latest = db.inspections.find(base_match).sort("created_at", DESCENDING).limit(5)
        latest_items = await cursor_latest.to_list(length=5)

        return {
            "inspections": insp_stats,
            "regions": reg_stats,
            "reviews": rev_stats,
            "latest_inspections": latest_items,
            "include_demo": include_demo,
        }

    @staticmethod
    async def cleanup_orphan_inspections() -> int:
        """Passe en erreur les inspections interrompues par un redémarrage inopiné du serveur."""
        db = get_database()
        now = datetime.now(timezone.utc)
        result = await db.inspections.update_many(
            {"status": {"$in": ["pending", "running"]}},
            {
                "$set": {
                    "status": "error",
                    "error_message": "interrompue par un redémarrage",
                    "completed_at": now,
                }
            },
        )
        return result.modified_count
