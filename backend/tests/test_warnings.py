"""Tests: early-warning pipeline — ingestion, recompute, thresholds, backtest.

Covers Agent 7's acceptance surface:
- Open-Meteo fetch: success path, malformed payload rejection, ANY failure →
  labeled simulated fallback (never raises, never presents sim as live).
- Risk recompute: seed-hint stability in simulated mode (Patna stays 82/high),
  no duplicate rows on unchanged recompute.
- Thresholds: upward crossing → automatic broadcast (deduplicated); audit +
  WS event emitted.
- Act 6 endpoints: /api/warnings/status and /api/districts/{id}/forecast shape.
- Backtest: deterministic; event-rule sanity on the Patna flood peak.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.models import Alert, AuditLog, District, DistrictRisk, DistrictWeatherSample
from tests.conftest import _admin_headers, _guest_headers
# NOTE (Wave 3, Agent 8): backend/warnings/ cannot be imported as `warnings`
# — the stdlib module is pre-cached in sys.modules. app.main (imported by
# conftest) loads it by file location as `sahayta_warnings`; import from that
# alias instead. See app/main.py.
from sahayta_warnings import (
    ADVISORY_THRESHOLD,
    WARNING_THRESHOLD,
    check_thresholds,
    ingest_district,
)
from sahayta_warnings.backtest import run_backtest
from sahayta_warnings.ingest import (
    WeatherFetchError,
    _parse_open_meteo,
    fetch_open_meteo,
    simulated_hours,
)
from sahayta_warnings.recompute import recompute_district
from sahayta_warnings.thresholds import broadcast_threshold_alert, process_crossings


# ---------------------------------------------------------------- live fetch

def _open_meteo_payload(n=48, wind_ms=5.0):
    base = datetime(2026, 10, 5, tzinfo=timezone.utc)
    return {
        "hourly": {
            "time": [(base + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(n)],
            "temperature_2m": [30.0] * n,
            "precipitation": [2.0] * n,
            "relative_humidity_2m": [85.0] * n,
            "wind_speed_10m": [wind_ms] * n,  # m/s (we request wind_speed_unit=ms)
        }
    }


async def test_parse_open_meteo_ok_and_unit_conversion():
    hours = _parse_open_meteo(_open_meteo_payload())
    assert len(hours) == 24  # trailing window
    assert hours[0]["rain_mm"] == 2.0
    assert hours[0]["wind_kph"] == pytest.approx(5.0 * 3.6)  # m/s → km/h
    assert hours[0]["ts"].tzinfo is not None


async def test_parse_open_meteo_rejects_malformed():
    bad = _open_meteo_payload()
    bad["hourly"]["precipitation"] = bad["hourly"]["precipitation"][:10]  # short
    with pytest.raises(WeatherFetchError):
        _parse_open_meteo(bad)
    with pytest.raises(WeatherFetchError):
        _parse_open_meteo({"hourly": {}})
    with pytest.raises(WeatherFetchError):
        _parse_open_meteo({"nope": 1})


async def test_fetch_open_meteo_http_error(monkeypatch):
    class Boom:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None, **k):
            raise httpx.ConnectError("dns down")

    monkeypatch.setattr(httpx, "AsyncClient", Boom)
    with pytest.raises(WeatherFetchError):
        await fetch_open_meteo(25.6, 85.1, "https://api.open-meteo.com/v1/forecast")


# ------------------------------------------------------------------ ingest

async def test_ingest_live_success(session, monkeypatch):
    from sahayta_warnings import ingest as ingest_mod

    hours = simulated_hours("patna")

    async def fake_fetch(lat, lon, api_url, timeout_s=20):
        assert abs(lat - 25.5941) < 0.01  # district coords actually used
        return hours

    monkeypatch.setattr(ingest_mod, "fetch_open_meteo", fake_fetch)
    monkeypatch.setattr(get_settings(), "weather_mode", "live")
    district = await session.get(District, "patna")
    res = await ingest_district(session, district)
    assert res.source == "live" and res.error is None and res.hours_written == 24
    n = (await session.execute(
        select(func.count()).select_from(DistrictWeatherSample)
        .where(DistrictWeatherSample.district_id == "patna",
               DistrictWeatherSample.source == "live")
    )).scalar_one()
    assert n == 24


async def test_ingest_failure_falls_back_to_simulated(session, monkeypatch):
    from sahayta_warnings import ingest as ingest_mod

    async def fake_fetch(lat, lon, api_url, timeout_s=20):
        raise WeatherFetchError("network failure: ConnectError")

    monkeypatch.setattr(ingest_mod, "fetch_open_meteo", fake_fetch)
    monkeypatch.setattr(get_settings(), "weather_mode", "live")
    district = await session.get(District, "patna")
    res = await ingest_district(session, district)
    # ANY failure → simulated, labeled, never raises
    assert res.source == "simulated" and res.error and res.hours_written == 24
    src = (await session.execute(
        select(DistrictWeatherSample.source)
        .where(DistrictWeatherSample.district_id == "patna")
        .order_by(DistrictWeatherSample.ts.desc()).limit(1)
    )).scalar_one()
    assert src == "simulated"


async def test_simulated_hours_deterministic():
    a = simulated_hours("patna")
    b = simulated_hours("patna")
    assert [r["rain_mm"] for r in a] == [r["rain_mm"] for r in b]
    assert len(a) == 24
    # rain sums to the sample's daily total
    import json
    day = json.load(open("/home/hatch/workspace/warriorhacks-sahayta/sahayta/data/weather-sample.json"))["districts"]["patna"][-1]
    assert sum(r["rain_mm"] for r in a) == pytest.approx(day["rain_mm"], abs=1.0)


# ---------------------------------------------------------------- recompute

async def test_recompute_patna_stays_82_high_simulated(session):
    new_row, prev = await recompute_district(session, "patna")
    # Seed already stored 82/high; recompute must reproduce it exactly
    # (seed-hint path mirrors seed.py) — or report no change.
    latest = (await session.execute(
        select(DistrictRisk).where(DistrictRisk.district_id == "patna")
        .order_by(DistrictRisk.computed_at.desc()).limit(1)
    )).scalar_one()
    assert latest.risk == 82 and latest.risk_level == "high"
    assert latest.weather_source == "simulated"
    assert any("rainfall_24h_mm" in f["name"] for f in latest.factors)
    # Second recompute with identical inputs writes no duplicate row.
    before = (await session.execute(
        select(func.count()).select_from(DistrictRisk)
        .where(DistrictRisk.district_id == "patna")
    )).scalar_one()
    new2, _ = await recompute_district(session, "patna")
    after = (await session.execute(
        select(func.count()).select_from(DistrictRisk)
        .where(DistrictRisk.district_id == "patna")
    )).scalar_one()
    assert new2 is None and after == before


# ---------------------------------------------------------------- thresholds

def test_check_thresholds_pure():
    assert check_thresholds(None, 90)[0]["kind"] == "warning"
    assert check_thresholds(40, 80)[0]["kind"] == "advisory"
    assert check_thresholds(40, 80)[0]["severity"] == 3
    assert check_thresholds(80, 90)[0]["kind"] == "warning"  # highest only
    assert check_thresholds(75, 80) == []     # no crossing, already above
    assert check_thresholds(90, 60) == []     # downward moves never fire


async def _seed_storm(session, district_id="gaya", rain_total=190.0):
    """Write 24 stormy hourly samples + a calm previous risk row."""
    now = datetime.now(timezone.utc)
    for h in range(24):
        session.add(DistrictWeatherSample(
            district_id=district_id,
            ts=now - timedelta(hours=23 - h),
            rain_mm=round(rain_total / 24, 1),
            temp_c=31.0, humidity_pct=95.0, wind_kph=12.0,
            river_level_m=49.0, river_trend="rising", source="simulated",
        ))
    prev = DistrictRisk(district_id=district_id, risk=40, risk_level="moderate",
                        factors=[], advisory="calm", weather_source="simulated",
                        computed_at=now - timedelta(hours=2))
    session.add(prev)
    await session.commit()
    return prev


async def test_threshold_crossing_broadcasts_and_dedups(session):
    await _seed_storm(session)
    new_row, prev_row = await recompute_district(session, "gaya")
    assert new_row is not None and new_row.risk > ADVISORY_THRESHOLD
    assert new_row.risk < WARNING_THRESHOLD  # flood-only caps below severe (documented)
    events = check_thresholds(prev_row.risk, new_row.risk)
    assert events and events[0]["kind"] == "advisory"

    sent = await process_crossings(session, [(new_row, prev_row)])
    assert len(sent) == 1
    alert = sent[0]
    assert alert.created_by == "system:early-warning"
    assert alert.district_ids == ["gaya"] and alert.type == "flood"
    assert alert.severity == 3 and len(alert.messages) == 10  # all languages
    assert all(len(m) <= 480 for m in alert.messages.values())  # SMS-length

    audit = (await session.execute(
        select(AuditLog).where(AuditLog.action == "alert.broadcast",
                               AuditLog.actor == "system:early-warning")
    )).scalars().all()
    assert len(audit) == 1 and audit[0].details["trigger"] == "early_warning_threshold"

    # Second pass with the same rows → dedup, no second broadcast.
    sent2 = await process_crossings(session, [(new_row, prev_row)])
    assert sent2 == []
    n_alerts = (await session.execute(
        select(func.count()).select_from(Alert)
        .where(Alert.created_by == "system:early-warning")
    )).scalar_one()
    assert n_alerts == 1


# ------------------------------------------------------- Act 6 HTTP surface

async def test_warnings_status_shape(client):
    r = await client.get("/api/warnings/status", headers=_guest_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert body["districts_tracked"] == 20
    assert body["last_ingest_ok"] is True
    assert body["weather_api"] == "https://api.open-meteo.com/v1/forecast"


async def test_forecast_72_hours_with_risk(client):
    r = await client.get("/api/districts/patna/forecast", headers=_guest_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["district_id"] == "patna"
    assert body["weather_source"] in ("live", "simulated")
    assert len(body["hours"]) == 72
    for h in body["hours"]:
        assert "risk" in h and "risk_level" in h
        assert 0 <= h["risk"] <= 100
        assert h["risk_level"] in ("low", "moderate", "high", "severe")


async def test_forecast_404_unknown_district(client):
    r = await client.get("/api/districts/nope/forecast", headers=_guest_headers())
    assert r.status_code == 404


# ------------------------------------------------------------------ backtest

async def test_backtest_deterministic_and_sane():
    m1 = run_backtest()
    m2 = run_backtest()
    assert m1 == m2  # pure functions, no randomness
    assert m1["districts"] == 20 and m1["district_days"] == 580
    assert m1["event_days"] > 0
    # Patna flood peak (2026-10-06, 184.7 mm) is an event day by the rain rule.
    patna_peak = [e for e in m1["events"]
                  if e["district"] == "patna" and e["date"] == "2026-10-06"]
    assert patna_peak and "rain" in patna_peak[0]["reason"]
    for level in ("warning", "advisory"):
        for k in ("precision", "recall"):
            assert 0.0 <= m1[level][k] <= 1.0
