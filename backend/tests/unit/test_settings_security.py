"""Garde-fous de configuration de sécurité (CORS + cookie de session)."""
import pytest
from app.core.config import Settings

SECRET = "s" * 40


def test_wildcard_cors_is_rejected_because_cookies_are_credentialed():
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        Settings(JWT_SECRET=SECRET, CORS_ORIGINS="*")
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        Settings(JWT_SECRET=SECRET, CORS_ORIGINS="http://localhost:5173,*")


def test_cookie_secure_defaults_to_true_only_in_prod():
    assert Settings(JWT_SECRET=SECRET, ENV="prod").cookie_secure is True
    assert Settings(JWT_SECRET=SECRET, ENV="dev").cookie_secure is False
    assert Settings(JWT_SECRET=SECRET, ENV="dev", COOKIE_SECURE=True).cookie_secure is True
    assert Settings(JWT_SECRET=SECRET, ENV="prod", COOKIE_SECURE=False).cookie_secure is False
