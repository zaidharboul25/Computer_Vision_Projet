"""Script d'archivage et de sauvegarde complète WeaveGuard AI (MongoDB + Storage).

Sauvegarde :
- Collections MongoDB : users, inspections, regions, feedback, audit_log, settings
- Sérialisation BSON / JSON Util préservant strictement les types (datetime, UUID)
- Dossier persistant backend/storage/ (images originales, cartes de chaleur, overlays)
- Manifeste d'intégrité avec horodatage et décompte des collections.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
from bson import json_util
from pymongo import AsyncMongoClient

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.core.logging import logger, setup_logging


COLLECTIONS = ["users", "inspections", "regions", "feedback", "audit_log", "settings"]


async def create_backup(db_name: str, out_dir: Path, include_storage: bool = True) -> Path:
    setup_logging()
    client = AsyncMongoClient(settings.MONGODB_URI)
    db = client[db_name]

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = out_dir / f"backup_{db_name}_{timestamp_str}"
    backup_path.mkdir(parents=True, exist_ok=True)

    db_dump_dir = backup_path / "mongo"
    db_dump_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_db": db_name,
        "collections": {},
        "has_storage": False,
    }

    logger.info(f"Début de la sauvegarde de la base '{db_name}' vers {backup_path}...")

    # 1. Sauvegarde des collections MongoDB
    for col_name in COLLECTIONS:
        cursor = db[col_name].find({})
        docs = await cursor.to_list(length=100000)
        col_file = db_dump_dir / f"{col_name}.json"
        with open(col_file, "w", encoding="utf-8") as f:
            f.write(json_util.dumps(docs, indent=2))
        manifest["collections"][col_name] = len(docs)
        logger.info(f"  - Collection '{col_name}' : {len(docs)} document(s) exporté(s).")

    # 2. Sauvegarde du stockage de fichiers (backend/storage)
    storage_dir = settings.get_storage_dir()
    if include_storage and storage_dir.exists():
        storage_dest = backup_path / "storage"
        logger.info(f"Copie du stockage de fichiers depuis {storage_dir}...")
        shutil.copytree(storage_dir, storage_dest, dirs_exist_ok=True)
        manifest["has_storage"] = True

    # 3. Écriture du manifeste
    with open(backup_path / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    await client.close()
    logger.info(f"Sauvegarde terminée avec succès dans : {backup_path}")
    return backup_path


def main():
    parser = argparse.ArgumentParser(description="Sauvegarde WeaveGuard AI (MongoDB + Storage)")
    parser.add_argument("--db", default=None, help="Base source (défaut: settings.DB_NAME)")
    parser.add_argument("--out", default=None, help="Dossier de destination (défaut: backups/)")
    parser.add_argument("--no-storage", action="store_true", help="Ne pas inclure les fichiers de stockage")
    args = parser.parse_args()

    db_name = args.db or settings.DB_NAME
    root_dir = BACKEND_DIR.parent
    out_dir = Path(args.out) if args.out else (root_dir / "backups")

    asyncio.run(create_backup(db_name, out_dir, include_storage=not args.no_storage))


if __name__ == "__main__":
    main()

