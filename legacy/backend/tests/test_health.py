from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app


@pytest.fixture
def mock_db():
    """Mock DB session that returns a fake Postgres version string."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one.return_value = "PostgreSQL 16.0 on x86_64"
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.mark.asyncio
async def test_health_ok(mock_db):
    with patch("app.routers.meta.get_db", return_value=mock_db):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == "2.0.0"


@pytest.mark.asyncio
async def test_about_has_sources():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/about")
    assert resp.status_code == 200
    body = resp.json()
    source_names = [s["name"] for s in body["sources"]]
    assert "MPA OceansX" in source_names
    assert "OpenSanctions" in source_names


def test_clamp_future():
    from datetime import datetime, timedelta, timezone
    from app.utils.timezone import clamp_future

    now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)
    future = now + timedelta(hours=2)
    clamped, was_clamped = clamp_future(future, now=now)
    assert was_clamped
    assert clamped == now

    past = now - timedelta(hours=1)
    same, was_clamped = clamp_future(past, now=now)
    assert not was_clamped
    assert same == past


def test_imo_luhn():
    from app.utils.imo import luhn_valid
    assert luhn_valid("9074729")  # known valid IMO
    assert not luhn_valid("1234567")
    assert not luhn_valid("abc1234")
