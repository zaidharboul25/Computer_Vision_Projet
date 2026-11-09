#!/usr/bin/env python
"""
Script de reproduction des métriques de validation (Phase 2, condition 6).
Exécute YOLO + PatchCore + Fusion via les moteurs du backend sur datasets/images/val
et compare les résultats à models/fusion/fusion_v1/fusion_spec.json.

Tolérance maximale contractuelle : ±0.03 sur les rappels.

Usage:
    python backend/scripts/reproduce_metrics.py --limit 10   # Contrôle rapide
    python backend/scripts/reproduce_metrics.py              # Exécution complète (162 images)
"""
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
from PIL import Image, ImageOps

# Ajout du répertoire backend au chemin Python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.engines.fusion import check_overlap
from app.engines.patchcore_engine import PatchCoreEngine
from app.engines.yolo_engine import YOLOEngine


def read_ground_truth(label_file: Path, W: int, H: int) -> List[Tuple[int, float, float, float, float]]:
    """Lit les boîtes GT normalisées et les convertit en pixels natifs (c, x0, y0, x1, y1)."""
    gt = []
    if not label_file.exists():
        return gt
    for line in label_file.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) == 5:
            c = int(parts[0])
            cx, cy, bw, bh = map(float, parts[1:])
            x0 = (cx - bw / 2.0) * W
            y0 = (cy - bh / 2.0) * H
            x1 = (cx + bw / 2.0) * W
            y1 = (cy + bh / 2.0) * H
            gt.append((c, x0, y0, x1, y1))
    return gt


def _inter(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h)


def _area(b: Tuple[float, float, float, float]) -> float:
    return max(1e-9, (b[2] - b[0]) * (b[3] - b[1]))


def _iou(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    i = _inter(a, b)
    return i / (_area(a) + _area(b) - i)


def evaluate_image(
    gt: List[Tuple[int, float, float, float, float]],
    yolo_regions: List[Dict[str, Any]],
    pcr_regions: List[Dict[str, Any]],
    classes: List[str],
) -> Dict[str, Any]:
    # YOLO boxes: (c, conf, x0, y0, x1, y1)
    y_boxes = []
    for r in yolo_regions:
        c_name = r.get("classification")
        c_idx = classes.index(c_name) if c_name in classes else -1
        x, y, w, h = r["bbox"]
        y_boxes.append((c_idx, r["score"], x, y, x + w, y + h))

    # Tri par confiance décroissante
    y_boxes.sort(key=lambda t: -t[1])

    used_gt = set()
    for p in y_boxes:
        best_iou, best_j = 0.0, -1
        for j, g in enumerate(gt):
            if j in used_gt or g[0] != p[0]:
                continue
            v = _iou((p[2], p[3], p[4], p[5]), (g[1], g[2], g[3], g[4]))
            if v >= 0.5 and v > best_iou:
                best_iou, best_j = v, j
        if best_j >= 0:
            used_gt.add(best_j)

    # PatchCore boxes: (x0, y0, x1, y1)
    p_boxes = []
    for r in pcr_regions:
        x, y, w, h = r["bbox"]
        p_boxes.append((x, y, x + w, y + h))

    found_y = [j in used_gt for j in range(len(gt))]
    found_p_loose = [
        any(_inter((g[1], g[2], g[3], g[4]), b) / _area((g[1], g[2], g[3], g[4])) >= 0.10 for b in p_boxes)
        for g in gt
    ]
    found_p_strict = [
        any(_iou((g[1], g[2], g[3], g[4]), b) >= 0.30 for b in p_boxes)
        for g in gt
    ]

    # Nombre de régions PatchCore seules (ne recouvrant aucune boîte YOLO)
    pc_only = 0
    for pb in p_boxes:
        if not any(check_overlap((yb[2], yb[3], yb[4], yb[5]), pb) for yb in y_boxes):
            pc_only += 1

    return {
        "n_gt": len(gt),
        "found_y": found_y,
        "found_p_loose": found_p_loose,
        "found_p_strict": found_p_strict,
        "pc_only": pc_only,
    }


def main():
    parser = argparse.ArgumentParser(description="Reproduction des métriques WeaveGuard AI")
    parser.add_argument("--limit", type=int, default=None, help="Nombre max d'images à traiter")
    args = parser.parse_args()

    print("=" * 65)
    print(" WeaveGuard AI - Reproduction des Métriques de Validation (§6)")
    print("=" * 65)

    # 1. Chargement de la spécification de fusion de référence
    spec_path = settings.get_models_dir() / "fusion" / "fusion_v1" / "fusion_spec.json"
    with open(spec_path, "r", encoding="utf-8") as f:
        spec = json.load(f)
    ref_val = spec["validation"]

    # 2. Initialisation des moteurs backend
    print("Initialisation des moteurs YOLO et PatchCore...")
    yolo_engine = YOLOEngine()
    yolo_engine.load()

    patchcore_engine = PatchCoreEngine()
    patchcore_engine.load()

    classes = yolo_engine.classes
    val_images_dir = settings.get_dataset_dir() / "images" / "val"
    val_labels_dir = settings.get_dataset_dir() / "labels" / "val"

    image_paths = sorted(val_images_dir.glob("*"))
    if args.limit:
        image_paths = image_paths[: args.limit]

    n_images = len(image_paths)
    print(f"Évaluation sur {n_images} image(s) de validation...")

    all_found_y = []
    all_found_p_loose = []
    all_found_p_strict = []
    all_pc_only = []
    total_gt = 0

    t0 = time.time()
    for idx, p in enumerate(image_paths, 1):
        im = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
        W, H = im.size

        # Lecture annotations GT correspondantes
        lab_file = val_labels_dir / (p.stem + ".txt")
        gt = read_ground_truth(lab_file, W, H)
        total_gt += len(gt)

        # Inférence backend réelle
        y_res = yolo_engine.infer(im)
        p_res = patchcore_engine.infer(im)

        eval_res = evaluate_image(gt, y_res.regions, p_res.regions, classes)
        all_found_y.extend(eval_res["found_y"])
        all_found_p_loose.extend(eval_res["found_p_loose"])
        all_found_p_strict.extend(eval_res["found_p_strict"])
        all_pc_only.append(eval_res["pc_only"])

        if idx % 20 == 0 or idx == n_images:
            print(f"  [{idx}/{n_images}] {time.time() - t0:.1f}s écoulées...")

    # Calcul des métriques
    yolo_hits = sum(all_found_y)
    pcr_loose_hits = sum(all_found_p_loose)
    union_loose_hits = sum(a or b for a, b in zip(all_found_y, all_found_p_loose))
    pc_only_total = sum(all_pc_only)

    r_yolo = yolo_hits / max(1, total_gt)
    r_pcr_loose = pcr_loose_hits / max(1, total_gt)
    r_union_loose = union_loose_hits / max(1, total_gt)
    pc_only_per_img = pc_only_total / max(1, n_images)

    print("\n" + "=" * 65)
    print(f"RÉSULTATS OBTENUS (sur {n_images} images, {total_gt} boîtes GT) :")
    print(f"  - Rappel YOLO seul                : {r_yolo:.3f} ({yolo_hits}/{total_gt})")
    print(f"  - Rappel PatchCore seul (souple)  : {r_pcr_loose:.3f} ({pcr_loose_hits}/{total_gt})")
    print(f"  - Rappel Union souple             : {r_union_loose:.3f} ({union_loose_hits}/{total_gt})")
    print(f"  - Régions PatchCore seules / img  : {pc_only_per_img:.3f} ({pc_only_total} régions sur {n_images} images)")
    print("=" * 65)

    if not args.limit or args.limit >= 162:
        ref_yolo = ref_val["recalls"]["YOLO seul"]["rappel"]
        ref_pcr = ref_val["recalls"]["PatchCore seul (recouvrement >= 10 % de la boîte)"]["rappel"]
        ref_union = ref_val["recalls"]["Union YOLO + PatchCore (souple)"]["rappel"]
        ref_pc_only = ref_val["patchcore_only_regions_per_image"]

        print("COMPARAISON AVEC LA RÉFÉRENCE CONTRACTUELLE (fusion_spec.json) :")
        print(f"  - YOLO seul         : Réf = {ref_yolo:.3f} | Calculé = {r_yolo:.3f} | Écart = {abs(r_yolo - ref_yolo):.3f}")
        print(f"  - PatchCore seul    : Réf = {ref_pcr:.3f} | Calculé = {r_pcr_loose:.3f} | Écart = {abs(r_pcr_loose - ref_pcr):.3f}")
        print(f"  - Union souple      : Réf = {ref_union:.3f} | Calculé = {r_union_loose:.3f} | Écart = {abs(r_union_loose - ref_union):.3f}")
        print(f"  - PatchCore seul/img: Réf = {ref_pc_only:.3f} | Calculé = {pc_only_per_img:.3f} | Écart = {abs(pc_only_per_img - ref_pc_only):.3f}")

        TOLERANCE = 0.03
        yolo_ok = abs(r_yolo - ref_yolo) <= TOLERANCE
        pcr_ok = abs(r_pcr_loose - ref_pcr) <= TOLERANCE
        union_ok = abs(r_union_loose - ref_union) <= TOLERANCE


        if yolo_ok and pcr_ok and union_ok:
            print("\n[SUCCÈS] Tous les rappels respectent la tolérance stricte de ±0.03.")
            return True
        else:
            print(f"\n[ALERTE] Écart hors tolérance (±{TOLERANCE}) :")
            if not yolo_ok:
                print(f"  -> YOLO écart={abs(r_yolo - ref_yolo):.4f} > {TOLERANCE}")
            if not pcr_ok:
                print(f"  -> PatchCore écart={abs(r_pcr_loose - ref_pcr):.4f} > {TOLERANCE}")
            if not union_ok:
                print(f"  -> Union écart={abs(r_union_loose - ref_union):.4f} > {TOLERANCE}")
            return False

    return True


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)

