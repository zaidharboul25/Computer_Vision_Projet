"""Session par cookie httpOnly, protection CSRF et limitation de débit par IP (/api/v1/auth)."""
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.permissions import compute_csrf_token

PASSWORD = "SecretAlice2026!"


async def _login(client: AsyncClient):
    res = await client.post("/api/v1/auth/login", json={"username": "alice", "password": PASSWORD})
    assert res.status_code == 200, res.text
    return res


@pytest.mark.asyncio
async def test_login_sets_httponly_cookie_and_returns_csrf(async_client: AsyncClient, create_user_helper):
    await create_user_helper("alice", "operator", PASSWORD)
    res = await _login(async_client)

    set_cookie = res.headers["set-cookie"].lower()
    assert f"{settings.COOKIE_NAME}=" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    body = res.json()
    assert body["csrf_token"] == compute_csrf_token(body["access_token"])


@pytest.mark.asyncio
async def test_me_works_with_cookie_only_and_returns_csrf(async_client: AsyncClient, create_user_helper):
    await create_user_helper("alice", "operator", PASSWORD)
    login_body = (await _login(async_client)).json()

    res = await async_client.get("/api/v1/auth/me")  # le client rejoue le cookie, aucun en-tête Authorization
    assert res.status_code == 200
    assert res.json()["username"] == "alice"
    assert res.json()["csrf_token"] == login_body["csrf_token"]


@pytest.mark.asyncio
async def test_mutating_request_with_cookie_requires_valid_csrf(async_client: AsyncClient, create_user_helper):
    await create_user_helper("alice", "operator", PASSWORD)
    csrf = (await _login(async_client)).json()["csrf_token"]

    missing = await async_client.post("/api/v1/inspections")
    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "FORBIDDEN"

    wrong = await async_client.post("/api/v1/inspections", headers={"X-CSRF-Token": "invalide"})
    assert wrong.status_code == 403

    # Avec le bon jeton, la garde CSRF est franchie (l'upload manquant donne alors 422, pas 403)
    ok = await async_client.post("/api/v1/inspections", headers={"X-CSRF-Token": csrf})
    assert ok.status_code == 422


@pytest.mark.asyncio
async def test_bearer_clients_are_not_subject_to_csrf(async_client: AsyncClient, create_user_helper):
    await create_user_helper("alice", "operator", PASSWORD)
    token = (await _login(async_client)).json()["access_token"]
    async_client.cookies.clear()

    res = await async_client.post("/api/v1/inspections", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 422  # authentifié, mais fichier absent


@pytest.mark.asyncio
async def test_logout_clears_cookie(async_client: AsyncClient, create_user_helper):
    await create_user_helper("alice", "operator", PASSWORD)
    await _login(async_client)

    res = await async_client.post("/api/v1/auth/logout")
    assert res.status_code == 200
    assert "max-age=0" in res.headers["set-cookie"].lower()

    async_client.cookies.clear()
    assert (await async_client.get("/api/v1/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_ip_throttle_blocks_password_spraying_on_unknown_accounts(async_client: AsyncClient, create_user_helper):
    await create_user_helper("alice", "operator", PASSWORD)

    for i in range(settings.LOGIN_IP_MAX_ATTEMPTS):
        res = await async_client.post(
            "/api/v1/auth/login", json={"username": f"inconnu{i}", "password": "nimportequoi"}
        )
        assert res.status_code == 401

    blocked = await async_client.post("/api/v1/auth/login", json={"username": "alice", "password": PASSWORD})
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "TOO_MANY_REQUESTS"
    assert blocked.json()["error"]["details"]["retry_after_seconds"] > 0
