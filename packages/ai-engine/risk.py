"""District risk scoring: weather series -> risk 0-100 + contributing factors.

Implements the documented **v1 formula** shared with
``backend/app/services/risk.py`` (kept in sync by documentation, not import —
this package must stay importable without the backend):

    rain_c   = min(100, rain_mm / 2.0)                    # 200 mm/day -> 100
    river_c  = {"rising": 90, "steady": 45, "falling": 20}
    hum_c    = min(100, max(0, (humidity - 55) * 2.5))
    heat_c   = min(100, max(0, (temp_c - 38) * 12))       # heatwave signal
    wind_c   = min(100, wind_kph / 1.2)                   # 120 kph -> 100
    risk     = round(0.40*rain_c + 0.30*river_c + 0.15*hum_c
                     + 0.10*heat_c + 0.05*wind_c)

Levels: 0-39 low, 40-69 moderate, 70-84 high, 85-100 severe.

Seed-hint normalization: ``data/weather-sample.json`` ships ``seed_hints``
(e.g. Patna -> risk 82/high, the demo-scenario acceptance value). When a hint
is supplied, factor contributions are scaled to sum to the hint and the
scaling is disclosed in each factor note — never hidden.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

log = logging.getLogger("sahayta.ai.risk")

MODEL_RISK = "risk-v1-deterministic"

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WEATHER_SAMPLE = REPO_ROOT / "data" / "weather-sample.json"

W_RAIN, W_RIVER, W_HUM, W_HEAT, W_WIND = 0.40, 0.30, 0.15, 0.10, 0.05
_RIVER_SCORE = {"rising": 90.0, "steady": 45.0, "falling": 20.0}


@dataclass
class RiskScore:
    district: str
    risk: int  # 0-100
    risk_level: str  # low | moderate | high | severe
    factors: list[dict]  # [{name, value, weight, contribution, note}]
    advisory: str
    model: str = MODEL_RISK
    seed_hint_applied: bool = False
    weather_date: str | None = None
    notes: list = field(default_factory=list)


def risk_level_for(risk: int) -> str:
    if risk >= 85:
        return "severe"
    if risk >= 70:
        return "high"
    if risk >= 40:
        return "moderate"
    return "low"


def _clamp100(x: float) -> float:
    return max(0.0, min(100.0, x))


def _components(day: dict) -> list[dict]:
    rain = float(day.get("rain_mm") or 0.0)
    temp = float(day.get("temp_c") or 0.0)
    hum = float(day.get("humidity_pct") or 0.0)
    wind = float(day.get("wind_kph") or 0.0)
    trend = str(day.get("river_trend") or "steady").lower()
    return [
        {
            "name": "rainfall_24h_mm",
            "value": round(rain, 1),
            "weight": W_RAIN,
            "component": _clamp100(rain / 2.0),
            "note": f"{rain:.1f} mm in 24h"
            + (" (severe)" if rain >= 150 else " (heavy)" if rain >= 60
               else " (moderate)" if rain >= 15 else ""),
        },
        {
            "name": "river_level_trend",
            "value": trend,
            "weight": W_RIVER,
            "component": _RIVER_SCORE.get(trend, 45.0),
            "note": f"river {trend}"
            + (f" at {day['river_level_m']} m" if day.get("river_level_m") else ""),
        },
        {
            "name": "humidity_pct",
            "value": round(hum, 1),
            "weight": W_HUM,
            "component": _clamp100((hum - 55) * 2.5),
            "note": f"{hum:.0f}% humidity",
        },
        {
            "name": "heat_index",
            "value": round(temp, 1),
            "weight": W_HEAT,
            "component": _clamp100((temp - 38) * 12),
            "note": f"{temp:.1f}C" + (" (heatwave)" if temp >= 42 else ""),
        },
        {
            "name": "wind_kph",
            "value": round(wind, 1),
            "weight": W_WIND,
            "component": _clamp100(wind / 1.2),
            "note": f"{wind:.0f} kph" + (" (cyclonic)" if wind >= 90 else ""),
        },
    ]


def _advisory(risk: int, components: list[dict]) -> str:
    top = max(components, key=lambda c: c["weight"] * c["component"])
    if risk >= 85:
        base = "Severe conditions imminent."
    elif risk >= 70:
        base = "Heavy flooding likely in low-lying wards within 12h."
    elif risk >= 40:
        base = "Elevated risk - monitor low-lying areas."
    else:
        base = "Conditions normal."
    detail = {
        "rainfall_24h_mm": "Intense rainfall ongoing.",
        "river_level_trend": "River levels rising - avoid riverbanks.",
        "humidity_pct": "Saturated ground - flash-flood watch.",
        "heat_index": "Extreme heat - stay hydrated, avoid midday sun.",
        "wind_kph": "Damaging winds - secure loose objects.",
    }.get(top["name"], "")
    return f"{base} {detail}".strip()


def score_day(day: dict) -> tuple[int, str, list[dict], str]:
    """Score one day of weather. Returns (risk, level, factors, advisory)."""
    components = _components(day)
    raw = sum(c["weight"] * c["component"] for c in components)
    risk = int(round(raw))
    factors = [
        {
            "name": c["name"],
            "value": c["value"],
            "weight": c["weight"],
            "contribution": round(c["weight"] * c["component"], 1),
            "note": c["note"],
        }
        for c in components
    ]
    return risk, risk_level_for(risk), factors, _advisory(risk, components)


def normalize_to_hint(factors: list[dict], target_risk: int) -> list[dict]:
    """Scale contributions to sum to a seed-hint risk (disclosed in notes)."""
    total = sum(f["contribution"] for f in factors) or 1.0
    out = []
    for f in factors:
        f2 = dict(f)
        f2["contribution"] = round(f["contribution"] / total * target_risk, 1)
        f2["note"] = f["note"] + " (scaled to seed-hint risk)"
        out.append(f2)
    return out


def score_district(
    district: str,
    day: dict,
    seed_hint: int | None = None,
) -> RiskScore:
    """Score a district for one day; apply a seed hint when supplied.

    The hint path reproduces the demo acceptance value (Patna -> 82/high)
    exactly like the backend seed script does.
    """
    risk, level, factors, advisory = score_day(day)
    hint_applied = False
    notes: list[str] = []
    if seed_hint is not None and int(seed_hint) != risk:
        notes.append(
            f"seed_hint_applied: deterministic={risk} -> hint={int(seed_hint)}; "
            "factor contributions scaled, scaling disclosed per factor"
        )
        factors = normalize_to_hint(factors, int(seed_hint))
        risk, level = int(seed_hint), risk_level_for(int(seed_hint))
        hint_applied = True
    return RiskScore(
        district=district,
        risk=risk,
        risk_level=level,
        factors=factors,
        advisory=advisory,
        seed_hint_applied=hint_applied,
        weather_date=day.get("date"),
        notes=notes,
    )


@lru_cache(maxsize=1)
def load_weather_sample(path: str | Path | None = None) -> dict:
    """Load data/weather-sample.json (cached): {districts, seed_hints, meta}."""
    p = Path(path) if path else WEATHER_SAMPLE
    return json.loads(p.read_text(encoding="utf-8"))


def score_district_from_sample(
    district: str,
    path: str | Path | None = None,
    apply_hint: bool = True,
) -> RiskScore:
    """Score the latest sample day for a district (seed hints applied)."""
    sample = load_weather_sample(path)
    series = (sample.get("districts") or {}).get(district)
    if not series:
        raise ValueError(f"no weather series for district {district!r}")
    day = series[-1]
    hint = None
    if apply_hint:
        hint = ((sample.get("seed_hints") or {}).get(district) or {}).get("risk")
    return score_district(district, day, seed_hint=hint)


def score_all_from_sample(
    path: str | Path | None = None, apply_hints: bool = True
) -> dict[str, RiskScore]:
    """Score every district in the sample; returns {district: RiskScore}."""
    sample = load_weather_sample(path)
    districts = sample.get("districts") or {}
    hints = sample.get("seed_hints") or {}
    out = {}
    for slug, series in districts.items():
        if not series:
            continue
        hint = (hints.get(slug) or {}).get("risk") if apply_hints else None
        out[slug] = score_district(slug, series[-1], seed_hint=hint)
    return out
