"""Append-only audit log writer. Every admin action calls append_audit_log."""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog
from app.utils.timezone import utc_now


async def append_audit_log(
    session: AsyncSession,
    *,
    actor: str,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: dict[str, Any] | None = None,
    severity: str = "info",
) -> AuditLog:
    entry = AuditLog(
        occurred_at=utc_now(),
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
        severity=severity,
    )
    session.add(entry)
    await session.flush()
    return entry
