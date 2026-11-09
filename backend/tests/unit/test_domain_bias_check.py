"""Tests unitaires pour l'évaluation de biais de domaine / représentativité hors domaine."""
import json
from pathlib import Path
from PIL import Image
import numpy as np
import pytest

from app.core.config import settings
from app.engines.registry import engine_registry
from app.services.queue import evaluate_domain_bias


def test_domain_check_validation_image_in_range():
    """Vérifie qu'une image du jeu de données WeaveGuard produit un statut in_range sans avertissement."""
    # Sélectionner une image de validation réelle
    val_images = list(Path("datasets").rglob("*.jpg"))
    assert len(val_images) > 0, "Le dossier datasets doit contenir des images de test"
    
    val_img = Image.open(val_images[0]).convert("RGB")
    domain_check, warning = evaluate_domain_bias(val_img)

    assert domain_check["status"] == "in_range"
    assert domain_check["max_similarity"] is not None
    assert domain_check["reference_min"] > 0.0
    assert domain_check["reference_source"] == "models/domain_bias_report_v1.json"
    assert domain_check["max_similarity"] >= domain_check["reference_min"]
    assert warning is None


def test_domain_check_out_of_domain_noise_below_range_and_warning():
    """Vérifie qu'une image hors domaine (bruit aléatoire) produit below_range et le message contractuel exact."""
    # Bruit aléatoire non structuré
    np.random.seed(42)
    noise_arr = np.random.randint(0, 256, (256, 256, 3), dtype=np.uint8)
    noise_img = Image.fromarray(noise_arr)

    domain_check, warning = evaluate_domain_bias(noise_img)

    assert domain_check["status"] == "below_range"
    assert domain_check["max_similarity"] is not None
    assert domain_check["max_similarity"] < domain_check["reference_min"]
    assert warning is not None

    # Vérification du texte exact contractuel
    max_sim = domain_check["max_similarity"]
    ref_min = domain_check["reference_min"]
    expected_warning = (
        f"Cette image ressemble peu aux images d'apprentissage "
        f"(similarité maximale {max_sim:.4f}, minimum observé en validation/test {ref_min:.4f}). "
        f"Les résultats peuvent être moins fiables."
    )
    assert warning == expected_warning


def test_domain_check_dynamic_threshold_reading(tmp_path):
    """Vérifie que le seuil reference_min n'est pas codé en dur et provient de domain_bias_report_v1.json."""
    report_path = settings.get_models_dir() / "domain_bias_report_v1.json"
    with open(report_path, "r", encoding="utf-8") as f:
        rep_data = json.load(f)
    expected_min = round(float(rep_data["familiarity_quantiles"][0]), 4)

    noise_img = Image.new("RGB", (64, 64), color=(0, 0, 0))
    domain_check, _ = evaluate_domain_bias(noise_img)

    assert domain_check["reference_min"] == expected_min


def test_domain_check_unavailable_when_engine_missing(monkeypatch):
    """Vérifie qu'en cas d'indisponibilité du moteur, le statut 'unavailable' est enregistré sans valeur inventée."""
    monkeypatch.setattr(engine_registry, "is_engine_available", lambda name: False)

    test_img = Image.new("RGB", (64, 64), color=(100, 100, 100))
    domain_check, warning = evaluate_domain_bias(test_img)

    assert domain_check["status"] == "unavailable"
    assert domain_check["max_similarity"] is None
    assert domain_check["reference_min"] > 0
    assert warning is None

