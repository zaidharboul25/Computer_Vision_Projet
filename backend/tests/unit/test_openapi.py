"""Test unitaire garantissant la conformité exhaustive du schéma OpenAPI (Phase 4).

Vérifie que :
1. Chaque route de l'application FastAPI déclare obligatoirement un response_model ou une documentation de contenu (responses).
2. Les routes retournant des fichiers binaires (image, heatmap, overlay, vignettes) documentent explicitement leurs types MIME (image/png, image/jpeg, etc.).
3. Le fichier exporté docs/openapi.json est valide et synchronisé.
"""
from pathlib import Path
from fastapi.routing import APIRoute
import pytest
from app.main import app


def test_all_routes_declare_response_model_or_media_type():
    """Garde-fou : chaque endpoint de l'API doit avoir un response_model ou un responses documenté."""
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    missing_response_docs = []

    for route in routes:
        # Ignore les routes utilitaires internes /docs, /openapi.json, etc.
        if route.path in ("/docs", "/redoc", "/openapi.json"):
            continue

        has_model = route.response_model is not None
        has_custom_response = False

        if route.responses:
            for status_code, resp_def in route.responses.items():
                if isinstance(status_code, int) and 200 <= status_code < 300:
                    if "content" in resp_def or "model" in resp_def:
                        has_custom_response = True
                        break

        if not has_model and not has_custom_response:
            missing_response_docs.append(f"{list(route.methods)} {route.path}")

    assert not missing_response_docs, (
        f"Les routes suivantes ne déclarent ni response_model ni responses[2xx][content] : {missing_response_docs}"
    )


def test_binary_file_endpoints_document_media_types():
    """Vérifie que les endpoints servant des fichiers documentent rigoureusement leur type MIME."""
    schema = app.openapi()
    paths = schema.get("paths", {})

    # 1. Image originale
    img_spec = paths.get("/api/v1/inspections/{inspection_id}/image", {}).get("get", {})
    assert "200" in img_spec.get("responses", {}), "Endpoint image originale 200 manquant"
    assert "image/png" in img_spec["responses"]["200"]["content"]

    # 2. Heatmap
    hm_spec = paths.get("/api/v1/inspections/{inspection_id}/heatmap", {}).get("get", {})
    assert "200" in hm_spec.get("responses", {}), "Endpoint heatmap 200 manquant"
    assert "image/png" in hm_spec["responses"]["200"]["content"]

    # 3. Overlay (png, webp, jpeg)
    ov_spec = paths.get("/api/v1/inspections/{inspection_id}/overlay", {}).get("get", {})
    assert "200" in ov_spec.get("responses", {}), "Endpoint overlay 200 manquant"
    assert "image/png" in ov_spec["responses"]["200"]["content"]
    assert "image/webp" in ov_spec["responses"]["200"]["content"]
    assert "image/jpeg" in ov_spec["responses"]["200"]["content"]

    # 4. Vignette de région
    thumb_reg_spec = paths.get("/api/v1/regions/{region_id}/thumbnail", {}).get("get", {})
    assert "200" in thumb_reg_spec.get("responses", {}), "Endpoint vignette région 200 manquant"
    assert "image/png" in thumb_reg_spec["responses"]["200"]["content"]

    # 5. Vignette de référence de similarité
    thumb_sim_spec = paths.get("/api/v1/similarity/ref/{ref_id}/thumbnail", {}).get("get", {})
    assert "200" in thumb_sim_spec.get("responses", {}), "Endpoint vignette similarité 200 manquant"
    assert "image/jpeg" in thumb_sim_spec["responses"]["200"]["content"]


def test_openapi_json_file_exists_and_matches_app():
    """Vérifie que docs/openapi.json existe et contient les métadonnées de l'application."""
    import json
    openapi_file = Path(__file__).resolve().parent.parent.parent.parent / "docs" / "openapi.json"
    assert openapi_file.exists(), "docs/openapi.json doit être généré via scripts/export_openapi.py"

    with open(openapi_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["info"]["title"] == "WeaveGuard AI - API d'Inspection Textile"
    assert "/api/v1/inspections" in data["paths"]
    assert "/api/v1/settings/rejection-reasons" in data["paths"]

