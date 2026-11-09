#!/usr/bin/env python
"""Benchmark de performance WeaveGuard AI.

Mesure les latences des moteurs, l'API end-to-end, le throughput
et les métriques de ressources (mémoire, taille image Docker, bundle frontend).

Usage :
    # Serveur doit être démarré avant l'API benchmark
    cd c:\\Users\\zaidh\\Desktop\\VPO
    backend\\.venv\\Scripts\\python.exe scripts\\benchmark.py
    backend\\.venv\\Scripts\\python.exe scripts\\benchmark.py --images 20 --warmup 2
    backend\\.venv\\Scripts\\python.exe scripts\\benchmark.py --no-api  # sans test API
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageOps

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))


def get_val_images(n: int = 20) -> List[Path]:
    """Retourne les n premières images val (tri lexicographique)."""
    val_dir = PROJECT_ROOT / "datasets" / "images" / "val"
    all_images: List[Path] = []
    for ext in ("*.webp", "*.jpg", "*.jpeg", "*.png"):
        all_images.extend(val_dir.glob(ext))
    return sorted(all_images)[:n]


def open_image(path: Path) -> Image.Image:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def measure_engine(engine_cls, engine_name: str, images: List[Path],
                   warmup: int = 2) -> Dict[str, Any]:
    """Mesure les latences d'un moteur sur un lot d'images (après warmup)."""
    import psutil
    import torch

    print(f"\n  Chargement {engine_name}...")
    engine = engine_cls()
    engine.load()

    # Warmup
    warmup_imgs = images[:warmup] if len(images) >= warmup else images
    for p in warmup_imgs:
        engine.infer(open_image(p))
    print(f"  {engine_name}: warmup ({warmup} images) terminé")

    # Mesures
    pre_times, mod_times, post_times, total_times = [], [], [], []
    process = psutil.Process()
    mem_before = process.memory_info().rss / 1024 / 1024  # MB

    for p in images:
        img = open_image(p)
        result = engine.infer(img)
        lat = result.latency
        pre_times.append(lat.preprocess_ms)
        mod_times.append(lat.model_ms)
        post_times.append(lat.postprocess_ms)
        total_times.append(lat.total_ms)

    mem_after = process.memory_info().rss / 1024 / 1024  # MB

    def stats(times: List[float]) -> Dict[str, float]:
        s = sorted(times)
        return {
            "min": round(min(s), 2),
            "median": round(statistics.median(s), 2),
            "p95": round(s[int(len(s) * 0.95)], 2),
            "max": round(max(s), 2),
        }

    return {
        "engine": engine_name,
        "n_images": len(images),
        "warmup": warmup,
        "preprocess_ms": stats(pre_times),
        "model_ms": stats(mod_times),
        "postprocess_ms": stats(post_times),
        "total_ms": stats(total_times),
        "peak_rss_mb": round(mem_after, 1),
        "rss_delta_mb": round(mem_after - mem_before, 1),
        "torch_num_threads": torch.get_num_threads(),
        "cpu_count": os.cpu_count(),
    }


def measure_api(base_url: str, username: str, password: str,
                image_path: Path, n_runs: int = 5) -> Dict[str, Any]:
    """Mesure la latence API end-to-end via httpx."""
    try:
        import httpx
    except ImportError:
        return {"error": "httpx non installé"}

    print(f"\n  Authentification API ({base_url})...")
    try:
        r = httpx.post(f"{base_url}/api/v1/auth/token",
                       data={"username": username, "password": password},
                       timeout=10)
        r.raise_for_status()
        token = r.json()["access_token"]
    except Exception as e:
        return {"error": f"Auth échouée: {e}"}

    headers = {"Authorization": f"Bearer {token}"}
    times = []

    print(f"  Benchmark API ({n_runs} runs)...")
    for i in range(n_runs):
        with open(image_path, "rb") as f:
            files = {"file": (image_path.name, f, "image/webp")}
            data = {"engines": "yolo,patchcore"}
            t0 = time.perf_counter()
            r = httpx.post(f"{base_url}/api/v1/inspections",
                           headers=headers, files=files, data=data, timeout=60)
            post_time = (time.perf_counter() - t0) * 1000

        if r.status_code not in (200, 201, 202):
            print(f"    Run {i+1}: HTTP {r.status_code}")
            continue

        # Polling jusqu'à done
        inspection_id = r.json().get("id")
        for _ in range(60):
            time.sleep(1)
            sr = httpx.get(f"{base_url}/api/v1/inspections/{inspection_id}",
                           headers=headers, timeout=10)
            if sr.json().get("status") in ("done", "error"):
                break

        total_time = (time.perf_counter() - t0) * 1000
        times.append(round(total_time, 1))
        print(f"    Run {i+1}: {total_time:.0f} ms")

    if not times:
        return {"error": "Aucun run réussi"}

    s = sorted(times)
    return {
        "n_runs": len(times),
        "total_ms": {
            "min": min(s),
            "median": round(statistics.median(s), 1),
            "p95": s[int(len(s) * 0.95)],
            "max": max(s),
        },
        "image_used": image_path.name,
    }


def measure_docker_image() -> Dict[str, Any]:
    """Mesure la taille de l'image Docker vpo-app."""
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", "vpo-app", "--format", "{{.Size}}"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            size_bytes = int(result.stdout.strip())
            return {
                "image": "vpo-app",
                "size_bytes": size_bytes,
                "size_mb": round(size_bytes / 1024 / 1024, 1),
                "size_gb": round(size_bytes / 1024 / 1024 / 1024, 2),
            }
        return {"error": result.stderr.strip()}
    except Exception as e:
        return {"error": str(e)}


def measure_frontend_bundle() -> Dict[str, Any]:
    """Mesure la taille du bundle frontend compilé."""
    dist_dir = PROJECT_ROOT / "frontend" / "dist" / "assets"
    if not dist_dir.exists():
        return {"error": "frontend/dist/assets absent — lancez npm run build"}

    js_files = list(dist_dir.glob("*.js"))
    css_files = list(dist_dir.glob("*.css"))

    total_js = sum(f.stat().st_size for f in js_files)
    total_css = sum(f.stat().st_size for f in css_files)

    return {
        "js_total_kb": round(total_js / 1024, 1),
        "css_total_kb": round(total_css / 1024, 1),
        "total_kb": round((total_js + total_css) / 1024, 1),
        "js_files": [{"name": f.name, "kb": round(f.stat().st_size / 1024, 1)} for f in js_files],
    }


def print_table(results: Dict[str, Any]) -> None:
    """Affiche un tableau récapitulatif."""
    print("\n" + "=" * 70)
    print("RÉSULTATS BENCHMARK WeaveGuard AI")
    print("=" * 70)

    for eng_name in ("yolo", "patchcore", "similarity"):
        eng = results.get("engines", {}).get(eng_name)
        if not eng or "error" in eng:
            continue
        print(f"\n{eng_name.upper()} ({eng['n_images']} images, {eng['warmup']} warmup)")
        print(f"  Prétraitement : median={eng['preprocess_ms']['median']} ms, p95={eng['preprocess_ms']['p95']} ms")
        print(f"  Modèle        : median={eng['model_ms']['median']} ms, p95={eng['model_ms']['p95']} ms")
        print(f"  Post-trt.     : median={eng['postprocess_ms']['median']} ms, p95={eng['postprocess_ms']['p95']} ms")
        print(f"  TOTAL         : median={eng['total_ms']['median']} ms, p95={eng['total_ms']['p95']} ms")
        print(f"  Peak RSS      : {eng['peak_rss_mb']} MB (+{eng['rss_delta_mb']} MB delta)")
        print(f"  Threads PyTorch: {eng['torch_num_threads']} / {eng['cpu_count']} CPUs")

    api = results.get("api")
    if api and "error" not in api:
        print(f"\nAPI END-TO-END ({api['n_runs']} runs)")
        t = api["total_ms"]
        print(f"  Total pipeline : median={t['median']} ms, p95={t['p95']} ms, max={t['max']} ms")

    docker = results.get("docker")
    if docker and "error" not in docker:
        print(f"\nDOCKER IMAGE vpo-app")
        print(f"  Taille : {docker['size_mb']} MB ({docker['size_gb']} GB)")

    frontend = results.get("frontend")
    if frontend and "error" not in frontend:
        print(f"\nFRONTEND BUNDLE")
        print(f"  JS total : {frontend['js_total_kb']} KB | CSS total : {frontend['css_total_kb']} KB")


def main():
    parser = argparse.ArgumentParser(description="Benchmark WeaveGuard AI")
    parser.add_argument("--images", type=int, default=20, help="Nombre d'images val (défaut: 20)")
    parser.add_argument("--warmup", type=int, default=2, help="Warmup passes (défaut: 2)")
    parser.add_argument("--no-api", action="store_true", help="Désactiver le benchmark API")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000", help="URL base du serveur")
    parser.add_argument("--api-user", default="admin", help="Utilisateur API")
    parser.add_argument("--api-password", default="AdminPassword123!", help="Mot de passe API")
    parser.add_argument("--output", default="docs/perf_baseline.json", help="Fichier JSON de sortie")
    parser.add_argument("--engines", default="yolo,patchcore,similarity",
                        help="Moteurs à benchmarker (virgule)")
    args = parser.parse_args()

    import torch
    print(f"Machine : {os.cpu_count()} CPU, PyTorch {torch.__version__}, {torch.get_num_threads()} threads")

    images = get_val_images(args.images)
    if not images:
        print("[ERREUR] Aucune image val trouvée")
        sys.exit(1)
    print(f"Images : {len(images)} (val set, tri lexicographique)")

    results: Dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "machine": {
            "cpu_count": os.cpu_count(),
            "torch_version": torch.__version__,
            "torch_num_threads": torch.get_num_threads(),
        },
        "engines": {},
        "api": {},
        "docker": {},
        "frontend": {},
    }

    engine_map = {
        "yolo": ("app.engines.yolo_engine", "YOLOEngine"),
        "patchcore": ("app.engines.patchcore_engine", "PatchCoreEngine"),
        "similarity": ("app.engines.similarity_engine", "SimilarityEngine"),
    }

    for eng_name in args.engines.split(","):
        eng_name = eng_name.strip()
        if eng_name not in engine_map:
            continue
        mod_name, cls_name = engine_map[eng_name]
        import importlib
        mod = importlib.import_module(mod_name)
        cls = getattr(mod, cls_name)
        try:
            results["engines"][eng_name] = measure_engine(
                cls, eng_name, images, warmup=args.warmup
            )
        except Exception as e:
            results["engines"][eng_name] = {"error": str(e)}
            print(f"  [ERREUR] {eng_name}: {e}")

    # API benchmark
    if not args.no_api and images:
        results["api"] = measure_api(
            args.api_url, args.api_user, args.api_password, images[0]
        )

    # Docker
    results["docker"] = measure_docker_image()

    # Frontend
    results["frontend"] = measure_frontend_bundle()

    # Affichage
    print_table(results)

    # Sauvegarde JSON
    output_path = PROJECT_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Résultats sauvegardés : {output_path}")
    print("     Générez le rapport Markdown avec les résultats pour docs/PERF_BASELINE.md")


if __name__ == "__main__":
    main()

