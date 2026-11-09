"""Tests unitaires de la sécurité (Argon2, JWT)."""
from datetime import timedelta
import jwt
import pytest
from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hashing():
    pwd = "MonSuperMotDePasse2026!"
    hashed = hash_password(pwd)

    assert hashed != pwd
    assert hashed.startswith("$argon2")
    assert verify_password(pwd, hashed) is True
    assert verify_password("MauvaisMotDePasse", hashed) is False


def test_jwt_token_roundtrip():
    token = create_access_token(subject="operator1", role="operator")
    payload = decode_access_token(token)

    assert payload["sub"] == "operator1"
    assert payload["role"] == "operator"
    assert "exp" in payload
    assert "iat" in payload


def test_jwt_expired_token():
    # Jeton expiré il y a 5 minutes
    expired_token = create_access_token(
        subject="operator1",
        role="operator",
        expires_delta=timedelta(minutes=-5),
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired_token)


def test_jwt_tampered_token():
    token = create_access_token(subject="operator1", role="operator")
    tampered = token[:-4] + "abcd"
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(tampered)


def test_jwt_enforced_algorithm_rejection():
    """Vérifie qu'un jeton encodé sans algorithme ou avec un algorithme différent est rejeté."""
    payload = {"sub": "attacker", "role": "admin", "iat": 1000, "exp": 9999999999}
    
    # Tentative d'attaque algorithme "none"
    token_none = jwt.encode(payload, key="", algorithm="none")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token_none)

    # Tentative avec un secret différent
    token_wrong_secret = jwt.encode(payload, key="another-secret-key-32-chars-long!", algorithm="HS256")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token_wrong_secret)
