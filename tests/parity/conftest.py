"""Configuration pytest pour la suite de tests de parité WeaveGuard AI.

Ces tests comparent les sorties des moteurs (YOLO, PatchCore, Similarité)
avant et après chaque optimisation exacte, sur 50 images de validation gelées.

Les tests sont skippés automatiquement si les sorties de référence n'ont pas
encore été générées (exécuter scripts/generate_parity_reference.py d'abord).
"""
import pytest
from pathlib import Path

PARITY_DIR = Path(__file__).parent
REFERENCE_DIR = PARITY_DIR / "reference_outputs"

@pytest.fixture(scope="session")
def parity_reference_dir() -> Path:
    return REFERENCE_DIR

