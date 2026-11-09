"""Schémas Pydantic pour les régions détectées (Phase 3).

Garantit le format contractuel des boîtes [x, y, w, h] en coordonnées natives de l'image stockée,
les libellés stricts et la distinction claire entre scores/confiances/seuils (§1, AC-02, AC-05, AC-06).
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from app.schemas.feedback import FeedbackResponse


class Corroboration(BaseModel):
    detected: bool = Field(..., description="Vrai si corroboré par le moteur PatchCore")
    overlap_ratio_box: Optional[float] = Field(None, description="Ratio de recouvrement de la boîte YOLO")
    overlap_ratio_region: Optional[float] = Field(None, description="Ratio de recouvrement de l'anomalie PatchCore")
    score_patchcore: Optional[float] = Field(None, description="Score de distance PatchCore maximal dans l'intersection")
    tau_patchcore: Optional[float] = Field(None, description="Seuil d'anomalie PatchCore")


class RegionResponse(BaseModel):
    id: str = Field(..., description="Identifiant unique UUID de la région")
    display_id: Optional[str] = Field(None, description="Identifiant court d'affichage : Y1, Y2... pour YOLO, P1, P2... pour PatchCore")
    inspection_id: str = Field(..., description="Identifiant de l'inspection associée")
    engine: Literal["yolo", "patchcore"] = Field(..., description="Moteur source ayant produit la région")
    bbox: List[float] = Field(..., min_length=4, max_length=4, description="Coordonnées [x, y, largeur, hauteur] en repère natif")
    area: float = Field(..., description="Surface de la région en pixels carrés")
    label: str = Field(..., description="Libellé textuel exact et documenté")
    score: Optional[float] = Field(None, description="Confiance modèle (YOLO) ou score de distance (PatchCore)")
    classification: Optional[str] = Field(None, description="Nom de la classe (YOLO uniquement, None pour PatchCore)")
    tau: Optional[float] = Field(None, description="Seuil de décision PatchCore")
    corroboration: Optional[Corroboration] = Field(None, description="Informations de corroboration croisée")
    created_at: Optional[datetime] = Field(None, description="Horodatage de création de la région")
    latest_decision: Optional[str] = Field(None, description="Dernière décision humaine validée (Confirmé, Rejeté, Incertain)")


class RegionListResponse(BaseModel):
    items: List[RegionResponse]
    total: int


class RegionDetailResponse(RegionResponse):
    latest_feedback: Optional[FeedbackResponse] = None

