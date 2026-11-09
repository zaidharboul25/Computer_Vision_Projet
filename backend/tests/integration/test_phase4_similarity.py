"""Tests d'intégration pour le moteur et l'API de similarité visuelle (Phase 4).

Vérifie les critères contractuels :
- Exactitude des libellés UI
- Présence de metric="cosine_similarity" et higher_is_better=True
- Absence de pourcentages, de classes arbitraires et de chemins fichiers locaux
- Sécurité anti-traversal et gestion des erreurs 400/404 sur les vignettes
- Protection par jeton Bearer
"""
import io
import pytest
from PIL import Image
from app.core.permissions import UserRole


@pytest.mark.asyncio
async def test_similarity_search_and_labels(async_client, create_user_helper):
    """Vérifie la réponse de recherche de similarité sur les index WeaveGuard et DTD."""
    _, token = await create_user_helper("sim_user", UserRole.OPERATOR.value)
    headers = {"Authorization": f"Bearer {token}"}

    # Création d'une fausse image textile en mémoire
    img = Image.new("RGB", (256, 256), color=(120, 80, 100))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    files = {"file": ("query.png", buf.getvalue(), "image/png")}
    data = {"index_name": "all", "k": 3}

    res = await async_client.post("/api/v1/similarity/search", headers=headers, files=files, data=data)
    assert res.status_code == 200
    res_data = res.json()

    # 1. Vérification index WeaveGuard
    assert "weaveguard" in res_data
    wg = res_data["weaveguard"]
    assert wg["metric"] == "cosine_similarity"
    assert wg["higher_is_better"] is True
    assert wg["label"] == "Textiles similaires (index WeaveGuard)"
    assert "similarité visuelle" in wg["note"]
    assert len(wg["results"]) <= 3

    for item in wg["results"]:
        assert "score" in item
        # Pas de pourcentages
        assert isinstance(item["score"], float)
        assert 0.0 <= item["score"] <= 1.05
        # Pas de chemins locaux
        assert "path" not in item
        assert "filepath" not in item
        assert "local_path" not in item

    # 2. Vérification index DTD
    assert "dtd" in res_data
    dtd = res_data["dtd"]
    assert dtd["metric"] == "cosine_similarity"
    assert dtd["higher_is_better"] is True
    assert dtd["label"] == "Textures similaires (galerie DTD générique)"
    assert len(dtd["results"]) <= 3

    for item in dtd["results"]:
        assert "score" in item
        assert isinstance(item["score"], float)
        assert "path" not in item


@pytest.mark.asyncio
async def test_similarity_thumbnail_security_and_errors(async_client, create_user_helper):
    """Vérifie le contrôle d'accès et la résistance aux attaques par traversée de chemin."""
    _, token = await create_user_helper("sim_thumb_user", UserRole.OPERATOR.value)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Accès sans token -> 401
    res_no_auth = await async_client.get("/api/v1/similarity/ref/dtd:banded_0001.jpg/thumbnail")
    assert res_no_auth.status_code == 401

    # 2. Tentative de traversée de chemin (path traversal) -> 400 SECURITY_ERROR
    res_traversal = await async_client.get("/api/v1/similarity/ref/dtd:..%2F..%2Fetc%2Fpasswd/thumbnail", headers=headers)
    assert res_traversal.status_code == 400
    assert res_traversal.json()["error"]["code"] == "SECURITY_ERROR"

    # 3. Schéma invalide -> 400 SECURITY_ERROR
    res_bad_schema = await async_client.get("/api/v1/similarity/ref/unknown_prefix:123/thumbnail", headers=headers)
    assert res_bad_schema.status_code == 400
    assert res_bad_schema.json()["error"]["code"] == "SECURITY_ERROR"

    # 4. Référence introuvable -> 404 REFERENCE_NOT_FOUND
    res_not_found = await async_client.get("/api/v1/similarity/ref/dtd:non_existent_texture_xyz.jpg/thumbnail", headers=headers)
    assert res_not_found.status_code == 404
    assert res_not_found.json()["error"]["code"] == "REFERENCE_NOT_FOUND"
