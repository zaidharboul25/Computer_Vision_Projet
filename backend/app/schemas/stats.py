"""Schémas Pydantic pour les statistiques synthétiques du tableau de bord (Phase 4).

RÈGLE MÉTHODOLOGIQUE STRICTE (§14.2) :
Ces statistiques ne contiennent QUE des décomptes calculés depuis la base de données.
Aucune métrique de performance ML (mAP, précision, rappel, etc.) n'est exposée ici.
"""
from typing import Dict, List
from pydantic import BaseModel, Field
from app.schemas.inspection import InspectionResponse


class InspectionStats(BaseModel):
    total: int = 0
    pending: int = 0
    running: int = 0
    done: int = 0
    error: int = 0


class RegionStats(BaseModel):
    total: int = 0
    yolo: int = 0
    patchcore: int = 0


class ReviewStats(BaseModel):
    total: int = 0
    confirmed: int = 0
    rejected: int = 0
    uncertain: int = 0
    unreviewed: int = 0


class SummaryStatsResponse(BaseModel):
    inspections: InspectionStats
    regions: RegionStats
    reviews: ReviewStats
    latest_inspections: List[InspectionResponse]
    include_demo: bool = Field(..., description="Indique si les données de démonstration sont incluses")

