from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Maximum tolerance for future-dated timestamps from external sources.
_FUTURE_TOLERANCE = timedelta(minutes=5)


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def clamp_future(ts: datetime, now: datetime | None = None, tolerance: timedelta = _FUTURE_TOLERANCE) -> tuple[datetime, bool]:
    """
    If ts is more than tolerance ahead of now, replace it with now.
    Returns (clamped_ts, was_clamped).
    Prevents future-dated news items from displaying as "in X hours".
    """
    if now is None:
        now = utc_now()
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if ts > now + tolerance:
        return now, True
    return ts, False


def ensure_utc(ts: datetime) -> datetime:
    """Attach UTC tzinfo to a naive datetime, or convert an aware datetime to UTC."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)
