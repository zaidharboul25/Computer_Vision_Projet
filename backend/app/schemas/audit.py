"""Schémas Pydantic pour la consultation des journaux d'audit (Phase 4)."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AuditLogItem(BaseModel):
    id: str = Field(..., alias="_id", description="Identifiant unique de l'événement")
    action: str = Field(..., description="Type d'action auditée")
    user_id: Optional[str] = Field(None, description="Identifiant de l'utilisateur ayant réalisé l'action")
    username: Optional[str] = Field(None, description="Nom de l'utilisateur")
    at: datetime = Field(..., description="Horodatage UTC")
    details: Dict[str, Any] = Field(default_factory=dict, description="Métadonnées assainies de l'événement")

    model_config = {"populate_by_name": True}


class AuditLogListResponse(BaseModel):
    items: List[AuditLogItem]
    total: int
    skip: int
    limit: int

