"""Routeur de métadonnées des modèles et rapports ML (Phase 3).

Expose les cartes de modèles et les rapports de biais de domaine (§10, AC-10)
sans JAMAIS exposer de chemin local absolu ni de secret (§1.1, §9.1).
"""
import json
from pathlib import Path
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.errors import AppException
from app.core.permissions import AuthenticatedUser, get_current_user
from app.engines.integrity import IntegrityVerifier
from app.engines.registry import engine_registry
from app.schemas.errors import ErrorResponse
from app.schemas.model import DomainBiasReportResponse, ModelsListResponse


router = APIRouter(prefix="", tags=["Modèles & Rapports"])


@router.get(
    "/models",
    response_model=ModelsListResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentification requise"},
    },
    summary="Consulter les métadonnées et versions des modèles d'inspection",
)
async def list_models_info(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Renvoie les informations publiques, paramètres et empreintes des modèles chargés."""
    models_info = {}
    for engine_name, engine in engine_registry.get_all_engines().items():
        info = engine.info()
        models_info[engine_name] = {
            "engine": info.engine_id,
            "version": info.version,
            "role": info.role,
            "parameters": info.params,
            "thresholds": info.thresholds,
            "labels": info.labels,
        }

    return {
        "models": models_info,
        "integrity": IntegrityVerifier.get_expected_hashes(),
        "device": settings.get_effective_device(),
    }


@router.get(
    "/reports/domain-bias",
    response_model=DomainBiasReportResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentification requise"},
        404: {"model": ErrorResponse, "description": "Rapport introuvable"},
        500: {"model": ErrorResponse, "description": "Erreur lors du chargement du rapport"},
    },
    summary="Consulter le rapport d'évaluation du biais de domaine",
)
async def get_domain_bias_report(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Renvoie le contenu du rapport contractuel d'évaluation du biais de domaine."""
    report_path = settings.get_models_dir() / "domain_bias_report_v1.json"
    if not report_path.exists():
        raise AppException(
            code="REPORT_NOT_FOUND",
            message="Rapport de biais de domaine introuvable",
            status_code=404,
        )

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise AppException(
            code="INTERNAL_ERROR",
            message=f"Impossible de charger le rapport de biais de domaine : {str(e)}",
            status_code=500,
        )
