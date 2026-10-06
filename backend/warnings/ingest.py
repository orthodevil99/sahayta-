"""Weather ingestion worker — Open-Meteo polling with labeled simulated fallback.

External call (the ONLY one in this module):
    GET {SAHAYTA_WEATHER_API_URL}          (default https://api.open-meteo.com/v1/forecast)
        ?latitude={lat}&longitude={lon}
        &hourly=temperature_2m,precipitation,relative_humidity_2m,wind_speed_10m
        &past_days=1&forecast_days=1&timezone=UTC

Open-Meteo needs no API key. On ANY failure — DNS, connect timeout, HTTP error,
malformed JSON, missing/short arrays — the district is ingested from the
SIMULATED feed instead (deterministic projection of data/weather-sample.json)
and ``weather_source`` is recorded as ``"simulated"``. Simulated data is never
presented as live: the label flows from ``DistrictWeatherSample.source`` /
``DistrictRisk.weather_source`` into the API responses, where the frontend
renders the "SIMULATED FEED" badge.

River data: Open-Meteo has no river-level series, so ``river_trend`` /
``river_level_m`` are carried forward from the most recent stored sample for
the district (seeded from data/weather-sample.json). This is documented here
and in warnings/README.md — the risk formula still gets a river signal, but it
is explicitly NOT a live river reading.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models import District, DistrictWeatherSample

log = logging.getLogger("sahayta.warnings.ingest")

# backend/warnings/ingest.py -> backend/warnings -> backend -> sahayta (repo root)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WEATHER_SAMPLE = REPO_ROOT / "data" / "weather-sample.json"

HOURLY_VARS = "temperature_2m,precipitation,relative_humidity_2m,wind_speed_10m"
FETCH_TIMEOUT_S = 20
# One trailing day of hourly rows per district per ingest cycle.
WINDOW_HOURS = 24


class WeatherFetchError(RuntimeError):
    """Raised when the live weather fetch fails in any way."""


@dataclass
class IngestResult:
    """Outcome of ingesting one district."""

    district_id: str
    source: str  # "live" | "simulated"
    hours_written: int
    error: str | None = None


@lru_cache(maxsize=1)
def _load_sample() -> dict:
    return json.loads(WEATHER_SAMPLE.read_text(encoding="utf-8"))


def _parse_open_meteo(payload: dict) -> list[dict]:
    """Validate + normalize an Open-Meteo hourly payload.

    Raises WeatherFetchError on anything unexpected — the caller treats every
    failure identically (fall back to simulated).
    """
    try:
        hourly = payload["hourly"]
        times = hourly["time"]
        t2m = hourly["temperature_2m"]
        precip = hourly["precipitation"]
        rh = hourly["relative_humidity_2m"]
        wind = hourly["wind_speed_10m"]
    except (KeyError, TypeError) as exc:
        raise WeatherFetchError(f"missing hourly fields: {exc}") from exc
    n = len(times)
    if not (len(t2m) == len(precip) == len(rh) == len(wind) == n) or n < WINDOW_HOURS:
        raise WeatherFetchError(
            f"hourly arrays inconsistent/too short (n={n}, need >={WINDOW_HOURS})"
        )
    hours: list[dict] = []
    for i in range(n - WINDOW_HOURS, n):
        try:
            ts = datetime.fromisoformat(times[i])
        except ValueError as exc:
            raise WeatherFetchError(f"bad timestamp {times[i]!r}") from exc
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        try:
            hours.append(
                {
                    "ts": ts.astimezone(timezone.utc),
                    "rain_mm": max(0.0, float(precip[i])),
                    "temp_c": float(t2m[i]),
                    "humidity_pct": min(100.0, max(0.0, float(rh[i]))),
                    "wind_kph": max(0.0, float(wind[i]) * 3.6),
                }
            )
        except (TypeError, ValueError) as exc:
            raise WeatherFetchError(f"non-numeric value at hour {i}: {exc}") from exc
    return hours


async def fetch_open_meteo(
    lat: float, lon: float, api_url: str, timeout_s: int = FETCH_TIMEOUT_S
) -> list[dict]:
    """Fetch the trailing 24 h of hourly weather from Open-Meteo.

    Raises WeatherFetchError on network errors, HTTP errors, timeouts and
    malformed payloads alike.
    """
    params = {
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "hourly": HOURLY_VARS,
        "past_days": 1,
        "forecast_days": 1,
        "timezone": "UTC",
        # Explicit SI units so parsing never depends on API defaults:
        # temperature °C, precipitation mm, wind m/s (converted to km/h below).
        "temperature_unit": "celsius",
        "wind_speed_unit": "ms",
        "precipitation_unit": "mm",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.get(api_url, params=params)
    except (httpx.HTTPError, OSError) as exc:
        # HTTPError is the base of every httpx failure: ConnectError,
        # ConnectTimeout, ReadTimeout, RemoteProtocolError, etc.
        raise WeatherFetchError(f"network failure: {type(exc).__name__}: {exc}") from exc
    if resp.status_code != 200:
        raise WeatherFetchError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    try:
        payload = resp.json()
    except ValueError as exc:
        raise WeatherFetchError(f"invalid JSON: {exc}") from exc
    return _parse_open_meteo(payload)


def _jitter(district_id: str, hour: int, salt: str) -> float:
    """Deterministic 0..1 jitter — stable across runs, no random module."""
    h = hashlib.sha256(f"{district_id}:{hour}:{salt}".encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def simulated_hours(district_id: str, now: datetime | None = None) -> list[dict]:
    """Build 24 trailing hourly rows from the synthetic sample (SIMULATED FEED).

    Deterministic projection of the district's latest daily record in
    data/weather-sample.json: rain follows a diurnal curve that sums to the
    daily total, temp/humidity/wind get fixed diurnal shapes plus deterministic
    jitter. River fields are NOT synthesized here — the caller carries forward
    the last stored river reading (see ingest_district).
    """
    now = now or datetime.now(timezone.utc)
    sample = _load_sample()
    series = (sample.get("districts") or {}).get(district_id)
    if not series:
        raise WeatherFetchError(f"no simulated series for district {district_id!r}")
    day = series[-1]
    rain_total = float(day.get("rain_mm") or 0.0)
    temp = float(day.get("temp_c") or 30.0)
    hum = float(day.get("humidity_pct") or 80.0)
    wind = float(day.get("wind_kph") or 10.0)

    hours: list[dict] = []
    # Diurnal weights peaking in the late afternoon (monsoon pattern).
    weights = [1 + 0.6 * math.sin(2 * math.pi * (h - 16) / 24) for h in range(24)]
    wsum = sum(weights)
    for h in range(1, WINDOW_HOURS + 1):
        idx = WINDOW_HOURS - h  # idx 23 = oldest hour, 0 = current hour
        w = weights[idx] / wsum
        j = _jitter(district_id, idx, "sim")
        hours.append(
            {
                "ts": now - timedelta(hours=h - 1),
                "rain_mm": round(max(0.0, rain_total * w * (0.7 + 0.6 * j)), 1),
                "temp_c": round(temp + 1.8 * math.sin(2 * math.pi * (idx - 14) / 24), 1),
                "humidity_pct": round(
                    min(100.0, max(20.0, hum + 4 * math.sin(2 * math.pi * idx / 24)
                                           + (j - 0.5) * 4)), 0),
                "wind_kph": round(max(0.0, wind * (0.85 + 0.3 * j)), 1),
            }
        )
    # Chronological order (oldest first) — matches the DB ordering the
    # forecast endpoint relies on.
    hours.sort(key=lambda r: r["ts"])
    # Renormalize rain so the 24 h window sums to the daily total exactly.
    total = sum(r["rain_mm"] for r in hours) or 1.0
    for r in hours:
        r["rain_mm"] = round(r["rain_mm"] / total * rain_total, 1)
    return hours


async def _latest_river(session: AsyncSession, district_id: str) -> tuple[float | None, str]:
    """Carry forward the last stored river reading (Open-Meteo has no river data)."""
    row = (
        await session.execute(
            select(DistrictWeatherSample.river_level_m, DistrictWeatherSample.river_trend)
            .where(
                DistrictWeatherSample.district_id == district_id,
                DistrictWeatherSample.river_trend.is_not(None),
            )
            .order_by(DistrictWeatherSample.ts.desc())
            .limit(1)
        )
    ).first()
    if row:
        return row[0], row[1]
    return None, "steady"


async def _store_hours(
    session: AsyncSession,
    district_id: str,
    hours: list[dict],
    source: str,
    river_level_m: float | None,
    river_trend: str,
) -> int:
    """Replace the trailing-window samples for a district (idempotent re-run)."""
    if not hours:
        return 0
    window_start = min(r["ts"] for r in hours)
    await session.execute(
        delete(DistrictWeatherSample).where(
            DistrictWeatherSample.district_id == district_id,
            DistrictWeatherSample.ts >= window_start,
        )
    )
    for r in hours:
        session.add(
            DistrictWeatherSample(
                district_id=district_id,
                ts=r["ts"],
                rain_mm=r["rain_mm"],
                temp_c=r["temp_c"],
                humidity_pct=r["humidity_pct"],
                wind_kph=r["wind_kph"],
                river_level_m=river_level_m,
                river_trend=river_trend,
                source=source,
            )
        )
    await session.flush()
    return len(hours)


async def ingest_district(
    session: AsyncSession,
    district: District,
    settings: Settings | None = None,
) -> IngestResult:
    """Ingest one district: live fetch when enabled, else simulated fallback.

    Never raises for weather reasons — a failed live fetch degrades to the
    simulated feed and records the error on the result.
    """
    settings = settings or get_settings()
    source = "simulated"
    error: str | None = None
    hours: list[dict] = []
    if settings.weather_mode == "live":
        try:
            hours = await fetch_open_meteo(
                district.lat, district.lon, settings.weather_api_url
            )
            source = "live"
        except WeatherFetchError as exc:
            error = str(exc)
            log.warning(
                "live weather fetch failed for %s (%s) — falling back to simulated",
                district.id, error,
            )
    if not hours:
        hours = simulated_hours(district.id)
        source = "simulated"
    river_level_m, river_trend = await _latest_river(session, district.id)
    n = await _store_hours(session, district.id, hours, source, river_level_m, river_trend)
    await session.commit()
    return IngestResult(district_id=district.id, source=source, hours_written=n, error=error)


async def ingest_all(
    session: AsyncSession,
    settings: Settings | None = None,
    district_ids: list[str] | None = None,
) -> list[IngestResult]:
    """Ingest every tracked district (all DB districts when ids is None)."""
    settings = settings or get_settings()
    stmt = select(District).order_by(District.id)
    if district_ids:
        stmt = stmt.where(District.id.in_(district_ids))
    districts = (await session.execute(stmt)).scalars().all()
    results: list[IngestResult] = []
    for d in districts:
        results.append(await ingest_district(session, d, settings))
    return results
