"""OceansX client — wraps the MPA OceansX REST API.

API key is read from app_config ('oceansx_api_key') via ConfigCache at request time,
never from Settings directly. Falls back to no key header if not configured.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from app import cache as l1_cache
from app.config import get_settings
from app.utils.http_allowlist import make_allowlisted_client
from app.utils.timezone import utc_now

log = logging.getLogger(__name__)

_MOCKS_DIR = Path(__file__).resolve().parent.parent / "mocks"


def _load_mock(name: str) -> Any:
    with (_MOCKS_DIR / name).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _drift_position(item: dict[str, Any]) -> dict[str, Any]:
    new = json.loads(json.dumps(item))
    new["latitudeDegrees"] = round(item["latitudeDegrees"] + random.uniform(-0.001, 0.001), 6)
    new["longitudeDegrees"] = round(item["longitudeDegrees"] + random.uniform(-0.001, 0.001), 6)
    new["timeStamp"] = utc_now().strftime("%Y-%m-%d %H:%M:%S")
    return new


# Module-level config_cache reference — set by main.py lifespan
_config_cache = None


def set_config_cache(cache) -> None:
    global _config_cache
    _config_cache = cache


class OceansXClient:
    """Async wrapper around the MPA OceansX API.

    API key is resolved from ConfigCache at request time (not cached in __init__)
    so that key rotations take effect within the 5-minute TTL window.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client: httpx.AsyncClient | None = None

    async def _api_key(self) -> str | None:
        if _config_cache is not None:
            key = _config_cache.get_plain_sync("oceansx_api_key")
            if key:
                return key
        return None

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            headers: dict[str, str] = {"Accept": "application/json"}
            api_key = await self._api_key()
            if api_key:
                headers["apikey"] = api_key
            self._client = make_allowlisted_client(
                base_url=self._settings.oceansx_base_url,
                headers=headers,
                timeout=httpx.Timeout(20.0, connect=10.0),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def _use_mocks(self) -> bool:
        return not bool(_config_cache and _config_cache.get_plain_sync("oceansx_api_key"))

    async def _get_json(
        self,
        path: str,
        params: dict | None = None,
        *,
        cache_key: str | None = None,
        ttl: int = 60,
    ) -> Any:
        if cache_key:
            cached = l1_cache.get(cache_key)
            if cached is not None:
                return cached

        client = await self._http()
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = await client.get(path, params=params)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"upstream {resp.status_code}", request=resp.request, response=resp
                    )
                resp.raise_for_status()
                data = resp.json()
                if cache_key:
                    l1_cache.set(cache_key, data, ttl)
                return data
            except (httpx.HTTPError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                wait = 0.5 * (2**attempt)
                log.warning("oceansx GET %s attempt=%d (%s) — retrying in %.1fs", path, attempt + 1, exc, wait)
                await asyncio.sleep(wait)
        raise last_exc  # type: ignore[misc]

    # ── Vessels ────────────────────────────────────────────────────────

    async def vessel_positions_snapshot(self) -> list[dict]:
        if self._use_mocks:
            return [_drift_position(v) for v in _load_mock("vessel_positions_snapshot.json")]
        return await self._get_json(
            "/api/v1/vessel/positions/snapshot",
            cache_key="oceansx:positions:snapshot",
            ttl=60,
        )

    async def vessel_particulars_by_imo(self, imo: str) -> dict | None:
        if self._use_mocks:
            items = _load_mock("vessel_particulars.json")
            rec = items[0] if items else None
            if rec:
                rec = dict(rec)
                rec["imoNumber"] = imo
            return rec
        data = await self._get_json(
            f"/api/v1/vessel/particulars/imonumber/{imo}",
            cache_key=f"oceansx:particulars:{imo}",
            ttl=6 * 3600,
        )
        if isinstance(data, list):
            return data[0] if data else None
        return data

    async def vessel_movements_by_imo(self, imo: str) -> list[dict]:
        if self._use_mocks:
            return _load_mock("vessel_movements.json")
        return await self._get_json(
            f"/api/v1/vessel/movements/imonumber/{imo}",
            cache_key=f"oceansx:movements:{imo}",
            ttl=300,
        )

    async def vessels_due_to_arrive(self, dt: datetime, hours: int = 6) -> list[dict]:
        if self._use_mocks:
            return _load_mock("vessels_due_to_arrive.json")
        date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        return await self._get_json(
            f"/api/v1/vessel/duetoarrive/date/{date_str}/hours/{hours}",
            cache_key=f"oceansx:duetoarrive:{date_str}:{hours}",
            ttl=600,
        )

    async def vessels_due_to_depart(self, dt: datetime, hours: int = 6) -> list[dict]:
        if self._use_mocks:
            return _load_mock("vessels_due_to_depart.json")
        date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        return await self._get_json(
            f"/api/v1/vessel/duetodepart/date/{date_str}/hours/{hours}",
            cache_key=f"oceansx:duetodepart:{date_str}:{hours}",
            ttl=600,
        )

    # ── Macro statistics ───────────────────────────────────────────────

    async def cargo_monthly_throughput(self, months: int = 12) -> list[dict]:
        if self._use_mocks:
            return _load_mock("cargo_monthly_throughput.json")
        return await self._get_json(f"/api/v1/macro/cargo/throughput/monthly/months/{months}", cache_key=f"oceansx:macro:cargo:{months}", ttl=3600)

    async def container_monthly_throughput(self, months: int = 12) -> list[dict]:
        if self._use_mocks:
            return _load_mock("container_monthly_throughput.json")
        return await self._get_json(f"/api/v1/macro/container/throughput/monthly/months/{months}", cache_key=f"oceansx:macro:container:{months}", ttl=3600)

    async def bunkers_monthly_sales(self, months: int = 12) -> list[dict]:
        if self._use_mocks:
            return _load_mock("bunkers_monthly_sales.json")
        return await self._get_json(f"/api/v1/macro/bunkers/sales/monthly/months/{months}", cache_key=f"oceansx:macro:bunkers:{months}", ttl=3600)

    async def shipping_monthly_tonnage(self, months: int = 12) -> list[dict]:
        if self._use_mocks:
            return _load_mock("shipping_monthly_tonnage.json")
        return await self._get_json(f"/api/v1/macro/shipping/tonnage/monthly/months/{months}", cache_key=f"oceansx:macro:tonnage:{months}", ttl=3600)

    async def monthly_vessel_call_volume(self, months: int = 12) -> list[dict]:
        if self._use_mocks:
            return _load_mock("monthly_vessel_call_volume.json")
        return await self._get_json(f"/api/v1/macro/vessel/calls/monthly/months/{months}", cache_key=f"oceansx:macro:calls:{months}", ttl=3600)

    # ── Geospatial layers ──────────────────────────────────────────────

    async def coastline_a(self) -> dict:
        if self._use_mocks: return _load_mock("coastline_a.json")
        return await self._get_json("/api/v1/geo/coastline/a", cache_key="oceansx:geo:coastline_a", ttl=86400)

    async def coastline_l(self) -> dict:
        if self._use_mocks: return _load_mock("coastline_l.json")
        return await self._get_json("/api/v1/geo/coastline/l", cache_key="oceansx:geo:coastline_l", ttl=86400)

    async def dangers_a(self) -> dict:
        if self._use_mocks: return _load_mock("dangers_a.json")
        return await self._get_json("/api/v1/geo/dangers/a", cache_key="oceansx:geo:dangers_a", ttl=86400)

    async def dangers_l(self) -> dict:
        if self._use_mocks: return _load_mock("dangers_l.json")
        return await self._get_json("/api/v1/geo/dangers/l", cache_key="oceansx:geo:dangers_l", ttl=86400)

    async def dangers_p(self) -> dict:
        if self._use_mocks: return _load_mock("dangers_p.json")
        return await self._get_json("/api/v1/geo/dangers/p", cache_key="oceansx:geo:dangers_p", ttl=86400)

    async def aids_to_navigation_p(self) -> dict:
        if self._use_mocks: return _load_mock("aids_to_navigation_p.json")
        return await self._get_json("/api/v1/geo/aton/p", cache_key="oceansx:geo:aton_p", ttl=86400)

    async def ports_and_services_a(self) -> dict:
        if self._use_mocks: return _load_mock("ports_and_services_a.json")
        return await self._get_json("/api/v1/geo/ports/a", cache_key="oceansx:geo:ports_a", ttl=86400)

    async def ports_and_services_l(self) -> dict:
        if self._use_mocks: return _load_mock("ports_and_services_l.json")
        return await self._get_json("/api/v1/geo/ports/l", cache_key="oceansx:geo:ports_l", ttl=86400)

    async def ports_and_services_p(self) -> dict:
        if self._use_mocks: return _load_mock("ports_and_services_p.json")
        return await self._get_json("/api/v1/geo/ports/p", cache_key="oceansx:geo:ports_p", ttl=86400)

    async def offshore_installations_a(self) -> dict:
        if self._use_mocks: return _load_mock("offshore_installations_a.json")
        return await self._get_json("/api/v1/geo/offshore/a", cache_key="oceansx:geo:offshore_a", ttl=86400)

    async def offshore_installations_l(self) -> dict:
        if self._use_mocks: return _load_mock("offshore_installations_l.json")
        return await self._get_json("/api/v1/geo/offshore/l", cache_key="oceansx:geo:offshore_l", ttl=86400)


_client_singleton: OceansXClient | None = None


def get_oceansx_client() -> OceansXClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = OceansXClient()
    return _client_singleton
