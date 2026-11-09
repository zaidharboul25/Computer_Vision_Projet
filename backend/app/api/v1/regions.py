"""Routeur pour les régions détectées et la revue humaine (Phase 4).

Règles de sécurité et de validation (§6.5, §10, AC-07) :
- POST /regions/{id}/feedback :
  * Décisions : confirmed | rejected | uncertain
  * Motif obligatoire pour 'rejected', interdit pour 'confirmed' (INVALID_FEEDBACK si non respecté).
  * Réservé aux opérateurs sur LEURS propres inspections (FORBIDDEN si autre rôle, INSPECTION_NOT_FOUND si inspection invisible).
  * Historique en ajout seul ; la décision courante est la plus récente.
- GET /regions/{id}/thumbnail :
  * Découpe de la vignette de la région dans l'image originale stockée.
  * Isolation : un opérateur ne peut pas obtenir la vignette d'une inspection d'un tiers (404 INSPECTION_NOT_FOUND).
- Immutabilité : aucune méthode PUT/PATCH/DELETE n'est acceptée sur les régions (405).
"""
import io
from typing import List
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, Response
from PIL import Image
from app.core.config import settings
from app.core.errors import (
    ForbiddenException,
    InspectionNotFoundException,
    InvalidFeedbackException,
    RegionNotFoundException,
)
from app.core.permissions import AuthenticatedUser, UserRole, get_current_user, require_roles
from app.db.mongo import get_database
from app.db.repositories.audit import AuditRepository
from app.db.repositories.feedback import FeedbackRepository
from app.db.repositories.inspections import InspectionRepository
from app.schemas.errors import ErrorResponse
from app.schemas.feedback import FeedbackCreateRequest, FeedbackResponse
from app.schemas.region import RegionDetailResponse
from app.services.storage import StorageService


router = APIRouter(prefix="/regions", tags=["Régions & Revue Humaine"])


@router.get(
    "/{region_id}",
    response_model=RegionDetailResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentification requise"},
        404: {"model": ErrorResponse, "description": "Région ou inspection introuvable"},
    },
    summary="Récupérer les détails d'une région",
)
async def get_region_details(
    region_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Récupère une région avec sa décision humaine courante.
    Contrôle de visibilité : un opérateur n'a pas accès aux régions d'une inspection invisible (404).
    """
    db = get_database()
    region = await db.regions.find_one({"id": region_id})
    if not region:
        raise RegionNotFoundException()

    inspection_id = region["inspection_id"]
    inspection = await InspectionRepository.get_by_id(inspection_id)
    if not inspection:
        raise InspectionNotFoundException()

    if current_user.role == UserRole.OPERATOR and inspection.get("created_by") != current_user.username:
        raise InspectionNotFoundException()

    latest_feedback = await FeedbackRepository.get_latest_by_region(region_id)
    doc = dict(region)
    doc["latest_feedback"] = latest_feedback
    return doc


@router.post(
    "/{region_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Motif de rejet invalide ou manquant"},
        401: {"model": ErrorResponse, "description": "Authentification requise"},
        403: {"model": ErrorResponse, "description": "Rôle opérateur requis"},
        404: {"model": ErrorResponse, "description": "Région ou inspection introuvable"},
    },
    summary="Enregistrer une décision humaine sur une région",
)
async def submit_region_feedback(
    region_id: str,
    payload: FeedbackCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Enregistre une décision de validation humaine (confirmed, rejected, uncertain).

    Règles contractuelles :
    - Seuls les opérateurs peuvent soumettre un feedback (FORBIDDEN pour tout autre rôle).
    - L'opérateur ne peut agir que sur ses propres inspections (INSPECTION_NOT_FOUND si invisible).
    - Validation stricte du motif de rejet (obligatoire si rejected, interdit si confirmed).
    """
    # 1. Rôle strictement réservé aux opérateurs (§6.5 & Exigence A)
    if current_user.role != UserRole.OPERATOR:
        raise ForbiddenException("Seuls les opérateurs sont habilités à soumettre une revue humaine")

    # 2. Validation métier des motifs de rejet
    try:
        payload.validate_business_rules()
    except ValueError as e:
        raise InvalidFeedbackException(message=str(e))

    # 3. Récupération de la région
    db = get_database()
    region = await db.regions.find_one({"id": region_id})
    if not region:
        raise RegionNotFoundException()

    # 4. Récupération de l'inspection associée et vérification de visibilité
    inspection_id = region["inspection_id"]
    inspection = await InspectionRepository.get_by_id(inspection_id)
    if not inspection:
        raise InspectionNotFoundException()

    # Un opérateur ne peut valider que ses propres inspections
    if inspection.get("created_by") != current_user.username:
        raise InspectionNotFoundException()

    # 5. Persistance en ajout seul dans la collection feedback
    created_feedback = await FeedbackRepository.add_feedback(
        region_id=region_id,
        inspection_id=inspection_id,
        decision=payload.decision,
        reviewed_by=current_user.username,
        rejection_reason=payload.rejection_reason,
        comment=payload.comment,
    )

    # 6. Audit de la décision humaine
    audit_repo = AuditRepository(db)
    await audit_repo.log_action(
        action="feedback_submitted",
        user_id=current_user.id,
        username=current_user.username,
        details={
            "region_id": region_id,
            "inspection_id": inspection_id,
            "decision": payload.decision,
            "rejection_reason": payload.rejection_reason,
        },
    )

    return FeedbackResponse(**created_feedback)


@router.get(
    "/{region_id}/thumbnail",
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "Vignette de la région recadrée au format PNG",
        },
        401: {"model": ErrorResponse, "description": "Authentification requise"},
        404: {"model": ErrorResponse, "description": "Région ou inspection introuvable"},
    },
    summary="Télécharger la vignette recadrée de la région",
)
async def get_region_thumbnail(
    region_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Découpe et renvoie la vignette de la région depuis l'image originale stockée.

    Renvoie 404 INSPECTION_NOT_FOUND si l'inspection n'appartient pas à l'opérateur (Exigence 4.d).
    """
    db = get_database()
    region = await db.regions.find_one({"id": region_id})
    if not region:
        raise RegionNotFoundException()

    inspection_id = region["inspection_id"]
    inspection = await InspectionRepository.get_by_id(inspection_id)
    if not inspection:
        raise InspectionNotFoundException()

    # Contrôle de visibilité : un opérateur n'a pas accès aux vignettes d'autrui
    if current_user.role == UserRole.OPERATOR and inspection.get("created_by") != current_user.username:
        raise InspectionNotFoundException()

    try:
        orig_img_path = StorageService.get_stored_image_path(inspection_id)
    except FileNotFoundError:
        raise InspectionNotFoundException("Image source introuvable sur disque")

    # Découpe de la boîte [x, y, w, h]
    with Image.open(orig_img_path) as full_img:
        bbox = region.get("bbox", [0, 0, full_img.width, full_img.height])
        x, y, w, h = bbox
        x0 = max(0, int(round(x)))
        y0 = max(0, int(round(y)))
        x1 = min(full_img.width, int(round(x + w)))
        y1 = min(full_img.height, int(round(y + h)))

        if x1 <= x0 or y1 <= y0:
            crop_img = full_img
        else:
            crop_img = full_img.crop((x0, y0, x1, y1))

        buf = io.BytesIO()
        crop_img.save(buf, format="PNG")
        return Response(content=buf.getvalue(), media_type="image/png")


@router.get(
    "/{region_id}/history",
    response_model=List[FeedbackResponse],
    responses={
        401: {"model": ErrorResponse, "description": "Authentification requise"},
        404: {"model": ErrorResponse, "description": "Région ou inspection introuvable"},
    },
    summary="Historique complet des revues pour une région",
)
async def get_region_feedback_history(
    region_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Renvoie l'historique chronologique inverse de toutes les validations humaines sur cette région."""
    db = get_database()
    region = await db.regions.find_one({"id": region_id})
    if not region:
        raise RegionNotFoundException()

    inspection = await InspectionRepository.get_by_id(region["inspection_id"])
    if not inspection:
        raise InspectionNotFoundException()

    if current_user.role == UserRole.OPERATOR and inspection.get("created_by") != current_user.username:
        raise InspectionNotFoundException()

    history = await FeedbackRepository.get_history_by_region(region_id)
    return [FeedbackResponse(**f) for f in history]
