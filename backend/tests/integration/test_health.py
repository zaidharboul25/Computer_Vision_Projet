"""Tests d'intégration de l'endpoint /health."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded")
    assert "database" in data
    assert data["database"] == "connected"
    assert "device_active" in data
    assert "gpu" in data
    assert "engines" in data
    assert "timestamp" in data

    # Vérification de l'en-tête de corrélation
    assert "x-correlation-id" in response.headers

