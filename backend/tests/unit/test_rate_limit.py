"""Tests unitaires du limiteur à fenêtre glissante."""
from app.core.rate_limit import SlidingWindowLimiter


def test_blocks_after_max_events_then_releases_after_window():
    now = [0.0]
    limiter = SlidingWindowLimiter(max_events=3, window_seconds=10, clock=lambda: now[0])

    for _ in range(3):
        assert limiter.retry_after("ip") == 0
        limiter.register("ip")

    assert limiter.retry_after("ip") > 0
    assert limiter.retry_after("autre-ip") == 0  # clés indépendantes

    now[0] = 10.5
    assert limiter.retry_after("ip") == 0


def test_reset_clears_state():
    limiter = SlidingWindowLimiter(max_events=1, window_seconds=60)
    limiter.register("ip")
    assert limiter.retry_after("ip") > 0
    limiter.reset("ip")
    assert limiter.retry_after("ip") == 0
    limiter.register("a")
    limiter.reset()
    assert limiter.retry_after("a") == 0


def test_memory_is_bounded(monkeypatch):
    import app.core.rate_limit as rl

    monkeypatch.setattr(rl, "_MAX_KEYS", 5)
    now = [0.0]
    limiter = SlidingWindowLimiter(max_events=10, window_seconds=1000, clock=lambda: now[0])
    for i in range(20):
        now[0] += 1
        limiter.register(f"ip{i}")
    assert len(limiter._events) <= 5
