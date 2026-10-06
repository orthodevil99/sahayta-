"""Districts & risk router — contracts §3.

Current risk = latest DistrictRisk row per district. Forecast = deterministic
72h projection from stored weather samples (no external calls in v1).
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import schemas as S
from ..auth import Identity, require_identity
from ..config import Settings, get_settings
from ..database import get_session
from ..models import District, DistrictRisk, DistrictWeatherSample, SOSReport, Volunteer
from ..services.risk import risk_level_for, score_district
from .common import ACTIVE_SOS_STATUSES, utcnow

log = logging.getLogger("sahayta.routers.districts")

router = APIRouter(prefix="/api", tags=["districts"])


async def _latest_risk(session: AsyncSession, district_id: str) -> DistrictRisk | None:
    return (
        await session.execute(
            select(DistrictRisk)
            .where(DistrictRisk.district_id == district_id)
            .order_by(DistrictRisk.computed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _district_snapshot(
    session: AsyncSession, district: District
) -> S.DistrictRead:
    risk_row = await _latest_risk(session, district.id)
    active_sos = (
        await session.execute(
            select(func.count())
            .select_from(SOSReport)
            .where(
                SOSReport.district_id == district.id,
                SOSReport.status.in_(ACTIVE_SOS_STATUSES),
            )
        )
    ).scalar_one()
    active_volunteers = (
        await session.execute(
            select(func.count())
            .select_from(Volunteer)
            .where(Volunteer.district_id == district.id, Volunteer.active.is_(True))
        )
    ).scalar_one()
    return S.DistrictRead(
        id=district.id,
        name=district.name,
        state=district.state,
        lat=district.lat,
        lon=district.lon,
        population=district.population,
        risk=risk_row.risk if risk_row else 0,
        risk_level=risk_row.risk_level if risk_row else "low",  # type: ignore[arg-type]
        active_sos=int(active_sos),
        active_volunteers=int(active_volunteers),
        updated_at=risk_row.computed_at if risk_row else utcnow(),
    )


@router.get("/districts", summary="All districts with current risk snapshot")
async def list_districts(
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> list[S.DistrictRead]:
    districts = (await session.execute(select(District).order_by(District.name))).scalars().all()
    return [await _district_snapshot(session, d) for d in districts]


@router.get("/districts/{district_id}", summary="District detail + risk factors")
async def get_district(
    district_id: str,
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> dict:
    district = await session.get(District, district_id)
    if district is None:
        raise HTTPException(status_code=404, detail="district not found")
    snap = await _district_snapshot(session, district)
    risk_row = await _latest_risk(session, district_id)
    out = snap.model_dump(mode="json")
    out["risk_factors"] = (
        [dict(f) for f in (risk_row.factors or [])] if risk_row else []
    )
    out["weather_source"] = risk_row.weather_source if risk_row else "simulated"
    return out


@router.get("/districts/{district_id}/risk", summary="Current district risk")
async def get_risk(
    district_id: str,
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> S.DistrictRiskRead:
    district = await session.get(District, district_id)
    if district is None:
        raise HTTPException(status_code=404, detail="district not found")
    risk_row = await _latest_risk(session, district_id)
    if risk_row is None:
        # No stored snapshot yet — score live from the latest sample (or zeros).
        sample = (
            await session.execute(
                select(DistrictWeatherSample)
                .where(DistrictWeatherSample.district_id == district_id)
                .order_by(DistrictWeatherSample.ts.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        day = {
            "rain_mm": sample.rain_mm if sample else 0,
            "temp_c": sample.temp_c if sample else 0,
            "humidity_pct": sample.humidity_pct if sample else 0,
            "wind_kph": sample.wind_kph if sample else 0,
            "river_trend": sample.river_trend if sample else "steady",
            "river_level_m": sample.river_level_m if sample else None,
        }
        risk, level, factors, advisory = score_district(day)
        source = sample.source if sample else "simulated"
        computed_at = utcnow()
    else:
        risk, level, factors = risk_row.risk, risk_row.risk_level, list(risk_row.factors or [])
        advisory = risk_row.advisory or ""
        source = risk_row.weather_source
        computed_at = risk_row.computed_at
    return S.DistrictRiskRead(
        district_id=district_id,
        risk=risk,
        risk_level=level,  # type: ignore[arg-type]
        factors=[S.RiskFactor(**f) for f in factors],
        computed_at=computed_at,
        weather_source=source,  # type: ignore[arg-type]
        advisory=advisory,
    )


def _project_hours(
    samples: list[DistrictWeatherSample], district_id: str
) -> list[dict]:
    """Deterministic 72h projection from the trailing week of samples.

    Rain decays geometrically with a diurnal modulation; temp follows a daily
    cycle peaking at 14:00; humidity/wind persist with mild decay. Everything
    is a pure function of the stored samples — no randomness, no network.
    """
    if not samples:
        return []
    last = samples[-1]
    base_ts = last.ts
    if base_ts.tzinfo is None:
        base_ts = base_ts.replace(tzinfo=timezone.utc)

    rain0 = float(last.rain_mm or 0.0)
    temp0 = float(last.temp_c or 30.0)
    hum0 = float(last.humidity_pct or 80.0)
    wind0 = float(last.wind_kph or 10.0)
    trend = last.river_trend or "steady"
    phase = (hash(district_id) % 24)  # deterministic per-district diurnal offset

    hours: list[dict] = []
    for h in range(1, 73):
        rain = max(0.0, rain0 * (0.985**h) * (1 + 0.15 * math.sin(2 * math.pi * (h + phase) / 24)))
        temp = temp0 + 1.5 * math.sin(2 * math.pi * (h - 14) / 24)
        hum = max(20.0, min(100.0, hum0 * (0.999**h) + 2 * math.sin(2 * math.pi * h / 24)))
        wind = max(0.0, wind0 * (0.995**h))
        risk, level, _, _ = score_district(
            {"rain_mm": rain, "temp_c": temp, "humidity_pct": hum,
             "wind_kph": wind, "river_trend": trend}
        )
        hours.append(
            {
                "ts": base_ts + timedelta(hours=h),
                "rain_mm": round(rain, 1),
                "temp_c": round(temp, 1),
                "humidity": round(hum, 0),
                "wind_kph": round(wind, 1),
                "risk": risk,
                "risk_level": level,
            }
        )
    return hours


@router.get("/districts/{district_id}/forecast", summary="72-hour forecast view")
async def get_forecast(
    district_id: str,
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> S.ForecastRead:
    district = await session.get(District, district_id)
    if district is None:
        raise HTTPException(status_code=404, detail="district not found")
    samples = (
        await session.execute(
            select(DistrictWeatherSample)
            .where(DistrictWeatherSample.district_id == district_id)
            .order_by(DistrictWeatherSample.ts.asc())
        )
    ).scalars().all()
    source = samples[-1].source if samples else "simulated"
    if settings.weather_mode == "live":
        # v1 has no live poller yet (Wave 3, Agent 7) — stay honest.
        source = "simulated"
    return S.ForecastRead(
        district_id=district_id,
        weather_source=source,  # type: ignore[arg-type]
        hours=[S.ForecastHour(**h) for h in _project_hours(list(samples), district_id)],
    )
