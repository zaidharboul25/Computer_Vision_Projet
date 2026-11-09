"""Script de restauration WeaveGuard AI (MongoDB + Storage).

Restaure :
- Collections MongoDB depuis le format JSON Util (types datetime, UUID intacts)
- Insertion dans la base cible spécifiée (--target-db)
- Vérification de cohérence avec le manifeste de sauvegarde.
"""
import argparse
import asyncio
import json
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
from app.db.indexes import ensure_indexes


async def restore_backup(backup_dir: Path, target_db: str, restore_storage: bool = False) -> bool:
    setup_logging()
    manifest_file = backup_dir / "manifest.json"
    if not manifest_file.exists():
        logger.error(f"Fichier manifeste manquant dans le dossier de sauvegarde : {manifest_file}")
        return False

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    logger.info(f"Restauration de la sauvegarde du {manifest.get('timestamp')} vers la base '{target_db}'...")

    client = AsyncMongoClient(settings.MONGODB_URI)
    db = client[target_db]
    await ensure_indexes(db)

    db_dump_dir = backup_dir / "mongo"
    for col_name, expected_count in manifest.get("collections", {}).items():
        col_file = db_dump_dir / f"{col_name}.json"
        if not col_file.exists():
            logger.warning(f"Fichier manquant pour collection {col_name} : {col_file}")
            continue

        with open(col_file, "r", encoding="utf-8") as f:
            docs = json_util.loads(f.read())

        await db[col_name].delete_many({})
        if docs:
            await db[col_name].insert_many(docs)

        actual_count = await db[col_name].count_documents({})
        logger.info(f"  - Collection '{col_name}' : {actual_count}/{expected_count} document(s) restauré(s).")
        if actual_count != expected_count:
            logger.error(f"Échec de concordance pour '{col_name}' : attendu {expected_count}, obtenu {actual_count}")
            await client.close()
            return False

    if restore_storage and manifest.get("has_storage"):
        backup_storage = backup_dir / "storage"
        target_storage = settings.get_storage_dir()
        if backup_storage.exists():
            logger.info(f"Restauration des fichiers de stockage vers {target_storage}...")
            shutil.copytree(backup_storage, target_storage, dirs_exist_ok=True)

    await client.close()
    logger.info(f"Restauration achevée avec succès dans '{target_db}'.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Restauration WeaveGuard AI (MongoDB + Storage)")
    parser.add_argument("--backup-dir", required=True, help="Chemin du dossier de sauvegarde contenant manifest.json")
    parser.add_argument("--target-db", required=True, help="Nom de la base MongoDB de destination")
    parser.add_argument("--restore-storage", action="store_true", help="Restaurer également les fichiers disque de stockage")
    args = parser.parse_args()

    success = asyncio.run(restore_backup(Path(args.backup_dir), args.target_db, restore_storage=args.restore_storage))
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()

