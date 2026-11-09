"""Schéma de réponse pour l'endpoint /health."""
from typing import Any, Dict
from pydantic import BaseModel


class GPUHealthInfo(BaseModel):
    available: bool
    device_name: str = "N/A"
    total_memory_mb: float = 0.0
    allocated_memory_mb: float = 0.0
    sm_61_supported: bool = False


class HealthResponse(BaseModel):
    status: str
    database: str
    device_active: str
    gpu: GPUHealthInfo
    engines: Dict[str, Any]
    timestamp: str

