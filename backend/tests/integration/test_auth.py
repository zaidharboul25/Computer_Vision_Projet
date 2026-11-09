"""Tests d'intégration de l'authentification (/api/v1/auth)."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success_and_audit(async_client: AsyncClient, create_user_helper, setup_test_db):
    db = setup_test_db
    await create_user_helper("alice", "operator", "SecretAlice2026!")

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "SecretAlice2026!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "alice"
    assert data["user"]["role"] == "operator"

    # Vérification entrée audit
    audit = await db.audit_log.find_one({"action": "login_success"})
    assert audit is not None
    assert audit["details"]["username"] == "alice"


@pytest.mark.asyncio
async def test_login_identical_error_message_and_audit(async_client: AsyncClient, create_user_helper, setup_test_db):
    """Vérifie que l'erreur est strictement identique entre utilisateur inconnu et mauvais mot de passe."""
    db = setup_test_db
    await create_user_helper("alice", "operator", "SecretAlice2026!")

    # Cas 1 : utilisateur inexistant
    res_unknown = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "inconnu_total", "password": "NimporteQuelMotDePasse"},
    )
    assert res_unknown.status_code == 401
    err_unknown = res_unknown.json()

    # Cas 2 : bon utilisateur, mauvais mot de passe
    res_bad = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "MauvaisMotDePasse"},
    )
    assert res_bad.status_code == 401
    err_bad = res_bad.json()

    # Les messages et codes doivent être STRICTEMENT identiques (anti-énumération)
    assert err_unknown["error"]["code"] == err_bad["error"]["code"] == "UNAUTHENTICATED"
    assert err_unknown["error"]["message"] == err_bad["error"]["message"] == "Identifiant ou mot de passe incorrect"

    # Audit des échecs
    audits = await db.audit_log.find({"action": "login_failure"}).to_list(10)
    assert len(audits) >= 2


@pytest.mark.asyncio
async def test_login_lockout_stored_in_mongodb_and_audited(async_client: AsyncClient, create_user_helper, setup_test_db):
    db = setup_test_db
    await create_user_helper("bob", "operator", "SecretBob2026!")

    # 4 échecs consécutifs -> 401
    for i in range(1, 5):
        res = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "bob", "password": "FauxPassword"},
        )
        assert res.status_code == 401
        user_doc = await db.users.find_one({"username": "bob"})
        assert user_doc["failed_attempts"] == i
        assert user_doc["locked_until"] is None

    # 5ème échec -> verrouille l'utilisateur dans MongoDB
    res5 = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "bob", "password": "FauxPassword"},
    )
    assert res5.status_code == 401

    user_doc = await db.users.find_one({"username": "bob"})
    assert user_doc["failed_attempts"] == 5
    assert user_doc["locked_until"] is not None

    # Vérification entrée audit de verrouillage
    lock_audit = await db.audit_log.find_one({"action": "account_locked"})
    assert lock_audit is not None
    assert lock_audit["details"]["username"] == "bob"
    assert lock_audit["details"]["duration_minutes"] == 15

    # 6ème tentative (même avec le bon mot de passe) -> 403 verrouillé
    res_locked = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "bob", "password": "SecretBob2026!"},
    )
    assert res_locked.status_code == 403
    err = res_locked.json()
    assert err["error"]["code"] == "FORBIDDEN"
    assert "verrouillé" in err["error"]["message"].lower()


@pytest.mark.asyncio
async def test_auth_me_endpoints(async_client: AsyncClient, operator_auth):
    # Sans token -> 401
    res_no_token = await async_client.get("/api/v1/auth/me")
    assert res_no_token.status_code == 401
    assert res_no_token.json()["error"]["code"] == "UNAUTHENTICATED"

    # Avec token valide
    res = await async_client.get("/api/v1/auth/me", headers=operator_auth["headers"])
    assert res.status_code == 200
    assert res.json()["username"] == "operator_test"
    assert res.json()["role"] == "operator"
