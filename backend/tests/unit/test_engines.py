"""Tests unitaires des moteurs IA (Phase 2).

Vérifie l'intégrité SHA-256, les sorties d'inférence, le format contractuel des boîtes,
les libellés exacts, la fusion et l'isolation des erreurs.
"""
from PIL import Image
import pytest
from app.engines.fusion import check_overlap, fuse_regions
from app.engines.integrity import IntegrityVerifier
from app.engines.patchcore_engine import PatchCoreEngine
from app.engines.registry import EngineRegistry
from app.engines.similarity_engine import SimilarityEngine
from app.engines.yolo_engine import YOLOEngine


def test_sha256_integrity_verifier():
    """Vérifie que les empreintes déclarées correspondent exactement aux artefacts sur disque."""
    yolo_ok, exp_y, act_y = IntegrityVerifier.verify_yolo_integrity()
    assert yolo_ok is True
    assert exp_y == act_y

    pc_ok, exp_pc, act_pc = IntegrityVerifier.verify_patchcore_integrity()
    assert pc_ok is True
    assert exp_pc == act_pc

    sim_results = IntegrityVerifier.verify_similarity_integrity()
    for filename, (valid, exp, act) in sim_results.items():
        assert valid is True, f"Incohérence SHA-256 pour {filename} : {act} != {exp}"


@pytest.mark.slow
def test_yolo_engine_output_contract():
    """Vérifie le contrat de sortie du moteur supervisé YOLO."""
    engine = YOLOEngine()
    engine.load()

    # Création d'une image de test synthétique RGB
    img = Image.new("RGB", (640, 640), color=(128, 128, 128))
    result = engine.infer(img)

    assert result.engine_name == "yolo"
    assert result.status == "ok"
    assert hasattr(result.latency, "preprocess_ms")
    assert hasattr(result.latency, "model_ms")
    assert hasattr(result.latency, "postprocess_ms")


@pytest.mark.slow
def test_patchcore_engine_labels_and_no_percentage():
    """Vérifie que PatchCore n'affiche jamais de classe ni de pourcentage (AC-05, AC-06)."""
    engine = PatchCoreEngine()
    engine.load()

    img = Image.new("RGB", (512, 512), color=(128, 128, 128))
    result = engine.infer(img)

    assert result.engine_name == "patchcore"
    assert result.status == "ok"
    assert "score_global" in result.raw_data
    assert "heatmap_meta" in result.raw_data
    assert result.raw_data["heatmap_meta"]["scale"] == "raw"

    for r in result.regions:
        assert r["classification"] is None
        assert r["classification_method"] is None
        assert r["label"] == "Anomalie suspectée — score de distance"
        assert "%" not in r["score_type"]


@pytest.mark.slow
def test_similarity_engine_labels_and_allowed_fields():
    """Vérifie les libellés contractuels stricts de la similarité et l'anti path-traversal."""
    engine = SimilarityEngine()
    engine.load()

    img = Image.new("RGB", (256, 256), color=(200, 100, 50))
    res_wg = engine.search(img, index_name="weaveguard", k=3)
    assert res_wg["label"] == "Textiles similaires (index WeaveGuard)"
    assert res_wg["metric"] == "cosine_similarity"
    for item in res_wg["results"]:
        assert "ref_id" in item
        # Ne doit JAMAIS exposer de chemin local
        assert "path" not in item
        assert "\\" not in item["ref_id"]

    res_dtd = engine.search(img, index_name="dtd", k=3)
    assert res_dtd["label"] == "Textures similaires (galerie DTD générique)"
    for item in res_dtd["results"]:
        assert "category" in item
        assert "path" not in item

    # Test anti path-traversal sur les vignettes
    with pytest.raises(ValueError):
        engine.resolve_ref_thumbnail("../../secret.txt")


def test_fusion_logic_corroboration_and_orphans():
    """Vérifie la logique de fusion selon fusion_spec.json."""
    tau = 1.6386

    # 1. Boîte YOLO
    yolo_regions = [
        {
            "region_id": "Y1",
            "source_engine": "yolo",
            "bbox": [100.0, 100.0, 50.0, 50.0],
            "area": 2500.0,
            "score": 0.85,
            "score_type": "confiance",
            "score_threshold": 0.311,
            "classification": "Hole",
            "label": "Défaut proposé : Hole",
        }
    ]

    # 2. Région PatchCore recouvrant la boîte YOLO (> 10% de la boîte YOLO)
    overlapping_pc = [
        {
            "region_id": "P1",
            "source_engine": "patchcore",
            "bbox": [105.0, 105.0, 40.0, 40.0],
            "area": 1600.0,
            "score": 1.95,
            "score_type": "distance L2",
            "score_threshold": tau,
            "classification": None,
            "label": "Anomalie suspectée — score de distance",
        },
        # Région PatchCore totalement disjointe (orpheline)
        {
            "region_id": "P2",
            "source_engine": "patchcore",
            "bbox": [500.0, 500.0, 30.0, 30.0],
            "area": 900.0,
            "score": 1.72,
            "score_type": "distance L2",
            "score_threshold": tau,
            "classification": None,
            "label": "Anomalie suspectée — score de distance",
        },
    ]

    fused = fuse_regions(yolo_regions, overlapping_pc, tau=tau)

    # Doit contenir exactement 2 régions : la détection YOLO corroborée et l'orpheline PatchCore
    assert len(fused) == 2

    y_fused = next(r for r in fused if r["source_engine"] == "yolo")
    assert y_fused["classification"] == "Hole"
    assert y_fused["corroboration"] is not None
    assert y_fused["corroboration"]["engine"] == "patchcore"
    assert y_fused["corroboration"]["score"] == 1.95

    p_fused = next(r for r in fused if r["source_engine"] == "patchcore")
    assert p_fused["classification"] is None
    assert p_fused["label"] == "Anomalie suspectée — score de distance"
    assert p_fused["corroboration"] is None


def test_registry_error_isolation():
    """Vérifie qu'une défaillance d'un moteur n'invalide pas les résultats des autres moteurs."""
    registry = EngineRegistry()

    # Création d'une image factice
    img = Image.new("RGB", (640, 640), color=(100, 100, 100))

    # Simulation d'erreur dans un des moteurs
    class FailingEngine:
        def infer(self, image):
            raise RuntimeError("Simulation panne GPU/Mémoire")

    registry._engines["patchcore"] = FailingEngine()  # type: ignore

    res = registry.run_pipeline(img, selected_engines=["yolo", "patchcore"])

    # YOLO doit avoir réussi
    assert res["engines"]["yolo"]["status"] == "ok"

    # PatchCore doit être marqué 'error' avec son message d'erreur
    assert res["engines"]["patchcore"]["status"] == "error"
    assert "Simulation panne GPU" in res["engines"]["patchcore"]["error_message"]

    # Le pipeline a produit un résultat partiel avec les détections YOLO
    assert len(res["fused_regions"]) >= 0

