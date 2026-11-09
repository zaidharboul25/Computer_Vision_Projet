"""Routeur d'inspections WeaveGuard AI (Phase 3).

Exigences respectées :
- Exigence A : Endpoints protégés par Authorization: Bearer (JAMAIS de jeton dans l'URL).
- Exigence B : Règle de visibilité : inspection inaccessible -> 404 INSPECTION_NOT_FOUND (jamais 403).
- Exigence C : Contrôles d'upload stricts (vide, format, taille max, décompression).
- Exigence E : Overlay servi généré d'après les régions en base (AC-03).
- Exigence F : Heatmap 8 bits servie avec en-têtes sécurisés.
- Exigence I : Export JSON validé sans fuite d'information sensible.
"""
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional
import uuid
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from app.core.config import settings
from app.core.errors import (
    AppException,
    InspectionNotFoundException,
    InvalidImageException,
)
from app.core.permissions import UserRole, get_current_user, require_roles
from app.db.mongo import get_database
from app.db.repositories.inspections import InspectionRepository
from app.db.repositories.regions import RegionRepository
from app.schemas.errors import ErrorResponse
from app.schemas.inspection import (
    InspectionCreateResponse,
    InspectionListResponse,
    InspectionResponse,
)
from app.schemas.region import RegionListResponse, RegionResponse
from app.schemas.user import UserResponse
from app.services.export import ExportService
from app.services.queue import inspection_worker
from app.services.storage import StorageService


router = APIRouter(prefix="/inspections", tags=["Inspections"])

# Rôles habilités à voir toutes les inspections
ROLES_VIEW_ALL = {
    UserRole.SUPERVISOR,
    UserRole.ADMIN,
    UserRole.AUDITOR,
    UserRole.ML_ENGINEER,
}


def verify_inspection_access(inspection: dict, current_user: UserResponse) -> None:
    """Vérifie les droits d'accès. Si refusé, lève INSPECTION_NOT_FOUND (404) pour ne pas révéler l'existence (Exigence B)."""
    if current_user.role in ROLES_VIEW_ALL:
        return
    # Pour un opérateur standard, visibilité restreinte à ses propres inspections
    if inspection.get("created_by") != current_user.username:
        raise InspectionNotFoundException()


@router.post(
    "",
    response_model=InspectionCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Créer et soumettre une inspection",
)
async def create_inspection(
    file: UploadFile = File(..., description="Fichier image à inspecter"),
    engines: Optional[str] = Form(None, description="Liste des moteurs séparés par virgule (ex: 'yolo,patchcore,similarity')"),
    scale_mode: Literal["native", "normalized"] = Form("native", description="Mode d'échelle d'inférence : 'native' (défaut) ou 'normalized' (agrandissement bicubique jusqu'à INFERENCE_LONG_SIDE)"),
    current_user: UserResponse = Depends(
        require_roles(UserRole.OPERATOR, UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.ML_ENGINEER)
    ),
):
    """Télécharge une image textile, la valide et l'ajoute à la file d'attente d'inspection."""
    # 1. Sélection des moteurs demandés
    if engines:
        requested_engines = [e.strip().lower() for e in engines.split(",") if e.strip()]
    else:
        requested_engines = list(settings.ENGINES_ENABLED)

    # Filtrage par rapport aux moteurs globalement activés
    valid_engines = [e for e in requested_engines if e in settings.ENGINES_ENABLED]
    if not valid_engines:
        raise AppException(
            code="INVALID_PARAMS",
            message=f"Aucun moteur valide sélectionné parmi les moteurs activés : {settings.ENGINES_ENABLED}",
            status_code=400,
        )

    # 2. Lecture des octets uploadés
    content = await file.read()

    # 3. Validation et prétraitement (anti-bombe, conversion RGB, EXIF, échelle et mode de normalisation)
    stored_img, inf_img, image_meta = StorageService.validate_and_preprocess_upload(
        file_bytes=content,
        original_filename=file.filename or "upload.png",
        scale_mode=scale_mode,
    )

    # 4. Création de l'identifiant d'inspection
    inspection_id = str(uuid.uuid4())

    # 5. Sauvegarde de l'image stockée
    StorageService.save_stored_image(inspection_id, stored_img)

    # 6. Enregistrement initial dans MongoDB (état 'pending')
    created_doc = await InspectionRepository.create_inspection(
        inspection_id=inspection_id,
        created_by=current_user.username,
        image_meta=image_meta,
        enabled_engines=valid_engines,
    )

    # 7. Ajout à la file d'attente séquentielle (peut lever ServerBusyException 503)
    await inspection_worker.enqueue(
        inspection_id=inspection_id,
        stored_image=stored_img,
        inference_image=inf_img,
        resize_factor=image_meta.resize_factor,
        selected_engines=valid_engines,
    )

    return InspectionCreateResponse(
        id=inspection_id,
        status="pending",
        created_at=created_doc["created_at"],
    )


@router.get(
    "",
    response_model=InspectionListResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentification requise"},
    },
    summary="Lister l'historique des inspections",
)
async def list_inspections(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filtrer par statut (pending, running, done, error)"),
    created_by: Optional[str] = Query(None, description="Filtrer par opérateur créateur"),
    date_from: Optional[datetime] = Query(None, description="Date minimale de soumission"),
    date_to: Optional[datetime] = Query(None, description="Date maximale de soumission"),
    id_filter: Optional[str] = Query(None, description="Filtrer par préfixe d'identifiant"),
    review_status: Optional[str] = Query(None, description="Filtrer par statut de revue (reviewed, unreviewed)"),
    current_user: UserResponse = Depends(get_current_user),
):
    """Renvoie la liste paginée des inspections selon les droits de visibilité de l'utilisateur."""
    can_view_all = current_user.role in ROLES_VIEW_ALL
    items, total = await InspectionRepository.list_inspections(
        username=current_user.username,
        can_view_all=can_view_all,
        skip=skip,
        limit=limit,
        status=status,
        created_by=created_by,
        date_from=date_from,
        date_to=date_to,
        id_filter=id_filter,
        review_status=review_status,
    )
    return InspectionListResponse(
        items=[InspectionResponse(**item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{inspection_id}",
    response_model=InspectionResponse,
    summary="Consulter les détails d'une inspection",
)
async def get_inspection(
    inspection_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """Consulte une inspection par son ID. Renvoie 404 si inexistante ou non autorisée."""
    doc = await InspectionRepository.get_by_id(inspection_id)
    if not doc:
        raise InspectionNotFoundException()
    verify_inspection_access(doc, current_user)
    return InspectionResponse(**doc)


@router.get(
    "/{inspection_id}/regions",
    response_model=RegionListResponse,
    summary="Consulter les régions détectées d'une inspection",
)
async def get_inspection_regions(
    inspection_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """Récupère les régions détectées associées à une inspection."""
    doc = await InspectionRepository.get_by_id(inspection_id)
    if not doc:
        raise InspectionNotFoundException()
    verify_inspection_access(doc, current_user)

    regions = await RegionRepository.get_by_inspection_id(inspection_id)
    return RegionListResponse(
        items=[RegionResponse(**r) for r in regions],
        total=len(regions),
    )


@router.get(
    "/{inspection_id}/image",
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "Image stockée au format PNG",
        },
        401: {"model": ErrorResponse, "description": "Authentification requise"},
        404: {"model": ErrorResponse, "description": "Inspection ou image introuvable"},
    },
    summary="Télécharger l'image d'inspection stockée",
)
async def get_inspection_image(
    inspection_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """Renvoie l'image stockée. Exige un jeton Bearer dans l'en-tête Authorization (Exigence A)."""
    doc = await InspectionRepository.get_by_id(inspection_id)
    if not doc:
        raise InspectionNotFoundException()
    verify_inspection_access(doc, current_user)

    try:
        path = StorageService.get_stored_image_path(inspection_id)
    except FileNotFoundError:
        raise InspectionNotFoundException("Fichier image non trouvé sur le stockage")

    return FileResponse(path, media_type="image/png")


@router.get(
    "/{inspection_id}/heatmap",
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "Carte de chaleur PatchCore normalisée 8-bit (PNG)",
        },
        401: {"model": ErrorResponse, "description": "Authentification requise"},
        404: {"model": ErrorResponse, "description": "Inspection ou carte de chaleur introuvable"},
    },
    summary="Télécharger la carte de chaleur PatchCore normalisée",
)
async def get_inspection_heatmap(
    inspection_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """Renvoie la heatmap PNG 8-bit normalisée. Exige un jeton Bearer dans l'en-tête Authorization."""
    doc = await InspectionRepository.get_by_id(inspection_id)
    if not doc:
        raise InspectionNotFoundException()
    verify_inspection_access(doc, current_user)

    try:
        path = StorageService.get_heatmap_path(inspection_id)
    except FileNotFoundError:
        raise InspectionNotFoundException("Heatmap non disponible pour cette inspection")

    return FileResponse(path, media_type="image/png")


@router.get(
    "/{inspection_id}/overlay",
    responses={
        200: {
            "content": {
                "image/png": {},
                "image/webp": {},
                "image/jpeg": {},
            },
            "description": "Overlay annoté des boîtes et détections (PNG, WebP ou JPEG)",
        },
        401: {"model": ErrorResponse, "description": "Authentification requise"},
        404: {"model": ErrorResponse, "description": "Inspection ou overlay introuvable"},
    },
    summary="Télécharger l'overlay annoté",
)
async def get_inspection_overlay(
    inspection_id: str,
    format: str = Query("png", description="Format de sortie (png, webp, jpeg)"),
    current_user: UserResponse = Depends(get_current_user),
):
    """Renvoie l'overlay annoté (AC-03). Exige un jeton Bearer dans l'en-tête Authorization.
    
    Supporte les formats PNG (par défaut, sans perte), WebP et JPEG (qualité 90).
    """
    doc = await InspectionRepository.get_by_id(inspection_id)
    if not doc:
        raise InspectionNotFoundException()
    verify_inspection_access(doc, current_user)

    try:
        path = StorageService.get_overlay_path(inspection_id)
    except FileNotFoundError:
        raise InspectionNotFoundException("Overlay non disponible pour cette inspection")

    fmt = format.lower().strip()
    if fmt in ("jpeg", "jpg"):
        import io
        from PIL import Image
        from fastapi import Response
        im = Image.open(path).convert("RGB")
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=90)
        return Response(content=buf.getvalue(), media_type="image/jpeg")
    elif fmt == "webp":
        import io
        from PIL import Image
        from fastapi import Response
        im = Image.open(path).convert("RGB")
        buf = io.BytesIO()
        im.save(buf, format="WEBP", quality=90)
        return Response(content=buf.getvalue(), media_type="image/webp")
    else:
        return FileResponse(path, media_type="image/png")


@router.get(
    "/{inspection_id}/export",
    responses={
        200: {
            "content": {"application/json": {}},
            "description": "Rapport d'inspection normalisé conforme au schéma versionné export_schema_v1.json",
        },
        401: {"model": ErrorResponse, "description": "Authentification requise"},
        404: {"model": ErrorResponse, "description": "Inspection introuvable"},
        500: {"model": ErrorResponse, "description": "Erreur d'export ou fuite de sécurité détectée"},
    },
    summary="Exporter le rapport d'inspection au format JSON versionné",
)
async def get_inspection_export(
    inspection_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """Renvoie le JSON d'export normalisé conforme à export_schema_v1.json (AC-04)."""
    doc = await InspectionRepository.get_by_id(inspection_id)
    if not doc:
        raise InspectionNotFoundException()
    verify_inspection_access(doc, current_user)

    db = get_database()
    regions = await RegionRepository.get_by_inspection_id(inspection_id)
    cursor_fb = db.feedback.find({"inspection_id": inspection_id})
    feedback_items = await cursor_fb.to_list(length=1000)

    export_payload = ExportService.build_export_payload(
        inspection=doc,
        regions=regions,
        human_reviews=feedback_items,
    )

    return JSONResponse(content=export_payload)

