"""Fonctions helper partagées pour les tests de parité WeaveGuard AI."""
import json
from pathlib import Path
from typing import Any, Dict, List

import pytest


PARITY_DIR = Path(__file__).parent
REFERENCE_DIR = PARITY_DIR / "reference_outputs"

# 50 premières images val (tri lexicographique, déterministe)
VAL_DIR = Path(__file__).resolve().parents[2] / "datasets" / "images" / "val"


def get_val_images(n: int = 50) -> List[Path]:
    """Retourne les n premières images val triées, indépendamment de l'extension."""
    all_images: List[Path] = []
    for ext in ("*.webp", "*.jpg", "*.jpeg", "*.png"):
        all_images.extend(VAL_DIR.glob(ext))
    return sorted(all_images)[:n]


def load_reference(image_stem: str) -> Dict[str, Any]:
    """Charge la sortie de référence JSON pour une image donnée."""
    ref_file = REFERENCE_DIR / f"{image_stem}.json"
    if not ref_file.exists():
        pytest.skip(
            f"Référence absente : {ref_file}. "
            "Exécutez scripts/generate_parity_reference.py d'abord."
        )
    with open(ref_file, "r", encoding="utf-8") as f:
        return json.load(f)


def references_exist() -> bool:
    """Vérifie si au moins un fichier de référence existe."""
    return any(REFERENCE_DIR.glob("*.json"))


def skip_if_no_references() -> None:
    """Skip toute la suite si les références sont absentes."""
    if not references_exist():
        pytest.skip(
            "Aucune sortie de référence trouvée dans tests/parity/reference_outputs/. "
            "Exécutez d'abord : python scripts/generate_parity_reference.py"
        )

