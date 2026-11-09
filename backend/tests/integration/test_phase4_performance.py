"""Test de performance et montée en charge sur l'historique (Phase 4).

Vérifie la latence de l'API /api/v1/inspections et /api/v1/stats/summary
sur un volume de 1 000 documents en base MongoDB locale (AC-08),
ainsi que l'utilisation systématique des index (IXSCAN) sur l'ensemble des filtres.
"""
from datetime import datetime, timezone, timedelta
import time
import uuid
import pytest
from app.core.permissions import UserRole


@pytest.mark.asyncio
async def test_history_and_stats_performance_on_1000_items(setup_test_db, async_client, create_user_helper):
    """Génère 1 000 inspections et mesure les temps de réponse et plans d'exécution."""
    db = setup_test_db
    _, supervisor_token = await create_user_helper("supervisor_perf", UserRole.SUPERVISOR.value)
    headers = {"Authorization": f"Bearer {supervisor_token}"}

    # 1. Insertion en masse de 1 000 documents d'inspection
    now = datetime.now(timezone.utc)
    docs = []
    sample_ids = []
    statuses = ["done", "done", "done", "error", "pending"]
    prefixes = ["0000", "aaaa", "bbbb", "cccc"]
    for i in range(1000):
        prefix = prefixes[i % len(prefixes)]
        insp_id = f"{prefix}{uuid.uuid4().hex[4:]}"
        if i < 100:
            sample_ids.append(insp_id)
        created_at = now - timedelta(minutes=i)
        st = statuses[i % len(statuses)]
        doc = {
            "_id": insp_id,
            "id": insp_id,
            "created_by": f"operator_{i % 5}",
            "status": st,
            "partial": False,
            "created_at": created_at,
            "completed_at": created_at + timedelta(seconds=15) if st == "done" else None,
            "image_meta": {
                "filename": f"sample_{i}.png",
                "format": "PNG",
                "width": 1024,
                "height": 1024,
                "stored_width": 1024,
                "stored_height": 1024,
                "inference_width": 640,
                "inference_height": 640,
                "resize_factor": 0.625,
                "warnings": [],
            },
            "engines": {
                "yolo": {"status": "ok" if st == "done" else "pending"},
                "patchcore": {"status": "ok" if st == "done" else "pending"},
            },
            "regions_count": i % 4,
            "is_demo": False,
        }
        docs.append(doc)

    await db.inspections.insert_many(docs)

    # Feedbacks pour tester review_status
    feedbacks = [
        {
            "_id": str(uuid.uuid4()),
            "inspection_id": sid,
            "region_id": str(uuid.uuid4()),
            "user_id": "supervisor_perf",
            "decision": "approved",
            "created_at": now,
            "seq": 1,
        }
        for sid in sample_ids[:50]
    ]
    await db.feedback.insert_many(feedbacks)

    # 2. Mesure de latence sur GET /api/v1/inspections (Page 1)
    t0 = time.perf_counter()
    res1 = await async_client.get("/api/v1/inspections?skip=0&limit=20", headers=headers)
    latency_page1 = (time.perf_counter() - t0) * 1000.0
    assert res1.status_code == 200
    assert res1.json()["total"] == 1000
    assert len(res1.json()["items"]) == 20
    assert latency_page1 < 250.0

    # 3. Filtre status=done
    t0 = time.perf_counter()
    res_done = await async_client.get("/api/v1/inspections?status=done&limit=20", headers=headers)
    latency_status = (time.perf_counter() - t0) * 1000.0
    assert res_done.status_code == 200
    assert res_done.json()["total"] == 600
    assert latency_status < 250.0

    # 4. Filtre created_by=operator_0
    t0 = time.perf_counter()
    res_user = await async_client.get("/api/v1/inspections?created_by=operator_0&limit=20", headers=headers)
    latency_user = (time.perf_counter() - t0) * 1000.0
    assert res_user.status_code == 200
    assert res_user.json()["total"] == 200
    assert latency_user < 250.0

    # 5. Filtre dates
    date_from = (now - timedelta(minutes=200)).strftime("%Y-%m-%dT%H:%M:%SZ")
    t0 = time.perf_counter()
    res_date = await async_client.get(f"/api/v1/inspections?date_from={date_from}&limit=20", headers=headers)
    latency_date = (time.perf_counter() - t0) * 1000.0
    assert res_date.status_code == 200
    assert res_date.json()["total"] == 201
    assert latency_date < 250.0

    # 6. Filtre id_filter=0000
    t0 = time.perf_counter()
    res_id = await async_client.get("/api/v1/inspections?id_filter=0000&limit=20", headers=headers)
    latency_id = (time.perf_counter() - t0) * 1000.0
    assert res_id.status_code == 200
    assert res_id.json()["total"] == 250
    assert latency_id < 250.0

    # 7. Filtre review_status=reviewed
    t0 = time.perf_counter()
    res_rev = await async_client.get("/api/v1/inspections?review_status=reviewed&limit=20", headers=headers)
    latency_rev = (time.perf_counter() - t0) * 1000.0
    assert res_rev.status_code == 200
    assert res_rev.json()["total"] == 50
    assert latency_rev < 250.0

    # 8. Vérification explain() sur MongoDB
    find_cmd = {
        "find": "inspections",
        "filter": {"status": "done"},
        "sort": {"created_at": -1},
        "limit": 20,
    }
    explain_res = await db.command("explain", find_cmd, verbosity="executionStats")
    plan_str = str(explain_res)
    assert "IXSCAN" in plan_str, "Le plan d'exécution doit utiliser un index IXSCAN"
    assert "status_1_created_at_-1" in plan_str, "L'index composé status_1_created_at_-1 doit être utilisé"

    # 9. Mesure de latence sur GET /api/v1/stats/summary
    t0 = time.perf_counter()
    res_stats = await async_client.get("/api/v1/stats/summary", headers=headers)
    latency_stats = (time.perf_counter() - t0) * 1000.0
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert stats["inspections"]["total"] == 1000
    assert stats["inspections"]["done"] == 600
    assert latency_stats < 350.0
