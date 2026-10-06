# NOTES — Agent 7 (Early Warning, Wave 3)

## What was built

`backend/warnings/` — the weather → risk → threshold-alert loop:

- `ingest.py` — Open-Meteo polling (keyless) with ANY-failure → labeled
  simulated fallback; persists 24 trailing hourly `DistrictWeatherSample`
  rows per district.
- `recompute.py` — trailing-24h aggregate → shared v1 formula
  (`app.services.risk.score_district`, imported not reimplemented) →
  `DistrictRisk` rows (written only on change) → WS `risk.updated`.
- `thresholds.py` — upward crossings of 70 (advisory, severity 3) / 85
  (warning, severity 4) trigger automatic multilingual broadcasts through the
  same render/persist/audit path as the admin endpoint (actor
  `system:early-warning`), deduplicated to 1 per (district, type) per 24 h.
- `scheduler.py` — asyncio background loop in the app lifespan; first cycle
  delayed one interval so boot stays fast and tests are undisturbed.
- `backtest.py` — 30-day replay → `BACKTEST_REPORT.md`.
- `GET /api/warnings/status` and `GET /api/districts/{id}/forecast` already
  existed (Agent 5); this wave makes the pipeline behind them real and keeps
  the demo-scenario Act 6 acceptance values green.

## Deliberate decisions

1. **Package named `warnings` shadows stdlib `warnings`** whenever `backend/`
   is on `sys.path` (it always is). `__init__.py` therefore (a) re-exports the
   real stdlib surface (`warn`, `filterwarnings`, …) loaded from the stdlib
   file location, and (b) uses lazy PEP-562 submodule exports so importing the
   package never pulls in httpx. Verified: `import random` + `from warnings
   import warn` + `python -m warnings.backtest` all work.
2. **Absolute imports inside the package** (`from app.config import …`, not
   `from ..app…`) — the package is imported as top-level `warnings`, so
   double-dot relative imports escape the package. Matches `seed.py`'s
   convention.
3. **Seed hints applied in simulated mode only** (mirrors `seed.py` exactly).
   Patna stays 82/high across recompute cycles → demo Acts 5–6 stable. Live
   mode runs the pure formula — honest numbers, no calibration.
4. **No new DistrictRisk row when nothing changed** — avoids a no-op row every
   15 min; the time series stays meaningful.
5. **Threshold broadcast reuses the admin path as a service call**, never HTTP
   to self. Dedup via recent `Alert` rows (Python-side 24 h window check —
   SQLite JSON containment queries are clumsy; 25-row scan is fine at v1
   scale).
6. **Alert type from the dominant factor** (rain/river → flood, heat →
   heatwave, wind → cyclone) rather than hardcoding flood — cheap and more
   truthful for Nagpur/Puri.
7. **Wind units fixed properly**: request `wind_speed_unit=ms` explicitly and
   convert to km/h, instead of relying on the API default.
8. **River trend carried forward** from the last stored sample — Open-Meteo has
   no river data; documented in README, never implied to be live.
9. **`SAHAYTA_DISTRICTS` default changed `patna` → `all`** (config default was
   an Agent 5 placeholder; nothing in the frozen contracts references it).
   `"all"`/empty = every district in the DB; otherwise the listed slugs.
   `.env.example` updated.

## Backtest headline (honest, not flattering)

30-day replay: warning/advisory precision = recall = **0.0**. The analysis in
`BACKTEST_REPORT.md` shows why: the v1 formula's theoretical max for a pure
flood is **82**, so the global `> 85` warning band is unreachable for floods
by construction (severe needs heat/cyclone on top), and 29/30 event days are
SOS-defined on days whose weather was still moderate (SOS is a lagging
indicator). **Recommendation for the coordinator**: re-weight flood components
or make thresholds hazard-specific — NOT applied here (formula is frozen and
shared with the AI engine).

## Known gaps / for later waves

- Multi-worker deployments would run N scheduler loops — document
  `--workers 1` for v1 (README).
- Threshold broadcasts are Hindi-first templates via `render_multilingual`
  (same as admin path); no LLM rephrasing unless configured.
- No `POST /api/warnings/ingest` manual-trigger endpoint — contracts are
  frozen and it would need a version bump; `run_cycle()` is importable
  instead (README documents the one-liner).
- The forecast endpoint still uses the deterministic projection from stored
  samples (Agent 5's design); ingestion keeps the projection base fresh.
