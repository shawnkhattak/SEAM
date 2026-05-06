from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta

from app.services.vessels import normalize_position, parse_mpa_timestamp, _infer_status
from app.services.history import _haversine_m


def _make_raw(
    imo: str = "9462045",
    lat: float = 1.2612,
    lon: float = 103.8338,
    speed: float = 0.0,
    heading: float = 270.0,
    timestamp: str = "2026-04-30 12:00:00",
) -> dict:
    return {
        "vesselParticulars": {
            "imoNumber": imo,
            "vesselName": "TEST VESSEL",
            "flag": "PA",
            "vesselType": "CS",
            "grossTonnage": 99155,
            "mmsiNumber": "371234500",
            "yearBuilt": "2010",
        },
        "latitudeDegrees": lat,
        "longitudeDegrees": lon,
        "speed": speed,
        "course": heading,
        "heading": heading,
        "timeStamp": timestamp,
    }


class TestNormalizePosition:
    def test_valid_record(self):
        raw = _make_raw()
        result = normalize_position(raw)
        assert result is not None
        assert result["imo"] == 9462045
        assert result["name"] == "TEST VESSEL"
        assert result["lat"] == 1.2612
        assert result["lon"] == 103.8338

    def test_invalid_imo_rejected(self):
        raw = _make_raw(imo="1234567")  # bad Luhn
        assert normalize_position(raw) is None

    def test_missing_lat_rejected(self):
        raw = _make_raw()
        raw["latitudeDegrees"] = None
        assert normalize_position(raw) is None

    def test_timestamp_converted_to_utc(self):
        # MPA timestamps are Singapore time (UTC+8); 12:00 SGT = 04:00 UTC
        raw = _make_raw(timestamp="2026-04-30 12:00:00")
        result = normalize_position(raw)
        assert result is not None
        ts: datetime = result["recorded_at"]
        assert ts.tzinfo is not None
        assert ts.utcoffset() == timedelta(0)
        assert ts.hour == 4  # 12:00 SGT - 8h = 04:00 UTC

    def test_future_timestamp_clamped(self):
        # Supply a far-future timestamp — should be clamped to now
        raw = _make_raw(timestamp="2035-01-01 00:00:00")
        result = normalize_position(raw)
        assert result is not None
        now = datetime.now(tz=timezone.utc)
        assert abs((result["recorded_at"] - now).total_seconds()) < 10


class TestInferStatus:
    def test_arrived_in_harbour_slow(self):
        assert _infer_status(1.265, 103.82, 0.0) == "arrived"

    def test_departing_in_harbour_fast(self):
        assert _infer_status(1.265, 103.82, 3.0) == "departing"

    def test_incoming_near_sg(self):
        # Just outside the harbour box but in the broader approach area
        assert _infer_status(1.30, 103.70, 5.0) == "incoming"

    def test_departed_far_away(self):
        assert _infer_status(-5.0, 90.0, 12.0) == "departed"


class TestHaversine:
    def test_same_point(self):
        assert _haversine_m(1.265, 103.82, 1.265, 103.82) == 0.0

    def test_100m_apart(self):
        # 0.001 degrees latitude ≈ 111 m
        dist = _haversine_m(1.265, 103.82, 1.266, 103.82)
        assert 100 < dist < 130

    def test_dedup_threshold(self):
        # Within 100 m — should NOT archive
        dist = _haversine_m(1.265, 103.82, 1.2651, 103.82)
        assert dist < 100
