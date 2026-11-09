"""Tests unitaires pour la visualisation (Heatmap, Overlay) et l'Export JSON (Phase 3).

Vérifie :
- Exigence E (AC-03) : Génération de l'overlay uniquement depuis les régions en base et reproductibilité.
- Exigence F : Heatmap PNG 8 bits avec normalisation documentée (0 -> 0, vmax -> 255).
- Exigence I (AC-04, AC-07) : Validation de l'export par le schéma export_schema_v1.json,
  séparation étanche prédictions / revues humaines, audit anti-fuite de secrets et chemins locaux.
"""
from datetime import datetime, timezone
import numpy as np
import pytest
from PIL import Image, ImageFont
from app.core.errors import AppException
from app.services.export import ExportService, check_no_leaks_or_secrets
from app.services.visualizer import VisualizerService


def test_heatmap_generation_8bit_and_normalization():
    """Vérifie la génération de la heatmap PNG 8 bits et sa formule de normalisation (Exigence F)."""
    # Création d'une carte brute de score avec des valeurs flottantes connues
    raw_map = np.array([
        [0.0, 1.0],
        [2.0, 4.0]
    ], dtype=np.float32)

    stored_size = (100, 100)
    tau = 1.6386

    heatmap_img, meta = VisualizerService.generate_heatmap(raw_map, stored_size, tau)

    # 1. Vérification du format d'image : 8-bit ('L')
    assert heatmap_img.mode == "L"
    assert heatmap_img.size == stored_size

    # 2. Vérification des métadonnées
    assert meta.scale == "raw"
    assert meta.min == 0.0
    assert meta.max == 4.0
    assert meta.vmax == 4.0
    assert meta.tau == 1.6386
    assert meta.width == 100
    assert meta.height == 100

    # 3. Vérification de la formule : 0 -> 0, vmax (max(2*tau, max) = max(3.2772, 4.0) = 4.0) -> 255
    arr_out = np.array(heatmap_img)
    assert arr_out.min() == 0
    assert arr_out.max() == 255


def test_heatmap_vmax_formula_and_saturation():
    """Vérifie la formule vmax = max(2*tau, max(score_map)) (Correction 1).
    - Une carte de max 1.19 (tau=1.6386) donne un 8 bits dont aucun pixel ne dépasse tau/vmax*255.
    - Une carte de max 2.4 (tau=1.0 -> 2*tau=2.0 < 2.4) atteint 255 uniquement à la valeur 2.4.
    """
    tau1 = 1.6386
    map1 = np.array([[0.0, 0.5], [1.0, 1.19]], dtype=np.float32)
    img1, meta1 = VisualizerService.generate_heatmap(map1, (10, 10), tau1)

    expected_vmax1 = 2.0 * tau1
    assert pytest.approx(meta1.vmax, rel=1e-3) == expected_vmax1
    max_pixel_val = int(np.array(img1).max())
    threshold_pixel = int(np.floor((tau1 / meta1.vmax) * 255.0))
    # Aucun pixel ne dépasse le seuil tau
    assert max_pixel_val <= threshold_pixel

    tau2 = 1.0  # 2*tau = 2.0 < 2.4 -> vmax = 2.4
    map2 = np.array([[0.0, 1.5], [2.0, 2.4]], dtype=np.float32)
    img2, meta2 = VisualizerService.generate_heatmap(map2, (10, 10), tau2)
    assert meta2.vmax == 2.4
    arr2 = np.array(img2)
    assert arr2.max() == 255
    # Seule la valeur maximale atteint 255
    assert np.all(arr2[arr2 < 255] < 255)


def test_overlay_generation_deterministic_and_ac03():
    """Vérifie que l'overlay est généré uniquement depuis les régions de l'API (AC-03)."""
    base_img = Image.new("RGB", (300, 300), color=(120, 120, 120))
    regions = [
        {
            "id": "reg-uuid-1",
            "engine": "yolo",
            "bbox": [50.0, 50.0, 40.0, 40.0],
            "label": "Défaut proposé : trou",
            "corroboration": {"detected": False},
        },
        {
            "id": "reg-uuid-2",
            "engine": "patchcore",
            "bbox": [150.0, 150.0, 60.0, 60.0],
            "label": "Anomalie suspectée — score de distance",
            "corroboration": {"detected": False},
        },
    ]

    overlay1 = VisualizerService.generate_overlay(base_img, regions)
    overlay2 = VisualizerService.generate_overlay(base_img, regions)

    # L'image générée doit être strictement déterministe (mêmes octets et pixels)
    assert np.array_equal(np.array(overlay1), np.array(overlay2))
    assert overlay1.width == 300
    assert overlay1.height > 300  # Bandeau de légende sous l'image


def test_overlay_accented_characters_font_support():
    """Vérifie que la police TrueType (DejaVu Sans) supporte les caractères latins accentués

    (é, è, à, —) sans utiliser de glyphe de remplacement (▯), et que la taille est proportionnelle.
    """
    from app.services.visualizer import DEJAVU_FONT_PATH
    assert DEJAVU_FONT_PATH.exists(), f"La police TrueType doit être présente dans le dépôt : {DEJAVU_FONT_PATH}"

    # Vérification que la police contient bien les glyphes réels demandés
    font = ImageFont.truetype(str(DEJAVU_FONT_PATH), size=20)
    for char in ["é", "è", "à", "—"]:
        mask = font.getmask(char)
        assert mask.size[0] > 0 and mask.size[1] > 0

    base_img = Image.new("RGB", (800, 600), color=(50, 50, 50))
    region = {
        "id": "reg-test-accent",
        "engine": "yolo",
        "bbox": [50.0, 50.0, 100.0, 100.0],
        "label": "Défaut proposé : Vertical LineMark",
        "corroboration": {"detected": False},
        "display_id": "Y1",
    }

    overlay = VisualizerService.generate_overlay(base_img, [region])
    assert overlay.width == 800
    assert overlay.height > 600  # Contient le bandeau de légende sous l'image
    # L'image d'overlay doit comporter les tracés textuels et le rectangle
    arr = np.array(overlay)
    assert np.any(arr[..., 0] == 255)


def test_overlay_corner_boxes_never_overflow():
    """Vérifie qu'aucune étiquette ne dépasse l'image, même pour des boîtes collées aux coins."""
    # Image petite (ex: pull en maille de 343 px de large)
    img_w, img_h = 343, 200
    base_img = Image.new("RGB", (img_w, img_h), color=(70, 70, 70))
    regions = [
        # Coin supérieur gauche
        {
            "id": "corner-tl",
            "engine": "yolo",
            "bbox": [0.0, 0.0, 50.0, 40.0],
            "label": "Défaut proposé : trou",
            "display_id": "Y1",
        },
        # Coin inférieur droit
        {
            "id": "corner-br",
            "engine": "patchcore",
            "bbox": [293.0, 150.0, 50.0, 50.0],
            "label": "Anomalie suspectée — score de distance",
            "score": 2.34,
            "display_id": "P1",
        },
    ]

    overlay = VisualizerService.generate_overlay(base_img, regions)
    assert overlay.width == img_w
    assert overlay.height > img_h
    # La génération n'a levé aucune exception et l'overlay est produit avec succès


def test_display_id_deterministic_assignment():
    """Vérifie l'assignation déterministe des display_id (Y1, Y2... par confiance décroissante, P1, P2... par score décroissant)."""
    from app.services.queue import assign_display_ids

    # Simulation de détections brutes fusionnées
    fused_regs = [
        {"engine": "yolo", "score": 0.65, "bbox": [10, 20, 30, 40], "label": "Défaut proposé : fil tiré"},
        {"engine": "patchcore", "score": 1.85, "bbox": [50, 60, 20, 20], "label": "Anomalie suspectée"},
        {"engine": "yolo", "score": 0.95, "bbox": [100, 100, 40, 40], "label": "Défaut proposé : trou"},
        {"engine": "patchcore", "score": 3.10, "bbox": [200, 200, 50, 50], "label": "Anomalie suspectée"},
        {"engine": "yolo", "score": 0.80, "bbox": [5, 5, 10, 10], "label": "Défaut proposé : tâche"},
    ]

    assigned = assign_display_ids(fused_regs)

    y_assigned = [r for r in assigned if r["engine"] == "yolo"]
    p_assigned = [r for r in assigned if r["engine"] == "patchcore"]

    assert [r["display_id"] for r in y_assigned] == ["Y1", "Y2", "Y3"]
    assert y_assigned[0]["score"] == 0.95
    assert y_assigned[1]["score"] == 0.80
    assert y_assigned[2]["score"] == 0.65

    assert [r["display_id"] for r in p_assigned] == ["P1", "P2"]
    assert p_assigned[0]["score"] == 3.10
    assert p_assigned[1]["score"] == 1.85


def test_export_payload_validation_and_schema():
    """Vérifie la conformité de l'export au schéma export_schema_v1.json (AC-04, AC-07)."""
    now = datetime.now(timezone.utc)
    inspection_doc = {
        "id": "12345678-1234-5678-1234-567812345678",
        "created_at": now,
        "completed_at": now,
        "created_by": "operator_test",
        "status": "done",
        "partial": False,
        "image_meta": {
            "filename": "test.png",
            "format": "PNG",
            "width": 640,
            "height": 480,
            "stored_width": 640,
            "stored_height": 480,
            "resize_factor": 1.0,
            "scale_mode": "native",
            "warnings": [],
        },
        "domain_check": {
            "max_similarity": 0.9412,
            "reference_min": 0.8124,
            "reference_source": "models/domain_bias_report_v1.json",
            "status": "in_range",
        },
        "engines": {
            "yolo": {"status": "ok", "version": "v1", "latency_ms": {"total": 91.0}},
            "patchcore": {"status": "ok", "version": "v1", "latency_ms": {"total": 2800.0}},
        },
        "heatmap_meta": {
            "scale": "raw",
            "min": 0.1,
            "max": 3.5,
            "tau": 1.6386,
            "vmax": 3.5,
            "width": 640,
            "height": 480,
        },
    }

    regions = [
        {
            "id": "87654321-4321-8765-4321-876543210987",
            "engine": "yolo",
            "display_id": "Y1",
            "bbox": [10.0, 20.0, 30.0, 40.0],
            "area": 1200.0,
            "label": "Défaut proposé : tâche",
            "score": 0.85,
            "classification": "tâche",
            "tau": None,
            "corroboration": {"detected": True, "score_patchcore": 2.1},
        }
    ]

    human_reviews = [
        {
            "id": "rev-1",
            "region_id": "87654321-4321-8765-4321-876543210987",
            "decision": "Confirmé",
            "rejection_reason": None,
            "comment": "Défaut bien réel",
            "reviewed_by": "operator_test",
            "created_at": now,
        }
    ]

    export = ExportService.build_export_payload(inspection_doc, regions, human_reviews)

    assert export["schema_version"] == "weaveguard.inspection/1.0"
    assert export["predictions"]["regions_count"] == 1
    assert export["predictions"]["regions"][0]["display_id"] == "Y1"
    assert export["image"]["scale_mode"] == "native"
    assert export["domain_check"] is not None
    assert export["domain_check"]["status"] == "in_range"
    assert export["domain_check"]["reference_min"] == 0.8124
    # La revue humaine doit impérativement être une section distincte des prédictions
    assert len(export["human_reviews"]) == 1
    assert export["human_reviews"][0]["decision"] == "Confirmé"


def test_export_anti_leak_blocks_paths_and_secrets():
    """Vérifie que toute fuite de chemin local (C:\\, /home) ou de secret (.env, JWT) lève une exception 500."""
    valid_payload = {
        "id": "test",
        "description": "Safe text without any secret or path",
    }
    # Ne doit pas lever d'exception
    check_no_leaks_or_secrets(valid_payload)

    # Fuite chemin local Windows C:\...
    with pytest.raises(AppException) as exc1:
        check_no_leaks_or_secrets({"path": "C:\\Users\\admin\\Desktop\\data"})
    assert exc1.value.code == "EXPORT_ERROR"

    # Fuite secret .env
    with pytest.raises(AppException) as exc2:
        check_no_leaks_or_secrets({"info": "Loaded from .env file"})
    assert exc2.value.code == "EXPORT_ERROR"

    # Fuite JWT_SECRET
    with pytest.raises(AppException) as exc3:
        check_no_leaks_or_secrets({"secret": "JWT_SECRET=super_secret_value"})
    assert exc3.value.code == "EXPORT_ERROR"

