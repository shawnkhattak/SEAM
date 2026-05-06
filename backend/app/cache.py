from __future__ import annotations

import time
from threading import Lock
from typing import Any

_store: dict[str, tuple[Any, float]] = {}
_lock = Lock()


def get(key: str) -> Any | None:
    with _lock:
        entry = _store.get(key)
    if entry is None:
        return None
    value, expires_at = entry
    if time.monotonic() > expires_at:
        with _lock:
            _store.pop(key, None)
        return None
    return value


def set(key: str, value: Any, ttl_seconds: int) -> None:
    with _lock:
        _store[key] = (value, time.monotonic() + ttl_seconds)


def delete(key: str) -> None:
    with _lock:
        _store.pop(key, None)


def clear() -> int:
    with _lock:
        count = len(_store)
        _store.clear()
    return count


def sweep_expired() -> int:
    now = time.monotonic()
    with _lock:
        expired = [k for k, (_, exp) in _store.items() if now > exp]
        for k in expired:
            del _store[k]
    return len(expired)
