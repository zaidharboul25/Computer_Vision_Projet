"""Schémas Pydantic pour les métadonnées de modèles et rapports (Phase 3 & 4)."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ModelItemDetail(BaseModel):
    engine: str
    version: str
    role: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    thresholds: Dict[str, Any] = Field(default_factory=dict)
    labels: Dict[str, Any] = Field(default_factory=dict)


class ModelsListResponse(BaseModel):
    models: Dict[str, ModelItemDetail]
    integrity: Dict[str, str]
    device: str


class DomainBiasReportResponse(BaseModel):
    title: Optional[str] = None
    version: Optional[str] = None
    generated_at: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    details: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}

