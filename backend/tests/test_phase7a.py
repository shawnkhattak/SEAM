"""Phase 7a tests: audit_log writer, journal_indexer markdown parsing."""
from __future__ import annotations

import textwrap
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.services.journal_indexer import (
    _parse_adr_file,
    _parse_glossary_file,
    _parse_phase_file,
)


def _make_tmp_file(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


class TestParsePhaseFile:
    def test_extracts_phase_number_and_title(self, tmp_path):
        f = _make_tmp_file(tmp_path, "03-phase-1-live.md", """
            # Phase 1: Live Tracking

            **Status:** Complete

            ## What Was Built

            Live vessel positions, the MPA client, and 15-minute polling.

            More detail here.

            ## Design Decisions

            Some decisions.
        """)
        result = _parse_phase_file(f)
        assert result is not None
        assert result["phase_number"] == 1
        assert result["title"] == "Live Tracking"

    def test_complete_status_detected(self, tmp_path):
        f = _make_tmp_file(tmp_path, "03-phase-1.md", """
            # Phase 1: Live Tracking
            **Status:** Complete
            ## What Was Built
            Some content.
        """)
        result = _parse_phase_file(f)
        assert result["completed"] is True

    def test_upcoming_status_not_complete(self, tmp_path):
        f = _make_tmp_file(tmp_path, "09-phase-7.md", """
            # Phase 7: Hardening
            **Status:** Upcoming
            ## What Was Built
            Not yet built.
        """)
        result = _parse_phase_file(f)
        assert result["completed"] is False

    def test_summary_from_what_was_built(self, tmp_path):
        f = _make_tmp_file(tmp_path, "03-phase-1.md", """
            # Phase 1: Live Tracking
            **Status:** Complete
            ## What Was Built
            This is the summary paragraph.
            ## Design Decisions
            Other section.
        """)
        result = _parse_phase_file(f)
        assert result["summary_md"] is not None
        assert "summary paragraph" in result["summary_md"]

    def test_returns_none_for_non_phase_file(self, tmp_path):
        f = _make_tmp_file(tmp_path, "README.md", """
            # Project Journey
            Some intro text with no Phase heading.
        """)
        result = _parse_phase_file(f)
        assert result is None

    def test_phase_number_with_letter_suffix(self, tmp_path):
        f = _make_tmp_file(tmp_path, "06b-phase-4b.md", """
            # Phase 4b: Sanctions UI
            **Status:** Complete
        """)
        result = _parse_phase_file(f)
        assert result is not None
        assert result["phase_number"] == 4


class TestParseAdrFile:
    def test_extracts_adr_number_and_title(self, tmp_path):
        f = _make_tmp_file(tmp_path, "0001-postgres-over-sqlite.md", """
            # ADR 0001: Postgres Over SQLite

            **Status:** Accepted
            **Decided:** 2026-04-30
            **Deciders:** Solo

            ---

            ## Context

            SEAM V1 used SQLite. V2 needs concurrent writers.
        """)
        result = _parse_adr_file(f)
        assert result is not None
        assert result["adr_number"] == 1
        assert result["title"] == "Postgres Over SQLite"

    def test_extracts_status(self, tmp_path):
        f = _make_tmp_file(tmp_path, "0001.md", """
            # ADR 0001: Some Decision
            **Status:** Superseded
            **Decided:** 2026-04-30
        """)
        result = _parse_adr_file(f)
        assert result["status"] == "superseded"

    def test_extracts_decided_at(self, tmp_path):
        f = _make_tmp_file(tmp_path, "0001.md", """
            # ADR 0001: Some Decision
            **Status:** Accepted
            **Decided:** 2026-04-30
        """)
        result = _parse_adr_file(f)
        assert result["decided_at"] == datetime(2026, 4, 30, tzinfo=timezone.utc)

    def test_extracts_context_summary(self, tmp_path):
        f = _make_tmp_file(tmp_path, "0001.md", """
            # ADR 0001: Some Decision
            **Status:** Accepted
            **Decided:** 2026-04-30

            ## Context

            This is the context paragraph explaining why we made this decision.

            ## Decision

            We chose Postgres.
        """)
        result = _parse_adr_file(f)
        assert result["summary_md"] is not None
        assert "context paragraph" in result["summary_md"]

    def test_returns_none_for_file_without_adr_heading(self, tmp_path):
        f = _make_tmp_file(tmp_path, "README.md", """
            # Architecture Decision Records
            No ADR heading here.
        """)
        result = _parse_adr_file(f)
        assert result is None

    def test_leading_zeros_in_adr_number(self, tmp_path):
        f = _make_tmp_file(tmp_path, "0025.md", """
            # ADR 0025: Shadow Fleet Prominent Treatment
            **Status:** Accepted
            **Decided:** 2026-04-30
        """)
        result = _parse_adr_file(f)
        assert result["adr_number"] == 25


class TestParseGlossaryFile:
    def test_extracts_terms(self, tmp_path):
        f = _make_tmp_file(tmp_path, "glossary.md", """
            # Glossary

            ## IMO Number

            **Category:** Maritime

            A permanent seven-digit identifier assigned to a ship.

            **Why it matters in this project.** IMO numbers are the gold standard.

            **Related terms:** Sanctions Match

            ---

            ## Shadow Fleet

            **Category:** Compliance

            Older tankers used to move sanctioned cargo.

            **Why it matters in this project.** Singapore sees many of these vessels.
        """)
        terms = _parse_glossary_file(f)
        names = [t["term"] for t in terms]
        assert "IMO Number" in names
        assert "Shadow Fleet" in names

    def test_extracts_category(self, tmp_path):
        f = _make_tmp_file(tmp_path, "glossary.md", """
            # Glossary

            ## IMO Number

            **Category:** Maritime

            A permanent identifier.
        """)
        terms = _parse_glossary_file(f)
        imo = next(t for t in terms if t["term"] == "IMO Number")
        assert imo["category"] == "Maritime"

    def test_extracts_plain_definition(self, tmp_path):
        f = _make_tmp_file(tmp_path, "glossary.md", """
            # Glossary

            ## IMO Number

            **Category:** Maritime

            A permanent seven-digit identifier assigned to a ship.

            **Why it matters in this project.** It matters a lot.
        """)
        terms = _parse_glossary_file(f)
        imo = next(t for t in terms if t["term"] == "IMO Number")
        assert imo["plain_definition"] is not None
        assert "seven-digit" in imo["plain_definition"]

    def test_extracts_why_it_matters(self, tmp_path):
        f = _make_tmp_file(tmp_path, "glossary.md", """
            # Glossary

            ## Shadow Fleet

            **Category:** Compliance

            Older tankers used to evade sanctions.

            **Why it matters in this project.** Singapore waters see many of these.
        """)
        terms = _parse_glossary_file(f)
        sf = next(t for t in terms if t["term"] == "Shadow Fleet")
        assert sf["why_it_matters_in_project"] is not None
        assert "Singapore" in sf["why_it_matters_in_project"]

    def test_skips_h1_and_intro_section(self, tmp_path):
        f = _make_tmp_file(tmp_path, "glossary.md", """
            # SEAM Glossary

            Intro paragraph that is not a term.

            ---

            ## First Term

            **Category:** Technical

            The definition of the first term.
        """)
        terms = _parse_glossary_file(f)
        assert all(t["term"] != "SEAM Glossary" for t in terms)
        assert any(t["term"] == "First Term" for t in terms)

    def test_empty_file_returns_empty_list(self, tmp_path):
        f = _make_tmp_file(tmp_path, "glossary.md", "")
        terms = _parse_glossary_file(f)
        assert terms == []


class TestAuditLogWriter:
    @pytest.mark.asyncio
    async def test_append_creates_audit_log_entry(self):
        from app.services.audit_log import append_audit_log

        session = AsyncMock()
        session.flush = AsyncMock()

        entry = await append_audit_log(
            session,
            actor="admin",
            action="force_poll",
            target_type="scheduler",
            detail={"positions": 42},
        )

        session.add.assert_called_once()
        session.flush.assert_awaited_once()
        assert entry.actor == "admin"
        assert entry.action == "force_poll"
        assert entry.target_type == "scheduler"
        assert entry.detail == {"positions": 42}
        assert entry.severity == "info"

    @pytest.mark.asyncio
    async def test_append_accepts_custom_severity(self):
        from app.services.audit_log import append_audit_log

        session = AsyncMock()
        session.flush = AsyncMock()

        entry = await append_audit_log(
            session,
            actor="cron",
            action="secret_rotation_reminder",
            severity="warning",
        )

        assert entry.severity == "warning"
        assert entry.target_type is None
