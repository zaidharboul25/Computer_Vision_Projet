"""Benchmark de performance et capture des plans d'exécution explain() (Phase 4).

Mesure la latence de GET /api/v1/inspections sur 1 000 inspections avec les filtres :
- Aucun filtre (baseline)
- status=done
- created_by=operator_0
- dates (date_from & date_to)
- review_status=reviewed
- id_filter=<prefix>

Vérifie l'utilisation des index via db.command('explain', ...).
"""
import asyncio
import json
import time
import uuid
from datetime import datetime, timezone, timedelta
import httpx
from app.core.config import settings
from app.db.mongo import mongo_manager, get_database
from app.db.indexes import ensure_indexes
from app.core.security import create_access_token
from app.core.permissions import UserRole
from app.main import app

async def run_benchmark():
    # Utiliser une base temporaire dédiée weaveguard_benchmark
    settings.DB_NAME = "weaveguard_benchmark"
    await mongo_manager.connect()
    db = get_database()
    await db.client.drop_database("weaveguard_benchmark")
    await ensure_indexes(db)

    print("Insertion de 1 000 inspections de test...")
    now = datetime.now(timezone.utc)
    docs = []
    statuses = ["done", "done", "done", "error", "pending"]
    prefixes = ["0000", "aaaa", "bbbb", "cccc"]
    
    admin_token = create_access_token(subject="supervisor_bench", role=UserRole.SUPERVISOR.value)
    headers = {"Authorization": f"Bearer {admin_token}"}

    sample_ids = []
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

    # Créer feedbacks pour review_status
    feedbacks = []
    for sid in sample_ids[:50]:
        feedbacks.append({
            "_id": str(uuid.uuid4()),
            "inspection_id": sid,
            "region_id": str(uuid.uuid4()),
            "user_id": "supervisor_bench",
            "decision": "approved",
            "created_at": now,
            "seq": 1,
        })
    await db.feedback.insert_many(feedbacks)

    print("Index et 1 000 documents insérés. Démarrage des mesures...")

    transport = httpx.ASGITransport(app=app)
    results = {}

    test_cases = [
        ("1. Sans filtre (baseline)", "/api/v1/inspections?skip=0&limit=20", {}),
        ("2. Filtre statut (status=done)", "/api/v1/inspections?status=done&limit=20", {"status": "done"}),
        ("3. Filtre utilisateur (created_by=operator_0)", "/api/v1/inspections?created_by=operator_0&limit=20", {"created_by": "operator_0"}),
        ("4. Filtre dates (200 dernières min)", f"/api/v1/inspections?date_from={(now - timedelta(minutes=200)).strftime('%Y-%m-%dT%H:%M:%SZ')}&limit=20", {"created_at": {"$gte": now - timedelta(minutes=200)}}),
        ("5. Filtre revue (review_status=reviewed)", "/api/v1/inspections?review_status=reviewed&limit=20", {"id": {"$in": sample_ids[:50]}}),
        ("6. Filtre préfixe ID (id_filter=0000)", "/api/v1/inspections?id_filter=0000&limit=20", {"id": {"$regex": "^0000", "$options": "i"}}),
    ]

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Préchauffage
        await client.get("/api/v1/inspections?limit=5", headers=headers)

        for label, url, mongo_filter in test_cases:
            latencies = []
            total_items = 0
            for _ in range(7):
                t0 = time.perf_counter()
                res = await client.get(url, headers=headers)
                t_elapsed = (time.perf_counter() - t0) * 1000.0
                assert res.status_code == 200, f"Erreur {res.status_code}: {res.text}"
                latencies.append(t_elapsed)
                total_items = res.json()["total"]

            # Tri des latencies pour médiane
            latencies.sort()
            median_lat = latencies[len(latencies) // 2]

            # Explain plan via MongoDB command
            find_cmd = {
                "find": "inspections",
                "filter": mongo_filter,
                "sort": {"created_at": -1},
                "limit": 20
            }
            explain_res = await db.command("explain", find_cmd, verbosity="executionStats")
            query_planner = explain_res.get("queryPlanner", {})
            winning_plan = query_planner.get("winningPlan", {})
            
            # Recherche de l'index dans les stages imbriqués
            def extract_index_and_stage(plan):
                stage = plan.get("stage")
                idx = plan.get("indexName")
                if idx:
                    return stage, idx
                if "inputStage" in plan:
                    sub_stage, sub_idx = extract_index_and_stage(plan["inputStage"])
                    return f"{stage} -> {sub_stage}", sub_idx
                if "inputStages" in plan:
                    stages = [extract_index_and_stage(s) for s in plan["inputStages"]]
                    return f"{stage} -> [{', '.join(s[0] for s in stages)}]", ", ".join(s[1] for s in stages if s[1])
                return stage, None

            stage_desc, index_name = extract_index_and_stage(winning_plan)
            exec_stats = explain_res.get("executionStats", {})
            exec_time_ms = exec_stats.get("executionTimeMillis", 0)
            docs_examined = exec_stats.get("totalDocsExamined", 0)
            keys_examined = exec_stats.get("totalKeysExamined", 0)
            n_returned = exec_stats.get("nReturned", 0)

            results[label] = {
                "median_lat_ms": round(median_lat, 2),
                "total_items": total_items,
                "stage": stage_desc,
                "index_name": index_name,
                "exec_time_ms": exec_time_ms,
                "docs_examined": docs_examined,
                "keys_examined": keys_examined,
                "n_returned": n_returned,
            }
            print(f"[{label}]\n  -> API Latence médiane: {median_lat:.2f} ms (Total: {total_items})\n  -> Plan: {stage_desc} | Index: {index_name}\n  -> Exec time: {exec_time_ms} ms | Clés: {keys_examined} | Docs examinés: {docs_examined} | Renvoyés: {n_returned}\n")

    # Nettoyage
    await db.client.drop_database("weaveguard_benchmark")
    await mongo_manager.close()
    
    with open("docs/benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("Résultats sauvegardés dans docs/benchmark_results.json")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
