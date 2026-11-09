"""Tests de parité — Moteur YOLO.

Vérifie que les sorties YOLO (boîtes, classes, scores) ne régressent pas
après une optimisation exacte.

Critères de parité :
  - Même nombre de détections
  - IoU ≥ 0.99 pour chaque boîte correspondante
  - |score_avant - score_après| ≤ 1e-3
  - Même classe (classification)

Usage :
    pytest tests/parity/test_parity_yolo.py -v
    # (nécessite d'avoir exécuté scripts/generate_parity_reference.py)
"""
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageOps

# Ajout des répertoires au sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from parity_helpers import get_val_images, load_reference, skip_if_no_references


SCORE_TOL = 1e-3
IOU_MIN = 0.99


def _iou(a, b) -> float:
    """IoU entre deux boîtes [x, y, w, h]."""
    ax0, ay0, aw, ah = a
    bx0, by0, bw, bh = b
    ax1, ay1 = ax0 + aw, ay0 + ah
    bx1, by1 = bx0 + bw, by0 + bh
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    union = aw * ah + bw * bh - inter
    return inter / max(union, 1e-9)


def run_yolo(image_path: Path):
    """Exécute YOLO sur une image et retourne les régions."""
    from app.engines.yolo_engine import YOLOEngine

    engine = YOLOEngine()
    img = Image.open(image_path)
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    result = engine.infer(img)
    return result.regions


@pytest.fixture(scope="module")
def yolo_engine():
    """Charge le moteur YOLO une seule fois pour tout le module."""
    skip_if_no_references()
    from app.engines.yolo_engine import YOLOEngine
    engine = YOLOEngine()
    engine.load()
    return engine


class TestYoloParity:
    """Suite de tests de parité pour le moteur YOLO."""

    def test_references_present(self):
        """Vérifie que les références existent avant de lancer les tests."""
        skip_if_no_references()

    @pytest.mark.slow
    @pytest.mark.parametrize("image_path", get_val_images(50), ids=lambda p: p.stem)
    def test_yolo_parity_per_image(self, image_path: Path, yolo_engine):
        """Pour chaque image, vérifie que les sorties YOLO correspondent aux références."""
        skip_if_no_references()
        ref = load_reference(image_path.stem)
        ref_regions = ref.get("yolo", {}).get("regions", [])

        img = Image.open(image_path)
        img = ImageOps.exif_transpose(img)
        if img.mode != "RGB":
            img = img.convert("RGB")

        result = yolo_engine.infer(img)
        cur_regions = result.regions

        # Même nombre de détections
        assert len(cur_regions) == len(ref_regions), (
            f"{image_path.name}: {len(cur_regions)} détections vs {len(ref_regions)} en référence"
        )

        # Comparaison boîte à boîte (déjà triées par score décroissant)
        for i, (cur, ref_r) in enumerate(zip(cur_regions, ref_regions)):
            iou = _iou(cur["bbox"], ref_r["bbox"])
            assert iou >= IOU_MIN, (
                f"{image_path.name} région {i}: IoU={iou:.4f} < {IOU_MIN} "
                f"(cur={cur['bbox']}, ref={ref_r['bbox']})"
            )
            score_diff = abs(cur.get("score", 0.0) - ref_r.get("score", 0.0))
            assert score_diff <= SCORE_TOL, (
                f"{image_path.name} région {i}: |score|={score_diff:.6f} > {SCORE_TOL}"
            )
            assert cur.get("classification") == ref_r.get("classification"), (
                f"{image_path.name} région {i}: classe '{cur.get('classification')}' "
                f"!= référence '{ref_r.get('classification')}'"
            )
