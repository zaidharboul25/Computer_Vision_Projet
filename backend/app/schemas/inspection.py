"""Schémas Pydantic pour les inspections (Phase 3).

Garantit le typage strict des états d'inspection, des métadonnées images,
de la progression temps réel par moteur et des réponses d'API.
"""
from datetime import datetime
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


EngineExecutionStatus = Literal["pending", "running", "ok", "error", "skipped"]
InspectionStatus = Literal["pending", "running", "done", "error"]


class EngineProgress(BaseModel):
    status: EngineExecutionStatus = Field(..., description="État d'avancement du moteur")
    version: Optional[str] = Field(None, description="Version ou hash de l'artefact")
    error: Optional[str] = Field(None, description="Message d'erreur éventuel en cas d'échec du moteur")
    latency_ms: Optional[Dict[str, float]] = Field(None, description="Détail des temps de traitement (preprocess, model, postprocess, total)")


class ImageMeta(BaseModel):
    filename: str = Field(..., description="Nom de fichier d'origine de l'image")
    format: str = Field(..., description="Format d'encodage (JPEG, PNG)")
    width: int = Field(..., description="Largeur originale de l'image")
    height: int = Field(..., description="Hauteur originale de l'image")
    stored_width: int = Field(..., description="Largeur après redressement EXIF")
    stored_height: int = Field(..., description="Hauteur après redressement EXIF")
    inference_width: int = Field(..., description="Largeur redimensionnée passée aux modèles")
    inference_height: int = Field(..., description="Hauteur redimensionnée passée aux modèles")
    resize_factor: float = Field(..., description="Facteur d'échelle appliqué (<= 1.0 en réduction, > 1.0 en agrandissement)")
    scale_mode: Literal["native", "normalized"] = Field("native", description="Mode d'échelle utilisé ('native' ou 'normalized')")
    warnings: List[str] = Field(default_factory=list, description="Avertissements éventuels sur le format ou l'échelle")


DomainCheckStatus = Literal["in_range", "below_range", "unavailable"]


class DomainCheck(BaseModel):
    max_similarity: Optional[float] = Field(None, description="Similarité cosinus maximale observée avec l'index WeaveGuard")
    reference_min: float = Field(..., description="Minimum observé sur validation+test dans le rapport de biais de domaine")
    reference_source: str = Field("models/domain_bias_report_v1.json", description="Fichier source du seuil de référence")
    status: DomainCheckStatus = Field(..., description="Statut de représentativité : in_range, below_range, unavailable")


class HeatmapMeta(BaseModel):
    scale: str = Field("raw", description="Échelle de normalisation de la carte d'anomalies")
    min: float = Field(..., description="Valeur minimale du score PatchCore")
    max: float = Field(..., description="Valeur maximale du score PatchCore")
    tau: float = Field(..., description="Seuil d'anomalie de décision PatchCore")
    vmax: float = Field(..., description="Valeur maximale d'écrêtage pour la visualisation (vmax -> 255)")
    width: int = Field(..., description="Largeur de la carte de chaleur")
    height: int = Field(..., description="Hauteur de la carte de chaleur")


class InspectionCreateResponse(BaseModel):
    id: str = Field(..., description="Identifiant unique de l'inspection créée")
    status: InspectionStatus = Field("pending", description="Statut initial dans la file d'attente")
    created_at: datetime = Field(..., description="Date et heure de soumission")


class InspectionResponse(BaseModel):
    id: str = Field(..., description="Identifiant unique de l'inspection")
    status: InspectionStatus = Field(..., description="Statut global du traitement")
    partial: bool = Field(False, description="Vrai si au moins un moteur a échoué mais d'autres ont produit un résultat")
    created_by: str = Field(..., description="Nom d'utilisateur de l'opérateur créateur")
    created_at: datetime = Field(..., description="Date de soumission")
    completed_at: Optional[datetime] = Field(None, description="Date d'achèvement")
    image_meta: ImageMeta = Field(..., description="Métadonnées dimensionnelles et repère")
    engines: Dict[str, EngineProgress] = Field(..., description="Progression et statut détaillé de chaque moteur")
    regions_count: int = Field(0, description="Nombre total de régions candidates détectées")
    heatmap_meta: Optional[HeatmapMeta] = Field(None, description="Métadonnées de la carte de chaleur si générée")
    domain_check: Optional[DomainCheck] = Field(None, description="Évaluation de représentativité dans le domaine d'apprentissage")
    warnings: List[str] = Field(default_factory=list, description="Avertissements généraux sur l'inspection")
    error_message: Optional[str] = Field(None, description="Message global d'erreur en cas d'échec total")
    is_demo: bool = Field(False, description="Vrai s'il s'agit d'une inspection de démonstration")


class InspectionListResponse(BaseModel):
    items: List[InspectionResponse]
    total: int
    skip: int
    limit: int

