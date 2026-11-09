"""Journalisation JSON structurée pour WeaveGuard AI.

Formate tous les logs au format JSON avec timestamp UTC, niveau,
message, correlation_id et métadonnées contextuelles, sans données sensibles.
"""
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict
from app.core.correlation import get_correlation_id


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", None) or get_correlation_id(),
        }

        # Champs contextuels optionnels
        for field in ("route", "duration_ms", "engine", "error_code", "status_code", "user_id"):
            val = getattr(record, field, None)
            if val is not None:
                log_obj[field] = val

        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            log_obj["exception"] = record.exc_text

        return json.dumps(log_obj, ensure_ascii=False)


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Évite les doublons de handlers
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)
    root_logger.addHandler(handler)

    # Réduire le verbiage de bibliothèques tierces
    logging.getLogger("uvicorn.access").handlers = [handler]
    logging.getLogger("pymongo").setLevel(logging.WARNING)


logger = logging.getLogger("weaveguard")

