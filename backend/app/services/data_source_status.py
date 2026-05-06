"""Update data_source_status after each scheduler job runs."""
from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DataSourceStatus
from app.utils.timezone import utc_now


async def record_success(
    session: AsyncSession,
    source_name: str,
    *,
    payload: bytes | None = None,
) -> None:
    now = utc_now()
    sha1 = hashlib.sha1(payload).hexdigest() if payload else None

    result = await session.execute(
        select(DataSourceStatus).where(DataSourceStatus.source_name == source_name)
    )
    row = result.scalar_one_or_none()

    if row is None:
        row = DataSourceStatus(source_name=source_name)
        session.add(row)

    row.last_attempt_at = now
    row.last_success_at = now
    row.last_error = None
    row.consecutive_failures = 0
    if sha1:
        row.last_payload_sha1 = sha1


async def record_failure(
    session: AsyncSession,
    source_name: str,
    error: str,
) -> None:
    now = utc_now()

    result = await session.execute(
        select(DataSourceStatus).where(DataSourceStatus.source_name == source_name)
    )
    row = result.scalar_one_or_none()

    if row is None:
        row = DataSourceStatus(source_name=source_name, consecutive_failures=0)
        session.add(row)

    row.last_attempt_at = now
    row.last_error = error[:2000]
    row.consecutive_failures = (row.consecutive_failures or 0) + 1


async def get_all_statuses(session: AsyncSession) -> list[DataSourceStatus]:
    result = await session.execute(
        select(DataSourceStatus).order_by(DataSourceStatus.source_name)
    )
    return list(result.scalars().all())
