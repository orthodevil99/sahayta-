# Sahayta — "When disaster strikes, help finds you."

A disaster-response OS for India. A citizen uploads a photo of rising floodwater →
AI estimates severity, geotags it, and files a verified SOS → volunteers get
matched and dispatched → district officials watch a live command view →
multilingual alerts go out to everyone at risk. Offline-first, because networks
die in disasters.

Built by a solo student (prakhar) plus 15 coordinated agent waves for
**WarriorHacks 2.0** (HACKATHON track — code required). Submission deadline:
**Oct 14, 2026, 10:15 AM IST**.

> **Demo data notice:** every dataset in `data/` is **synthetic**, generated for
> this project. It is labeled `DEMO DATA` in the UI and never presented as real.
> See `data/DEMO_DATA_README.md`.

---

## 5-minute quickstart

**Fastest path — frontend demo mode, zero backend, zero keys:**

```bash
cd frontend
npm install
npm run dev
# open http://localhost:3000/?demo=1  →  click "▶ Play Patna flood demo"
```

The app runs the full Patna flood scenario in-browser from bundled synthetic
data. No backend, no API keys, no network needed.

**Full stack (backend + AI engine + live API):**

```bash
# terminal 1 — backend
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python seed.py --fresh        # loads all synthetic data
.venv/bin/python -m uvicorn app.main:app --port 8000
# API docs: http://127.0.0.1:8000/docs

# terminal 2 — frontend against the live backend
cd frontend
npm install
cp .env.example .env.local              # set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

With no `SAHAYTA_LLM_*` keys set, the AI pipeline runs its deterministic
rule-based fallback (every assessment honestly labels its `model` path), and
weather runs on the labeled simulated feed. The demo works with **zero
credentials** — by design.

**Deterministic acceptance replay** (the 14-step Patna scenario, exit 0 on pass):

```bash
cd packages/simulation
python demo_director.py --scenario patna-flood   # expect 14/14 PASS
```

## Environment setup

All configuration is env-driven; nothing secret is hardcoded. Copy the template
and fill what you need:

```bash
cp .env.example .env   # never commit a filled .env
```

Key variables (full list in `.env.example`):

| Variable | Default | Meaning |
|---|---|---|
| `SAHAYTA_DATABASE_URL` | sqlite file in `backend/` | DB URL (Postgres-ready via asyncpg) |
| `SAHAYTA_ADMIN_KEY` | `demo-admin-key` | admin key — **change in production** |
| `SAHAYTA_LLM_BASE_URL` / `SAHAYTA_LLM_MODEL` | (unset) | OpenAI-compatible LLM endpoint; unset = rule fallback |
| `SAHAYTA_WEATHER_MODE` | `simulated` | `live` polls Open-Meteo (keyless); failures fall back labeled |
| `NEXT_PUBLIC_API_URL` | (unset → demo mode) | frontend backend URL |

## Architecture

Modular monolith + offline-first PWA. One FastAPI process, one Next.js app, one
database URL. The AI engine is an importable package with a strict seam
(`pipeline.assess_and_route`), extractable later without changing callers.
Full design: `docs/architecture.md`. Copy-pasteable diagram:
`docs/architecture-diagram.md`.

```
 phone browsers (citizens, volunteers, district officials)
        │  HTTPS (REST/JSON) + WSS (live events)
        ▼
 ┌─ FRONTEND — Next.js 14 PWA ──────────────────────────────┐
 │ / (landing)  /report (SOS wizard)  /board (live SOS map) │
 │ /volunteer (tasks)  /alerts (10-lang feed)  /admin       │
 │ Service Worker: app-shell cache + SOS outbox + bg sync   │
 │ Leaflet heatmap · i18n: 10 languages · low-bandwidth mode│
 │ lib/api.ts — typed client (matches api-contracts.md)    │
 └──────────────────────────┬──────────────────────────────┘
                            │ REST + WS /api/stream
                            ▼
 ┌─ BACKEND — FastAPI (one deployable) ─────────────────────┐
 │ routers: sos · assess · volunteers · tasks · shelters    │
 │          districts · alerts · admin · safety · warnings  │
 │ packages/ai-engine  → severity · triage · alerts · risk  │
 │                       pipeline (LLM + rule fallback)     │
 │ packages/simulation → scenario gen · load sim · demo dir │
 │ workers (asyncio): weather-ingest → risk → thresholds    │
 └──────────────────────────┬──────────────────────────────┘
                            │ SQLAlchemy 2.0 / Alembic
                            ▼
   SQLite (demo) ⇄ PostgreSQL (prod) — one URL env var

   LLM provider (env-configured, OpenAI-compatible; default GLM/Zhipu)
   called ONLY from packages/ai-engine — never directly by the backend.
```

The SOS hero loop: **report** (photo + text + geotag, queued offline if needed)
→ **AI assess** (severity 1–5 + rationale + category + priority, synchronous in
`POST /api/sos`, intake never fails) → **match** (skills × distance ×
availability → ranked volunteers) → **dispatch** (assign → accept → en-route →
complete, SOS status follows) → **broadcast** (one alert → 10-language
SMS-length messages) → **command view** (live map, risk panel, timeline, PDF
export).

## API overview

Contracts are **frozen at v1.3** (`docs/api-contracts.md` — every endpoint,
JSON shape, status code, and WS event; `MIGRATION.md` logs the deltas).

| Area | Endpoints |
|---|---|
| SOS | `POST /api/sos` · `GET /api/sos` (district/severity/status filters) · `PATCH /api/sos/{id}` · `POST /api/sos/{id}/verify` · `POST /api/assess` · `POST /api/media` |
| Volunteers & tasks | `/api/volunteers` (+ `/reputation`) · `/api/tasks` (match, assign, accept/decline → auto re-offer, en-route, complete with photo proof) |
| Shelters & districts | `GET /api/shelters` · `GET /api/districts/{id}/risk` · `GET /api/districts/{id}/forecast` (72h) |
| Alerts | `POST /api/alerts/broadcast` · `GET /api/alerts` (`?lang=all` for the 10-language map) |
| Admin | `/api/admin/overview` · verify queue · safety flags · audit log · incident export (real PDF) |
| Safety | dedup, conflict triage, spam throttle, reporter trust tiers |
| Warnings | `GET /api/warnings/status` · risk recompute worker (Open-Meteo → labeled simulated fallback) |
| Realtime | `WS /api/stream` — `sos.created/assessed`, `task.assigned/updated`, `alert.broadcast`, `risk.updated` |

## Module map

```
frontend/                 Next.js 14 PWA — 6 routes, 16 design-system components,
                          typed API client, service worker, Leaflet heatmap,
                          10-language dictionaries, seeded demo mode (?demo=1)
backend/                  FastAPI — 11 routers, SQLAlchemy 2.0 + Alembic,
                          WS hub, asyncio weather/risk workers, seed.py,
                          pytest suite (79/79 green)
packages/ai-engine/       severity.py · triage.py · alerts.py · risk.py ·
                          pipeline.py — provider-agnostic (env LLM, OpenAI-compat),
                          honest rule fallback, token accounting, 65/65 tests
packages/simulation/      2,000-scenario generator · load simulator ·
                          demo_director.py (14/14 PASS) · SIMULATION_REPORT.md
data/                     synthetic seed data (ALL labeled DEMO DATA):
                          3,000 SOS reports · 5,000 severity labels · 500 shelters ·
                          1,000 volunteers · 20 districts × 30d weather ·
                          alert templates (flood/heatwave/cyclone × 10 languages)
docs/                     architecture.md · api-contracts.md (v1.3 frozen) ·
                          data-models.md · demo-scenario.md (acceptance test) ·
                          design-system.md · wireframes/ · safety.md ·
                          i18n-coverage.md · launch/ (video script, Devpost copy)
```

## Measured results (every number traceable)

| Claim | Number | Source |
|---|---|---|
| Backend tests | 79/79 pass | `cd backend && .venv/bin/python -m pytest tests/ -q` |
| AI engine tests | 65/65 pass | `packages/ai-engine/tests` |
| Frontend tests | 6/6 files pass; `tsc` clean; `next build` clean (9 routes) | `cd frontend && npm test` |
| Simulation tests | 12/12 pass | `packages/simulation/tests` |
| Load (localhost VM) | 275 requests, **0 errors**, 16.8 req/s, **p95 107.0 ms** | `packages/simulation/load_results.json` |
| Severity estimator | **0.60 exact / 1.00 within-one** on seeded n=600 sample of the 5,000 hand-labeled fixtures | `packages/ai-engine/NOTES-agent6.md`, `data/severity-labels.csv` |
| Demo director | **14/14 PASS**, exit 0 | `packages/simulation/SIMULATION_REPORT.md` |
| i18n coverage | **10/10 locales × 311 keys = 100%** (computed, not claimed) | `docs/i18n-coverage.md`, `scripts/i18n-coverage.mjs` |
| Scenario corpus | 2,000 scenarios; 271,513 synthetic SOS events | `packages/simulation/scenarios/index.json` |
| Early-warning backtest | **0.0/0.0** precision/recall — documented limitation, see below | `backend/warnings/BACKTEST_REPORT.md` |

## Honest limitations

- **All data is synthetic.** Nothing here has seen a real disaster; the demo
  fixtures are labeled in every UI surface.
- **The default AI path is rules, not magic.** Without LLM keys, severity
  comes from a tuned keyword scorer — it is honest about it (`model:
  rule-fallback-v1`) and the demo fixture still scores 4/5.
- **Early warning is unproven.** The backtest measured 0.0 precision/recall:
  the v1 risk formula caps flood-only risk at 82, below the >85 warning band,
  so warnings can't fire for floods by construction. The pipeline mechanics
  work; the predictive skill is not validated. (Source:
  `backend/warnings/BACKTEST_REPORT.md`.)
- **Translations are hand-written but not native-speaker reviewed.**
- **Voice input** on the SOS form is progressive enhancement, untested against
  live speech; the fallback path is the tested one.
- **Load numbers are single-machine localhost**, sequential requests — not
  production capacity.
- **No real SMS gateway** — alert "sending" renders templates, clearly labeled.
- **Admin dashboard is online-only by design**; rate limits are in-memory.

## Roadmap

- Real SMS gateway integration behind the template renderer
- Native-speaker review pass over the 10 locales
- Hazard-specific warning thresholds (the backtest's recommendation)
- Postgres + proper WS auth tickets for production deploy
- Extract `packages/ai-engine` into a standalone service via the documented seam
- Volunteer GPS check-in (currently last-known location only)

## Submission

WarriorHacks 2.0 — HACKATHON track. Submission kit: `docs/launch/`
(video script + shot list + voiceover), `docs/launch/devpost-copy.md`,
`docs/launch/devpost-fields.md`. Demo video: 2:30 (Variant A recommended).
