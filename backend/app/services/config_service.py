"""ConfigCache — 5-minute TTL wrapper around the app_config table.

All API clients read keys through this cache instead of Settings.
Secrets are Fernet-encrypted at rest; this service decrypts on read.
The cache is initialized once by main.py lifespan and shared via
auth.admin.set_config_cache() and the FastAPI app state.

Thread-safety: asyncio.Lock protects the cache dict to prevent stampedes.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select, update, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import AppConfig

log = logging.getLogger(__name__)

_TTL_SECONDS = 300  # 5 minutes


class ConfigCache:
    """In-memory TTL cache over the app_config table.

    Usage:
        cache = ConfigCache()
        value = await cache.get(session, "oceansx_api_key")
        await cache.set(session, "oceansx_api_key", "secret", is_secret=True)
    """

    def __init__(self) -> None:
        self._cache: dict[str, tuple[Any, float]] = {}  # key → (value, expires_at)
        self._lock = asyncio.Lock()
        self._fernet: Fernet | None = None
        self._init_fernet()

    def _init_fernet(self) -> None:
        key = get_settings().encryption_key
        if key:
            try:
                self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
            except Exception:
                log.warning("Invalid ENCRYPTION_KEY — secrets will not be decryptable")

    def _encrypt(self, value: str) -> str:
        if not self._fernet:
            raise RuntimeError("No encryption key configured; cannot store secrets")
        return self._fernet.encrypt(value.encode()).decode()

    def _decrypt(self, ciphertext: str) -> str | None:
        if not self._fernet:
            return None
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            log.error("Failed to decrypt config value — key may have changed")
            return None

    def _cache_get(self, key: str) -> tuple[bool, Any]:
        """Return (hit, value). Value is None for explicit NULL stored values."""
        entry = self._cache.get(key)
        if entry is None:
            return False, None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._cache[key]
            return False, None
        return True, value

    def _cache_set(self, key: str, value: Any) -> None:
        self._cache[key] = (value, time.monotonic() + _TTL_SECONDS)

    def invalidate(self, key: str) -> None:
        self._cache.pop(key, None)

    def invalidate_all(self) -> None:
        self._cache.clear()

    async def get(self, session: AsyncSession, key: str) -> str | None:
        """Return decrypted value for key, or None if not set."""
        async with self._lock:
            hit, value = self._cache_get(key)
            if hit:
                return value

        row = await session.scalar(select(AppConfig).where(AppConfig.key == key))
        if row is None:
            async with self._lock:
                self._cache_set(key, None)
            return None

        if row.is_secret and row.value_encrypted:
            value = self._decrypt(row.value_encrypted)
        else:
            value = row.value_plain

        async with self._lock:
            self._cache_set(key, value)
        return value

    async def get_plain(self, key: str) -> str | None:
        """Read non-secret value without a session (uses only cache)."""
        async with self._lock:
            hit, value = self._cache_get(key)
        return value if hit else None

    def get_plain_sync(self, key: str) -> str | None:
        """Synchronous cache-only read for use in non-async dependency injection."""
        hit, value = self._cache_get(key)
        return value if hit else None

    async def set(
        self,
        session: AsyncSession,
        key: str,
        value: str,
        *,
        is_secret: bool = False,
        description: str | None = None,
        actor: str = "admin",
    ) -> None:
        """Upsert a config key. Secrets are encrypted before storage."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)

        if is_secret:
            enc = self._encrypt(value)
            payload: dict = {
                "value_encrypted": enc,
                "value_plain": None,
                "is_secret": True,
                "updated_at": now,
                "updated_by": actor,
            }
        else:
            payload = {
                "value_plain": value,
                "value_encrypted": None,
                "is_secret": False,
                "updated_at": now,
                "updated_by": actor,
            }
        if description is not None:
            payload["description"] = description

        existing = await session.scalar(select(AppConfig).where(AppConfig.key == key))
        if existing:
            await session.execute(
                update(AppConfig).where(AppConfig.key == key).values(**payload)
            )
        else:
            payload["key"] = key
            if description is None:
                payload.setdefault("description", None)
            await session.execute(insert(AppConfig).values(**payload))

        await session.commit()

        async with self._lock:
            self._cache_set(key, value)

    async def delete(self, session: AsyncSession, key: str) -> None:
        from sqlalchemy import delete as sa_delete
        await session.execute(sa_delete(AppConfig).where(AppConfig.key == key))
        await session.commit()
        self.invalidate(key)

    async def list_keys(self, session: AsyncSession) -> list[dict]:
        """Return all keys with metadata but never raw secret values."""
        rows = (await session.execute(select(AppConfig))).scalars().all()
        return [
            {
                "key": r.key,
                "is_secret": r.is_secret,
                "description": r.description,
                "updated_at": r.updated_at,
                "updated_by": r.updated_by,
                "has_value": bool(r.value_encrypted or r.value_plain),
            }
            for r in rows
        ]

    async def warm(self, session: AsyncSession) -> None:
        """Pre-load all non-secret values into cache at startup."""
        rows = (await session.execute(
            select(AppConfig).where(AppConfig.is_secret == False)  # noqa: E712
        )).scalars().all()
        async with self._lock:
            for r in rows:
                self._cache_set(r.key, r.value_plain)
        log.info("ConfigCache warmed with %d non-secret keys", len(rows))
