"""Schémas Pydantic pour la validation humaine et le retour opérateur (Phase 4).

Règles de validation strictes (§6.5, AC-07) :
- Décision : confirmed | rejected | uncertain
- Motif de rejet : obligatoire pour 'rejected', interdit pour 'confirmed', facultatif pour 'uncertain'.
  Doit appartenir à la liste configurable settings.REJECTION_REASONS.
- Commentaire : texte brut de 500 caractères maximum, jamais interprété.
"""
from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator
from app.core.config import settings


FeedbackDecision = Literal["confirmed", "rejected", "uncertain"]


class FeedbackCreateRequest(BaseModel):
    decision: FeedbackDecision = Field(..., description="Décision de revue humaine (confirmed, rejected, uncertain)")
    rejection_reason: Optional[str] = Field(None, description="Motif de rejet standardisé parmi la liste configurable")
    comment: Optional[str] = Field(None, max_length=500, description="Commentaire optionnel texte brut (max 500 car.)")

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, v: str) -> str:
        if v not in ("confirmed", "rejected", "uncertain"):
            raise ValueError("Décision invalide. Valeurs autorisées : confirmed, rejected, uncertain")
        return v

    def validate_business_rules(self) -> None:
        """Valide les règles métier de motif de rejet."""
        allowed_reasons = settings.REJECTION_REASONS
        if self.decision == "rejected":
            if not self.rejection_reason:
                raise ValueError("Le motif de rejet ('rejection_reason') est obligatoire lorsque la décision est 'rejected'")
            if self.rejection_reason not in allowed_reasons:
                raise ValueError(
                    f"Motif de rejet '{self.rejection_reason}' invalide. Motifs autorisés : {allowed_reasons}"
                )
        elif self.decision == "confirmed":
            if self.rejection_reason is not None:
                raise ValueError("Le motif de rejet ('rejection_reason') est strictement interdit lorsque la décision est 'confirmed'")
        elif self.decision == "uncertain":
            if self.rejection_reason is not None and self.rejection_reason not in allowed_reasons:
                raise ValueError(
                    f"Motif de rejet '{self.rejection_reason}' invalide. Motifs autorisés : {allowed_reasons}"
                )


class FeedbackResponse(BaseModel):
    id: str = Field(..., description="Identifiant unique UUID de l'entrée de feedback")
    region_id: str = Field(..., description="Identifiant de la région évaluée")
    inspection_id: str = Field(..., description="Identifiant de l'inspection associée")
    seq: Optional[int] = Field(None, description="Numéro de séquence croissant pour garantie d'ordre déterministe")
    decision: FeedbackDecision = Field(..., description="Décision humaine enregistrée")
    rejection_reason: Optional[str] = Field(None, description="Motif de rejet le cas échéant")
    comment: Optional[str] = Field(None, description="Commentaire textuel brut")
    reviewed_by: str = Field(..., description="Identifiant de l'opérateur ayant validé la région")
    created_at: datetime = Field(..., description="Horodatage ISO 8601 de la décision")


class FeedbackExportItem(BaseModel):
    id: str
    region_id: str
    inspection_id: str
    decision: FeedbackDecision
    rejection_reason: Optional[str] = None
    comment: Optional[str] = None
    bbox: List[float]
    classification: Optional[str] = None
    reviewed_by: str
    created_at: datetime
    quality_checked: bool = Field(False, description="Contrôle qualité pour ré-annotation future")


class FeedbackExportResponse(BaseModel):
    items: List[FeedbackExportItem]
    total: int

