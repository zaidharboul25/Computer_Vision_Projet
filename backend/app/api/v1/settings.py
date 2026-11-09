"""Routeur pour les paramètres et configurations exposés au frontend."""
from typing import List
from fastapi import APIRouter, Depends
from app.core.config import settings
from app.core.permissions import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/settings", tags=["Paramètres & Configuration"])


@router.get(
    "/rejection-reasons",
    response_model=List[str],
    summary="Obtenir la liste standardisée des motifs de rejet de détection",
)
async def get_rejection_reasons(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Renvoie la liste des motifs de rejet configurés dans settings.REJECTION_REASONS.

    Accessible à tous les utilisateurs authentifiés pour alimenter dynamiquement le frontend.
    """
    return list(settings.REJECTION_REASONS)

