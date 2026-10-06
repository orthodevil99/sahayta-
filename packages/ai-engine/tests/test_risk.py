"""Tests for risk.py — deterministic formula, seed hints, advisory."""
from __future__ import annotations

import risk
from risk import (
    normalize_to_hint,
    risk_level_for,
    score_all_from_sample,
    score_day,
    score_district,
    score_district_from_sample,
)


class TestFormula:
    def test_patna_seed_hint_reproduced(self, no_llm_env):
        r = score_district_from_sample("patna")
        assert r.risk == 82
        assert r.risk_level == "high"
        assert r.seed_hint_applied is True
        # contributions sum to the hint and scaling is disclosed
        total = sum(f["contribution"] for f in r.factors)
        assert abs(total - 82) < 1.0
        assert any("seed-hint" in f["note"] for f in r.factors)
        # rainfall is the dominant disclosed factor for the demo
        rain = next(f for f in r.factors if f["name"] == "rainfall_24h_mm")
        assert rain["contribution"] == max(f["contribution"] for f in r.factors)

    def test_deterministic_without_hint(self, no_llm_env):
        day = {"rain_mm": 185.0, "temp_c": 30.0, "humidity_pct": 95.0,
               "wind_kph": 20.0, "river_trend": "rising",
               "river_level_m": 50.3, "date": "2026-10-06"}
        r1 = score_district("patna", day)
        r2 = score_district("patna", day)
        assert (r1.risk, r1.risk_level) == (r2.risk, r2.risk_level)
        assert r1.seed_hint_applied is False
        assert r1.risk_level in ("high", "severe")
        assert r1.risk >= 70

    def test_heatwave_district(self, no_llm_env):
        day = {"rain_mm": 0.0, "temp_c": 46.0, "humidity_pct": 30.0,
               "wind_kph": 5.0, "river_trend": "falling"}
        risk_v, level, factors, advisory = score_day(day)
        heat = next(f for f in factors if f["name"] == "heat_index")
        assert heat["contribution"] == round(0.10 * 96.0, 1)  # (46-38)*12
        top = max(factors, key=lambda f: f["contribution"])
        assert top["name"] == "heat_index"
        assert "hydrated" in advisory

    def test_cyclone_district(self, no_llm_env):
        day = {"rain_mm": 40.0, "temp_c": 29.0, "humidity_pct": 90.0,
               "wind_kph": 110.0, "river_trend": "steady"}
        risk_v, level, factors, advisory = score_day(day)
        wind = next(f for f in factors if f["name"] == "wind_kph")
        assert wind["contribution"] > 4.5  # 0.05 * (110/1.2)

    def test_calm_day_is_low(self, no_llm_env):
        day = {"rain_mm": 2.0, "temp_c": 30.0, "humidity_pct": 60.0,
               "wind_kph": 10.0, "river_trend": "falling"}
        risk_v, level, _, _ = score_day(day)
        assert level == "low" and risk_v < 40

    def test_unknown_district_raises(self, no_llm_env):
        import pytest

        with pytest.raises(ValueError):
            score_district_from_sample("atlantis")


class TestLevels:
    def test_boundaries(self, no_llm_env):
        assert risk_level_for(0) == "low"
        assert risk_level_for(39) == "low"
        assert risk_level_for(40) == "moderate"
        assert risk_level_for(69) == "moderate"
        assert risk_level_for(70) == "high"
        assert risk_level_for(84) == "high"
        assert risk_level_for(85) == "severe"
        assert risk_level_for(100) == "severe"


class TestNormalize:
    def test_sums_to_hint(self, no_llm_env):
        _, _, factors, _ = score_day({"rain_mm": 100.0, "temp_c": 30.0,
                                      "humidity_pct": 80.0, "wind_kph": 10.0,
                                      "river_trend": "rising"})
        out = normalize_to_hint(factors, 82)
        assert abs(sum(f["contribution"] for f in out) - 82) < 1.0


class TestAllDistricts:
    def test_twenty_districts_scored(self, no_llm_env):
        out = score_all_from_sample()
        assert len(out) == 20
        for slug, r in out.items():
            assert 0 <= r.risk <= 100
            assert r.risk_level in ("low", "moderate", "high", "severe")
            assert len(r.factors) == 5
            assert r.advisory
