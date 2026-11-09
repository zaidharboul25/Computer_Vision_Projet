"""Tests d'intégration des endpoints d'inspection et de la file d'attente (Phase 3).

Vérifie :
- Exigence A : Protection Bearer sur tous les fichiers (/image, /heatmap, /overlay, /export, /ref/.../thumbnail).
- Exigence B : Isolation stricte de visibilité entre 2 opérateurs : accès interdit renvoie 404 INSPECTION_NOT_FOUND (jamais 403).
- Exigence G : Nettoyage des orphelins au redémarrage et réponse 503 SERVER_BUSY si file saturée.
- Exigence H : Progression des moteurs (pending -> running -> ok / error).
- Exigence J : Immutabilité stricte des régions (aucune méthode d'écriture exposée).
"""
import io
import uuid
import pytest
from httpx import AsyncClient
from PIL import Image
from app.core.config import settings
from app.core.permissions import UserRole
from app.core.security import create_access_token
from app.db.repositories.inspections import InspectionRepository
from app.db.repositories.regions import RegionRepository
from app.db.repositories.users import UserRepository
from app.services.queue import inspection_worker


@pytest.fixture
async def setup_two_operators(setup_test_db):
    """Crée deux opérateurs distincts pour tester l'isolation de visibilité."""
    user_repo = UserRepository(setup_test_db)
    user1 = await user_repo.create(
        username="operator_alice",
        password="ValidPassword123!",
        role=UserRole.OPERATOR.value,
    )
    user2 = await user_repo.create(
        username="operator_bob",
        password="ValidPassword123!",
        role=UserRole.OPERATOR.value,
    )
    supervisor = await user_repo.create(
        username="supervisor_claire",
        password="ValidPassword123!",
        role=UserRole.SUPERVISOR.value,
    )

    token_alice = create_access_token(subject="operator_alice", role=UserRole.OPERATOR.value)
    token_bob = create_access_token(subject="operator_bob", role=UserRole.OPERATOR.value)
    token_claire = create_access_token(subject="supervisor_claire", role=UserRole.SUPERVISOR.value)

    return {
        "alice": {"token": token_alice, "headers": {"Authorization": f"Bearer {token_alice}"}},
        "bob": {"token": token_bob, "headers": {"Authorization": f"Bearer {token_bob}"}},
        "claire": {"token": token_claire, "headers": {"Authorization": f"Bearer {token_claire}"}},
    }


def make_test_image_bytes(width: int = 200, height: int = 200) -> bytes:
    buf = io.BytesIO()
    im = Image.new("RGB", (width, height), color=(100, 150, 200))
    im.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_protected_files_require_bearer_token(async_client: AsyncClient, setup_two_operators):
    """Exigence A : Les endpoints de fichiers exigent l'en-tête Authorization: Bearer."""
    fake_id = str(uuid.uuid4())

    # Requêtes sans en-tête Authorization
    endpoints = [
        f"/api/v1/inspections/{fake_id}/image",
        f"/api/v1/inspections/{fake_id}/heatmap",
        f"/api/v1/inspections/{fake_id}/overlay",
        f"/api/v1/inspections/{fake_id}/export",
        "/api/v1/similarity/ref/sample.jpg/thumbnail",
    ]

    for ep in endpoints:
        resp = await async_client.get(ep)
        assert resp.status_code == 401, f"L'endpoint {ep} devrait exiger une authentification Bearer"
        assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.asyncio
async def test_operator_visibility_returns_404_never_403(async_client: AsyncClient, setup_two_operators):
    """Exigence B : Un opérateur tentant d'accéder à l'inspection d'un autre reçoit 404 (jamais 403)."""
    alice = setup_two_operators["alice"]
    bob = setup_two_operators["bob"]
    claire = setup_two_operators["claire"]

    # 1. Alice soumet une inspection
    img_bytes = make_test_image_bytes()
    resp_upload = await async_client.post(
        "/api/v1/inspections",
        headers=alice["headers"],
        files={"file": ("alice_fabric.png", img_bytes, "image/png")},
    )
    assert resp_upload.status_code == 202
    inspection_id = resp_upload.json()["id"]

    # 2. Bob tente d'accéder aux détails de l'inspection d'Alice -> 404 INSPECTION_NOT_FOUND
    resp_bob_detail = await async_client.get(f"/api/v1/inspections/{inspection_id}", headers=bob["headers"])
    assert resp_bob_detail.status_code == 404
    assert resp_bob_detail.json()["error"]["code"] == "INSPECTION_NOT_FOUND"

    # 3. Bob tente d'accéder aux régions d'Alice -> 404 INSPECTION_NOT_FOUND
    resp_bob_regions = await async_client.get(f"/api/v1/inspections/{inspection_id}/regions", headers=bob["headers"])
    assert resp_bob_regions.status_code == 404
    assert resp_bob_regions.json()["error"]["code"] == "INSPECTION_NOT_FOUND"

    # 4. Bob tente de télécharger l'image d'Alice -> 404 INSPECTION_NOT_FOUND
    resp_bob_img = await async_client.get(f"/api/v1/inspections/{inspection_id}/image", headers=bob["headers"])
    assert resp_bob_img.status_code == 404

    # 5. Bob liste les inspections : l'inspection d'Alice ne figure pas dans sa liste
    resp_bob_list = await async_client.get("/api/v1/inspections", headers=bob["headers"])
    assert resp_bob_list.status_code == 200
    bob_items = resp_bob_list.json()["items"]
    assert not any(item["id"] == inspection_id for item in bob_items)

    # 6. Claire (Superviseur) a le droit d'y accéder -> 200 OK
    resp_claire = await async_client.get(f"/api/v1/inspections/{inspection_id}", headers=claire["headers"])
    assert resp_claire.status_code == 200
    assert resp_claire.json()["created_by"] == "operator_alice"


@pytest.mark.asyncio
async def test_startup_cleans_orphan_inspections(setup_test_db):
    """Exigence G : Au redémarrage, les inspections 'pending' ou 'running' passent en 'error'."""
    from app.schemas.inspection import ImageMeta

    meta = ImageMeta(
        filename="test.png",
        format="PNG",
        width=100,
        height=100,
        stored_width=100,
        stored_height=100,
        inference_width=100,
        inference_height=100,
        resize_factor=1.0,
    )

    # Création directe d'une inspection en cours ('running') et d'une en attente ('pending')
    id_running = str(uuid.uuid4())
    id_pending = str(uuid.uuid4())

    doc1 = await InspectionRepository.create_inspection(id_running, "user1", meta, ["yolo"])
    await InspectionRepository.update_status(id_running, "running")

    doc2 = await InspectionRepository.create_inspection(id_pending, "user2", meta, ["yolo"])

    # Exécution du nettoyage de redémarrage
    cleaned = await InspectionRepository.cleanup_orphan_inspections()
    assert cleaned == 2

    # Vérification des statuts et du message exact
    res1 = await InspectionRepository.get_by_id(id_running)
    assert res1["status"] == "error"
    assert res1["error_message"] == "interrompue par un redémarrage"

    res2 = await InspectionRepository.get_by_id(id_pending)
    assert res2["status"] == "error"
    assert res2["error_message"] == "interrompue par un redémarrage"


@pytest.mark.asyncio
async def test_queue_saturation_returns_503_server_busy(async_client: AsyncClient, setup_two_operators):
    """Exigence G : Si la file d'attente est saturée, l'API renvoie 503 SERVER_BUSY."""
    alice = setup_two_operators["alice"]
    img_bytes = make_test_image_bytes()

    # Remplissage artificiel de la file jusqu'à saturation
    inspection_worker.initialize()
    original_max = settings.MAX_QUEUE
    try:
        # Simulation d'une file saturée
        while not inspection_worker._queue.full():
            inspection_worker._queue.put_nowait(None)

        resp = await async_client.post(
            "/api/v1/inspections",
            headers=alice["headers"],
            files={"file": ("test.png", img_bytes, "image/png")},
        )
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "SERVER_BUSY"
    finally:
        # Vider la file pour restaurer l'état
        while not inspection_worker._queue.empty():
            try:
                inspection_worker._queue.get_nowait()
            except Exception:
                pass


@pytest.mark.asyncio
async def test_regions_immutability(setup_test_db):
    """Exigence J : Les régions créées sont immuables (aucune écriture ultérieure)."""
    region_id = str(uuid.uuid4())
    inspection_id = str(uuid.uuid4())

    reg = {
        "id": region_id,
        "inspection_id": inspection_id,
        "engine": "yolo",
        "bbox": [10.0, 20.0, 30.0, 40.0],
        "area": 1200.0,
        "label": "Défaut proposé : trou",
        "score": 0.88,
        "classification": "trou",
    }

    await RegionRepository.bulk_create_regions([reg])
    stored_regions = await RegionRepository.get_by_inspection_id(inspection_id)
    assert len(stored_regions) == 1
    assert stored_regions[0]["id"] == region_id

    # Vérification qu'aucune méthode update/delete n'est définie sur RegionRepository
    assert not hasattr(RegionRepository, "update_region")
    assert not hasattr(RegionRepository, "delete_region")
    assert not hasattr(RegionRepository, "update_bbox")


@pytest.mark.asyncio
async def test_engine_progress_exposed_during_processing(async_client: AsyncClient, setup_two_operators):
    """Exigence H : Le document d'inspection expose l'état de chaque moteur en temps réel."""
    alice = setup_two_operators["alice"]
    inspection_id = str(uuid.uuid4())
    from app.schemas.inspection import ImageMeta

    meta = ImageMeta(
        filename="live.png",
        format="PNG",
        width=200,
        height=200,
        stored_width=200,
        stored_height=200,
        inference_width=200,
        inference_height=200,
        resize_factor=1.0,
    )

    # 1. État initial : pending
    await InspectionRepository.create_inspection(inspection_id, "operator_alice", meta, ["yolo", "patchcore"])
    resp_init = await async_client.get(f"/api/v1/inspections/{inspection_id}", headers=alice["headers"])
    assert resp_init.status_code == 200
    engines_state = resp_init.json()["engines"]
    assert engines_state["yolo"]["status"] == "pending"
    assert engines_state["patchcore"]["status"] == "pending"

    # 2. En cours de traitement : YOLO running
    await InspectionRepository.update_engine_progress(inspection_id, "yolo", "running")
    resp_running = await async_client.get(f"/api/v1/inspections/{inspection_id}", headers=alice["headers"])
    assert resp_running.status_code == 200
    assert resp_running.json()["engines"]["yolo"]["status"] == "running"
    assert resp_running.json()["engines"]["patchcore"]["status"] == "pending"

    # 3. Fin de traitement YOLO : ok avec latence
    await InspectionRepository.update_engine_progress(
        inspection_id, "yolo", "ok", version="v8n_640", latency_ms={"preprocess": 0.0, "model": 90.0, "total": 90.0}
    )
    resp_done_yolo = await async_client.get(f"/api/v1/inspections/{inspection_id}", headers=alice["headers"])
    assert resp_done_yolo.status_code == 200
    yolo_data = resp_done_yolo.json()["engines"]["yolo"]
    assert yolo_data["status"] == "ok"
    assert yolo_data["version"] == "v8n_640"
    assert yolo_data["latency_ms"]["total"] == 90.0

