"""Tests de parité — Moteur Similarité.

Vérifie que les embeddings ResNet-50 et les résultats de recherche FAISS
ne régressent pas après une optimisation exacte.

Critères de parité :
  - Similarité cosinus entre l'embedding courant et l'embedding de référence ≥ 0.9999
  - Même top-1 ref_id dans l'index WeaveGuard
  - |score_top1_avant - score_top1_après| ≤ 1e-3

Usage :
    pytest tests/parity/test_parity_similarity.py -v
    # (nécessite d'avoir exécuté scripts/generate_parity_reference.py)
"""
import sys
from pathlib import Path
from typing import Dict, Any

import numpy as np
import pytest
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from parity_helpers import get_val_images, load_reference, skip_if_no_references


COSINE_MIN = 0.9999
SCORE_TOL = 1e-3


@pytest.fixture(scope="module")
def similarity_engine():
    """Charge le moteur similarité une seule fois pour tout le module."""
    skip_if_no_references()
    from app.engines.similarity_engine import SimilarityEngine
    engine = SimilarityEngine()
    engine.load()
    return engine


class TestSimilarityParity:
    """Suite de tests de parité pour le moteur Similarité."""

    def test_references_present(self):
        """Vérifie que les références existent avant de lancer les tests."""
        skip_if_no_references()

    @pytest.mark.slow
    @pytest.mark.parametrize("image_path", get_val_images(50), ids=lambda p: p.stem)
    def test_similarity_embedding_cosine(self, image_path: Path, similarity_engine):
        """Vérifie que l'embedding produit est quasi-identique à la référence (cosine ≥ 0.9999)."""
        skip_if_no_references()
        ref = load_reference(image_path.stem)
        ref_embedding = ref.get("similarity", {}).get("embedding_wg")
        if ref_embedding is None:
            pytest.skip("Embedding de référence absent (référence générée sans embedding)")

        import torch
        import torch.nn.functional as F

        img = Image.open(image_path)
        img = ImageOps.exif_transpose(img)
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Extraction de l'embedding courant
        x_tensor = similarity_engine.transform(img).unsqueeze(0).to(similarity_engine.device)
        with torch.no_grad():
            cur_feat = similarity_engine.embedder(x_tensor).cpu().numpy().astype("float32")

        ref_arr = np.array(ref_embedding, dtype="float32").reshape(1, -1)
        # Normalisation L2 (au cas où)
        ref_norm = ref_arr / (np.linalg.norm(ref_arr) + 1e-9)
        cur_norm = cur_feat / (np.linalg.norm(cur_feat) + 1e-9)

        cosine = float(np.dot(cur_norm.flatten(), ref_norm.flatten()))
        assert cosine >= COSINE_MIN, (
            f"{image_path.name}: cosine={cosine:.6f} < {COSINE_MIN}"
        )

    @pytest.mark.slow
    @pytest.mark.parametrize("image_path", get_val_images(50), ids=lambda p: p.stem)
    def test_similarity_top1_weaveguard(self, image_path: Path, similarity_engine):
        """Vérifie que le top-1 WeaveGuard (ref_id et score) est identique à la référence."""
        skip_if_no_references()
        ref = load_reference(image_path.stem)
        ref_wg = ref.get("similarity", {}).get("wg_top1")
        if ref_wg is None:
            pytest.skip("wg_top1 absent de la référence")

        img = Image.open(image_path)
        img = ImageOps.exif_transpose(img)
        if img.mode != "RGB":
            img = img.convert("RGB")

        result = similarity_engine.search(img, index_name="weaveguard", k=1)
        results = result.get("results", [])
        assert len(results) >= 1, f"{image_path.name}: aucun résultat retourné"

        cur_top1 = results[0]
        assert cur_top1.get("ref_id") == ref_wg.get("ref_id"), (
            f"{image_path.name}: top-1 ref_id='{cur_top1.get('ref_id')}' "
            f"!= référence '{ref_wg.get('ref_id')}'"
        )
        score_diff = abs(cur_top1.get("score", 0.0) - ref_wg.get("score", 0.0))
        assert score_diff <= SCORE_TOL, (
            f"{image_path.name}: |score|={score_diff:.6f} > {SCORE_TOL}"
        )
