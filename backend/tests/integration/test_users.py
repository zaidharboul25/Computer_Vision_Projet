"""Tests d'intégration de la gestion des utilisateurs (/api/v1/users)."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_create_user(async_client: AsyncClient, admin_auth, setup_test_db):
    db = setup_test_db
    payload = {
        "username": "charlie_op",
        "password": "PasswordCharlie123!",
        "role": "operator",
    }
    response = await async_client.post(
        "/api/v1/users",
        json=payload,
        headers=admin_auth["headers"],
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "charlie_op"
    assert data["role"] == "operator"
    assert data["active"] is True
    assert "password_hash" not in data

    # Vérification entrée audit
    audit = await db.audit_log.find_one({"action": "user_created"})
    assert audit is not None
    assert audit["details"]["created_user"] == "charlie_op"


@pytest.mark.asyncio
async def test_create_user_duplicate_fails(async_client: AsyncClient, admin_auth):
    payload = {
        "username": "duplicate_user",
        "password": "Password12345!",
        "role": "operator",
    }
    res1 = await async_client.post("/api/v1/users", json=payload, headers=admin_auth["headers"])
    assert res1.status_code == 201

    res2 = await async_client.post("/api/v1/users", json=payload, headers=admin_auth["headers"])
    assert res2.status_code == 409
    err = res2.json()
    assert err["error"]["code"] == "USER_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_non_admin_cannot_create_user(
    async_client: AsyncClient,
    operator_auth,
    supervisor_auth,
    ml_engineer_auth,
    auditor_auth,
):
    payload = {"username": "hacker", "password": "Password123!", "role": "admin"}

    # Sans token -> 401
    res_none = await async_client.post("/api/v1/users", json=payload)
    assert res_none.status_code == 401
    assert res_none.json()["error"]["code"] == "UNAUTHENTICATED"

    # Autres rôles -> 403
    for auth in [operator_auth, supervisor_auth, ml_engineer_auth, auditor_auth]:
        res = await async_client.post("/api/v1/users", json=payload, headers=auth["headers"])
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_admin_update_and_reset_password(async_client: AsyncClient, admin_auth, setup_test_db):
    db = setup_test_db
    # 1. Création
    res_create = await async_client.post(
        "/api/v1/users",
        json={"username": "david", "password": "PasswordDavid123!", "role": "operator"},
        headers=admin_auth["headers"],
    )
    assert res_create.status_code == 201
    user_id = res_create.json()["id"]

    # 2. Modification du rôle et désactivation
    res_patch = await async_client.patch(
        f"/api/v1/users/{user_id}",
        json={"role": "supervisor", "active": False},
        headers=admin_auth["headers"],
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["role"] == "supervisor"
    assert res_patch.json()["active"] is False

    # Vérification entrée audit
    audit = await db.audit_log.find_one({"action": "user_updated"})
    assert audit is not None
    assert audit["details"]["target_user"] == "david"

    # 3. Réinitialisation du mot de passe
    res_reset = await async_client.post(
        f"/api/v1/users/{user_id}/reset-password",
        json={"new_password": "NewSecretDavid2026!"},
        headers=admin_auth["headers"],
    )
    assert res_reset.status_code == 200
    assert res_reset.json()["status"] == "ok"

    audit_reset = await db.audit_log.find_one({"action": "user_password_reset"})
    assert audit_reset is not None
    assert audit_reset["details"]["target_user"] == "david"
