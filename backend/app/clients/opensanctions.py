"""OpenSanctions bulk dataset client.

ADR-0002: daily bulk download only — no per-source parsers.
In mock mode, reads from app/mocks/opensanctions_maritime.json.
In live mode, downloads from the OpenSanctions data API.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_MOCK_FILE = Path(__file__).parent.parent / "mocks" / "opensanctions_maritime.json"

# Datasets that contain maritime-relevant entities
_MARITIME_DATASETS = [
    "sanctions",
    "us_ofac_sdn",
    "ru_nsd_sdn",
    "un_sc_sanctions",
    "eu_fto",
]


def _load_mock() -> list[dict[str, Any]]:
    with _MOCK_FILE.open() as fh:
        data = json.load(fh)
    return data.get("entities", [])


async def fetch_entities(dataset: str = "sanctions") -> list[dict[str, Any]]:
    """Download all entities for a dataset.

    Returns a list of FtM entity dicts with keys:
      id, schema, properties, referents, datasets, last_change, last_seen
    """
    settings = get_settings()

    if settings.opensanctions_mock_mode:
        logger.info("opensanctions: mock mode — reading fixture file")
        entities = _load_mock()
        # Filter to requested dataset if not 'all'
        if dataset != "all":
            entities = [
                e for e in entities if dataset in e.get("datasets", [])
            ]
        logger.info(
            "opensanctions: loaded %d mock entities for dataset=%s", len(entities), dataset
        )
        return entities

    # Live mode: stream the FtM JSON lines format from data.opensanctions.org
    url = f"https://data.opensanctions.org/datasets/latest/{dataset}/entities.ftm.json"
    headers: dict[str, str] = {}
    if settings.opensanctions_api_key:
        headers["Authorization"] = f"ApiKey {settings.opensanctions_api_key}"

    entities: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream("GET", url, headers=headers) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entity = json.loads(line)
                    entities.append(entity)
                except json.JSONDecodeError:
                    logger.debug("opensanctions: skipping non-JSON line")

    logger.info(
        "opensanctions: fetched %d entities for dataset=%s", len(entities), dataset
    )
    return entities


async def fetch_maritime_entities() -> list[dict[str, Any]]:
    """Fetch all maritime-relevant entities across configured datasets.

    In mock mode returns the fixture file. In live mode queries each dataset
    sequentially and deduplicates by entity id.
    """
    settings = get_settings()
    if settings.opensanctions_mock_mode:
        return await fetch_entities("all")

    seen: set[str] = set()
    combined: list[dict[str, Any]] = []
    for ds in _MARITIME_DATASETS:
        try:
            entities = await fetch_entities(ds)
            for e in entities:
                eid = e.get("id", "")
                if eid and eid not in seen:
                    seen.add(eid)
                    combined.append(e)
        except httpx.HTTPError as exc:
            logger.warning("opensanctions: failed to fetch dataset=%s: %s", ds, exc)

    logger.info("opensanctions: combined %d unique entities", len(combined))
    return combined
