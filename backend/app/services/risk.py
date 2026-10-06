"""District risk scoring — the v1 formula behind GET /api/districts/{id}/risk.

Inputs: one day of weather (rain, temp, humidity, wind, river level + trend).
Output: risk 0-100, risk_level, per-factor contributions, advisory text.

Formula (documented, deterministic):
    rain_c   = min(100, rain_mm / 2.0)                    # 200 mm/day -> 100
    river_c  = {"rising": 90, "steady": 45, "falling": 20}
    hum_c    = min(100, max(0, (humidity - 55) * 2.5))
    heat_c   = min(100, max(0, (temp_c - 38) * 12))       # heatwave signal
    wind_c   = min(100, wind_kph / 1.2)                   # 120 kph -> 100 (cyclone)
    risk     = round(0.40*rain_c + 0.30*river_c + 0.15*hum_c
                     + 0.10*heat_c + 0.05*wind_c)

Levels: 0-39 low, 40-69 moderate, 70-84 high, 85-100 severe.

The seed script stores initial snapshots; where data/weather-sample.json
provides ``seed_hints`` (Patna: risk 82), the hint value is honored and the
factor contributions are normalized to sum to it — documented in the seed log,
never hidden. Wave 3 (Agent 7) owns live recomputation against this module.
"""
from __future__ import annotations

import logging

log = logging.getLogger("sahayta.risk")

W_RAIN, W_RIVER, W_HUM, W_HEAT, W_WIND = 0.40, 0.30, 0.15, 0.10, 0.05
_RIVER_SCORE = {"rising": 90.0, "steady": 45.0, "falling": 20.0}


def risk_level_for(risk: int) -> str:
    if risk >= 85:
        return "severe"
    if risk >= 70:
        return "high"
    if risk >= 40:
        return "moderate"
    return "low"


def _clamp01(x: float) -> float:
    return max(0.0, min(100.0, x))


def score_district(day: dict) -> tuple[int, str, list[dict], str]:
    """Score one day of weather. Returns (risk, level, factors, advisory)."""
    rain = float(day.get("rain_mm") or 0.0)
    temp = float(day.get("temp_c") or 0.0)
    hum = float(day.get("humidity_pct") or 0.0)
    wind = float(day.get("wind_kph") or 0.0)
    trend = str(day.get("river_trend") or "steady").lower()

    components = [
        {
            "name": "rainfall_24h_mm",
            "value": round(rain, 1),
            "weight": W_RAIN,
            "component": _clamp01(rain / 2.0),
            "note": f"{rain:.1f} mm in 24h"
            + (" (severe)" if rain >= 150 else " (heavy)" if rain >= 60 else " (moderate)" if rain >= 15 else ""),
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
            "component": _clamp01((hum - 55) * 2.5),
            "note": f"{hum:.0f}% humidity",
        },
        {
            "name": "heat_index",
            "value": round(temp, 1),
            "weight": W_HEAT,
            "component": _clamp01((temp - 38) * 12),
            "note": f"{temp:.1f}°C" + (" (heatwave)" if temp >= 42 else ""),
        },
        {
            "name": "wind_kph",
            "value": round(wind, 1),
            "weight": W_WIND,
            "component": _clamp01(wind / 1.2),
            "note": f"{wind:.0f} kph" + (" (cyclonic)" if wind >= 90 else ""),
        },
    ]
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
    advisory = _advisory(risk, components)
    return risk, risk_level_for(risk), factors, advisory


def normalize_factors(factors: list[dict], target_risk: int) -> list[dict]:
    """Scale contributions so they sum to a seed-hint risk value (documented)."""
    total = sum(f["contribution"] for f in factors) or 1.0
    out = []
    for f in factors:
        f2 = dict(f)
        f2["contribution"] = round(f["contribution"] / total * target_risk, 1)
        f2["note"] = f["note"] + " (scaled to seed-hint risk)"
        out.append(f2)
    return out


def _advisory(risk: int, components: list[dict]) -> str:
    top = max(components, key=lambda c: c["weight"] * c["component"])
    if risk >= 85:
        base = "Severe conditions imminent."
    elif risk >= 70:
        base = "Heavy flooding likely in low-lying wards within 12h."
    elif risk >= 40:
        base = "Elevated risk — monitor low-lying areas."
    else:
        base = "Conditions normal."
    detail = {
        "rainfall_24h_mm": "Intense rainfall ongoing.",
        "river_level_trend": "River levels rising — avoid riverbanks.",
        "humidity_pct": "Saturated ground — flash-flood watch.",
        "heat_index": "Extreme heat — stay hydrated, avoid midday sun.",
        "wind_kph": "Damaging winds — secure loose objects.",
    }.get(top["name"], "")
    return f"{base} {detail}".strip()
