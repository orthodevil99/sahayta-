# Early-Warning Pipeline — `backend/warnings/`

Weather → district risk → threshold alerts. Runs as an asyncio background loop
inside the FastAPI lifespan (see `scheduler.py`; wired in `app/main.py`).

## Data flow

```
Open-Meteo ──GET──▶ ingest.py ──▶ DistrictWeatherSample (24 hourly rows/district)
   │ on ANY failure
   ▼
data/weather-sample.json ──▶ simulated_hours()  (DETERMINISTIC, labeled "simulated")
                                        │
                                        ▼
recompute.py: trailing-24h aggregate ─▶ app/services.risk.score_district (SHARED v1 formula)
                                        │  (+ seed-hint normalization in simulated mode, disclosed)
                                        ▼
                              DistrictRisk rows ──▶ WS risk.updated
                                        │
thresholds.py: prev ≤ 70 < new → advisory broadcast (severity 3)
               prev ≤ 85 < new → warning broadcast  (severity 4, implies advisory)
```

## External calls (every one)

### 1. Open-Meteo forecast API — the only external network call

- **URL:** `GET {SAHAYTA_WEATHER_API_URL}` (default `https://api.open-meteo.com/v1/forecast`)
- **Params:** `latitude`, `longitude` (district center, 4 dp),
  `hourly=temperature_2m,precipitation,relative_humidity_2m,wind_speed_10m`,
  `past_days=1`, `forecast_days=1`, `timezone=UTC`,
  `temperature_unit=celsius`, `wind_speed_unit=ms`, `precipitation_unit=mm`
  (explicit SI units — parsing never depends on API defaults; wind m/s is
  converted to km/h on ingest).
- **Auth:** none — Open-Meteo is keyless for non-commercial use.
- **Schedule:** every `SAHAYTA_WEATHER_INGEST_MINUTES` (default 15) via the
  lifespan background task. First cycle is delayed one full interval so boot
  stays fast. Single-worker assumption (`uvicorn --workers 1`); with N workers
  each would run the loop.
- **Timeout:** 20 s (`FETCH_TIMEOUT_S`).
- **Validation:** HTTP 200, JSON body, `hourly` with the four arrays present,
  equal length, ≥ 24 entries; timestamps parse as ISO. Anything else →
  `WeatherFetchError`.
- **Failure behavior:** on ANY failure (DNS, connect/read timeout, HTTP error,
  malformed JSON, short arrays) the district falls back to the simulated feed;
  the error is logged and recorded on the `IngestResult`, and
  `weather_source` is stored as `"simulated"`. Ingestion never raises for
  weather reasons and never blocks the rest of the cycle.

### 2. Simulated feed (fallback AND default mode)

- **Source:** `data/weather-sample.json` (ALL SYNTHETIC — see
  `data/DEMO_DATA_README.md`), trailing daily record per district.
- **Method:** `ingest.simulated_hours()` — deterministic diurnal projection
  (rain sums exactly to the daily total; temp/humidity/wind get fixed diurnal
  shapes + hash-based jitter; no `random` module, stable across runs).
- **Labeling:** `DistrictWeatherSample.source = "simulated"` →
  `DistrictRisk.weather_source = "simulated"` → API responses
  (`GET /api/districts/{id}/risk`, `/forecast`, `/api/warnings/status`) →
  frontend "SIMULATED FEED" badge. Never presented as live.
- **River data:** Open-Meteo has no river series, so `river_trend` /
  `river_level_m` are carried forward from the most recent stored sample
  (seeded from the synthetic series). The risk formula still gets a river
  signal, but it is explicitly NOT a live river reading.

### 3. Internal calls (no network)

- `POST /api/alerts/broadcast` semantics are reused via direct service call
  (`thresholds.broadcast_threshold_alert` → `services.alerts_render`,
  `Alert` row, audit log, WS `alert.broadcast`, actor `system:early-warning`).
  The worker never HTTP-calls itself.
- WS `risk.updated` is emitted via the in-process hub (`routers.common.emit`).

## Thresholds & broadcasts

| Rule | Meaning | Broadcast severity | Alert type |
|---|---|---|---|
| `prev ≤ 70 < new` | advisory | 3 | from dominant factor |
| `prev ≤ 85 < new` | warning | 4 | from dominant factor |

Alert type comes from the top contributing factor: `rainfall_24h_mm` /
`river_level_trend` → `flood`; `heat_index` → `heatwave`; `wind_kph` →
`cyclone`. A single jump crossing both fires only the warning. At most one
automatic broadcast per (district, type) per 24 h (deduplication).

## Seed hints (demo calibration)

In **simulated** mode only, `recompute` applies `data/weather-sample.json`
`seed_hints` (Patna → 82/high) exactly like `seed.py` does: factor
contributions are scaled to sum to the hint and each factor note says
"(scaled to seed-hint risk)". This keeps the demo-scenario acceptance value
stable across recompute cycles. In **live** mode the pure formula runs — honest
numbers, no hints.

## Manual trigger

```bash
cd backend && .venv/bin/python -c "
import asyncio
from warnings.scheduler import run_cycle
print(asyncio.run(run_cycle()))"
```

## Backtest

```bash
cd backend && .venv/bin/python -m warnings.backtest   # → warnings/BACKTEST_REPORT.md
```

## Files

| File | Owns |
|---|---|
| `ingest.py` | Open-Meteo fetch, simulated fallback, sample persistence |
| `recompute.py` | trailing-24h aggregate → v1 formula → `DistrictRisk` rows |
| `thresholds.py` | crossing detection → automatic multilingual broadcasts |
| `scheduler.py` | lifespan background loop + `run_cycle()` |
| `backtest.py` | 30-day replay → `BACKTEST_REPORT.md` |
| `NOTES-agent7.md` | design decisions |
