from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app import metrics
from app.limiter import limiter
from app.observability import install_log_handler, record_inbound


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

    # Initialize ConfigCache and share with auth + clients
    from app.db import get_session_factory
    from app.services.config_service import ConfigCache
    from app.auth import admin as auth_admin
    from app.clients import oceansx as oceansx_client

    config_cache = ConfigCache()
    async with get_session_factory()() as session:
        await config_cache.warm(session)

    auth_admin.set_config_cache(config_cache)
    oceansx_client.set_config_cache(config_cache)
    app.state.config_cache = config_cache

    from app.scheduler import build_scheduler
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
        title="SEAM API",
        description="Singapore Entity Analytics for Maritime",
        version="1.0.0",
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
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _observe(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        record_inbound(request.method, request.url.path, response.status_code, duration)
        return response

    # Phase 1 routers
    from app.routers import vessels, sse, history, meta
    app.include_router(vessels.router, prefix="/api")
    app.include_router(sse.router, prefix="/api")
    app.include_router(history.router, prefix="/api")
    app.include_router(meta.router, prefix="/api")

    # Phase 2 routers
    from app.routers import geospatial, ports, macro
    app.include_router(geospatial.router, prefix="/api")
    app.include_router(ports.router, prefix="/api")
    app.include_router(macro.router, prefix="/api")

    # Phase 3 routers
    from app.routers import news
    app.include_router(news.router, prefix="/api")

    # Phase 4 routers
    from app.routers import sanctions, search
    app.include_router(sanctions.router, prefix="/api")
    app.include_router(search.router, prefix="/api")

    # Phase 5 routers
    from app.routers import risk
    app.include_router(risk.router, prefix="/api")

    # Phase 6 routers
    from app.routers import about, journal
    app.include_router(about.router, prefix="/api")
    app.include_router(journal.router, prefix="/api")

    # Phase 7 routers
    from app.routers import admin
    app.include_router(admin.router, prefix="/api")

    @app.get("/api/health", tags=["meta"])
    async def health():
        return {"status": "ok", "service": "seam-api"}

    return app


app = create_app()
