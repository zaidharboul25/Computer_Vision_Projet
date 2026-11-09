"""Smoke Test End-to-End de l'API WeaveGuard AI (Phase 3).

Exécute le parcours complet avec mesures de durée :
1. Connexion (login) -> Obtention du jeton Bearer
2. Téléchargement d'une image de validation réelle
3. Attente active de la fin du traitement (polling de statut)
4. Récupération des régions détectées et labellisées
5. Téléchargement sécurisé de l'overlay annoté
6. Téléchargement sécurisé de la heatmap PatchCore
7. Téléchargement et validation du rapport JSON normalisé (export_schema_v1.json)
"""
import argparse
import getpass
import json
import os
from pathlib import Path
import shutil
import sys
import time
import httpx
import fastjsonschema
from pymongo import MongoClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_FILE = PROJECT_ROOT / "backend" / "app" / "schemas" / "export_schema_v1.json"


def find_default_validation_image() -> Path:
    val_dir = PROJECT_ROOT / "datasets" / "images" / "val"
    if val_dir.exists():
        images = sorted(list(val_dir.glob("*.jpg")) + list(val_dir.glob("*.png")))
        if images:
            return images[0]
    # Fallback si dataset non trouvé
    fallback = PROJECT_ROOT / "backend" / "storage" / "test.png"
    return fallback


def main():
    parser = argparse.ArgumentParser(description="Smoke test end-to-end de l'API WeaveGuard AI")
    parser.add_argument("--base-url", default="http://localhost:8000", help="URL de base du backend")
    parser.add_argument("--username", default="admin", help="Nom d'utilisateur")
    parser.add_argument("--password", default=None, help="Mot de passe (saisie masquée si omis)")
    parser.add_argument("--image", default=None, help="Chemin vers une image de test")
    parser.add_argument("--timeout", type=int, default=120, help="Délai max d'attente en secondes")
    args = parser.parse_args()

    password = os.environ.get("SMOKE_PASSWORD") or args.password
    if not password:
        password = getpass.getpass(f"Mot de passe pour l'utilisateur '{args.username}': ")

    image_path = Path(args.image) if args.image else find_default_validation_image()
    if not image_path.exists():
        print(f"[ERREUR] Image de test introuvable : {image_path}")
        sys.exit(1)

    print("=" * 65)
    print(" WEAVEGUARD AI — SMOKE TEST API END-TO-END (Phase 3)")
    print("=" * 65)
    print(f"Cible API       : {args.base_url}")
    print(f"Utilisateur     : {args.username}")
    print(f"Image testée    : {image_path.name} ({image_path.stat().st_size} octets)")
    print("=" * 65)

    timings = {}
    total_start = time.time()

    with httpx.Client(base_url=args.base_url, timeout=30.0) as client:
        # Étape 1 : Login
        print("\n[1/7] Authentification (POST /api/v1/auth/login)...")
        t0 = time.time()
        resp_login = client.post(
            "/api/v1/auth/login",
            json={"username": args.username, "password": password},
        )
        timings["1. Login"] = time.time() - t0

        if resp_login.status_code != 200:
            print(f"[ÉCHEC] Login refusé ({resp_login.status_code}) : {resp_login.text}")
            sys.exit(1)

        token = resp_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"  -> Succès ({timings['1. Login']*1000:.1f} ms) — Jeton Bearer obtenu.")

        # Étape 2 : Upload d'image & création d'inspection
        print("\n[2/7] Upload de l'image (POST /api/v1/inspections)...")
        t0 = time.time()
        with open(image_path, "rb") as f:
            resp_upload = client.post(
                "/api/v1/inspections",
                headers=headers,
                files={"file": (image_path.name, f, "image/jpeg")},
                data={"engines": "yolo,patchcore"},
            )
        timings["2. Upload & Enqueue"] = time.time() - t0

        if resp_upload.status_code != 202:
            print(f"[ÉCHEC] Création d'inspection refusée ({resp_upload.status_code}) : {resp_upload.text}")
            sys.exit(1)

        inspection_id = resp_upload.json()["id"]
        print(f"  -> Succès ({timings['2. Upload & Enqueue']*1000:.1f} ms) — Inspection ID : {inspection_id}")

        # Étape 3 : Attente de fin de traitement
        print("\n[3/7] Traitement séquentiel en arrière-plan (polling GET /api/v1/inspections/{id})...")
        t0 = time.time()
        status = "pending"
        insp_detail = {}
        while time.time() - t0 < args.timeout:
            resp_status = client.get(f"/api/v1/inspections/{inspection_id}", headers=headers)
            if resp_status.status_code != 200:
                print(f"[ERREUR] Impossible de lire le statut : {resp_status.text}")
                sys.exit(1)
            insp_detail = resp_status.json()
            status = insp_detail["status"]

            engines_st = {k: v["status"] for k, v in insp_detail.get("engines", {}).items()}
            print(f"  ... statut global : {status} | moteurs : {engines_st}")

            if status in ("done", "error"):
                break
            time.sleep(1.0)

        timings["3. Traitement Moteurs IA"] = time.time() - t0

        if status != "done":
            print(f"[ÉCHEC] Traitement inachevé ou en erreur : statut={status}")
            print(f"Détails : {insp_detail}")
            sys.exit(1)

        print(f"  -> Traitement terminé avec succès en {timings['3. Traitement Moteurs IA']:.2f} s !")
        print(f"  -> Régions candidates : {insp_detail.get('regions_count', 0)}")

        # Étape 4 : Récupération des régions
        print("\n[4/7] Récupération des régions (GET /api/v1/inspections/{id}/regions)...")
        t0 = time.time()
        resp_regions = client.get(f"/api/v1/inspections/{inspection_id}/regions", headers=headers)
        timings["4. Récupération Régions"] = time.time() - t0

        if resp_regions.status_code != 200:
            print(f"[ÉCHEC] Lecture des régions ({resp_regions.status_code}) : {resp_regions.text}")
            sys.exit(1)

        regions = resp_regions.json()["items"]
        print(f"  -> {len(regions)} région(s) récupérée(s) ({timings['4. Récupération Régions']*1000:.1f} ms)")
        for r in regions[:3]:
            print(f"     * [{r['engine']}] {r['label']} (boîte: {r['bbox']}, aire: {r['area']} px²)")

        # Étape 5 : Téléchargement de l'overlay
        print("\n[5/7] Téléchargement de l'overlay annoté (GET /api/v1/inspections/{id}/overlay)...")
        t0 = time.time()
        resp_overlay = client.get(f"/api/v1/inspections/{inspection_id}/overlay", headers=headers)
        timings["5. Téléchargement Overlay"] = time.time() - t0

        if resp_overlay.status_code != 200:
            print(f"[ÉCHEC] Téléchargement de l'overlay ({resp_overlay.status_code}) : {resp_overlay.text}")
            sys.exit(1)
        print(f"  -> Succès ({len(resp_overlay.content)} octets reçus en {timings['5. Téléchargement Overlay']*1000:.1f} ms)")

        # Étape 6 : Téléchargement de la heatmap PatchCore
        print("\n[6/7] Téléchargement de la heatmap 8-bit (GET /api/v1/inspections/{id}/heatmap)...")
        t0 = time.time()
        resp_heatmap = client.get(f"/api/v1/inspections/{inspection_id}/heatmap", headers=headers)
        timings["6. Téléchargement Heatmap"] = time.time() - t0

        if resp_heatmap.status_code != 200:
            print(f"[ÉCHEC] Téléchargement de la heatmap ({resp_heatmap.status_code}) : {resp_heatmap.text}")
            sys.exit(1)
        print(f"  -> Succès ({len(resp_heatmap.content)} octets reçus en {timings['6. Téléchargement Heatmap']*1000:.1f} ms)")

        # Étape 7 : Export JSON et validation du schéma
        print("\n[7/7] Export JSON et validation du schéma (GET /api/v1/inspections/{id}/export)...")
        t0 = time.time()
        resp_export = client.get(f"/api/v1/inspections/{inspection_id}/export", headers=headers)
        timings["7. Export JSON & Validation"] = time.time() - t0

        if resp_export.status_code != 200:
            print(f"[ÉCHEC] Export JSON refusé ({resp_export.status_code}) : {resp_export.text}")
            sys.exit(1)

        export_data = resp_export.json()

        # Validation stricte du schéma
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            schema_json = json.load(f)
        validator = fastjsonschema.compile(schema_json)
        try:
            validator(export_data)
            print(f"  -> Schéma {export_data['schema_version']} VALIDÉ avec succès !")
        except Exception as e:
            print(f"[ERREUR] Le JSON d'export ne valide pas le schéma : {e}")
            sys.exit(1)

        # Contrôle anti-fuite
        serialized = json.dumps(export_data)
        if "C:\\" in serialized or ".env" in serialized:
            print("[ALERTE] Fuite de chemin ou de secret détectée dans l'export !")
            sys.exit(1)
        print("  -> Contrôle anti-fuite (aucun chemin système C:\\ ni secret) : OK")

    total_duration = time.time() - total_start

    # Nettoyage automatique dans weaveguard (Exigence 3)
    print("\n[Nettoyage] Suppression de l'inspection de test et libération du stockage...")
    try:
        mc = MongoClient("mongodb://localhost:27017")
        db = mc["weaveguard"]
        db.inspections.delete_one({"_id": inspection_id})
        db.regions.delete_many({"inspection_id": inspection_id})
        db.audit_log.delete_many({"details.inspection_id": inspection_id})
        storage_p = PROJECT_ROOT / "backend" / "storage" / "inspections" / inspection_id
        if storage_p.exists():
            shutil.rmtree(storage_p)
        mc.close()
        print(f"  -> Inspection {inspection_id} et fichiers associés supprimés avec succès.")
    except Exception as e:
        print(f"  [AVERTISSEMENT] Échec du nettoyage automatique : {e}")

    print("\n" + "=" * 65)
    print(" RÉCAPITULATIF DES PERFORMANCES DU SMOKE TEST")
    print("=" * 65)
    for step_name, duration in timings.items():
        if duration >= 1.0:
            print(f"  {step_name:<32} : {duration:.2f} s")
        else:
            print(f"  {step_name:<32} : {duration*1000:.1f} ms")
    print("-" * 65)
    print(f"  {'DURÉE TOTALE DU PIPELINE':<32} : {total_duration:.2f} s")
    print("=" * 65)
    print("BILAN : Tous les critères de la Phase 3 sont validés avec succès.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
