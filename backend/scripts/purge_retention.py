"""Script de purge selon la politique de rétention des données (Phase 4).

RÈGLE DE SÉCURITÉ (§12, §14) :
- Le mode --dry-run est activé par défaut pour éviter toute suppression involontaire.
- Exige le drapeau explicite --apply (ou --execute) pour exécuter la suppression réelle.
- Supprime les inspections, régions, revues et artefacts disque antérieurs au seuil fixé.
- Consigne systématiquement un événement d'audit 'retention_purged'.
"""
import argparse
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
import shutil
import sys
import uuid
from pymongo import AsyncMongoClient

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.services.storage import StorageService


async def purge_expired_inspections(
    db_name: str,
    retention_days: int = 90,
    dry_run: bool = True,
) -> int:
    setup_logging()
    client = AsyncMongoClient(settings.MONGODB_URI)
    db = client[db_name]

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
    logger.info(
        f"Politique de rétention ({retention_days} jours) : recherche des inspections antérieures à {cutoff_date.isoformat()} "
        f"[Mode: {'SIMULATION (DRY-RUN)' if dry_run else 'EXÉCUTION RÉELLE'}]..."
    )

    query = {"created_at": {"$lt": cutoff_date}}
    cursor = db.inspections.find(query)
    expired_inspections = await cursor.to_list(length=5000)
    expired_ids = [d["id"] for d in expired_inspections if "id" in d]

    count_found = len(expired_ids)
    logger.info(f"Nombre d'inspections expirées identifiées : {count_found}")

    if count_found == 0 or dry_run:
        if dry_run and count_found > 0:
            logger.info(f"[DRY-RUN] {count_found} inspections auraient été purgées. Aucune modification effectuée.")
        await client.close()
        return count_found

    # Exécution réelle
    storage_deleted = 0
    for insp_id in expired_ids:
        try:
            insp_dir = StorageService.get_inspection_dir(insp_id)
            if insp_dir.exists():
                shutil.rmtree(insp_dir, ignore_errors=True)
                storage_deleted += 1
        except Exception:
            pass

    res_fb = await db.feedback.delete_many({"inspection_id": {"$in": expired_ids}})
    res_reg = await db.regions.delete_many({"inspection_id": {"$in": expired_ids}})
    res_insp = await db.inspections.delete_many({"id": {"$in": expired_ids}})

    # Journalisation d'audit
    await db.audit_log.insert_one({
        "_id": str(uuid.uuid4()),
        "action": "retention_purged",
        "username": "retention_job",
        "at": datetime.now(timezone.utc),
        "details": {
            "retention_days": retention_days,
            "cutoff_date": cutoff_date.isoformat(),
            "inspections_purged": res_insp.deleted_count,
            "regions_purged": res_reg.deleted_count,
            "feedback_purged": res_fb.deleted_count,
            "storage_dirs_deleted": storage_deleted,
        },
    })

    await client.close()
    logger.info(
        f"Purge de rétention terminée : {res_insp.deleted_count} inspections, "
        f"{res_reg.deleted_count} régions, {res_fb.deleted_count} revues supprimées."
    )
    return res_insp.deleted_count


def main():
    parser = argparse.ArgumentParser(description="Purge de rétention des données WeaveGuard AI")
    parser.add_argument("--days", type=int, default=90, help="Délai de rétention en jours (défaut: 90)")
    parser.add_argument("--db", default=None, help="Base MongoDB (défaut: settings.DB_NAME)")
    parser.add_argument("--apply", action="store_true", help="Appliquer réellement la suppression (par défaut: simulation dry-run)")
    args = parser.parse_args()

    db_name = args.db or settings.DB_NAME
    asyncio.run(purge_expired_inspections(db_name, retention_days=args.days, dry_run=not args.apply))


if __name__ == "__main__":
    main()

