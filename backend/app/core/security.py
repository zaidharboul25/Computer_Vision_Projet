"""Sécurité cryptographique : hachage de mots de passe Argon2 et jetons JWT.

Conforme aux spécifications du cahier des charges :
- Hachage Argon2 via argon2-cffi
- Signature JWT HS256 avec expiration courte
- Verrouillage temporaire après N échecs
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from app.core.config import settings

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    """Hache un mot de passe avec Argon2."""
    return _ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe en clair contre son empreinte Argon2."""
    try:
        return _ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError):
        return False


def needs_rehash(hashed_password: str) -> bool:
    """Indique si l'empreinte nécessite une mise à jour des paramètres de sécurité."""
    return _ph.check_needs_rehash(hashed_password)


def create_access_token(
    subject: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Génère un jeton JWT d'accès signé."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)

    payload = {
        "sub": subject,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)

    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token


def decode_access_token(token: str) -> Dict[str, Any]:
    """Décode et valide un jeton JWT d'accès.

    Lève jwt.PyJWTError en cas d'invalidité ou d'expiration.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["sub", "role", "exp", "iat"]},
    )

