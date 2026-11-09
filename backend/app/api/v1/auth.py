"""Routes d'authentification (/api/v1/auth)."""
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Request, Response, status
from pymongo.asynchronous.database import AsyncDatabase
from app.core.config import settings
from app.core.errors import AppException, UnauthenticatedException
from app.core.permissions import AuthenticatedUser, compute_csrf_token, get_current_user, resolve_token
from app.core.rate_limit import SlidingWindowLimiter
from app.core.security import create_access_token, hash_password, verify_password
from app.db.mongo import get_db
from app.db.repositories.audit import AuditRepository
from app.db.repositories.users import UserRepository
from app.schemas.user import ActionStatusResponse, MeResponse, UserLoginRequest, UserLoginResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentification"])

login_ip_limiter = SlidingWindowLimiter(settings.LOGIN_IP_MAX_ATTEMPTS, settings.LOGIN_IP_WINDOW_SECONDS)

# Empreinte factice : on vérifie toujours un mot de passe, même pour un identifiant inconnu,
# afin d'égaliser le temps de réponse (anti-énumération par chronométrage).
_DUMMY_HASH: Optional[str] = None


def _dummy_verify(password: str) -> None:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password("weaveguard-dummy-password")
    verify_password(password, _DUMMY_HASH)


def _client_ip(request: Request) -> str:
    # Derrière un reverse proxy, lancer uvicorn avec --proxy-headers --forwarded-allow-ips=<ip du proxy>
    return request.client.host if request.client else "unknown"


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )


@router.post("/login", response_model=UserLoginResponse)
async def login(
    credentials: UserLoginRequest,
    request: Request,
    response: Response,
    db: AsyncDatabase = Depends(get_db),
):
    user_repo = UserRepository(db)
    audit_repo = AuditRepository(db)
    ip = _client_ip(request)

    retry_after = login_ip_limiter.retry_after(ip)
    if retry_after:
        raise AppException(
            code="TOO_MANY_REQUESTS",
            message=f"Trop de tentatives de connexion depuis cette adresse. Réessayez dans {retry_after} s.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"retry_after_seconds": retry_after},
        )

    user = await user_repo.get_by_username(credentials.username)
    if not user:
        _dummy_verify(credentials.password)
        login_ip_limiter.register(ip)
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
        login_ip_limiter.register(ip)
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

    _set_session_cookie(response, token)
    return UserLoginResponse(
        access_token=token,
        token_type="bearer",
        user=user_resp,
        csrf_token=compute_csrf_token(token),
    )


@router.post(
    "/logout",
    response_model=ActionStatusResponse,
    summary="Fermer la session (supprime le cookie httpOnly)",
)
async def logout(response: Response):
    """Idempotent : supprime le cookie de session. Ne nécessite pas d'être authentifié."""
    response.delete_cookie(
        key=settings.COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.COOKIE_SAMESITE,
    )
    return ActionStatusResponse(status="ok", message="Session fermée")


@router.get("/me", response_model=MeResponse)
async def get_me(
    current_user: AuthenticatedUser = Depends(get_current_user),
    session_token: str = Depends(resolve_token),
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

    return MeResponse(
        id=user["_id"],
        username=user["username"],
        role=user["role"],
        active=user.get("active", True),
        created_at=c_at_str,
        last_login=l_login_str,
        csrf_token=compute_csrf_token(session_token),
    )
