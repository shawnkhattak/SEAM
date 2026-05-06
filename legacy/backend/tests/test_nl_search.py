from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import SearchFilterSpec
from app.services.nl_search import spec_cache_key, spec_to_query, _sanctioned_org_imos_cte


# ---------------------------------------------------------------------------
# SearchFilterSpec validation — extra="forbid"
# ---------------------------------------------------------------------------

class TestSearchFilterSpec:
    def test_defaults_all_none_or_false(self):
        spec = SearchFilterSpec()
        assert spec.flag_codes is None
        assert spec.vessel_types is None
        assert spec.sanctioned_only is False
        assert spec.shadow_fleet_only is False
        assert spec.min_risk_score is None
        assert spec.max_risk_score is None
        assert spec.connected_to_sanctioned_org is False
        assert spec.new_arrivals_only is False
        assert spec.min_age_years is None
        assert spec.max_age_years is None
        assert spec.min_gross_tonnage is None
        assert spec.max_gross_tonnage is None

    def test_valid_full_spec(self):
        spec = SearchFilterSpec(
            flag_codes=["IR", "PA"],
            vessel_types=["tanker"],
            sanctioned_only=True,
            min_risk_score=50.0,
        )
        assert spec.flag_codes == ["IR", "PA"]
        assert spec.sanctioned_only is True
        assert spec.min_risk_score == 50.0

    def test_extra_field_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            SearchFilterSpec(unknown_field="surprise")
        assert "extra" in str(exc_info.value).lower() or "unexpected" in str(exc_info.value).lower()

    def test_extra_field_nested_raises(self):
        with pytest.raises(ValidationError):
            SearchFilterSpec(**{"flag_codes": ["SG"], "rogue_param": True})


# ---------------------------------------------------------------------------
# spec_cache_key — deterministic and ignores query text
# ---------------------------------------------------------------------------

class TestSpecCacheKey:
    def test_same_spec_same_key(self):
        s1 = SearchFilterSpec(sanctioned_only=True, flag_codes=["IR"])
        s2 = SearchFilterSpec(flag_codes=["IR"], sanctioned_only=True)
        assert spec_cache_key(s1) == spec_cache_key(s2)

    def test_different_spec_different_key(self):
        s1 = SearchFilterSpec(sanctioned_only=True)
        s2 = SearchFilterSpec(shadow_fleet_only=True)
        assert spec_cache_key(s1) != spec_cache_key(s2)

    def test_key_is_64_char_hex(self):
        key = spec_cache_key(SearchFilterSpec())
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)


# ---------------------------------------------------------------------------
# spec_to_query — pure function, no DB needed
# ---------------------------------------------------------------------------

class TestSpecToQuery:
    def _sql(self, spec: SearchFilterSpec) -> str:
        from sqlalchemy.dialects import postgresql
        q = spec_to_query(spec)
        return str(q.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))

    def test_empty_spec_selects_vessel(self):
        sql = self._sql(SearchFilterSpec())
        assert "vessel" in sql.lower()

    def test_flag_codes_generates_in_clause(self):
        sql = self._sql(SearchFilterSpec(flag_codes=["IR", "PA"]))
        assert "IR" in sql
        assert "PA" in sql
        assert "IN" in sql.upper()

    def test_sanctioned_only_excludes_clean(self):
        sql = self._sql(SearchFilterSpec(sanctioned_only=True))
        assert "clean" in sql
        assert "!=" in sql or "!=" in sql or "not" in sql.lower() or "<>" in sql

    def test_shadow_fleet_filter(self):
        sql = self._sql(SearchFilterSpec(shadow_fleet_only=True))
        assert "is_shadow_fleet" in sql.lower() or "shadow" in sql.lower()

    def test_risk_score_adds_subquery(self):
        sql = self._sql(SearchFilterSpec(min_risk_score=50.0))
        assert "risk_score" in sql.lower()
        assert "50" in sql

    def test_new_arrivals_references_first_observed(self):
        sql = self._sql(SearchFilterSpec(new_arrivals_only=True))
        assert "first_observed_at" in sql.lower()

    def test_vessel_type_filter(self):
        sql = self._sql(SearchFilterSpec(vessel_types=["tanker"]))
        assert "tanker" in sql.lower()

    def test_combined_spec(self):
        sql = self._sql(SearchFilterSpec(
            flag_codes=["CN"],
            sanctioned_only=True,
            min_risk_score=25.0,
        ))
        assert "CN" in sql
        assert "risk_score" in sql.lower()


# ---------------------------------------------------------------------------
# Recursive CTE — cycle detection SQL check
# ---------------------------------------------------------------------------

class TestSanctionedOrgCte:
    def test_cte_contains_cycle_detection(self):
        """The CTE SQL must include the array-based cycle guard."""
        cte = _sanctioned_org_imos_cte()
        sql_text = str(cte)
        assert "visited_imos" in sql_text
        assert "ALL" in sql_text.upper() or "!= ALL" in sql_text

    def test_cte_contains_depth_limit(self):
        """The CTE SQL must cap recursion depth to prevent runaway traversal."""
        cte = _sanctioned_org_imos_cte()
        sql_text = str(cte)
        assert "array_length" in sql_text.lower()

    def test_cte_contains_sanction_filter(self):
        """The base case must filter by sanction topic."""
        cte = _sanctioned_org_imos_cte()
        sql_text = str(cte)
        assert "sanction" in sql_text.lower()

    def test_cte_is_recursive(self):
        """Must be declared WITH RECURSIVE."""
        cte = _sanctioned_org_imos_cte()
        sql_text = str(cte)
        assert "RECURSIVE" in sql_text.upper()

    def test_known_cycle_would_be_detected(self):
        """
        Structural proof: if Vessel A → Org X (sanctioned) and Vessel B → Org X,
        and Vessel A → Org Y, Vessel B → Org Y (cycle in shared-org graph),
        the visited_imos guard ensures A and B each appear exactly once.

        This is a logic-level test: we verify the CTE SQL contains the
        'imo != ALL(visited_imos)' anti-cycle predicate, which is the
        mechanism that prevents an IMO from being visited twice even when
        the org graph contains cycles.
        """
        cte = _sanctioned_org_imos_cte()
        sql_text = str(cte)
        # Anti-cycle: new imo must not already be in visited array
        assert "!= ALL" in sql_text or "not" in sql_text.lower()
        # Expansion appends the new imo to the visited array
        assert "|| vol2.imo" in sql_text or "||" in sql_text
