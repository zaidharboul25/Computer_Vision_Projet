"""Gestion de l'identifiant de corrélation (X-Correlation-ID).

Permet de suivre chaque requête de bout en bout à travers les logs,
les métadonnées d'erreur et les en-têtes HTTP de réponse.
"""
import uuid
from contextvars import ContextVar
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")

CORRELATION_HEADER = "X-Correlation-ID"


def get_correlation_id() -> str:
    """Retourne l'identifiant de corrélation courant, ou un nouvel UUID si vide."""
    cid = _correlation_id_ctx.get()
    if not cid:
        cid = str(uuid.uuid4())
        _correlation_id_ctx.set(cid)
    return cid


def set_correlation_id(correlation_id: str) -> None:
    _correlation_id_ctx.set(correlation_id)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        header_val = request.headers.get(CORRELATION_HEADER)
        cid = header_val.strip() if header_val else str(uuid.uuid4())
        _correlation_id_ctx.set(cid)

        response = await call_next(request)
        response.headers[CORRELATION_HEADER] = cid
        return response

