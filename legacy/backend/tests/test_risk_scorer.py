"""Unit tests for the deterministic risk scoring formula (Phase 5a).

All three canonical test cases from ADR-0026 / architecture §Risk are verified.
DB-dependent helpers (flag_mou_score) are tested via pure logic — no async session.
"""
import pytest

from app.services.risk_scorer import (
    CONGESTION_SCORE,
    WEATHER_SCORE,
    _age_score,
    _composite,
    _sanctions_score,
    _shadow_fleet_score,
)


class TestHardcodedConstants:
    def test_weather_score_is_zero(self):
        assert WEATHER_SCORE == 0.0

    def test_congestion_score_is_zero(self):
        assert CONGESTION_SCORE == 0.0


class TestSanctionsScore:
    def test_clean(self):
        assert _sanctions_score("clean") == 0.0

    def test_pending(self):
        assert _sanctions_score("pending") == 50.0

    def test_prev_sanctioned(self):
        assert _sanctions_score("prev_sanctioned") == 25.0

    def test_sanctioned(self):
        assert _sanctions_score("sanctioned") == 100.0

    def test_unknown_status_returns_zero(self):
        assert _sanctions_score("unknown_future_status") == 0.0


class TestShadowFleetScore:
    def test_shadow_fleet_true(self):
        assert _shadow_fleet_score(True) == 100.0

    def test_shadow_fleet_false(self):
        assert _shadow_fleet_score(False) == 0.0


class TestAgeScore:
    def test_null_year_built_returns_zero(self):
        assert _age_score(None, 2026) == 0.0

    def test_unparseable_year_returns_zero(self):
        assert _age_score("unknown", 2026) == 0.0

    def test_vessel_10_years_old_returns_zero(self):
        assert _age_score("2016", 2026) == 0.0

    def test_vessel_less_than_10_years_old(self):
        assert _age_score("2020", 2026) == 0.0

    def test_vessel_exactly_25_years_old_returns_100(self):
        assert _age_score("2001", 2026) == 100.0

    def test_vessel_older_than_25_years_caps_at_100(self):
        assert _age_score("1990", 2026) == 100.0

    def test_vessel_17_years_old(self):
        # 2025-2008=17 years → (17-10)/15 * 100 ≈ 46.67
        assert _age_score("2008", 2025) == pytest.approx(7 / 15.0 * 100.0, abs=1e-6)

    def test_linear_midpoint(self):
        # 17 years: (17-10)/15 * 100 = 46.667
        score = _age_score("2009", 2026)
        assert score == pytest.approx(7 / 15.0 * 100.0, abs=1e-6)


class TestCompositeFormula:
    """Canonical test cases from architecture §Risk (Decision 47)."""

    def test_sanctions_override_all_other_factors(self):
        # sanctions=100, flag_mou=100, age=100 → composite = 100 (short-circuit)
        assert _composite(100.0, 0.0, 100.0, 100.0) == 100.0

    def test_shadow_fleet_override_when_sanctions_zero(self):
        # sanctions=0, shadow=100, flag_mou=0, age=0 → composite = 100
        assert _composite(0.0, 100.0, 0.0, 0.0) == 100.0

    def test_weighted_formula_when_no_compliance_flags(self):
        # sanctions=0, shadow=0, flag_mou=50, age=60 → 50*0.40 + 60*0.30 = 38.0
        result = _composite(0.0, 0.0, 50.0, 60.0)
        assert result == pytest.approx(38.0)

    def test_both_sanctions_and_shadow_fleet_takes_max(self):
        # sanctions=50, shadow=100 → composite = 100
        assert _composite(50.0, 100.0, 0.0, 0.0) == 100.0

    def test_both_sanctions_and_shadow_fleet_sanctions_wins(self):
        # sanctions=100, shadow=50 → composite = 100
        assert _composite(100.0, 50.0, 80.0, 90.0) == 100.0

    def test_clean_vessel_full_weight(self):
        # white flag (0), new vessel (0) → 0
        assert _composite(0.0, 0.0, 0.0, 0.0) == 0.0

    def test_clean_vessel_black_flag_old_ship(self):
        # flag_mou=100, age=100, no compliance → 100*0.40 + 100*0.30 = 70.0
        result = _composite(0.0, 0.0, 100.0, 100.0)
        assert result == pytest.approx(70.0)

    def test_weather_and_congestion_contribute_nothing(self):
        # Explicitly passing zeros confirms the hardcoded constants don't drift
        result_default = _composite(0.0, 0.0, 50.0, 60.0)
        result_explicit = _composite(0.0, 0.0, 50.0, 60.0, congestion=0.0, weather=0.0)
        assert result_default == result_explicit
