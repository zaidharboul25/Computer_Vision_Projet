"""Erreurs structurées et gestionnaires d'exceptions de WeaveGuard AI.

Format contractuel garanti (§9 & §10.3 du cahier des charges) :
{
    "error": {
        "code": "...",
        "message": "...",
        "correlation_id": "...",
        "details": {...}
    }
}
"""
from typing import Any, Dict, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.correlation import get_correlation_id
from app.core.logging import logger


class AppException(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


# Exceptions métier spécifiques
class UnauthenticatedException(AppException):
    def __init__(self, message: str = "Authentification requise", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="UNAUTHENTICATED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class ForbiddenException(AppException):
    def __init__(self, message: str = "Accès non autorisé pour ce rôle", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class DatabaseUnavailableException(AppException):
    def __init__(self, message: str = "Base de données MongoDB indisponible", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="DATABASE_UNAVAILABLE",
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details,
        )


class ModelUnavailableException(AppException):
    def __init__(self, message: str = "Moteur IA indisponible", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="MODEL_UNAVAILABLE",
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details,
        )


class InferenceFailedException(AppException):
    def __init__(self, message: str = "Échec de l'inférence du modèle", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="INFERENCE_FAILED",
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class InspectionNotFoundException(AppException):
    def __init__(self, message: str = "Inspection introuvable", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="INSPECTION_NOT_FOUND",
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class RegionNotFoundException(AppException):
    def __init__(self, message: str = "Région introuvable", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="REGION_NOT_FOUND",
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class InvalidImageException(AppException):
    def __init__(self, message: str = "Fichier image invalide ou corrompu", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="INVALID_IMAGE",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class ServerBusyException(AppException):
    def __init__(self, message: str = "File d'attente d'inspection saturée, veuillez réessayer ultérieurement", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="SERVER_BUSY",
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details,
        )


class ImageTooLargeException(AppException):
    def __init__(self, message: str = "Taille ou dimensions de l'image dépassent la limite", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="IMAGE_TOO_LARGE",
            message=message,
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            details=details,
        )


# Alias pour rétrocompatibilité
FileTooLargeException = ImageTooLargeException


class InvalidFeedbackException(AppException):
    def __init__(self, message: str = "Payload de revue de région invalide", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="INVALID_FEEDBACK",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


def build_error_response(code: str, message: str, status_code: int, details: Optional[Dict[str, Any]] = None) -> JSONResponse:
    cid = get_correlation_id()
    payload = {
        "error": {
            "code": code,
            "message": message,
            "correlation_id": cid,
            "details": details or {},
        }
    }
    return JSONResponse(status_code=status_code, content=payload)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    logger.warning(
        f"AppException: {exc.code} - {exc.message}",
        extra={"error_code": exc.code, "status_code": exc.status_code, "route": request.url.path},
    )
    return build_error_response(exc.code, exc.message, exc.status_code, exc.details)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    # Nettoyage pour ne pas exposer d'informations internes
    cleaned_errors = []
    for e in errors:
        loc = " -> ".join(str(item) for item in e.get("loc", []))
        cleaned_errors.append({"location": loc, "message": e.get("msg", ""), "type": e.get("type", "")})

    return build_error_response(
        code="VALIDATION_ERROR",
        message="Erreur de validation de la requête",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details={"validation_errors": cleaned_errors},
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code_map = {
        status.HTTP_401_UNAUTHORIZED: "UNAUTHENTICATED",
        status.HTTP_403_FORBIDDEN: "FORBIDDEN",
        status.HTTP_404_NOT_FOUND: "NOT_FOUND",
        status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
    }
    code = code_map.get(exc.status_code, "HTTP_ERROR")
    return build_error_response(code=code, message=str(exc.detail), status_code=exc.status_code)


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Exception non interceptée", extra={"route": request.url.path})
    return build_error_response(
        code="INTERNAL_ERROR",
        message="Une erreur interne est survenue. L'incident a été consigné.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )

