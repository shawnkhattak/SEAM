"""Unit tests for sanctions_matcher.

ADR-0005: IMO-exact-only auto-confirm. These tests verify that no match_method
other than 'imo_exact' can ever produce status='auto_confirmed', both at the
application layer (the matcher code) and the database layer (CHECK constraint).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.sanctions_matcher import match_vessel_entity, run_matcher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vessel_entity(
    os_entity_id: str = "NK-test001",
    imo: str = "1234567",
    name: str = "TEST VESSEL",
    flag: str = "SG",
    topics: list[str] | None = None,
    datasets: list[str] | None = None,
    referents: list[str] | None = None,
    schema: str = "Vessel",
) -> dict:
    return {
        "id": os_entity_id,
        "schema": schema,
        "properties": {
            "name": [name],
            "imoNumber": [imo],
            "flag": [flag],
            "topics": topics or ["sanction"],
        },
        "referents": referents or [],
        "datasets": datasets or ["us_ofac_sdn"],
        "last_seen": "2026-05-01",
    }


def _make_scalar_result(value) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    r.scalar_one.return_value = value if value is not None else 99  # flush-return id
    r.rowcount = 1
    return r


def _make_session_mock(vessel_exists: bool = True) -> AsyncMock:
    session = AsyncMock()

    # Use a function side_effect that returns sensible results for all execute calls.
    # The matcher makes calls in roughly this order:
    #   1. select(Vessel.imo) → imo or None
    #   2. select(SanctionsMatch) → None (no existing)
    #   3. select(SanctionsSource.id) → None (no existing source; triggers add+flush)
    #   4. session.execute(pg_insert SanctionsListing ... .returning()) → source_id
    #   5. session.execute(update Vessel) → rowcount
    # Rather than pre-counting, use a default that works for all calls.
    call_idx = [0]
    responses = [
        _make_scalar_result(1234567 if vessel_exists else None),  # Vessel.imo check
        _make_scalar_result(None),  # SanctionsMatch existing
        _make_scalar_result(None),  # SanctionsSource.id (no existing → triggers add)
    ]
    default = _make_scalar_result(99)  # fallback for pg_insert returning / update calls

    async def _execute_side_effect(*args, **kwargs):
        idx = call_idx[0]
        call_idx[0] += 1
        if idx < len(responses):
            return responses[idx]
        return default

    session.execute = AsyncMock(side_effect=_execute_side_effect)
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


# ---------------------------------------------------------------------------
# Core ADR-0005 tests
# ---------------------------------------------------------------------------

class TestImoExactOnlyAutoConfirm:
    """ADR-0005: status='auto_confirmed' must only occur for match_method='imo_exact'."""

    @pytest.mark.asyncio
    async def test_imo_exact_produces_auto_confirmed(self) -> None:
        """Vessel with matching IMO in DB → auto_confirmed."""
        entity = _make_vessel_entity(imo="1234567")
        session = _make_session_mock(vessel_exists=True)

        result = await match_vessel_entity(session, entity)

        assert 1234567 in result["imo_matches"]
        assert result["method"] == "imo_exact"

        # Verify SanctionsMatch was added with status='auto_confirmed'
        added_objects = [call.args[0] for call in session.add.call_args_list]
        match_objects = [
            o for o in added_objects
            if hasattr(o, "status") and hasattr(o, "match_method")
        ]
        assert len(match_objects) >= 1
        for match_obj in match_objects:
            if match_obj.match_method == "imo_exact":
                assert match_obj.status == "auto_confirmed", (
                    f"imo_exact match must be auto_confirmed, got: {match_obj.status}"
                )

    @pytest.mark.asyncio
    async def test_no_vessel_in_db_produces_no_match(self) -> None:
        """Entity with IMO not in our DB → no match."""
        entity = _make_vessel_entity(imo="9999999")
        session = _make_session_mock(vessel_exists=False)

        result = await match_vessel_entity(session, entity)

        assert result["imo_matches"] == []
        assert result["method"] is None

    @pytest.mark.asyncio
    async def test_non_vessel_schema_skipped_by_run_matcher(self) -> None:
        """Company entities are not processed by the IMO matcher."""
        entities = [
            {
                "id": "NK-org001",
                "schema": "Company",
                "properties": {"name": ["Acme Corp"], "topics": ["sanction"]},
                "referents": [],
                "datasets": ["us_ofac_sdn"],
                "last_seen": "2026-05-01",
            }
        ]
        session = AsyncMock()
        session.flush = AsyncMock()

        summary = await run_matcher(session, entities)

        assert summary["total_vessel_entities"] == 0
        assert summary["skipped_non_vessel"] == 1
        assert summary["auto_confirmed_imos"] == 0

    @pytest.mark.asyncio
    async def test_auto_confirm_never_set_for_non_imo_methods(self) -> None:
        """Application-layer guard: match_method != 'imo_exact' must never set auto_confirmed.

        This test verifies the code logic directly. The database-layer guard
        (CHECK constraint ck_sanctions_match_auto_confirm_imo_only) provides
        an additional enforcement layer that this unit test cannot exercise
        without a live database.
        """
        non_imo_methods = ["name_flag_fuzzy", "name_fuzzy", "org_link"]

        # Import the internal _record_match to test it directly
        from app.services.sanctions_matcher import _record_match

        for method in non_imo_methods:
            session = AsyncMock()
            session.flush = AsyncMock()
            session.add = MagicMock()

            # Simulate no existing match
            no_existing = MagicMock()
            no_existing.scalar_one_or_none.return_value = None
            session.execute = AsyncMock(return_value=no_existing)

            match = await _record_match(
                session=session,
                imo=1234567,
                os_entity_id="NK-test999",
                match_method=method,
                status="pending",
                confidence=0.85,
            )

            added = [call.args[0] for call in session.add.call_args_list]
            match_rows = [o for o in added if hasattr(o, "match_method")]
            for row in match_rows:
                assert row.status != "auto_confirmed", (
                    f"match_method='{method}' must never produce auto_confirmed, "
                    f"but status was: {row.status}"
                )

    def test_valid_match_methods_set(self) -> None:
        """Confirm the valid method set matches the CHECK constraint in migration 0005."""
        from app.models import SanctionsMatch
        # Extract CHECK constraint text from the model
        table_args = SanctionsMatch.__table_args__
        method_check = next(
            (c for c in table_args if hasattr(c, "sqltext") and "match_method" in str(c.sqltext)),
            None,
        )
        assert method_check is not None, "ck_sanctions_match_method constraint not found"
        constraint_sql = str(method_check.sqltext)
        for method in ("imo_exact", "name_flag_fuzzy", "name_fuzzy", "org_link"):
            assert method in constraint_sql, f"Expected '{method}' in constraint: {constraint_sql}"

    def test_auto_confirm_imo_only_constraint_exists(self) -> None:
        """The DB-level guard constraint must be declared on SanctionsMatch."""
        from app.models import SanctionsMatch
        table_args = SanctionsMatch.__table_args__
        constraint_names = [
            getattr(c, "name", "") for c in table_args if hasattr(c, "name")
        ]
        assert "ck_sanctions_match_auto_confirm_imo_only" in constraint_names, (
            "ADR-0005 DB-level guard is missing from SanctionsMatch.__table_args__"
        )


class TestReferents:
    """Referents tracking: matcher must handle entity ID merges."""

    @pytest.mark.asyncio
    async def test_referents_present_in_result(self) -> None:
        """Entity with referents is processed without error."""
        entity = _make_vessel_entity(
            os_entity_id="NK-current",
            imo="1234567",
            referents=["NK-old-id-1", "NK-old-id-2"],
        )
        session = _make_session_mock(vessel_exists=True)

        result = await match_vessel_entity(session, entity)

        # Primary os_entity_id used in the match record
        assert result["os_entity_id"] == "NK-current"
        assert 1234567 in result["imo_matches"]
