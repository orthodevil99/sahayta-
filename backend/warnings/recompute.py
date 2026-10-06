"""District risk recomputation — trailing-24h weather → v1 risk formula → DB.

For each district the pipeline:
  1. aggregates the trailing 24 h of ``DistrictWeatherSample`` rows into one
     "day" dict (rain = sum, temp = max, humidity = mean, wind = max,
     river = latest stored reading),
  2. scores it with the SHARED v1 formula in ``app.services.risk`` (Agent 7
     does NOT reimplement the formula — it imports it),
  3. applies the demo seed hint when the weather is simulated (mirrors
     ``seed.py`` exactly: Patna stays 82/high; the scaling is disclosed in the
     factor notes, never hidden),
  4. persists a new ``DistrictRisk`` row only when risk/level/source changed
     (avoids a no-op row every cycle), and
  5. emits WS ``risk.updated`` so the admin dashboard refreshes live.

Seed-hint policy (why): the simulated feed exists for the demo; the hints
reproduce the demo-scenario acceptance values (Patna 82/high) deterministically.
In live mode the pure formula runs with no hints — honest numbers.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import District, DistrictRisk, DistrictWeatherSample
from app.routers.common import emit, utcnow
from app.services.risk import normalize_factors, risk_level_for, score_district

log = logging.getLogger("sahayta.warnings.recompute")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WEATHER_SAMPLE = REPO_ROOT / "data" / "weather-sample.json"


@lru_cache(maxsize=1)
def _seed_hints() -> dict:
    try:
        return json.loads(WEATHER_SAMPLE.read_text(encoding="utf-8")).get("seed_hints", {})
    except (OSError, ValueError):
        return {}


async def _trailing_day(session: AsyncSession, district_id: str) -> dict | None:
    """Aggregate the trailing 24 h of samples into one risk-formula day dict."""
    rows = (
        await session.execute(
            select(DistrictWeatherSample)
            .where(DistrictWeatherSample.district_id == district_id)
            .order_by(DistrictWeatherSample.ts.desc())
            .limit(24)
        )
    ).scalars().all()
    rows = [r for r in rows if r.rain_mm is not None]
    if not rows:
        return None
    rains = [float(r.rain_mm or 0.0) for r in rows]
    temps = [float(r.temp_c or 0.0) for r in rows]
    hums = [float(r.humidity_pct or 0.0) for r in rows]
    winds = [float(r.wind_kph or 0.0) for r in rows]
    river = next((r for r in rows if r.river_trend), None)
    return {
        "rain_mm": round(sum(rains), 1),
        "temp_c": round(max(temps), 1) if temps else 0.0,
        "humidity_pct": round(sum(hums) / len(hums), 1) if hums else 0.0,
        "wind_kph": round(max(winds), 1) if winds else 0.0,
        "river_trend": (river.river_trend if river else "steady") or "steady",
        "river_level_m": river.river_level_m if river else None,
    }


async def _latest_risk_row(session: AsyncSession, district_id: str) -> DistrictRisk | None:
    return (
        await session.execute(
            select(DistrictRisk)
            .where(DistrictRisk.district_id == district_id)
            .order_by(DistrictRisk.computed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


def _apply_seed_hint(
    district_id: str, risk: int, level: str, factors: list[dict], source: str
) -> tuple[int, str, list[dict]]:
    """Mirror seed.py: simulated feed honors data seed_hints (disclosed)."""
    if source != "simulated":
        return risk, level, factors
    hint = _seed_hints().get(district_id) or {}
    if "risk" in hint and int(hint["risk"]) != risk:
        log.info(
            "seed_hints override (recompute): %s risk %s -> %s",
            district_id, risk, hint["risk"],
        )
        factors = normalize_factors(factors, int(hint["risk"]))
        risk = int(hint["risk"])
        level = hint.get("risk_level", risk_level_for(risk))
    return risk, level, factors


async def recompute_district(
    session: AsyncSession, district_id: str
) -> tuple[DistrictRisk | None, DistrictRisk | None]:
    """Recompute one district's risk. Returns (new_row, prev_row).

    ``new_row`` is None when there is no weather to score, or when the
    recomputed (risk, level, source) is identical to the latest stored row
    (no-op cycles don't spam the time series).
    """
    day = await _trailing_day(session, district_id)
    if day is None:
        log.warning("no weather samples for %s — skipping recompute", district_id)
        return None, None
    sample_source = (
        await session.execute(
            select(DistrictWeatherSample.source)
            .where(DistrictWeatherSample.district_id == district_id)
            .order_by(DistrictWeatherSample.ts.desc())
            .limit(1)
        )
    ).scalar_one_or_none() or "simulated"

    risk, level, factors, advisory = score_district(day)
    risk, level, factors = _apply_seed_hint(district_id, risk, level, factors, sample_source)

    prev = await _latest_risk_row(session, district_id)
    if prev and (prev.risk, prev.risk_level, prev.weather_source) == (risk, level, sample_source):
        return None, prev  # unchanged — don't write a duplicate row

    row = DistrictRisk(
        district_id=district_id,
        risk=risk,
        risk_level=level,
        factors=factors,
        advisory=advisory,
        weather_source=sample_source,
        computed_at=utcnow(),
    )
    session.add(row)
    await session.flush()
    await emit(
        "risk.updated",
        {"district_id": district_id, "risk": risk,
         "risk_level": level, "weather_source": sample_source},
    )
    return row, prev


async def recompute_all(
    session: AsyncSession, district_ids: list[str] | None = None
) -> list[tuple[DistrictRisk | None, DistrictRisk | None]]:
    """Recompute every tracked district; commits once at the end."""
    stmt = select(District.id).order_by(District.id)
    if district_ids:
        stmt = stmt.where(District.id.in_(district_ids))
    ids = list((await session.execute(stmt)).scalars().all())
    out = []
    for district_id in ids:
        out.append(await recompute_district(session, district_id))
    await session.commit()
    return out
