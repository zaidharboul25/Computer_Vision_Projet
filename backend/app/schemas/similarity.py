"""Schémas Pydantic pour les réponses de similarité visuelle (Phase 3 & 4)."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SimilarityItem(BaseModel):
    rank: int = Field(..., description="Rang du voisin le plus proche (1-indexed)")
    score: float = Field(..., description="Similarité cosinus (comprise entre -1 et 1, typiquement > 0)")
    ref_id: str = Field(..., description="Identifiant unique de la référence")
    source: Optional[str] = Field(None, description="Source de l'index (weaveguard, dtd)")
    classes: Optional[List[str]] = Field(None, description="Classes textiles éventuelles")
    category: Optional[str] = Field(None, description="Catégorie DTD éventuelle")
    split: Optional[str] = Field(None, description="Sous-ensemble d'origine (train, val)")

    model_config = {"extra": "allow"}


class SimilarityLatency(BaseModel):
    preprocess: float
    model: float
    search: float
    total: float


class SimilarityIndexResult(BaseModel):
    engine: str = "similarity"
    extractor: str
    index: str
    metric: str = "cosine_similarity"
    higher_is_better: bool = True
    label: str
    note: str
    latency_ms: SimilarityLatency
    results: List[SimilarityItem]


class SimilaritySearchResponse(BaseModel):
    weaveguard: Optional[SimilarityIndexResult] = None
    dtd: Optional[SimilarityIndexResult] = None

