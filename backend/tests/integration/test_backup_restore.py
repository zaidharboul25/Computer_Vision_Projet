"""Test d'intégration pour les procédures d'exploitation de sauvegarde et restauration (Phase 4).

Vérifie :
1. Sauvegarde de weaveguard_test vers un dossier temporaire
2. Restauration vers une base tierce temporaire 'weaveguard_restore_test'
3. Égalité stricte des décomptes et de l'intégrité des documents
4. Nettoyage et suppression de la base temporaire restaurée
5. Politique de rétention et comportement du mode --dry-run
"""
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
import uuid
import pytest
from bson import json_util
from pymongo import AsyncMongoClient

from app.core.config import settings
from scripts.db_backup import create_backup
from scripts.db_restore import restore_backup
from scripts.purge_retention import purge_expired_inspections


RESTORE_TEST_DB = "weaveguard_restore_test"


def canonical_doc_hash(doc: dict) -> str:
    """Calcule le hachage SHA-256 canonique d'un document MongoDB sérialisé avec clés triées."""
    serialized = json_util.dumps(doc, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@pytest.mark.asyncio
async def test_full_backup_and_restore_cycle(setup_test_db, tmp_path):
    """Effectue un cycle complet de backup puis restore et vérifie la stricte parité des données."""
    db_source = setup_test_db
    source_db_name = settings.DB_NAME  # weaveguard_test

    # 1. Peuplement initial de weaveguard_test
    now = datetime.now(timezone.utc)
    user_id = str(uuid.uuid4())
    insp_id = str(uuid.uuid4())
    reg_id = str(uuid.uuid4())
    fb_id = str(uuid.uuid4())

    await db_source.users.insert_one({"_id": user_id, "username": "backup_op", "role": "operator", "active": True})
    await db_source.inspections.insert_one({"_id": insp_id, "id": insp_id, "created_by": "backup_op", "status": "done", "created_at": now})
    await db_source.regions.insert_one({"_id": reg_id, "id": reg_id, "inspection_id": insp_id, "engine": "yolo", "bbox": [1, 2, 3, 4]})
    await db_source.feedback.insert_one({"_id": fb_id, "id": fb_id, "region_id": reg_id, "decision": "confirmed", "created_at": now})
    await db_source.audit_log.insert_one({"_id": str(uuid.uuid4()), "action": "test_event", "at": now})

    collections_to_test = ["users", "inspections", "regions", "feedback", "audit_log"]

    # 2. Exécution du backup
    backup_dir = await create_backup(db_name=source_db_name, out_dir=tmp_path, include_storage=False)
    assert backup_dir.exists()
    assert (backup_dir / "manifest.json").exists()

    # 3. Restauration vers la base cible temporaire
    restore_success = await restore_backup(backup_dir=backup_dir, target_db=RESTORE_TEST_DB, restore_storage=False)
    assert restore_success is True

    # 4. Vérification approfondie : Décomptes + Contenu document par document + Index
    client = AsyncMongoClient(settings.MONGODB_URI)
    db_restored = client[RESTORE_TEST_DB]

    try:
        for col_name in collections_to_test:
            # a) Vérification des décomptes
            source_count = await db_source[col_name].count_documents({})
            restored_count = await db_restored[col_name].count_documents({})
            assert restored_count == source_count, f"Incohérence décompte sur {col_name}"

            # b) Comparaison document par document via hachage canonique
            src_docs = await db_source[col_name].find({}).to_list(length=1000)
            rst_docs = await db_restored[col_name].find({}).to_list(length=1000)

            src_hashes = {str(d["_id"]): canonical_doc_hash(d) for d in src_docs}
            rst_hashes = {str(d["_id"]): canonical_doc_hash(d) for d in rst_docs}

            assert rst_hashes == src_hashes, f"Contenu divergent document par document dans la collection '{col_name}'"

            # c) Vérification de la recréation des index
            src_indexes = await db_source[col_name].index_information()
            rst_indexes = await db_restored[col_name].index_information()
            for idx_name, idx_spec in src_indexes.items():
                assert idx_name in rst_indexes, f"Index manquant '{idx_name}' dans collection restaurée '{col_name}'"
                assert rst_indexes[idx_name]["key"] == idx_spec["key"], f"Clé d'index divergente pour '{idx_name}'"

    finally:
        # 5. Suppression impérative de la base temporaire de test
        await client.drop_database(RESTORE_TEST_DB)
        await client.close()


@pytest.mark.asyncio
async def test_retention_purge_dry_run_and_execution(setup_test_db):
    """Vérifie le respect du dry-run par défaut et l'exécution de la purge sur weaveguard_test."""
    db = setup_test_db
    source_db_name = settings.DB_NAME

    now = datetime.now(timezone.utc)
    old_date = now - timedelta(days=120)  # > 90 jours
    recent_date = now - timedelta(days=10)

    old_insp_id = str(uuid.uuid4())
    recent_insp_id = str(uuid.uuid4())

    await db.inspections.insert_one({"_id": old_insp_id, "id": old_insp_id, "created_at": old_date, "status": "done"})
    await db.inspections.insert_one({"_id": recent_insp_id, "id": recent_insp_id, "created_at": recent_date, "status": "done"})

    # 1. Exécution en mode Dry-Run : aucun document ne doit être supprimé
    count_identified = await purge_expired_inspections(db_name=source_db_name, retention_days=90, dry_run=True)
    assert count_identified == 1
    assert await db.inspections.count_documents({}) == 2

    # 2. Exécution réelle : l'ancienne inspection est supprimée, la récente est conservée
    count_purged = await purge_expired_inspections(db_name=source_db_name, retention_days=90, dry_run=False)
    assert count_purged == 1
    assert await db.inspections.count_documents({}) == 1

    remaining = await db.inspections.find_one({"id": recent_insp_id})
    assert remaining is not None

    # L'audit de purge doit être consigné
    logged_purge = await db.audit_log.find_one({"action": "retention_purged"})
    assert logged_purge is not None

