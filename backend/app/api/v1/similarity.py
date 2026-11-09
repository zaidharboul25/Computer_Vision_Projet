"""Routeur de recherche de similarité et vignettes associées (Phase 3).

Exigences respectées :
- Exigence A : Les vignettes exigent l'en-tête Authorization: Bearer (JAMAIS de jeton en paramètre d'URL).
- Libellés stricts : 'Textiles similaires (index WeaveGuard)' et 'Textures similaires (galerie DTD générique)'.
- Sécurité : Résolution stricte sans path-traversal (SECURITY_ERROR en cas de tentative).
"""
import io
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image
from app.core.errors import AppException, InvalidImageException
from app.core.permissions import AuthenticatedUser, UserRole, get_current_user, require_roles
from app.engines.registry import engine_registry
from app.engines.similarity_engine import SimilarityEngine
from app.schemas.errors import ErrorResponse
from app.schemas.similarity import SimilaritySearchResponse


router = APIRouter(prefix="/similarity", tags=["Similarité Visuelle"])


@router.post(
    "/search",
    response_model=SimilaritySearchResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Image corrompue, invalide ou vide"},
        401: {"model": ErrorResponse, "description": "Authentification requise"},
        503: {"model": ErrorResponse, "description": "Moteur de similarité indisponible"},
    },
    summary="Recherche de références visuelles similaires",
)
async def search_similarity(
    file: UploadFile = File(..., description="Vignette ou région à comparer"),
    index_name: Literal["weaveguard", "dtd", "all"] = Form("all", description="Index cible"),
    k: int = Form(5, ge=1, le=20, description="Nombre de voisins les plus proches"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Recherche visuelle par plongement vectoriel ResNet-50 GAP 2048 + FAISS."""
    sim_engine = engine_registry.get_engine("similarity")
    if not isinstance(sim_engine, SimilarityEngine):
        raise AppException(
            code="MODEL_UNAVAILABLE",
            message="Le moteur de similarité n'est pas disponible",
            status_code=503,
        )

    content = await file.read()
    if not content:
        raise InvalidImageException("Fichier image vide pour la recherche de similarité")

    try:
        img = Image.open(io.BytesIO(content)).convert("RGB")
    except Exception as e:
        raise InvalidImageException(f"Image corrompue ou illisible : {str(e)}")

    results = {}
    if index_name in ("weaveguard", "all"):
        results["weaveguard"] = sim_engine.search(img, index_name="weaveguard", k=k)

    if index_name in ("dtd", "all"):
        results["dtd"] = sim_engine.search(img, index_name="dtd", k=k)

    return results


@router.get(
    "/ref/{ref_id:path}/thumbnail",
    responses={
        200: {
            "content": {
                "image/png": {},
                "image/jpeg": {},
            },
            "description": "Vignette de référence visuelle (PNG ou JPEG)",
        },
        400: {"model": ErrorResponse, "description": "Tentative de traversée de chemin ou référence non autorisée"},
        401: {"model": ErrorResponse, "description": "Authentification requise"},
        404: {"model": ErrorResponse, "description": "Référence visuelle introuvable sur disque"},
        503: {"model": ErrorResponse, "description": "Moteur de similarité indisponible"},
    },
    summary="Télécharger la vignette d'une référence visuelle",
)
async def get_similarity_thumbnail(
    ref_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Sert la vignette d'une référence textile ou texture.

    Exige rigoureusement l'en-tête Authorization: Bearer (Exigence A).
    Protégé contre toute tentative de path traversal.
    """
    sim_engine = engine_registry.get_engine("similarity")
    if not isinstance(sim_engine, SimilarityEngine):
        raise AppException(
            code="MODEL_UNAVAILABLE",
            message="Le moteur de similarité n'est pas disponible",
            status_code=503,
        )

    try:
        thumb_path = sim_engine.resolve_ref_thumbnail(ref_id)
    except ValueError as e:
        raise AppException(
            code="SECURITY_ERROR",
            message=str(e),
            status_code=400,
        )
    except FileNotFoundError as e:
        raise AppException(
            code="REFERENCE_NOT_FOUND",
            message=str(e),
            status_code=404,
        )

    if not thumb_path.exists():
        raise AppException(
            code="REFERENCE_NOT_FOUND",
            message=f"La référence '{ref_id}' est introuvable sur disque",
            status_code=404,
        )

    # Détection MIME
    ext = thumb_path.suffix.lower()
    media_type = "image/png" if ext == ".png" else "image/jpeg"

    return FileResponse(thumb_path, media_type=media_type)

