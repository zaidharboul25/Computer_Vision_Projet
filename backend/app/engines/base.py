"""Interface commune et structures de données pour les moteurs IA WeaveGuard AI (§5, NFR-01, NFR-06)."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from PIL import Image
from pydantic import BaseModel, Field


class LatencyBreakdown(BaseModel):
    preprocess_ms: float = 0.0
    model_ms: float = 0.0
    postprocess_ms: float = 0.0
    total_ms: float = 0.0


class EngineInfo(BaseModel):
    engine_id: str
    version: str
    role: str
    artifacts_sha256: Dict[str, str]
    params: Dict[str, Any]
    thresholds: Dict[str, Any]
    labels: Dict[str, str]


class EngineResult(BaseModel):
    engine_name: str
    status: str  # "ok" | "error" | "skipped"
    regions: List[Dict[str, Any]] = Field(default_factory=list)
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    latency: LatencyBreakdown = Field(default_factory=LatencyBreakdown)
    error_message: Optional[str] = None


class BaseEngine(ABC):
    """Interface commune garantissant l'évolutivité (NFR-06) et l'isolation des pannes."""

    def __init__(self, name: str):
        self.name = name
        self.is_loaded = False

    @abstractmethod
    def load(self) -> None:
        """Charge le modèle et ses artefacts après vérification d'intégrité SHA-256."""
        pass

    @abstractmethod
    def infer(self, image: Image.Image) -> EngineResult:
        """Exécute l'inférence en isolant et mesurant chaque étape (pré/modèle/post)."""
        pass

    def get_info(self) -> EngineInfo:
        """Alias pour info()."""
        return self.info()

    @abstractmethod
    def info(self) -> EngineInfo:
        """Retourne les métadonnées, versions, hashes et seuils du moteur."""
        pass

    @abstractmethod
    def health(self) -> Dict[str, Any]:
        """Retourne l'état de santé du moteur (chargé, intégrité, mémoire)."""
        pass

    @abstractmethod
    def unload(self) -> None:
        """Libère la mémoire et les artefacts."""
        pass

