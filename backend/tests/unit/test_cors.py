"""Tests unitaires pour la politique CORS et les requêtes OPTIONS (preflight)."""
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_cors_preflight_options_request():
    """Vérifie la réponse preflight OPTIONS avec en-têtes Authorization et exposition de X-Correlation-ID."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Requête preflight depuis http://localhost:5173
        headers_localhost = {
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization, Content-Type, X-Correlation-ID",
        }
        res_loc = await client.options("/api/v1/inspections", headers=headers_localhost)
        assert res_loc.status_code == 200
        assert res_loc.headers.get("access-control-allow-origin") == "http://localhost:5173"
        allow_headers = res_loc.headers.get("access-control-allow-headers", "").lower()
        assert "authorization" in allow_headers
        assert "content-type" in allow_headers

        # Vérification exposition des en-têtes (Access-Control-Expose-Headers) sur une requête réelle
        res_real = await client.get("/health", headers={"Origin": "http://localhost:5173"})
        assert res_real.status_code == 200
        assert res_real.headers.get("access-control-allow-origin") == "http://localhost:5173"
        expose_headers = res_real.headers.get("access-control-expose-headers", "").lower()
        assert "x-correlation-id" in expose_headers
        assert "content-disposition" in expose_headers

        # 2. Requête preflight depuis http://127.0.0.1:5173
        headers_ip = {
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        }
        res_ip = await client.options("/api/v1/inspections", headers=headers_ip)
        assert res_ip.status_code == 200
        assert res_ip.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


@pytest.mark.asyncio
async def test_rejection_reasons_endpoint_includes_couture(async_client, create_user_helper):
    """Vérifie que l'endpoint /api/v1/settings/rejection-reasons renvoie bien 'couture'."""
    _, token = await create_user_helper("settings_user", "operator")
    headers = {"Authorization": f"Bearer {token}"}

    res = await async_client.get("/api/v1/settings/rejection-reasons", headers=headers)
    assert res.status_code == 200
    reasons = res.json()
    assert isinstance(reasons, list)
    assert "couture" in reasons
    assert "artefact_tissage" in reasons
    assert "pli_tissu" in reasons

