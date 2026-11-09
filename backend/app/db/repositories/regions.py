"""Dépôt MongoDB pour les régions d'inspection (Phase 3).

RÈGLE D'IMMUTABILITÉ STRICTE (§1, AC-07, Exigence J) :
Les régions détectées sont immuables. Aucune méthode de mise à jour ou de suppression
n'est exposée sur la collection 'regions' après leur création initiale.
"""
from typing import Any, Dict, List
from pymongo import ASCENDING
from app.db.mongo import get_database


class RegionRepository:
    @staticmethod
    async def bulk_create_regions(regions: List[Dict[str, Any]]) -> None:
        """Insère en masse les régions détectées (opération en ajout seul, immuable)."""
        if not regions:
            return
        db = get_database()
        # Copie propre avec _id = id
        docs = []
        for r in regions:
            doc = dict(r)
            doc["_id"] = doc["id"]
            docs.append(doc)
        await db.regions.insert_many(docs)

    @staticmethod
    async def get_by_inspection_id(inspection_id: str) -> List[Dict[str, Any]]:
        """Récupère toutes les régions associées à une inspection, triées par identifiant."""
        db = get_database()
        cursor = db.regions.find({"inspection_id": inspection_id}).sort("id", ASCENDING)
        return await cursor.to_list(length=1000)

