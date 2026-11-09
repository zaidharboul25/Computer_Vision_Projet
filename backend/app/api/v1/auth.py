"""Routes d'authentification (/api/v1/auth)."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, status
from pymongo.asynchronous.database import AsyncDatabase
from app.core.config import settings
from app.core.errors import AppException, UnauthenticatedException
from app.core.permissions import AuthenticatedUser, get_current_user
from app.core.security import create_access_token, verify_password
from app.db.mongo import get_db
from app.db.repositories.audit import AuditRepository
from app.db.repositories.users import UserRepository
from app.schemas.user import UserLoginRequest, UserLoginResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentification"])


@router.post("/login", response_model=UserLoginResponse)
async def login(credentials: UserLoginRequest, db: AsyncDatabase = Depends(get_db)):
    user_repo = UserRepository(db)
    audit_repo = AuditRepository(db)

    user = await user_repo.get_by_username(credentials.username)
    if not user:
        await audit_repo.log_action(
            action="login_failure",
            details={"username": credentials.username, "reason": "unknown_user"},
        )
        raise UnauthenticatedException(message="Identifiant ou mot de passe incorrect")

    if not user.get("active", True):
        raise AppException(
            code="FORBIDDEN",
            message="Ce compte utilisateur a été désactivé",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Vérification verrouillage temporaire après N échecs
    if await user_repo.is_locked(user):
        raise AppException(
            code="FORBIDDEN",
            message=f"Compte temporairement verrouillé suite à plusieurs tentatives infructueuses ({settings.MAX_LOGIN_ATTEMPTS} échecs). Réessayez plus tard.",
            status_code=status.HTTP_403_FORBIDDEN,
            details={"locked_until": user.get("locked_until")},
        )

    valid = verify_password(credentials.password, user["password_hash"])
    just_locked, _ = await user_repo.record_login_attempt(credentials.username, success=valid)

    if not valid:
        await audit_repo.log_action(
            action="login_failure",
            user_id=user["_id"],
            details={"username": credentials.username, "reason": "bad_password"},
        )
        if just_locked:
            await audit_repo.log_action(
                action="account_locked",
                user_id=user["_id"],
                details={"username": credentials.username, "duration_minutes": settings.LOCKOUT_MINUTES},
            )
        raise UnauthenticatedException(message="Identifiant ou mot de passe incorrect")

    # Connexion réussie
    token = create_access_token(
        subject=user["username"],
        role=user["role"],
        expires_delta=timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    )

    await audit_repo.log_action(
        action="login_success",
        user_id=user["_id"],
        details={"username": user["username"], "role": user["role"]},
    )

    c_at = user.get("created_at")
    if hasattr(c_at, "isoformat"):
        c_at_str = c_at.isoformat()
    elif c_at:
        c_at_str = str(c_at)
    else:
        c_at_str = datetime.now(timezone.utc).isoformat()

    user_resp = UserResponse(
        id=user["_id"],
        username=user["username"],
        role=user["role"],
        active=user.get("active", True),
        created_at=c_at_str,
        last_login=user.get("last_login"),
    )

    return UserLoginResponse(access_token=token, token_type="bearer", user=user_resp)


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
):
    user_repo = UserRepository(db)
    user = await user_repo.get_by_username(current_user.username)
    if not user:
        raise UnauthenticatedException(message="Utilisateur introuvable")

    c_at = user.get("created_at")
    if hasattr(c_at, "isoformat"):
        c_at_str = c_at.isoformat()
    elif c_at:
        c_at_str = str(c_at)
    else:
        c_at_str = datetime.now(timezone.utc).isoformat()

    l_login = user.get("last_login")
    if hasattr(l_login, "isoformat"):
        l_login_str = l_login.isoformat()
    elif l_login:
        l_login_str = str(l_login)
    else:
        l_login_str = None

    return UserResponse(
        id=user["_id"],
        username=user["username"],
        role=user["role"],
        active=user.get("active", True),
        created_at=c_at_str,
        last_login=l_login_str,
    )
