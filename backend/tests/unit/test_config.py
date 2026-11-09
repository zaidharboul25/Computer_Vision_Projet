"""Tests unitaires de la configuration et validation des artefacts."""
from app.core.config import settings


def test_settings_loaded():
    assert settings.DB_NAME is not None
    assert settings.JWT_SECRET is not None
    assert len(settings.JWT_SECRET) >= 32
    assert "yolo" in settings.ENGINES_ENABLED
    assert "patchcore" in settings.ENGINES_ENABLED
    assert "similarity" in settings.ENGINES_ENABLED


def test_required_artifacts_validation():
    errors = settings.validate_artifact_paths()
    # Tous les artefacts requis doivent être présents sur le disque
    assert errors == [], f"Des artefacts obligatoires sont introuvables : {errors}"


def test_tests_use_test_database():
    """Garantit que la suite de tests est configurée pour utiliser uniquement weaveguard_test."""
    assert settings.DB_NAME == "weaveguard_test", (
        f"Sécurité violée : les tests doivent impérativement s'exécuter sur 'weaveguard_test', trouvé : {settings.DB_NAME}"
    )
