#!/usr/bin/env python
"""Harnais d'évaluation sur jeu de données externe (WP2).

Permet d'évaluer la chaîne complète d'inférence (YOLO, PatchCore, Fusion)
sur un jeu d'images externes indépendant, sans jamais toucher à datasets/images/test.

Usage :
    cd c:\\Users\\zaidh\\Desktop\\VPO
    backend\\.venv\\Scripts\\python.exe scripts\\eval_external.py
    backend\\.venv\\Scripts\\python.exe scripts\\eval_external.py --dir data/external_test --output docs/PERF_EXTERNAL.md
"""
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageOps

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.engines.fusion import check_overlap, fuse_regions
from app.engines.patchcore_engine import PatchCoreEngine
from app.engines.yolo_engine import YOLOEngine


def load_annotations(ann_file: Path) -> Dict[str, List[Tuple[int, float, float, float, float]]]:
    """Charge les annotations au format WeaveGuard : {filename: [(cls_id, x0, y0, x1, y1), ...]}."""
    if not ann_file.exists():
        return {}
    with open(ann_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def eval_on_directory(images_dir: Path, output_file: Path) -> None:
    if not images_dir.exists() or not any(images_dir.iterdir()):
        print("\n" + "=" * 70)
        print("  HARNAIS D'ÉVALUATION EXTERNE (WP2)")
        print("=" * 70)
        print(f"\n[INFO] Le répertoire cible '{images_dir}' est absent ou vide.")
        print("Pour évaluer WeaveGuard sur un jeu de données externe indépendant :")
        print(f"  1. Créez le répertoire : {images_dir}")
        print("  2. Déposez vos clichés textiles (.jpg, .png, .webp).")
        print("  3. (Optionnel) Déposez un fichier 'annotations.json' avec les vérités terrain.")
        print("\nNote de conformité : Le jeu de test interne (datasets/images/test) reste inviolé.\n")
        return

    image_files = []
    for ext in ("*.webp", "*.jpg", "*.jpeg", "*.png"):
        image_files.extend(images_dir.glob(ext))
    image_files = sorted(image_files)

    if not image_files:
        print(f"[INFO] Aucune image trouvée dans {images_dir}.")
        return

    print(f"\nÉvaluation externe sur {len(image_files)} image(s) dans {images_dir}...")
    ann_file = images_dir / "annotations.json"
    annotations = load_annotations(ann_file) if ann_file.exists() else {}

    yolo = YOLOEngine()
    yolo.load()
    pc = PatchCoreEngine()
    pc.load()

    total_yolo = 0
    total_pc = 0
    total_fused = 0
    total_time = 0.0

    results = []

    for idx, p in enumerate(image_files, 1):
        img = Image.open(p)
        img = ImageOps.exif_transpose(img)
        if img.mode != "RGB":
            img = img.convert("RGB")

        t0 = time.perf_counter()
        y_res = yolo.infer(img)
        pc_res = pc.infer(img)
        fused = fuse_regions(y_res.regions, pc_res.regions)
        elapsed = time.perf_counter() - t0
        total_time += elapsed

        total_yolo += len(y_res.regions)
        total_pc += len(pc_res.regions)
        total_fused += len(fused)

        results.append({
            "image": p.name,
            "size": list(img.size),
            "yolo_count": len(y_res.regions),
            "patchcore_count": len(pc_res.regions),
            "fused_count": len(fused),
            "latency_ms": round(elapsed * 1000, 1),
        })

        print(f"  [{idx:3d}/{len(image_files)}] {p.name}: YOLO={len(y_res.regions)}, PC={len(pc_res.regions)}, Fusion={len(fused)} ({elapsed:.2f}s)")

    # Rapport Markdown
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# Rapport d'Évaluation sur Jeu Externe (WP2)\n\n")
        f.write(f"Date : {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Source : `{images_dir}`\n")
        f.write(f"Nombre d'images analysées : {len(image_files)}\n\n")
        f.write("## Synthèse globale\n\n")
        f.write(f"- Régions YOLO détectées : {total_yolo} (moyenne : {total_yolo/len(image_files):.2f}/image)\n")
        f.write(f"- Régions PatchCore détectées : {total_pc} (moyenne : {total_pc/len(image_files):.2f}/image)\n")
        f.write(f"- Régions fusionnées finales : {total_fused} (moyenne : {total_fused/len(image_files):.2f}/image)\n")
        f.write(f"- Temps moyen d'inférence complète : {total_time/len(image_files):.2f} s / image\n\n")
        f.write("## Détail par cliché\n\n")
        f.write("| Image | Dimensions | YOLO | PatchCore | Fusion | Latence |\n")
        f.write("|---|:---:|:---:|:---:|:---:|:---:|\n")
        for r in results:
            f.write(f"| {r['image']} | {r['size'][0]}x{r['size'][1]} | {r['yolo_count']} | {r['patchcore_count']} | {r['fused_count']} | {r['latency_ms']} ms |\n")

    print(f"\n[OK] Rapport d'évaluation consigné dans : {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Évaluation de WeaveGuard sur un jeu externe.")
    parser.add_argument("--dir", default="data/external_test", help="Répertoire contenant les images externes")
    parser.add_argument("--output", default="docs/PERF_EXTERNAL.md", help="Fichier de rapport Markdown")
    args = parser.parse_args()

    eval_on_directory(PROJECT_ROOT / args.dir, PROJECT_ROOT / args.output)


if __name__ == "__main__":
    main()

