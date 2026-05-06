from __future__ import annotations

from fastapi import Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

_bearer = HTTPBearer(auto_error=False)

# Module-level config cache reference — set by main.py lifespan after DB is ready.
# Falls back to settings.admin_token if not initialized.
_config_cache = None


def set_config_cache(cache) -> None:
    global _config_cache
    _config_cache = cache


async def _get_admin_token() -> str:
    """Return admin token from app_config (preferred) or settings fallback."""
    if _config_cache is not None:
        try:
            token = await _config_cache.get_plain("admin_token")
            if token:
                return token
        except Exception:
            pass
    return get_settings().admin_token


def require_admin(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> str:
    settings = get_settings()
    provided = x_admin_token or (credentials.credentials if credentials else None)
    if not provided:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin token required")

    # Synchronous fallback: compare against settings token.
    # The async version (reading from app_config) is used in startup validation.
    # For request-time validation we use the cached settings value or the DB value
    # exposed via config_cache (populated at startup).
    expected = None
    if _config_cache is not None:
        expected = _config_cache.get_plain_sync("admin_token")
    if not expected:
        expected = settings.admin_token

    if not expected or provided != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")
    return provided
