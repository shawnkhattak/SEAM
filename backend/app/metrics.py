from __future__ import annotations

from prometheus_client import Counter, Histogram

REQUEST_LATENCY = Histogram(
    "seam_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
)

REQUEST_ERRORS = Counter(
    "seam_request_errors_total",
    "HTTP request errors",
    ["method", "path", "status"],
)


def record_endpoint_error(method: str, path: str, status: int) -> None:
    REQUEST_ERRORS.labels(method=method, path=path, status=str(status)).inc()
