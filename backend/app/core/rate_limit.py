"""Limiteur de débit à fenêtre glissante, en mémoire (un seul processus uvicorn).

Utilisé pour freiner les tentatives de connexion échouées par adresse IP. Il complète le
verrouillage par compte (users.record_login_attempt) qui, lui, ne protège pas contre le
« password spraying » (1 essai sur chacun de nombreux comptes) ni contre les identifiants inconnus.

Limite connue : l'état n'est pas partagé entre plusieurs workers/instances. Pour un déploiement
multi-instances, remplacer par un compteur Redis ou MongoDB (index TTL).
"""
import time
from collections import deque
from typing import Deque, Dict, Optional

_MAX_KEYS = 10_000


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window_seconds: int, clock=time.monotonic):
        self.max_events = max_events
        self.window = window_seconds
        self._clock = clock
        self._events: Dict[str, Deque[float]] = {}

    def _purge(self, key: str, now: float) -> Optional[Deque[float]]:
        q = self._events.get(key)
        if q is None:
            return None
        while q and now - q[0] >= self.window:
            q.popleft()
        if not q:
            del self._events[key]
            return None
        return q

    def retry_after(self, key: str) -> int:
        """Secondes à attendre avant de pouvoir réessayer (0 si non bloqué)."""
        now = self._clock()
        q = self._purge(key, now)
        if q is None or len(q) < self.max_events:
            return 0
        return max(1, int(self.window - (now - q[0])) + 1)

    def register(self, key: str) -> None:
        """Enregistre un événement (échec de connexion) pour cette clé."""
        now = self._clock()
        if key not in self._events and len(self._events) >= _MAX_KEYS:
            # Protection mémoire : éliminer les clés expirées, puis la plus ancienne si besoin
            for k in list(self._events):
                self._purge(k, now)
            if len(self._events) >= _MAX_KEYS:
                oldest = min(self._events, key=lambda k: self._events[k][-1])
                del self._events[oldest]
        self._events.setdefault(key, deque()).append(now)

    def reset(self, key: Optional[str] = None) -> None:
        if key is None:
            self._events.clear()
        else:
            self._events.pop(key, None)
