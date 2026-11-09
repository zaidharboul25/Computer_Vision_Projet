"""Routeur pour les statistiques synthétiques du tableau de bord (Phase 4).

RÈGLE MÉTHODOLOGIQUE STRICTE (§14.2) :
Ces statistiques ne contiennent QUE des décomptes calculés depuis la base de données.
Aucune métrique de performance ML (mAP, précision, rappel, etc.) n'est exposée ici.
"""
from fastapi import APIRouter, Depends, Query
from app.core.permissions import AuthenticatedUser, get_current_user
from app.db.repositories.inspections import InspectionRepository
from app.schemas.inspection import InspectionResponse
from app.schemas.stats import (
    InspectionStats,
    RegionStats,
    ReviewStats,
    SummaryStatsResponse,
)

router = APIRouter(prefix="/stats", tags=["Statistiques Synthétiques"])


@router.get(
    "/summary",
    response_model=SummaryStatsResponse,
    summary="Synthèse statistique du tableau de bord (décomptes uniquement)",
)
async def get_summary_statistics(
    include_demo: bool = Query(True, description="Inclure ou exclure les inspections de démonstration"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Calcule et renvoie les agrégats de base de données :
    - Décomptes d'inspections par statut (total, pending, running, done, error)
    - Décomptes de régions détectées par moteur (total, yolo, patchcore)
    - Décomptes de décisions humaines courantes (total, confirmed, rejected, uncertain, unreviewed)
    - Liste des 5 dernières inspections
    """
    raw_stats = await InspectionRepository.get_summary_stats(include_demo=include_demo)

    # Assainir les dernières inspections pour Pydantic
    latest_inspections = []
    for item in raw_stats["latest_inspections"]:
        item_copy = dict(item)
        if "id" not in item_copy and "_id" in item_copy:
            item_copy["id"] = str(item_copy["_id"])
        latest_inspections.append(InspectionResponse(**item_copy))

    return SummaryStatsResponse(
        inspections=InspectionStats(**raw_stats["inspections"]),
        regions=RegionStats(**raw_stats["regions"]),
        reviews=ReviewStats(**raw_stats["reviews"]),
        latest_inspections=latest_inspections,
        include_demo=include_demo,
    )
