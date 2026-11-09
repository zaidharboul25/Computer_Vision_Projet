"""Service de génération et de validation des exports d'inspection (Phase 3).

Garantit :
- Le respect strict du schéma JSON versionné export_schema_v1.json (AC-04).
- La séparation étanche entre prédictions ML et revues humaines (AC-07, §6.5).
- L'audit anti-fuite de secrets et de chemins locaux (aucun chemin système C:\\, /home, aucun secret JWT/.env).
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import fastjsonschema
from app.core.config import settings
from app.core.errors import AppException
from app.engines.integrity import IntegrityVerifier


def format_iso_utc(dt_val: Any) -> Optional[str]:
    """Convertit une date ou chaîne en date-time ISO 8601 UTC strict (RFC 3339)."""
    if dt_val is None:
        return None
    if isinstance(dt_val, str):
        if not (dt_val.endswith("Z") or "+" in dt_val or "-" in dt_val[10:]):
            return dt_val + "Z"
        return dt_val
    if hasattr(dt_val, "tzinfo"):
        if dt_val.tzinfo is None:
            dt_val = dt_val.replace(tzinfo=timezone.utc)
        return dt_val.isoformat()
    return str(dt_val)


SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "export_schema_v1.json"
with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    _raw_schema = json.load(f)

# Compilateur rapide de schéma JSON
_validate_export = fastjsonschema.compile(_raw_schema)

# Motifs interdits dans les exports publics (anti-fuite)
LEAK_PATTERNS = [
    re.compile(r"[A-Za-z]:[\\/]", re.IGNORECASE),          # Chemins Windows absolus (ex: C:\, D:/)
    re.compile(r"/(?:home|Users|etc|var|root)/", re.IGNORECASE),  # Chemins Unix sensibles
    re.compile(r"\.env", re.IGNORECASE),                   # Référence au fichier de secrets
    re.compile(r"JWT_SECRET|argon2|bearer\s+[A-Za-z0-9\-_]{20,}", re.IGNORECASE),  # Secrets / tokens
]


def check_no_leaks_or_secrets(payload: Any) -> None:
    """Parcourt récursivement le dictionnaire d'export et vérifie l'absence absolue de chemins et de secrets."""
    serialized = json.dumps(payload, ensure_ascii=False)
    for pattern in LEAK_PATTERNS:
        match = pattern.search(serialized)
        if match:
            raise AppException(
                code="EXPORT_ERROR",
                message=f"Fuite d'information sensible détectée dans l'export : motif '{match.group(0)}' interdit",
                status_code=500,
            )


class ExportService:
    @staticmethod
    def build_export_payload(
        inspection: Dict[str, Any],
        regions: List[Dict[str, Any]],
        human_reviews: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Construit le payload d'export normalisé conforme à export_schema_v1.json."""
        image_meta = inspection.get("image_meta", {})
        engines_dict = {}
        for eng_name, eng_info in inspection.get("engines", {}).items():
            engines_dict[eng_name] = {
                "status": eng_info.get("status", "pending"),
                "version": eng_info.get("version"),
                "error": eng_info.get("error"),
                "latency_ms": eng_info.get("latency_ms"),
            }

        # Nettoyage et formatage strict des régions
        formatted_regions = []
        for r in regions:
            formatted_regions.append({
                "id": str(r.get("id")),
                "display_id": r.get("display_id"),
                "engine": r.get("engine"),
                "bbox": [float(x) for x in r.get("bbox", [0, 0, 0, 0])],
                "area": float(r.get("area", 0.0)),
                "label": str(r.get("label")),
                "score": float(r["score"]) if r.get("score") is not None else None,
                "classification": r.get("classification"),
                "tau": float(r["tau"]) if r.get("tau") is not None else None,
                "corroboration": r.get("corroboration"),
            })

        # Nettoyage des revues humaines (séparées des prédictions)
        formatted_reviews = []
        for rev in human_reviews:
            formatted_reviews.append({
                "id": str(rev.get("id")),
                "region_id": str(rev.get("region_id")),
                "decision": rev.get("decision"),
                "rejection_reason": rev.get("rejection_reason"),
                "comment": rev.get("comment"),
                "reviewed_by": str(rev.get("reviewed_by")),
                "created_at": format_iso_utc(rev.get("created_at")),
            })

        # Empreintes SHA-256 pour traçabilité et reproductibilité
        raw_hashes = IntegrityVerifier.get_expected_hashes()
        reproducibility_hashes = {
            "yolo_best_pt": raw_hashes["yolo_best_pt"],
            "patchcore_memory_bank_pt": raw_hashes["patchcore_memory_bank_pt"],
        }
        for k, v in raw_hashes.get("similarity_artifacts", {}).items():
            reproducibility_hashes[f"similarity_{k}"] = v

        created_at_str = format_iso_utc(inspection.get("created_at"))
        completed_at_str = format_iso_utc(inspection.get("completed_at"))

        export_data = {
            "schema_version": "weaveguard.inspection/1.0",
            "inspection_id": str(inspection.get("id")),
            "created_at": created_at_str,
            "completed_at": completed_at_str,
            "created_by": str(inspection.get("created_by")),
            "status": inspection.get("status", "done"),
            "partial": bool(inspection.get("partial", False)),
            "image": {
                "filename": str(image_meta.get("filename", "image.png")),
                "format": str(image_meta.get("format", "PNG")),
                "width": int(image_meta.get("width", 0)),
                "height": int(image_meta.get("height", 0)),
                "stored_width": int(image_meta.get("stored_width", 0)),
                "stored_height": int(image_meta.get("stored_height", 0)),
                "resize_factor": float(image_meta.get("resize_factor", 1.0)),
                "scale_mode": str(image_meta.get("scale_mode", "native")),
                "warnings": list(image_meta.get("warnings", inspection.get("warnings", []))),
            },
            "domain_check": inspection.get("domain_check"),
            "engines": engines_dict,
            "predictions": {
                "regions_count": len(formatted_regions),
                "regions": formatted_regions,
                "heatmap_meta": inspection.get("heatmap_meta"),
            },
            "human_reviews": formatted_reviews,
            "reproducibility": {
                "models_sha256": reproducibility_hashes,
                "inference_device": settings.get_effective_device(),
            },
        }

        # 1. Validation de schéma JSON
        try:
            _validate_export(export_data)
        except Exception as e:
            raise AppException(
                code="EXPORT_ERROR",
                message=f"Le document d'export ne respecte pas le schéma contractuel : {str(e)}",
                status_code=500,
            )

        # 2. Vérification anti-fuite de données sensibles
        check_no_leaks_or_secrets(export_data)

        return export_data
