"""Vérification d'intégrité cryptographique SHA-256 des artefacts IA (§5)."""
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
from app.core.config import settings
from app.core.errors import ModelUnavailableException
from app.core.logging import logger


def compute_sha256(file_path: Path) -> str:
    """Calcule l'empreinte SHA-256 d'un fichier binaire par blocs."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class IntegrityVerifier:
    @classmethod
    def get_expected_hashes(cls) -> Dict[str, Any]:
        """Retourne les empreintes déclarées des modèles."""
        _, yolo_hash, _ = cls.verify_yolo_integrity()
        _, pc_hash, _ = cls.verify_patchcore_integrity()
        sim_res = cls.verify_similarity_integrity()
        sim_hashes = {k: v[1] for k, v in sim_res.items()}
        return {
            "yolo_best_pt": yolo_hash,
            "patchcore_memory_bank_pt": pc_hash,
            "similarity_artifacts": sim_hashes,
        }

    @staticmethod
    def verify_yolo_integrity() -> Tuple[bool, str, str]:
        """Vérifie le fichier best.pt contre model_card.json."""
        models_dir = settings.get_models_dir()
        yolo_dir = models_dir / "weaveguard_yolo_v1"
        weights_file = yolo_dir / "best.pt"
        card_file = yolo_dir / "model_card.json"

        if not weights_file.exists() or not card_file.exists():
            raise ModelUnavailableException(
                message="Fichiers du modèle YOLO introuvables",
                details={"weights": str(weights_file), "card": str(card_file)},
            )

        with open(card_file, "r", encoding="utf-8") as f:
            card = json.load(f)

        expected_hash = card.get("weights_sha256", "")
        actual_hash = compute_sha256(weights_file)

        valid = (actual_hash == expected_hash)
        if not valid:
            logger.error(
                f"Écart d'intégrité SHA-256 pour YOLO : attendu {expected_hash}, calculé {actual_hash}"
            )
        return valid, expected_hash, actual_hash

    @staticmethod
    def verify_patchcore_integrity() -> Tuple[bool, str, str]:
        """Vérifie le fichier memory_bank.pt contre model_card.json."""
        models_dir = settings.get_models_dir()
        pc_dir = models_dir / "patchcore" / "patchcore_v1"
        bank_file = pc_dir / "memory_bank.pt"
        card_file = pc_dir / "model_card.json"

        if not bank_file.exists() or not card_file.exists():
            raise ModelUnavailableException(
                message="Fichiers du modèle PatchCore introuvables",
                details={"bank": str(bank_file), "card": str(card_file)},
            )

        with open(card_file, "r", encoding="utf-8") as f:
            card = json.load(f)

        expected_hash = card.get("memory_sha256", "")
        actual_hash = compute_sha256(bank_file)

        valid = (actual_hash == expected_hash)
        if not valid:
            logger.error(
                f"Écart d'intégrité SHA-256 pour PatchCore : attendu {expected_hash}, calculé {actual_hash}"
            )
        return valid, expected_hash, actual_hash

    @staticmethod
    def verify_similarity_integrity() -> Dict[str, Tuple[bool, str, str]]:
        """Vérifie tous les artefacts de similarité déclarés dans model_card.json."""
        models_dir = settings.get_models_dir()
        sim_dir = models_dir / "similarity" / "similarity_v1"
        card_file = sim_dir / "model_card.json"

        if not card_file.exists():
            raise ModelUnavailableException(
                message="Fiche modèle de similarité introuvable",
                details={"card": str(card_file)},
            )

        with open(card_file, "r", encoding="utf-8") as f:
            card = json.load(f)

        declared_hashes = card.get("artifacts_sha256", {})
        results = {}

        for filename, expected_hash in declared_hashes.items():
            artifact_path = sim_dir / filename
            if not artifact_path.exists():
                results[filename] = (False, expected_hash, "FILE_NOT_FOUND")
                continue

            actual_hash = compute_sha256(artifact_path)
            valid = (actual_hash == expected_hash)
            if not valid:
                logger.error(
                    f"Écart d'intégrité SHA-256 pour Similarité ({filename}) : attendu {expected_hash}, calculé {actual_hash}"
                )
            results[filename] = (valid, expected_hash, actual_hash)

        return results

