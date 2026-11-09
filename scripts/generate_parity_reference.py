#!/usr/bin/env python
"""Génération des sorties de référence pour les tests de parité WeaveGuard AI.

Prend les 50 premières images du split de validation (tri lexicographique),
exécute les 3 moteurs (YOLO, PatchCore, Similarité) sur chacune,
et sauvegarde les sorties dans tests/parity/reference_outputs/{stem}.json.

Ce script est exécuté UNE SEULE FOIS avant toute optimisation.
Les résultats sont immuables jusqu'à une régénération explicite (--force).

Usage :
    cd c:\\Users\\zaidh\\Desktop\\VPO
    backend\\.venv\\Scripts\\python.exe scripts\\generate_parity_reference.py
    backend\\.venv\\Scripts\\python.exe scripts\\generate_parity_reference.py --force  # écrase si existe
    backend\\.venv\\Scripts\\python.exe scripts\\generate_parity_reference.py --n 10   # 10 images seulement
"""
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image, ImageOps

# Racine du projet
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.engines.patchcore_engine import PatchCoreEngine
from app.engines.similarity_engine import SimilarityEngine
from app.engines.yolo_engine import YOLOEngine


REFERENCE_DIR = PROJECT_ROOT / "tests" / "parity" / "reference_outputs"
VAL_DIR = PROJECT_ROOT / "datasets" / "images" / "val"


def get_val_images(n: int = 50) -> List[Path]:
    """Retourne les n premières images val (tri lexicographique, toutes extensions)."""
    all_images: List[Path] = []
    for ext in ("*.webp", "*.jpg", "*.jpeg", "*.png"):
        all_images.extend(VAL_DIR.glob(ext))
    return sorted(all_images)[:n]


def open_image(path: Path) -> Image.Image:
    """Ouvre, transpose EXIF et convertit en RGB."""
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def run_yolo(engine: YOLOEngine, img: Image.Image) -> Dict[str, Any]:
    result = engine.infer(img)
    return {
        "regions": result.regions,
        "latency_ms": result.latency.model_dump(),
    }


def run_patchcore(engine: PatchCoreEngine, img: Image.Image) -> Dict[str, Any]:
    result = engine.infer(img)
    raw = result.raw_data
    return {
        "regions": result.regions,
        "score_global": raw.get("score_global"),
        "map_shape": raw.get("map_shape"),
        "latency_ms": result.latency.model_dump(),
        # score_map non sérialisé (numpy array) — non inclus dans la référence
    }


def run_similarity(engine: SimilarityEngine, img: Image.Image) -> Dict[str, Any]:
    import torch
    import numpy as np

    # Embedding (pour le test de parité cosinus)
    x_tensor = engine.transform(img).unsqueeze(0).to(engine.device)
    with torch.no_grad():
        feat = engine.embedder(x_tensor).cpu().numpy().astype("float32")
    embedding_wg = feat.flatten().tolist()

    # Recherche top-1 WeaveGuard
    wg_res = engine.search(img, index_name="weaveguard", k=1)
    wg_top1 = wg_res.get("results", [None])[0]

    return {
        "embedding_wg": embedding_wg,
        "wg_top1": wg_top1,
        "latency_ms": wg_res.get("latency_ms", {}),
    }


def main():
    parser = argparse.ArgumentParser(description="Génère les sorties de référence pour les tests de parité.")
    parser.add_argument("--n", type=int, default=50, help="Nombre d'images val à traiter (défaut: 50)")
    parser.add_argument("--force", action="store_true", help="Écrase les fichiers de référence existants")
    args = parser.parse_args()

    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)

    images = get_val_images(args.n)
    if not images:
        print(f"[ERREUR] Aucune image trouvée dans {VAL_DIR}")
        sys.exit(1)

    print(f"Chargement des moteurs...")
    t0 = time.perf_counter()
    yolo = YOLOEngine()
    yolo.load()
    pc = PatchCoreEngine()
    pc.load()
    sim = SimilarityEngine()
    sim.load()
    print(f"  Moteurs chargés en {time.perf_counter() - t0:.1f}s")

    skipped = 0
    generated = 0
    errors = 0

    print(f"\nTraitement de {len(images)} images...")
    for i, img_path in enumerate(images, 1):
        ref_file = REFERENCE_DIR / f"{img_path.stem}.json"

        if ref_file.exists() and not args.force:
            skipped += 1
            print(f"  [{i:3d}/{len(images)}] SKIP  {img_path.name} (référence existante)")
            continue

        try:
            img = open_image(img_path)
            t_img = time.perf_counter()

            yolo_out = run_yolo(yolo, img)
            pc_out = run_patchcore(pc, img)
            sim_out = run_similarity(sim, img)

            reference = {
                "image": img_path.name,
                "size": list(img.size),
                "yolo": yolo_out,
                "patchcore": pc_out,
                "similarity": sim_out,
            }

            with open(ref_file, "w", encoding="utf-8") as f:
                json.dump(reference, f, ensure_ascii=False, indent=2)

            elapsed = time.perf_counter() - t_img
            print(
                f"  [{i:3d}/{len(images)}] OK    {img_path.name} "
                f"(YOLO:{len(yolo_out['regions'])}det, "
                f"PC:{len(pc_out['regions'])}reg, "
                f"{elapsed:.1f}s)"
            )
            generated += 1

        except Exception as e:
            print(f"  [{i:3d}/{len(images)}] ERROR {img_path.name}: {e}")
            errors += 1

    print(f"\n{'='*60}")
    print(f"Résultat : {generated} générés, {skipped} ignorés, {errors} erreurs")
    print(f"Répertoire : {REFERENCE_DIR}")

    if errors > 0:
        print(f"\n[AVERTISSEMENT] {errors} erreur(s) — vérifiez les moteurs.")
        sys.exit(1)

    print("\n[OK] Références de parité générées. Lancez les tests avec :")
    print("     pytest tests/parity/ -v -m slow")


if __name__ == "__main__":
    main()

