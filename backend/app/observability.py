from __future__ import annotations

import logging
import time
from collections import deque
from threading import Lock

logger = logging.getLogger(__name__)

_log_buffer: deque[str] = deque(maxlen=200)
_lock = Lock()


class _BufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        line = self.format(record)
        with _lock:
            _log_buffer.append(line)


def install_log_handler() -> None:
    handler = _BufferHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.getLogger().addHandler(handler)


def get_recent_logs(n: int = 50) -> list[str]:
    with _lock:
        lines = list(_log_buffer)
    return lines[-n:]


def record_inbound(
    method: str,
    path: str,
    status: int,
    duration_ms: float,
    query: str | None = None,
) -> None:
    logger.info(
        "inbound method=%s path=%s status=%d duration_ms=%.1f query=%s",
        method, path, status, duration_ms, query or "",
    )
