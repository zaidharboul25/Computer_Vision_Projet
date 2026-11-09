"""Endpoint de surveillance de santé (/health).

Vérifie l'état de MongoDB, le matériel GPU/CPU et l'intégrité globale,
sans exposer de secret ni de chemin local.
"""
from datetime import datetime, timezone
from fastapi import APIRouter
from app.core.config import settings
from app.db.mongo import mongo_manager
from app.schemas.health import GPUHealthInfo, HealthResponse

router = APIRouter(tags=["Santé système"])


def get_gpu_info() -> tuple[str, GPUHealthInfo]:
    """Inspecte la présence et l'état de CUDA de manière sûre."""
    try:
        import torch

        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            total_mb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 2)
            alloc_mb = torch.cuda.memory_allocated(0) / (1024 ** 2)
            archs = getattr(torch.cuda, "get_arch_list", lambda: [])()
            sm61 = any("6.1" in a or "sm_61" in a for a in archs)
            active_dev = "cuda" if settings.DEVICE in ("cuda", "auto") else "cpu"
            return active_dev, GPUHealthInfo(
                available=True,
                device_name=name,
                total_memory_mb=round(total_mb, 1),
                allocated_memory_mb=round(alloc_mb, 1),
                sm_61_supported=sm61,
            )
    except Exception:
        pass

    return "cpu", GPUHealthInfo(available=False)


@router.get("/health", response_model=HealthResponse)
async def health_check():
    # 1. Vérification MongoDB
    db_ok = await mongo_manager.ping()
    db_status = "connected" if db_ok else "down"

    # 2. Vérification GPU
    active_device, gpu_info = get_gpu_info()

    # 3. État global
    overall_status = "ok" if db_ok else "degraded"

    # 4. Moteurs configurés
    engines_status = {
        eng: {"configured": True, "status": "registered"}
        for eng in settings.ENGINES_ENABLED
    }

    return HealthResponse(
        status=overall_status,
        database=db_status,
        device_active=active_device,
        gpu=gpu_info,
        engines=engines_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

