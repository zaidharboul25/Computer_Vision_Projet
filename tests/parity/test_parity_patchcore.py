"""Tests de parité — Moteur PatchCore.

Vérifie que les sorties PatchCore (boîtes de régions anomales, scores)
ne régressent pas après une optimisation exacte.

Critères de parité :
  - Même nombre de régions détectées
  - IoU ≥ 0.99 pour chaque région correspondante
  - |score_avant - score_après| ≤ 1e-3

Usage :
    pytest tests/parity/test_parity_patchcore.py -v
    # (nécessite d'avoir exécuté scripts/generate_parity_reference.py)
"""
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageOps

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


@pytest.fixture(scope="module")
def patchcore_engine():
    """Charge PatchCore une seule fois pour tout le module (~3s)."""
    skip_if_no_references()
    from app.engines.patchcore_engine import PatchCoreEngine
    engine = PatchCoreEngine()
    engine.load()
    return engine


class TestPatchCoreParity:
    """Suite de tests de parité pour le moteur PatchCore."""

    def test_references_present(self):
        """Vérifie que les références existent avant de lancer les tests."""
        skip_if_no_references()

    @pytest.mark.slow
    @pytest.mark.parametrize("image_path", get_val_images(50), ids=lambda p: p.stem)
    def test_patchcore_parity_per_image(self, image_path: Path, patchcore_engine):
        """Pour chaque image, vérifie que les sorties PatchCore correspondent aux références."""
        skip_if_no_references()
        ref = load_reference(image_path.stem)
        ref_regions = ref.get("patchcore", {}).get("regions", [])

        img = Image.open(image_path)
        img = ImageOps.exif_transpose(img)
        if img.mode != "RGB":
            img = img.convert("RGB")

        result = patchcore_engine.infer(img)
        cur_regions = result.regions

        # Même nombre de régions
        assert len(cur_regions) == len(ref_regions), (
            f"{image_path.name}: {len(cur_regions)} régions vs {len(ref_regions)} en référence"
        )

        # Comparaison région par région (triées par score décroissant)
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

    @pytest.mark.slow
    @pytest.mark.parametrize("image_path", get_val_images(50), ids=lambda p: p.stem)
    def test_patchcore_global_score_parity(self, image_path: Path, patchcore_engine):
        """Vérifie que le score global PatchCore ne dépasse pas la tolérance."""
        skip_if_no_references()
        ref = load_reference(image_path.stem)
        ref_global = ref.get("patchcore", {}).get("score_global")
        if ref_global is None:
            pytest.skip("score_global absent de la référence")

        img = Image.open(image_path)
        img = ImageOps.exif_transpose(img)
        if img.mode != "RGB":
            img = img.convert("RGB")

        result = patchcore_engine.infer(img)
        cur_global = result.raw_data.get("score_global", 0.0)

        assert abs(cur_global - ref_global) <= SCORE_TOL, (
            f"{image_path.name}: score_global {cur_global:.4f} vs ref {ref_global:.4f} "
            f"(diff={abs(cur_global - ref_global):.6f} > {SCORE_TOL})"
        )
