"""Routes d'administration des utilisateurs (/api/v1/users) — rôle admin obligatoire."""
from typing import List
from fastapi import APIRouter, Depends, Query, status
from pymongo.asynchronous.database import AsyncDatabase
from app.core.errors import AppException
from app.core.permissions import AuthenticatedUser, UserRole, require_roles
from app.core.security import hash_password
from app.db.mongo import get_db
from app.db.repositories.audit import AuditRepository
from app.db.repositories.users import UserRepository
from app.schemas.user import (
    ActionStatusResponse,
    UserCreateRequest,
    UserResetPasswordRequest,
    UserResponse,
    UserUpdateRequest,
)

router = APIRouter(prefix="/users", tags=["Gestion des utilisateurs"])


@router.get("", response_model=List[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    admin: AuthenticatedUser = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncDatabase = Depends(get_db),
):
    user_repo = UserRepository(db)
    users = await user_repo.list_users(skip=skip, limit=limit)
    return [
        UserResponse(
            id=u["_id"],
            username=u["username"],
            role=u["role"],
            active=u.get("active", True),
            created_at=u["created_at"],
            last_login=u.get("last_login"),
        )
        for u in users
    ]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    req: UserCreateRequest,
    admin: AuthenticatedUser = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncDatabase = Depends(get_db),
):
    user_repo = UserRepository(db)
    audit_repo = AuditRepository(db)

    existing = await user_repo.get_by_username(req.username)
    if existing:
        raise AppException(
            code="USER_ALREADY_EXISTS",
            message=f"L'utilisateur '{req.username}' existe déjà",
            status_code=status.HTTP_409_CONFLICT,
        )

    user = await user_repo.create(username=req.username, password=req.password, role=req.role.value)

    await audit_repo.log_action(
        action="user_created",
        user_id=admin.username,
        details={"created_user": req.username, "role": req.role.value},
    )

    return UserResponse(
        id=user["_id"],
        username=user["username"],
        role=user["role"],
        active=user["active"],
        created_at=user["created_at"],
        last_login=None,
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    req: UserUpdateRequest,
    admin: AuthenticatedUser = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncDatabase = Depends(get_db),
):
    user_repo = UserRepository(db)
    audit_repo = AuditRepository(db)

    user = await user_repo.get_by_id(user_id)
    if not user:
        raise AppException(
            code="USER_NOT_FOUND",
            message=f"Utilisateur introuvable : {user_id}",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    updates = {}
    if req.role is not None:
        updates["role"] = req.role.value
    if req.active is not None:
        updates["active"] = req.active

    if not updates:
        return UserResponse(
            id=user["_id"],
            username=user["username"],
            role=user["role"],
            active=user.get("active", True),
            created_at=user["created_at"],
            last_login=user.get("last_login"),
        )

    updated = await user_repo.update(user_id, updates)

    await audit_repo.log_action(
        action="user_updated",
        user_id=admin.username,
        details={"target_user": user["username"], "updates": updates},
    )

    return UserResponse(
        id=updated["_id"],
        username=updated["username"],
        role=updated["role"],
        active=updated.get("active", True),
        created_at=updated["created_at"],
        last_login=updated.get("last_login"),
    )


@router.post(
    "/{user_id}/reset-password",
    response_model=ActionStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Réinitialiser le mot de passe d'un utilisateur",
)
async def reset_password(
    user_id: str,
    req: UserResetPasswordRequest,
    admin: AuthenticatedUser = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncDatabase = Depends(get_db),
):
    user_repo = UserRepository(db)
    audit_repo = AuditRepository(db)

    user = await user_repo.get_by_id(user_id)
    if not user:
        raise AppException(
            code="USER_NOT_FOUND",
            message=f"Utilisateur introuvable : {user_id}",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    new_hash = hash_password(req.new_password)
    await user_repo.update(
        user_id,
        {"password_hash": new_hash, "failed_attempts": 0, "locked_until": None},
    )

    await audit_repo.log_action(
        action="user_password_reset",
        user_id=admin.username,
        details={"target_user": user["username"]},
    )

    return {"status": "ok", "message": f"Mot de passe réinitialisé pour l'utilisateur '{user['username']}'"}

