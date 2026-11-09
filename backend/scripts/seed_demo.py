"""Script de peuplement et d'initialisation de démonstration WeaveGuard AI (Phase 4).

RÈGLES STRICTES (§14.2, AC-08, AC-09) :
1. N'utilise QUE les images de validation (datasets/images/val). JAMAIS le jeu de test.
2. Toutes les données créées portent le marqueur 'is_demo=True'.
3. Idempotent : ne réinsère pas une image déjà présente.
4. Option --purge : supprime proprement toutes les données de démo (inspections, régions, revues, fichiers disque).
5. Exécute la vraie inférence IA locale (YOLO, PatchCore, Fusion) pour garantir la fidélité des résultats.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import secrets
import shutil
import sys
from pathlib import Path
from typing import Any, Dict
import uuid
from PIL import Image
from pymongo import AsyncMongoClient

# Configuration des imports backend
CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.core.permissions import UserRole
from app.core.security import hash_password
from app.db.indexes import ensure_indexes
from app.engines.fusion import fuse_regions
from app.engines.registry import engine_registry
from app.services.storage import StorageService
from app.services.visualizer import VisualizerService


async def purge_demo_data(db_name: str) -> None:
    """Supprime l'intégralité des inspections, régions, revues et artefacts de démonstration."""
    client = AsyncMongoClient(settings.MONGODB_URI)
    db = client[db_name]

    cursor = db.inspections.find({"is_demo": True})
    demo_inspections = await cursor.to_list(length=1000)
    demo_ids = [d["id"] for d in demo_inspections if "id" in d]

    logger.info(f"Purge de {len(demo_ids)} inspection(s) de démonstration...")

    storage_deleted = 0
    for insp_id in demo_ids:
        try:
            insp_dir = StorageService.get_inspection_dir(insp_id)
            if insp_dir.exists():
                shutil.rmtree(insp_dir, ignore_errors=True)
                storage_deleted += 1
        except Exception:
            pass

    res_feedback = await db.feedback.delete_many({"inspection_id": {"$in": demo_ids}})
    res_regions = await db.regions.delete_many({"inspection_id": {"$in": demo_ids}})
    res_inspections = await db.inspections.delete_many({"is_demo": True})

    await db.audit_log.insert_one({
        "_id": str(uuid.uuid4()),
        "action": "demo_purged",
        "username": "system_seed",
        "at": datetime.now(timezone.utc),
        "details": {
            "inspections_purged": res_inspections.deleted_count,
            "regions_purged": res_regions.deleted_count,
            "feedback_purged": res_feedback.deleted_count,
            "storage_dirs_deleted": storage_deleted,
        },
    })

    await client.close()
    logger.info(
        f"Purge achevée avec succès : {res_inspections.deleted_count} inspections, "
        f"{res_regions.deleted_count} régions, {res_feedback.deleted_count} revues supprimées."
    )


async def ensure_demo_users(db: Any) -> Dict[str, str]:
    """Vérifie ou crée les comptes de démonstration avec mots de passe sécurisés temporaires."""
    demo_roles = {
        "demo_operator": UserRole.OPERATOR.value,
        "demo_supervisor": UserRole.SUPERVISOR.value,
        "demo_ml_engineer": UserRole.ML_ENGINEER.value,
        "demo_auditor": UserRole.AUDITOR.value,
        "demo_admin": UserRole.ADMIN.value,
    }
    created_creds = {}
    for username, role in demo_roles.items():
        existing = await db.users.find_one({"username": username})
        if existing:
            logger.info(f"Compte existant conservé : {username} (rôle: {existing.get('role')})")
        else:
            pwd = secrets.token_urlsafe(16)
            now = datetime.now(timezone.utc)
            doc = {
                "_id": str(uuid.uuid4()),
                "username": username,
                "password_hash": hash_password(pwd),
                "role": role,
                "active": True,
                "failed_attempts": 0,
                "locked_until": None,
                "created_at": now,
            }
            await db.users.insert_one(doc)
            created_creds[username] = pwd
            print(f"[DEMO_USER_INIT] Compte: {username} | Rôle: {role} | Mot de passe généré: {pwd}")
    return created_creds


async def seed_demo_inspections(db_name: str, count: int = 12) -> None:
    """Génère un lot d'inspections de démonstration avec inférence réelle et revues simulées."""
    client = AsyncMongoClient(settings.MONGODB_URI)
    db = client[db_name]
    await ensure_indexes(db)

    # Assurer la présence des comptes de démonstration
    await ensure_demo_users(db)

    # Répertoire d'images de validation UNIQUEMENT (§2 contractuel)
    val_images_dir = settings.get_dataset_dir() / "images" / "val"
    if not val_images_dir.exists():
        logger.error(f"Dossier de validation introuvable : {val_images_dir}")
        await client.close()
        return

    val_images = sorted(list(val_images_dir.glob("*.jpg")))[:count]
    if not val_images:
        logger.warning(f"Aucune image trouvée dans {val_images_dir}")
        await client.close()
        return

    # Vérification des inspections de démo existantes (idempotence)
    existing_cursor = db.inspections.find({"is_demo": True})
    existing_docs = await existing_cursor.to_list(length=500)
    existing_filenames = {d.get("image_meta", {}).get("filename") for d in existing_docs}

    inserted_count = 0
    decision_pool = ["confirmed", "rejected", "uncertain", "confirmed"]
    reasons_pool = ["pli_tissu", "faux_positif_texture", "artefact_tissage"]

    for idx, img_path in enumerate(val_images):
        filename = img_path.name
        if filename in existing_filenames:
            logger.info(f"[{idx+1}/{len(val_images)}] Déjà présente (ignorée) : {filename}")
            continue

        logger.info(f"[{idx+1}/{len(val_images)}] Traitement IA de l'image de démo : {filename}")
        raw_bytes = img_path.read_bytes()

        # 1. Prétraitement
        stored_img, inf_img, image_meta = StorageService.validate_and_preprocess_upload(raw_bytes, filename)
        inspection_id = str(uuid.uuid4())

        # 2. Sauvegarde de l'image originale
        StorageService.save_stored_image(inspection_id, stored_img)

        # 3. Exécution séquentielle des moteurs IA réels
        pipeline_result = engine_registry.run_pipeline(
            inf_img,
            selected_engines=["yolo", "patchcore"],
        )

        engines_out = pipeline_result.get("engines", {})
        scale = image_meta.resize_factor
        raw_yolo_regions = engines_out.get("yolo", {}).get("regions", [])
        raw_pc_regions = engines_out.get("patchcore", {}).get("regions", [])
        pc_raw_data = engines_out.get("patchcore", {}).get("raw_data", {})

        # Rééchelonnage vers le repère natif stocké
        def rescale_region(r: Dict[str, Any]) -> Dict[str, Any]:
            rx, ry, rw, rh = r["bbox"]
            mapped_box = [
                round(rx / scale, 2),
                round(ry / scale, 2),
                round(rw / scale, 2),
                round(rh / scale, 2),
            ]
            area = round((rw / scale) * (rh / scale), 2)
            reg_copy = dict(r)
            reg_copy["bbox"] = mapped_box
            reg_copy["area"] = area
            return reg_copy

        scaled_yolo = [rescale_region(r) for r in raw_yolo_regions]
        scaled_pc = [rescale_region(r) for r in raw_pc_regions]
        fused_regions = fuse_regions(scaled_yolo, scaled_pc)

        now = datetime.now(timezone.utc)
        db_regions = []
        feedbacks_to_insert = []

        for r_i, reg in enumerate(fused_regions):
            reg_id = str(uuid.uuid4())
            engine_name = reg.get("source_engine") or reg.get("engine", "yolo")
            corro_raw = reg.get("corroboration")
            if corro_raw:
                corro_info = {
                    "detected": True,
                    "overlap_ratio_box": None,
                    "overlap_ratio_region": None,
                    "score_patchcore": corro_raw.get("score"),
                    "tau_patchcore": corro_raw.get("threshold"),
                }
            else:
                corro_info = None

            region_doc = {
                "_id": reg_id,
                "id": reg_id,
                "inspection_id": inspection_id,
                "engine": engine_name,
                "bbox": reg["bbox"],
                "area": reg["area"],
                "label": reg["label"],
                "score": reg.get("score"),
                "classification": reg.get("classification"),
                "tau": reg.get("tau") or reg.get("score_threshold"),
                "corroboration": corro_info,
                "created_at": now,
            }
            db_regions.append(region_doc)

            # Revue humaine d'exemple sur une partie des régions
            if r_i % 2 == 0:
                decision = decision_pool[(idx + r_i) % len(decision_pool)]
                reason = reasons_pool[(idx + r_i) % len(reasons_pool)] if decision == "rejected" else None
                comment = "Revue humaine de démonstration"

                feedback_doc = {
                    "_id": str(uuid.uuid4()),
                    "id": str(uuid.uuid4()),
                    "region_id": reg_id,
                    "inspection_id": inspection_id,
                    "decision": decision,
                    "rejection_reason": reason,
                    "comment": comment,
                    "reviewed_by": "demo_operator",
                    "created_at": now,
                    "seq": 1,
                    "quality_checked": False,
                }
                feedbacks_to_insert.append(feedback_doc)

        # Heatmap
        heatmap_meta_dict = None
        if "score_map" in pc_raw_data:
            raw_map = pc_raw_data["score_map"]
            tau_val = pc_raw_data.get("tau_global", 1.6386)
            StorageService.save_raw_map(inspection_id, raw_map)
            heatmap_img, heatmap_meta = VisualizerService.generate_heatmap(
                raw_score_map=raw_map,
                stored_size=(stored_img.width, stored_img.height),
                tau=tau_val,
            )
            StorageService.save_heatmap_png(inspection_id, heatmap_img)
            heatmap_meta_dict = heatmap_meta.model_dump()

        # Overlay
        overlay_img = VisualizerService.generate_overlay(stored_img, db_regions)
        StorageService.save_overlay_png(inspection_id, overlay_img)

        # Insertion BD
        if db_regions:
            await db.regions.insert_many(db_regions)
        if feedbacks_to_insert:
            await db.feedback.insert_many(feedbacks_to_insert)

        inspection_doc = {
            "_id": inspection_id,
            "id": inspection_id,
            "status": "done",
            "partial": False,
            "created_by": "demo_operator",
            "created_at": now,
            "completed_at": now,
            "image_meta": image_meta.model_dump(),
            "engines": {
                "yolo": {
                    "status": "ok",
                    "version": "weaveguard_yolo_v1",
                    "latency_ms": engines_out.get("yolo", {}).get("latency"),
                },
                "patchcore": {
                    "status": "ok",
                    "version": "patchcore_v1",
                    "latency_ms": engines_out.get("patchcore", {}).get("latency"),
                },
            },
            "regions_count": len(db_regions),
            "heatmap_meta": heatmap_meta_dict,
            "error_message": None,
            "is_demo": True,
        }
        await db.inspections.insert_one(inspection_doc)
        inserted_count += 1

    await client.close()
    logger.info(f"Peuplement terminé : {inserted_count} inspection(s) de démo générée(s).")


def main():
    parser = argparse.ArgumentParser(description="Gestion du jeu de données de démonstration WeaveGuard AI")
    parser.add_argument("--purge", action="store_true", help="Purger toutes les données de démo existantes")
    parser.add_argument("--count", type=int, default=12, help="Nombre d'images de démo à traiter (défaut: 12)")
    parser.add_argument("--db", type=str, default=None, help="Nom de la base MongoDB (défaut: configuration settings.DB_NAME)")
    args = parser.parse_args()

    setup_logging()
    db_name = args.db or settings.DB_NAME

    if args.purge:
        asyncio.run(purge_demo_data(db_name))
    else:
        asyncio.run(seed_demo_inspections(db_name, count=args.count))


if __name__ == "__main__":
    main()
