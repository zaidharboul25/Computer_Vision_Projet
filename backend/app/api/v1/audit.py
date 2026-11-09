"""Routeur pour la consultation des journaux d'audit (Phase 4).

RÈGLES DE SÉCURITÉ (§12) :
- Accès restreint aux rôles 'admin' et 'auditor'.
- Toute consultation consigne elle-même une entrée d'audit 'audit_view'.
- Filtrage paginé sans fuite de secrets ou de données sensibles.
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from app.core.permissions import AuthenticatedUser, UserRole, require_roles
from app.db.mongo import get_database
from app.db.repositories.audit import AuditRepository
from app.schemas.audit import AuditLogItem, AuditLogListResponse

router = APIRouter(prefix="/audit", tags=["Journalisation & Audit"])


@router.get(
    "",
    response_model=AuditLogListResponse,
    summary="Consulter le journal d'audit immuable",
)
async def list_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    action: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    current_user: AuthenticatedUser = Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR)),
):
    """Renvoie la liste paginée des traces d'audit et consigne l'accès."""
    db = get_database()
    audit_repo = AuditRepository(db)

    # Consigner l'action de consultation dans le journal d'audit lui-même
    await audit_repo.log_action(
        action="audit_view",
        user_id=current_user.id,
        username=current_user.username,
        details={
            "skip": skip,
            "limit": limit,
            "filter_action": action,
            "filter_user_id": user_id,
            "filter_username": username,
        },
    )

    items, total = await audit_repo.list_logs(
        skip=skip,
        limit=limit,
        action=action,
        user_id=user_id,
        username=username,
        date_from=date_from,
        date_to=date_to,
    )

    return AuditLogListResponse(
        items=[AuditLogItem(**item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )
