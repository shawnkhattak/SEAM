from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app import metrics
from app.limiter import limiter
from app.observability import install_log_handler, record_inbound
from app.routers import about, admin, geospatial, history, journal, macro, meta, news, ports, risk, sanctions, search, sse, vessels
from app.scheduler import build_scheduler


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    install_log_handler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    _configure_logging(settings.log_level)
    scheduler = build_scheduler()
    scheduler.start()
    app.state.scheduler = scheduler
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="OceansX Visualizer API",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Admin-Token"],
    )

    @app.middleware("http")
    async def security_and_logging_mw(request: Request, call_next):
        start = time.monotonic()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            raise
        finally:
            path = request.url.path
            if path.startswith("/api/"):
                duration = (time.monotonic() - start) * 1000
                record_inbound(
                    method=request.method,
                    path=path,
                    status=status,
                    duration_ms=duration,
                    query=request.url.query or None,
                )
                if status >= 400:
                    metrics.record_endpoint_error(request.method, path, status)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    app.include_router(meta.router, prefix="/api")
    app.include_router(vessels.router, prefix="/api")
    app.include_router(history.router, prefix="/api")
    app.include_router(sse.router, prefix="/api")
    app.include_router(macro.router, prefix="/api")
    app.include_router(geospatial.router, prefix="/api")
    app.include_router(ports.router, prefix="/api")
    app.include_router(news.router, prefix="/api")
    app.include_router(sanctions.router, prefix="/api")
    app.include_router(risk.router, prefix="/api")
    app.include_router(search.router, prefix="/api")
    app.include_router(journal.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    app.include_router(about.router, prefix="/api")

    _seam_dir = Path(__file__).parent.parent.parent / "seam"
    if _seam_dir.exists():
        app.mount("/seam", StaticFiles(directory=str(_seam_dir), html=True), name="seam")

    return app


app = create_app()
