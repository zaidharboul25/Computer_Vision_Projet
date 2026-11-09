"""Test de cohérence entre appel direct des moteurs et sortie via l'orchestrateur (Phase 2)."""
from pathlib import Path
from PIL import Image, ImageOps
import pytest
from app.core.config import settings
from app.engines.patchcore_engine import PatchCoreEngine
from app.engines.registry import engine_registry
from app.engines.similarity_engine import SimilarityEngine
from app.engines.yolo_engine import YOLOEngine


@pytest.fixture
def sample_validation_image() -> Image.Image:
    val_dir = settings.get_dataset_dir() / "images" / "val"
    first_img_path = sorted(val_dir.glob("*"))[0]
    return ImageOps.exif_transpose(Image.open(first_img_path)).convert("RGB")


@pytest.mark.slow
def test_yolo_direct_vs_registry_consistency(sample_validation_image: Image.Image):
    """La sortie de YOLO via le registre doit être strictement identique à un appel direct."""
    yolo_direct = YOLOEngine()
    yolo_direct.load()
    res_direct = yolo_direct.infer(sample_validation_image)

    res_pipeline = engine_registry.run_pipeline(sample_validation_image, selected_engines=["yolo"])
    yolo_reg = res_pipeline["engines"]["yolo"]

    assert res_direct.status == yolo_reg["status"] == "ok"
    assert len(res_direct.regions) == len(yolo_reg["regions"])

    for r_dir, r_pipe in zip(res_direct.regions, yolo_reg["regions"]):
        assert r_dir["bbox"] == r_pipe["bbox"]
        assert r_dir["score"] == r_pipe["score"]
        assert r_dir["classification"] == r_pipe["classification"]
        assert r_dir["label"] == r_pipe["label"]


@pytest.mark.slow
def test_patchcore_direct_vs_registry_consistency(sample_validation_image: Image.Image):
    """La sortie de PatchCore via le registre doit être strictement identique à un appel direct."""
    pcr_direct = PatchCoreEngine()
    pcr_direct.load()
    res_direct = pcr_direct.infer(sample_validation_image)

    res_pipeline = engine_registry.run_pipeline(sample_validation_image, selected_engines=["patchcore"])
    pcr_reg = res_pipeline["engines"]["patchcore"]

    assert res_direct.status == pcr_reg["status"] == "ok"
    assert res_direct.raw_data["score_global"] == pcr_reg["raw_data"]["score_global"]
    assert res_direct.raw_data["tau_global"] == pcr_reg["raw_data"]["tau_global"]
    assert len(res_direct.regions) == len(pcr_reg["regions"])


@pytest.mark.slow
def test_similarity_direct_vs_registry_consistency(sample_validation_image: Image.Image):
    """La sortie de similarité via le registre doit être strictement identique à un appel direct."""
    sim_direct = SimilarityEngine()
    sim_direct.load()
    wg_direct = sim_direct.search(sample_validation_image, "weaveguard", k=5)
    dtd_direct = sim_direct.search(sample_validation_image, "dtd", k=5)

    res_pipeline = engine_registry.run_pipeline(sample_validation_image, selected_engines=["similarity"])
    sim_reg = res_pipeline["engines"]["similarity"]

    assert sim_reg["status"] == "ok"

    wg_pipe = sim_reg["raw_data"]["weaveguard"]
    assert len(wg_direct["results"]) == len(wg_pipe["results"])
    for r_dir, r_pipe in zip(wg_direct["results"], wg_pipe["results"]):
        assert r_dir["ref_id"] == r_pipe["ref_id"]
        assert r_dir["score"] == r_pipe["score"]
        assert r_dir["rank"] == r_pipe["rank"]

    dtd_pipe = sim_reg["raw_data"]["dtd"]
    assert len(dtd_direct["results"]) == len(dtd_pipe["results"])
    for r_dir, r_pipe in zip(dtd_direct["results"], dtd_pipe["results"]):
        assert r_dir["ref_id"] == r_pipe["ref_id"]
        assert r_dir["score"] == r_pipe["score"]
        assert r_dir["rank"] == r_pipe["rank"]

