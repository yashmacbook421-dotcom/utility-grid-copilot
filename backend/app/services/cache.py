"""Tiny in-memory TTL cache, generic key/value.

Originally for /api/recommend: repeated identical (region, question, top_k)
requests are a real cost driver in a dashboard setting — someone reloading
the page, or several operators asking the same obvious question. Trades a
little staleness for a Claude call skipped entirely; the agentic endpoint is
left uncached so its tool-choice behavior stays visible on every call.

Also used by app.services.weather_ingest: the 30s-polled regional dashboard
calls forecasting.forecast() constantly, which would otherwise hit the
weather API on every tick for data that doesn't change that fast.
"""

import threading
import time
from typing import Any

_TTL_SECONDS = 300

_lock = threading.Lock()
_store: dict[str, tuple[float, Any]] = {}


def get(key: str) -> Any | None:
    with _lock:
        entry = _store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del _store[key]
            return None
        return value


def set(key: str, value: Any) -> None:
    with _lock:
        _store[key] = (time.monotonic() + _TTL_SECONDS, value)


def make_key(*parts: str) -> str:
    return "|".join(parts)
