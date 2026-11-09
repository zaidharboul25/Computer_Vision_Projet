"""Tests d'intégration pour la Phase 4 : Revue humaine, Régions, Audit et Immutabilité.

Couvre :
- AC-07 : Cycle de validation humaine (confirmed, rejected, uncertain) et règles de motif.
- AC-03 : Reproductibilité stricte de l'overlay depuis les régions.
- Sécurité : Isolation multi-opérateur (404 sur les régions/vignettes d'autrui), 403 sur non-opérateurs.
- Immutabilité : Aucun endpoint de mise à jour/suppression sur les régions (405) et aucune méthode d'écriture destructive.
- Audit : Inscription d'audit automatique et traçabilité de l'accès aux logs ('audit_view').
"""
import asyncio
import io
import uuid
import pytest
from PIL import Image
from app.core.permissions import UserRole
from app.db.repositories.regions import RegionRepository
from app.services.storage import StorageService
from app.services.visualizer import VisualizerService


@pytest.mark.asyncio
async def test_region_immutability(async_client, create_user_helper):
    """Vérifie l'immutabilité contractuelle des régions."""
    # 1. Vérification statique sur le repository
    forbidden_methods = ["update", "update_one", "update_many", "delete", "delete_one", "delete_many", "remove"]
    for method in forbidden_methods:
        assert not hasattr(RegionRepository, method), f"RegionRepository ne doit pas exposer {method}"

    # 2. Vérification HTTP : PUT, PATCH, DELETE renvoient 405 Method Not Allowed
    _, token = await create_user_helper("admin_user", UserRole.ADMIN.value)
    headers = {"Authorization": f"Bearer {token}"}
    sample_reg_id = str(uuid.uuid4())

    res_put = await async_client.put(f"/api/v1/regions/{sample_reg_id}", headers=headers, json={"some": "data"})
    assert res_put.status_code == 405

    res_patch = await async_client.patch(f"/api/v1/regions/{sample_reg_id}", headers=headers, json={"some": "data"})
    assert res_patch.status_code == 405

    res_delete = await async_client.delete(f"/api/v1/regions/{sample_reg_id}", headers=headers)
    assert res_delete.status_code == 405


@pytest.mark.asyncio
async def test_feedback_rules_and_history(setup_test_db, async_client, create_user_helper):
    """Vérifie les règles métier strictes de validation humaine (AC-07)."""
    db = setup_test_db
    _, op1_token = await create_user_helper("operator_1", UserRole.OPERATOR.value)
    _, op2_token = await create_user_helper("operator_2", UserRole.OPERATOR.value)
    _, admin_token = await create_user_helper("admin_user", UserRole.ADMIN.value)

    # Création d'une inspection appartenant à operator_1
    insp_id = str(uuid.uuid4())
    await db.inspections.insert_one({
        "_id": insp_id,
        "id": insp_id,
        "created_by": "operator_1",
        "status": "done",
        "engines": {},
        "is_demo": False,
    })

    # Création d'une région associée
    reg_id = str(uuid.uuid4())
    await db.regions.insert_one({
        "_id": reg_id,
        "id": reg_id,
        "inspection_id": insp_id,
        "engine": "yolo",
        "bbox": [10.0, 10.0, 50.0, 50.0],
        "classification": {"class_name": "hole", "label": "Défaut proposé : hole", "score": 0.85},
    })

    headers_op1 = {"Authorization": f"Bearer {op1_token}"}
    headers_op2 = {"Authorization": f"Bearer {op2_token}"}
    headers_admin = {"Authorization": f"Bearer {admin_token}"}

    # 1. Rôle non-opérateur -> 403 Forbidden
    res_admin = await async_client.post(
        f"/api/v1/regions/{reg_id}/feedback",
        headers=headers_admin,
        json={"decision": "confirmed"},
    )
    assert res_admin.status_code == 403

    # 2. Opérateur tiers -> 404 INSPECTION_NOT_FOUND (pas de fuite d'existence)
    res_op2 = await async_client.post(
        f"/api/v1/regions/{reg_id}/feedback",
        headers=headers_op2,
        json={"decision": "confirmed"},
    )
    assert res_op2.status_code == 404
    assert res_op2.json()["error"]["code"] == "INSPECTION_NOT_FOUND"

    # 3. 'confirmed' avec motif de rejet -> 400 INVALID_FEEDBACK
    res_bad_confirm = await async_client.post(
        f"/api/v1/regions/{reg_id}/feedback",
        headers=headers_op1,
        json={"decision": "confirmed", "rejection_reason": "pli_tissu"},
    )
    assert res_bad_confirm.status_code == 400
    assert res_bad_confirm.json()["error"]["code"] == "INVALID_FEEDBACK"

    # 4. 'rejected' SANS motif de rejet -> 400 INVALID_FEEDBACK
    res_bad_reject = await async_client.post(
        f"/api/v1/regions/{reg_id}/feedback",
        headers=headers_op1,
        json={"decision": "rejected"},
    )
    assert res_bad_reject.status_code == 400
    assert res_bad_reject.json()["error"]["code"] == "INVALID_FEEDBACK"

    # 5. Premier feedback valide : 'rejected' avec motif
    res_ok_1 = await async_client.post(
        f"/api/v1/regions/{reg_id}/feedback",
        headers=headers_op1,
        json={"decision": "rejected", "rejection_reason": "pli_tissu", "comment": "Pli au tissage"},
    )
    assert res_ok_1.status_code == 201
    f1 = res_ok_1.json()
    assert f1["decision"] == "rejected"
    assert f1["rejection_reason"] == "pli_tissu"

    # 6. Deuxième feedback valide : révision en 'confirmed' (sans motif)
    res_ok_2 = await async_client.post(
        f"/api/v1/regions/{reg_id}/feedback",
        headers=headers_op1,
        json={"decision": "confirmed", "comment": "Erreur initiale, vrai trou"},
    )
    assert res_ok_2.status_code == 201
    f2 = res_ok_2.json()
    assert f2["decision"] == "confirmed"

    # 7. Consultation de l'historique : 2 entrées, la plus récente en premier
    res_hist = await async_client.get(f"/api/v1/regions/{reg_id}/history", headers=headers_op1)
    assert res_hist.status_code == 200
    history = res_hist.json()
    assert len(history) == 2
    assert history[0]["decision"] == "confirmed"
    assert history[1]["decision"] == "rejected"


@pytest.mark.asyncio
async def test_concurrent_feedback_sequence_guarantee(setup_test_db, async_client, create_user_helper):
    """Vérifie l'attribution déterministe d'un numéro de séquence croissant lors d'envois quasi-simultanés."""
    db = setup_test_db
    _, op_token = await create_user_helper("op_concurrent", UserRole.OPERATOR.value)
    headers = {"Authorization": f"Bearer {op_token}"}

    insp_id = str(uuid.uuid4())
    await db.inspections.insert_one({
        "_id": insp_id,
        "id": insp_id,
        "created_by": "op_concurrent",
        "status": "done",
    })

    reg_id = str(uuid.uuid4())
    await db.regions.insert_one({
        "_id": reg_id,
        "id": reg_id,
        "inspection_id": insp_id,
        "engine": "yolo",
        "bbox": [10.0, 10.0, 50.0, 50.0],
    })

    # Envoi de deux requêtes concurrentes via asyncio.gather
    req1 = async_client.post(
        f"/api/v1/regions/{reg_id}/feedback",
        headers=headers,
        json={"decision": "uncertain", "comment": "Doute 1"},
    )
    req2 = async_client.post(
        f"/api/v1/regions/{reg_id}/feedback",
        headers=headers,
        json={"decision": "confirmed", "comment": "Confirmation 2"},
    )

    res1, res2 = await asyncio.gather(req1, req2)
    assert res1.status_code == 201
    assert res2.status_code == 201

    seqs = {res1.json()["seq"], res2.json()["seq"]}
    assert seqs == {1, 2}, f"Les numéros de séquence doivent être 1 et 2, obtenu {seqs}"

    # Vérification de l'ordre dans l'historique : seq=2 en premier
    res_hist = await async_client.get(f"/api/v1/regions/{reg_id}/history", headers=headers)
    assert res_hist.status_code == 200
    history = res_hist.json()
    assert len(history) == 2
    assert history[0]["seq"] == 2
    assert history[1]["seq"] == 1



@pytest.mark.asyncio
async def test_region_thumbnail_isolation(setup_test_db, async_client, create_user_helper):
    """Vérifie l'accès à la vignette et l'isolation stricte multi-opérateur."""
    db = setup_test_db
    _, op1_token = await create_user_helper("operator_owner", UserRole.OPERATOR.value)
    _, op2_token = await create_user_helper("operator_other", UserRole.OPERATOR.value)

    insp_id = str(uuid.uuid4())
    img_dir = StorageService.get_inspection_dir(insp_id)
    img_dir.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (200, 200), color=(100, 150, 200))
    img_path = img_dir / "original.png"
    img.save(img_path)

    await db.inspections.insert_one({
        "_id": insp_id,
        "id": insp_id,
        "created_by": "operator_owner",
        "status": "done",
        "engines": {},
    })

    reg_id = str(uuid.uuid4())
    await db.regions.insert_one({
        "_id": reg_id,
        "id": reg_id,
        "inspection_id": insp_id,
        "engine": "yolo",
        "bbox": [20.0, 20.0, 60.0, 60.0],
    })

    headers_op1 = {"Authorization": f"Bearer {op1_token}"}
    headers_op2 = {"Authorization": f"Bearer {op2_token}"}

    # Opérateur propriétaire -> 200 image/png
    res1 = await async_client.get(f"/api/v1/regions/{reg_id}/thumbnail", headers=headers_op1)
    assert res1.status_code == 200
    assert res1.headers["content-type"] == "image/png"
    thumb = Image.open(io.BytesIO(res1.content))
    assert thumb.size == (60, 60)

    # Opérateur tiers -> 404 INSPECTION_NOT_FOUND
    res2 = await async_client.get(f"/api/v1/regions/{reg_id}/thumbnail", headers=headers_op2)
    assert res2.status_code == 404
    assert res2.json()["error"]["code"] == "INSPECTION_NOT_FOUND"


@pytest.mark.asyncio
async def test_ac03_overlay_exact_reproducibility(setup_test_db, async_client, create_user_helper):
    """Critère AC-03 : l'overlay servi par l'API est strictement identique à celui régénéré depuis les régions."""
    db = setup_test_db
    _, token = await create_user_helper("op_ac03", UserRole.OPERATOR.value)
    headers = {"Authorization": f"Bearer {token}"}

    insp_id = str(uuid.uuid4())
    insp_dir = StorageService.get_inspection_dir(insp_id)
    insp_dir.mkdir(parents=True, exist_ok=True)

    base_img = Image.new("RGB", (300, 300), color=(50, 50, 50))
    base_img.save(insp_dir / "original.png")

    regions = [
        {
            "_id": str(uuid.uuid4()),
            "id": "reg-ac03-1",
            "inspection_id": insp_id,
            "engine": "yolo",
            "bbox": [30.0, 30.0, 70.0, 70.0],
            "area": 4900.0,
            "label": "Défaut proposé : hole",
            "classification": "hole",
            "score": 0.92,
        },
        {
            "_id": str(uuid.uuid4()),
            "id": "reg-ac03-2",
            "inspection_id": insp_id,
            "engine": "patchcore",
            "bbox": [120.0, 120.0, 50.0, 50.0],
            "area": 2500.0,
            "label": "Anomalie suspectée — score de distance",
            "classification": None,
            "score": 2.15,
            "tau": 1.25,
        },
    ]

    await db.inspections.insert_one({
        "_id": insp_id,
        "id": insp_id,
        "created_by": "op_ac03",
        "status": "done",
        "engines": {"yolo": {"status": "ok"}, "patchcore": {"status": "ok"}},
        "regions_count": len(regions),
    })
    await db.regions.insert_many(regions)

    # Générer et stocker l'overlay officiel via le VisualizerService
    official_overlay_img = VisualizerService.generate_overlay(base_img, regions)
    StorageService.save_overlay_png(insp_id, official_overlay_img)

    # 1. Appel HTTP à l'API pour récupérer les régions
    res_regions = await async_client.get(f"/api/v1/inspections/{insp_id}/regions", headers=headers)
    assert res_regions.status_code == 200
    api_regions = res_regions.json()["items"]
    assert len(api_regions) == 2

    # 2. Appel HTTP à l'API pour récupérer l'overlay
    res_overlay = await async_client.get(f"/api/v1/inspections/{insp_id}/overlay?format=png", headers=headers)
    assert res_overlay.status_code == 200
    api_overlay_bytes = res_overlay.content

    # 3. Régénération indépendante côté client avec le même code VisualizerService
    reproduced_overlay_img = VisualizerService.generate_overlay(base_img, api_regions)
    buf = io.BytesIO()
    reproduced_overlay_img.save(buf, format="PNG")
    reproduced_overlay_bytes = buf.getvalue()

    # Comparaison bit-à-bit / pixel-à-pixel
    assert api_overlay_bytes == reproduced_overlay_bytes


@pytest.mark.asyncio
async def test_audit_log_and_feedback_export(setup_test_db, async_client, create_user_helper):
    """Vérifie l'audit de consultation ('audit_view') et l'export ML."""
    db = setup_test_db
    _, admin_token = await create_user_helper("admin_audit", UserRole.ADMIN.value)
    _, auditor_token = await create_user_helper("auditor_user", UserRole.AUDITOR.value)
    _, ml_token = await create_user_helper("ml_user", UserRole.ML_ENGINEER.value)
    _, op_token = await create_user_helper("op_user", UserRole.OPERATOR.value)

    # 1. Consultation d'audit par un opérateur -> 403
    res_op = await async_client.get("/api/v1/audit", headers={"Authorization": f"Bearer {op_token}"})
    assert res_op.status_code == 403

    # 2. Consultation d'audit par l'auditeur -> 200 et consigne 'audit_view'
    res_auditor = await async_client.get("/api/v1/audit", headers={"Authorization": f"Bearer {auditor_token}"})
    assert res_auditor.status_code == 200

    # Vérification que 'audit_view' a été consigné
    logged_view = await db.audit_log.find_one({"action": "audit_view", "username": "auditor_user"})
    assert logged_view is not None

    # 3. Export feedback par ML engineer -> 200 et consigne 'feedback_export'
    res_export = await async_client.get("/api/v1/feedback/export", headers={"Authorization": f"Bearer {ml_token}"})
    assert res_export.status_code == 200
    logged_export = await db.audit_log.find_one({"action": "feedback_export", "username": "ml_user"})
    assert logged_export is not None
