"""Routeur pour l'export des revues humaines et annotations futures (Phase 4).

RÈGLES CONTRACTUELLES (§6.5, §12) :
- Accès restreint aux rôles 'admin' et 'ml_engineer'.
- Export combiné du feedback humain avec la géométrie et classification de la région.
- Consigne un événement d'audit 'feedback_export'.
"""
from typing import List
from fastapi import APIRouter, Depends, Query
from app.core.permissions import AuthenticatedUser, UserRole, require_roles
from app.db.mongo import get_database
from app.db.repositories.audit import AuditRepository
from app.db.repositories.feedback import FeedbackRepository
from app.schemas.feedback import FeedbackExportItem

router = APIRouter(prefix="/feedback", tags=["Export & Annotations"])


@router.get(
    "/export",
    response_model=List[FeedbackExportItem],
    summary="Exporter les décisions humaines pour réentraînement ou analyse ML",
)
async def export_feedback_dataset(
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=5000),
    current_user: AuthenticatedUser = Depends(require_roles(UserRole.ADMIN, UserRole.ML_ENGINEER)),
):
    """Exporte l'historique des revues humaines associées à leurs boîtes englobantes et classifications.

    Permet aux ingénieurs ML de constituer des jeux d'évaluation ou de réentraînement futurs.
    """
    db = get_database()
    items = await FeedbackRepository.list_feedback_for_export(skip=skip, limit=limit)

    # Consigner l'export dans l'audit
    audit_repo = AuditRepository(db)
    await audit_repo.log_action(
        action="feedback_export",
        user_id=current_user.id,
        username=current_user.username,
        details={
            "skip": skip,
            "limit": limit,
            "count_returned": len(items),
        },
    )

    return [FeedbackExportItem(**item) for item in items]
