"""Schémas d'erreurs contractuels WeaveGuard AI."""
from typing import Any, Dict
from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    correlation_id: str
    details: Dict[str, Any] = {}


class ErrorResponse(BaseModel):
    error: ErrorBody


COMMON_ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Requête invalide ou corrompue"},
    401: {"model": ErrorResponse, "description": "Authentification manquante, invalide ou expirée"},
    403: {"model": ErrorResponse, "description": "Droits d'accès insuffisants pour ce rôle"},
    404: {"model": ErrorResponse, "description": "Ressource inexistante ou inaccessible"},
    413: {"model": ErrorResponse, "description": "Image ou fichier trop volumineux"},
    422: {"model": ErrorResponse, "description": "Erreur de validation des paramètres"},
    500: {"model": ErrorResponse, "description": "Erreur interne du serveur"},
    503: {"model": ErrorResponse, "description": "Base de données ou modèle IA indisponible"},
}

