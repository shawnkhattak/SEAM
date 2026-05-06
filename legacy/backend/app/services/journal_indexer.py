"""Walk docs/journey/ + docs/adr/ + docs/glossary.md and upsert journal_* / glossary_term rows.

Parsing rules (no YAML frontmatter in any of these files):
  - Phase files:  # Phase N: TITLE  (first H1 heading)
  - ADR files:    # ADR NNNN: TITLE  (first H1 heading)
                  **Status:** VALUE
                  **Decided:** YYYY-MM-DD
  - Glossary:     ## TERM  (H2 sections)
                  **Category:** VALUE
                  First non-empty paragraph = plain definition
                  Paragraph starting with "**Why it matters" = why_it_matters
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GlossaryTerm, JournalAdr, JournalPhase
from app.utils.timezone import utc_now

logger = logging.getLogger(__name__)

_DOCS_ROOT = Path(__file__).parents[3] / "docs"
_PROJECT_ROOT = Path(__file__).parents[3]


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(_PROJECT_ROOT))
    except ValueError:
        return str(path)

_RE_PHASE_HEADING = re.compile(r"^#\s+Phase\s+(\d+)[a-z]?\s*[:\-–]\s*(.+)$", re.IGNORECASE)
_RE_ADR_HEADING = re.compile(r"^#\s+ADR\s+0*(\d+)\s*[:\-–]\s*(.+)$", re.IGNORECASE)
_RE_BOLD_FIELD = re.compile(r"^\*\*([^*:]+):?\*\*\s*[:\-–]?\s*(.*)$")


# ---------------------------------------------------------------------------
# Phase journal files
# ---------------------------------------------------------------------------

def _parse_phase_file(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    phase_number: int | None = None
    title: str | None = None
    status: str | None = None
    summary_lines: list[str] = []
    in_what_was_built = False
    capturing_summary = False

    for line in lines:
        if phase_number is None:
            m = _RE_PHASE_HEADING.match(line.strip())
            if m:
                phase_number = int(m.group(1))
                title = m.group(2).strip()
            continue

        stripped = line.strip()

        # Grab status from bold field line
        if stripped.startswith("**Status:**") or stripped.startswith("**Status**:"):
            bm = _RE_BOLD_FIELD.match(stripped)
            if bm:
                status = bm.group(2).strip()

        # Start capturing after "## What Was Built"
        if re.match(r"^##\s+What Was Built", stripped, re.IGNORECASE):
            in_what_was_built = True
            capturing_summary = False
            continue

        if in_what_was_built:
            # Stop at next H2
            if stripped.startswith("## "):
                break
            if stripped and not capturing_summary:
                capturing_summary = True
            if capturing_summary:
                summary_lines.append(line)
                # Cap at ~500 chars
                if sum(len(l) for l in summary_lines) > 500:
                    break

    if phase_number is None:
        return None

    summary = "\n".join(summary_lines).strip() or None
    return {
        "phase_number": phase_number,
        "title": title or f"Phase {phase_number}",
        "completed": (status or "").lower() == "complete",
        "summary_md": summary,
        "markdown_file_path": _rel(path),
    }


async def index_phases(session: AsyncSession) -> int:
    journey_dir = _DOCS_ROOT / "journey"
    if not journey_dir.exists():
        return 0

    now = utc_now()
    upserted = 0

    for path in sorted(journey_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        parsed = _parse_phase_file(path)
        if parsed is None:
            continue

        result = await session.execute(
            select(JournalPhase).where(JournalPhase.phase_number == parsed["phase_number"])
        )
        row = result.scalar_one_or_none()

        if row is None:
            row = JournalPhase(phase_number=parsed["phase_number"], indexed_at=now)
            session.add(row)

        row.title = parsed["title"]
        row.summary_md = parsed["summary_md"]
        row.markdown_file_path = parsed["markdown_file_path"]
        row.indexed_at = now
        if parsed["completed"] and row.completed_at is None:
            row.completed_at = now
        upserted += 1

    return upserted


# ---------------------------------------------------------------------------
# ADR files
# ---------------------------------------------------------------------------

def _parse_adr_file(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    adr_number: int | None = None
    title: str | None = None
    status = "accepted"
    decided_at: datetime | None = None
    superseded_by: int | None = None
    summary_lines: list[str] = []
    in_context = False
    capturing = False

    for line in lines:
        stripped = line.strip()

        if adr_number is None:
            m = _RE_ADR_HEADING.match(stripped)
            if m:
                adr_number = int(m.group(1))
                title = m.group(2).strip()
            continue

        bm = _RE_BOLD_FIELD.match(stripped)
        if bm:
            key = bm.group(1).strip().lower()
            val = bm.group(2).strip()
            if key == "status":
                status = val.lower()
            elif key == "decided":
                try:
                    decided_at = datetime.strptime(val, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
            elif key == "superseded by":
                m2 = re.search(r"\d+", val)
                if m2:
                    superseded_by = int(m2.group())

        if re.match(r"^##\s+Context", stripped, re.IGNORECASE):
            in_context = True
            capturing = False
            continue

        if in_context:
            if stripped.startswith("## "):
                break
            if stripped and not capturing:
                capturing = True
            if capturing:
                summary_lines.append(line)
                if sum(len(l) for l in summary_lines) > 500:
                    break

    if adr_number is None:
        return None

    return {
        "adr_number": adr_number,
        "title": title or f"ADR {adr_number:04d}",
        "status": status,
        "decided_at": decided_at,
        "superseded_by_adr_number": superseded_by,
        "summary_md": "\n".join(summary_lines).strip() or None,
        "markdown_file_path": _rel(path),
    }


async def index_adrs(session: AsyncSession) -> int:
    adr_dir = _DOCS_ROOT / "adr"
    if not adr_dir.exists():
        return 0

    now = utc_now()
    upserted = 0

    for path in sorted(adr_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        parsed = _parse_adr_file(path)
        if parsed is None:
            continue

        result = await session.execute(
            select(JournalAdr).where(JournalAdr.adr_number == parsed["adr_number"])
        )
        row = result.scalar_one_or_none()

        if row is None:
            row = JournalAdr(adr_number=parsed["adr_number"], indexed_at=now)
            session.add(row)

        row.title = parsed["title"]
        row.status = parsed["status"]
        row.decided_at = parsed["decided_at"]
        row.superseded_by_adr_number = parsed["superseded_by_adr_number"]
        row.summary_md = parsed["summary_md"]
        row.markdown_file_path = parsed["markdown_file_path"]
        row.indexed_at = now
        upserted += 1

    return upserted


# ---------------------------------------------------------------------------
# Glossary file
# ---------------------------------------------------------------------------

def _parse_glossary_file(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    sections = re.split(r"^(?=## )", text, flags=re.MULTILINE)
    terms: list[dict] = []

    file_path_str = _rel(path)

    for section in sections:
        lines = section.splitlines()
        if not lines:
            continue

        # H2 heading is the term
        heading_match = re.match(r"^## (.+)$", lines[0].strip())
        if not heading_match:
            continue

        term = heading_match.group(1).strip()
        category: str | None = None
        plain_paragraphs: list[str] = []
        why_paragraph: str | None = None

        # Split remaining into paragraphs
        body = "\n".join(lines[1:])
        paragraphs = [p.strip() for p in re.split(r"\n\n+", body) if p.strip()]

        for para in paragraphs:
            bm = _RE_BOLD_FIELD.match(para)
            if bm and bm.group(1).strip().lower() == "category":
                category = bm.group(2).strip()
                continue

            if para.lower().startswith("**why it matters"):
                # Strip the bold prefix
                why_paragraph = re.sub(r"^\*\*[^*]+\*\*\s*", "", para).strip()
                continue

            if para.lower().startswith("**related terms"):
                continue

            # First non-metadata, non-bold paragraph is the definition
            if not plain_paragraphs and not para.startswith("**"):
                plain_paragraphs.append(para)

        terms.append({
            "term": term,
            "category": category,
            "plain_definition": plain_paragraphs[0] if plain_paragraphs else None,
            "why_it_matters_in_project": why_paragraph,
            "markdown_file_path": file_path_str,
        })

    return terms


async def index_glossary(session: AsyncSession) -> int:
    glossary_path = _DOCS_ROOT / "glossary.md"
    if not glossary_path.exists():
        return 0

    now = utc_now()
    terms = _parse_glossary_file(glossary_path)
    upserted = 0

    for parsed in terms:
        result = await session.execute(
            select(GlossaryTerm).where(GlossaryTerm.term == parsed["term"])
        )
        row = result.scalar_one_or_none()

        if row is None:
            row = GlossaryTerm(term=parsed["term"], indexed_at=now)
            session.add(row)

        row.category = parsed["category"]
        row.plain_definition = parsed["plain_definition"]
        row.why_it_matters_in_project = parsed["why_it_matters_in_project"]
        row.markdown_file_path = parsed["markdown_file_path"]
        row.indexed_at = now
        upserted += 1

    return upserted


# ---------------------------------------------------------------------------
# Top-level runner (called by scheduler)
# ---------------------------------------------------------------------------

async def run_journal_indexer(session: AsyncSession) -> dict:
    phases = await index_phases(session)
    adrs = await index_adrs(session)
    glossary = await index_glossary(session)
    return {"phases": phases, "adrs": adrs, "glossary": glossary}
