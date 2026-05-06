"""Phase 7b tests: data_source_status writer, about router seed, DB explorer allowlist,
admin stats endpoints (unit — no DB), dependency audit log model."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# data_source_status writer (unit — no DB)
# ---------------------------------------------------------------------------

class TestDataSourceStatus:
    @pytest.mark.asyncio
    async def test_record_success_creates_row(self):
        from app.services.data_source_status import record_success

        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None))

        await record_success(session, "opensanctions")

        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        assert added.source_name == "opensanctions"
        assert added.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_record_success_resets_failures(self):
        from app.services.data_source_status import record_success
        from app.models import DataSourceStatus

        existing = DataSourceStatus(source_name="opensanctions", consecutive_failures=3)
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: existing))

        await record_success(session, "opensanctions")

        assert existing.consecutive_failures == 0
        assert existing.last_error is None
        assert existing.last_success_at is not None

    @pytest.mark.asyncio
    async def test_record_success_stores_sha1_of_payload(self):
        import hashlib
        from app.services.data_source_status import record_success

        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None))

        payload = b"hello world"
        await record_success(session, "oceansx", payload=payload)

        added = session.add.call_args[0][0]
        assert added.last_payload_sha1 == hashlib.sha1(payload).hexdigest()

    @pytest.mark.asyncio
    async def test_record_failure_increments_count(self):
        from app.services.data_source_status import record_failure
        from app.models import DataSourceStatus

        existing = DataSourceStatus(source_name="rss_app", consecutive_failures=2)
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: existing))

        await record_failure(session, "rss_app", "connection timeout")

        assert existing.consecutive_failures == 3
        assert "connection timeout" in existing.last_error

    @pytest.mark.asyncio
    async def test_record_failure_creates_row_if_missing(self):
        from app.services.data_source_status import record_failure

        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None))

        await record_failure(session, "open_meteo", "HTTP 503")

        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        assert added.source_name == "open_meteo"

    @pytest.mark.asyncio
    async def test_record_failure_truncates_long_error(self):
        from app.services.data_source_status import record_failure
        from app.models import DataSourceStatus

        existing = DataSourceStatus(source_name="x", consecutive_failures=0)
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: existing))

        long_error = "e" * 5000
        await record_failure(session, "x", long_error)

        assert len(existing.last_error) <= 2000


# ---------------------------------------------------------------------------
# about router seed logic (unit — no DB)
# ---------------------------------------------------------------------------

class TestAboutSeed:
    @pytest.mark.asyncio
    async def test_seed_attributions_inserts_expected_sources(self):
        from app.routers.about import seed_attributions, _SEED_ATTRIBUTIONS

        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None))

        count = await seed_attributions(session)

        assert count == len(_SEED_ATTRIBUTIONS)
        assert session.add.call_count == len(_SEED_ATTRIBUTIONS)

    @pytest.mark.asyncio
    async def test_seed_attributions_updates_existing(self):
        from app.routers.about import seed_attributions
        from app.models import DataSourceAttribution

        existing = DataSourceAttribution(
            source_name="opensanctions",
            display_text="old",
            attribution_required=False,
            non_commercial_only=False,
        )
        session = AsyncMock()
        calls = 0

        def make_result(item):
            nonlocal calls
            calls += 1
            if item["source_name"] == "opensanctions":
                return MagicMock(scalar_one_or_none=lambda: existing)
            return MagicMock(scalar_one_or_none=lambda: None)

        from app.routers.about import _SEED_ATTRIBUTIONS
        results = [make_result(item) for item in _SEED_ATTRIBUTIONS]
        session.execute = AsyncMock(side_effect=results)

        await seed_attributions(session)

        # The opensanctions row was updated
        assert existing.attribution_required is True


# ---------------------------------------------------------------------------
# DB explorer allowlist
# ---------------------------------------------------------------------------

class TestDBExplorerAllowlist:
    def test_vessel_in_allowlist(self):
        from app.routers.admin import _ALLOWED_TABLES
        assert "vessel" in _ALLOWED_TABLES

    def test_audit_log_in_allowlist(self):
        from app.routers.admin import _ALLOWED_TABLES
        assert "audit_log" in _ALLOWED_TABLES

    def test_all_9_tables_from_0009_in_allowlist(self):
        from app.routers.admin import _ALLOWED_TABLES
        for table in ("data_source_status", "outbound_request_log",
                      "dependency_audit_log", "data_source_attribution"):
            assert table in _ALLOWED_TABLES, f"{table!r} missing from allowlist"

    def test_page_size_is_50(self):
        from app.routers.admin import _PAGE_SIZE
        assert _PAGE_SIZE == 50


# ---------------------------------------------------------------------------
# Admin auth dependency
# ---------------------------------------------------------------------------

class TestAdminAuth:
    def test_accepts_x_admin_token_header_value(self):
        from app.auth.admin import require_admin

        with patch("app.auth.admin.get_settings", return_value=MagicMock(admin_token="secret")):
            assert require_admin(x_admin_token="secret", credentials=None) == "secret"

    def test_accepts_bearer_token_for_compatibility(self):
        from fastapi.security import HTTPAuthorizationCredentials
        from app.auth.admin import require_admin

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="secret")
        with patch("app.auth.admin.get_settings", return_value=MagicMock(admin_token="secret")):
            assert require_admin(x_admin_token=None, credentials=credentials) == "secret"

    def test_rejects_missing_or_wrong_admin_token(self):
        from fastapi import HTTPException
        from app.auth.admin import require_admin

        with patch("app.auth.admin.get_settings", return_value=MagicMock(admin_token="secret")):
            with pytest.raises(HTTPException) as exc:
                require_admin(x_admin_token="wrong", credentials=None)
        assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# ORM model smoke tests — Phase 7b tables
# ---------------------------------------------------------------------------

class TestPhase7bModels:
    def test_data_source_status_tablename(self):
        from app.models import DataSourceStatus
        assert DataSourceStatus.__tablename__ == "data_source_status"

    def test_outbound_request_log_tablename(self):
        from app.models import OutboundRequestLog
        assert OutboundRequestLog.__tablename__ == "outbound_request_log"

    def test_dependency_audit_log_tablename(self):
        from app.models import DependencyAuditLog
        assert DependencyAuditLog.__tablename__ == "dependency_audit_log"

    def test_data_source_attribution_tablename(self):
        from app.models import DataSourceAttribution
        assert DataSourceAttribution.__tablename__ == "data_source_attribution"

    def test_data_source_status_has_consecutive_failures(self):
        from app.models import DataSourceStatus
        cols = {c.key for c in DataSourceStatus.__table__.columns}
        assert "consecutive_failures" in cols
        assert "last_payload_sha1" in cols

    def test_outbound_request_log_has_indexes(self):
        from app.models import OutboundRequestLog
        index_names = {i.name for i in OutboundRequestLog.__table__.indexes}
        assert "ix_outbound_request_log_requested_at" in index_names
        assert "ix_outbound_request_log_source" in index_names

    def test_dependency_audit_log_has_jsonb_vulnerabilities(self):
        from app.models import DependencyAuditLog
        from sqlalchemy.dialects.postgresql import JSONB
        col = DependencyAuditLog.__table__.c["vulnerabilities"]
        assert isinstance(col.type, JSONB)

    def test_data_source_attribution_boolean_columns(self):
        from app.models import DataSourceAttribution
        from sqlalchemy import Boolean
        assert isinstance(DataSourceAttribution.__table__.c["attribution_required"].type, Boolean)
        assert isinstance(DataSourceAttribution.__table__.c["non_commercial_only"].type, Boolean)
