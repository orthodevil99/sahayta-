# Sahayta — System Architecture

**Version:** 1.0 (Wave 1 — Product Architect)
**Status:** CONTRACT SOURCE OF TRUTH for Waves 2–5. Later agents implement the interfaces defined here verbatim.
**One-line pitch:** "When disaster strikes, help finds you." A disaster-response OS for India.

---

## 0. Context & Constraints

Sahayta is built for **WarriorHacks 2.0** (HACKATHON track — code required) by a solo builder
(prakhar) plus coordinated agent waves, with an internal hard deadline of **Oct 13, 2026 EOD IST**
and a Devpost submission deadline of **Oct 14, 2026, 10:15 AM IST**. Judging criteria:
**Impact · Feasibility · User Experience · Technical Craft**.

Hard constraints the architecture must respect:

1. **9 days, solo dev + agents.** The design must be buildable in parallel by independent
   agent waves with minimal integration risk. Every cross-module boundary is defined in
   `docs/api-contracts.md` and `docs/data-models.md` and frozen after Wave 2.
2. **Networks die in disasters.** The frontend is an offline-first PWA: app-shell caching,
   local SOS queueing with sync-on-reconnect, and a low-bandwidth text-first mode.
3. **No real API keys in the repo.** Everything secret lives in env vars (see `.env.example`).
   LLM access is provider-agnostic and env-configured; every AI call has a deterministic
   rule-based fallback so the demo runs with zero credentials.
4. **Demo determinism.** The "Monsoon flood in Patna district" scenario (see
   `docs/demo-scenario.md`) must run identically every time for video recording. The
   simulation package owns a deterministic "demo director" mode.
5. **All data is synthetic.** Every seed dataset is labeled DEMO DATA in the UI and README.
   Nothing is ever presented as real.
6. **10 Indian languages** across UI and alerts: Hindi, Hinglish, Bengali, Tamil, Telugu,
   Marathi, Gujarati, Kannada, Malayalam, Punjabi.

---

## 1. Chosen Architecture — Modular Monolith + Offline-First PWA

### 1.1 System text diagram

```
 ┌──────────────────────────────────────────────────────────────────────┐
 │  CLIENTS — phone browsers (citizens, volunteers, district officials) │
 │  Low bandwidth, intermittent connectivity, low-literacy friendly      │
 └──────────────────────────────┬───────────────────────────────────────┘
                                │  HTTPS (REST/JSON)  +  WSS (events)
                                ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │  FRONTEND — Next.js 14 PWA (App Router, Tailwind, TypeScript)        │
 │                                                                      │
 │  Screens (6):                    Cross-cutting:                      │
 │   /            landing           ┌──────────────────────────────┐    │
 │   /report      SOS intake       │ Service Worker: app-shell     │    │
 │   /board       SOS board        │ cache, SOS outbox queue,      │    │
 │   /volunteer   task view        │ background sync on reconnect  │    │
 │   /alerts      alerts feed      └──────────────────────────────┘    │
 │   /admin       command dash     Leaflet map (heatmap + pins)        │
 │                                i18n: 10 languages (next-intl)        │
 │  lib/api.ts — typed client implementing api-contracts.md            │
 │  Low-bandwidth mode toggle (text-first, no map tiles, no images)    │
 └──────────────────────────────┬───────────────────────────────────────┘
                                │ REST JSON  │  WebSocket events (WS /api/stream)
                                ▼            ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │  BACKEND — FastAPI, Python 3.11+ (MODULAR MONOLITH, one deployable)  │
 │                                                                      │
 │  Routers (one module each, own tests):                               │
 │   /api/sos         intake, list, status, verify                      │
 │   /api/assess      severity estimation entry point                   │
 │   /api/volunteers  profiles                                          │
 │   /api/tasks       matching, assign, accept, en-route, complete      │
 │   /api/shelters    directory                                         │
 │   /api/districts   risk scores, forecast                             │
 │   /api/alerts      broadcast composer + history                      │
 │   /api/admin       incident export, verify queue, audit log           │
 │   /api/safety      dedup, misinformation flags, rate limits           │
 │                                                                      │
 │  Internal packages (imported, NOT separate services):                │
 │   packages/ai-engine/   severity.py, triage.py, alerts.py,           │
 │                         risk.py, pipeline.py  (LLM + rule fallback)  │
 │   packages/simulation/  scenario gen, load sim, demo director         │
 │                                                                      │
 │  Background workers (asyncio, in-process):                           │
 │   weather-ingest  →  risk-recompute  →  threshold rules  →  alerts   │
 │                                                                      │
 │  Auth: API-key header (X-API-Key) for officials; guest mode (device  │
 │  UUID) for citizens/volunteers; rate limits per key/device.          │
 └──────────────────────────────┬───────────────────────────────────────┘
                                │ SQLAlchemy 2.0 (async)
                                ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │  DATABASE — SQLite (dev/demo) ⇄ PostgreSQL (prod), via one URL env   │
 │  Alembic migrations. Seed script loads data/*.json|csv.              │
 └──────────────────────────────────────────────────────────────────────┘

          ┌────────────────────────────────────────────────┐
          │  LLM PROVIDER (env-configured, OpenAI-compat)   │
          │  default: GLM (Zhipu) — SAHAYTA_LLM_BASE_URL +  │
          │  SAHAYTA_LLM_MODEL. Rule-based fallback always │
          │  available: ai-engine never hard-fails.         │
          └────────────────────────────────────────────────┘
                    ▲ called only from packages/ai-engine
                    │ (backend never calls the LLM directly)
```

### 1.2 Component responsibilities

| Component | Owns | Must never |
|---|---|---|
| Frontend PWA | All UI, offline queue, map rendering, i18n, demo-mode seeding | Call the LLM directly; trust client-side severity |
| FastAPI backend | Routing, auth, validation, orchestration, websockets, workers | Hardcode LLM model/URL; present synthetic data as real |
| packages/ai-engine | severity, triage, multilingual alerts, risk scoring, pipeline | Touch HTTP layer or DB; import from backend |
| packages/simulation | Scenario gen, load sim, deterministic demo director | Run in production request path |
| data/ | Synthetic seed datasets + DEMO_DATA_README.md | Contain real personal data or real API keys |

### 1.3 The SOS hero loop — data flow (numbered, end to end)

```
 1. CITIZEN — /report
    photo (file) + description (text, any of 10 langs) + geotag
    (GPS via browser geolocation OR manual Leaflet pin drop)
    → if offline: Service Worker stores SOS draft in IndexedDB outbox,
      UI shows "Queued — will send when online", background sync retries.
 2. FRONTEND → POST /api/sos  (multipart: photo + fields; or JSON if no photo)
 3. BACKEND — routers/sos.py
    a. Validate (Pydantic), virus/safety scan upload (safety module),
       compute photo perceptual hash for dedup.
    b. Persist SOSReport(status="reported") → DB.
    c. Call ai-engine.pipeline.assess_and_route(report):
         severity.py   → severity 1–5 + one-line rationale + area tags
                         (LLM if configured, else rule-based fallback)
         triage.py     → category (medical|rescue|food|shelter|
                         infrastructure) + priority + needed volunteer skills
    d. Persist SeverityAssessment; update SOSReport
       (severity, category, priority, status stays "reported").
    e. Emit WS event `sos.created` + `sos.assessed` on /api/stream.
 4. MATCHING — routers/tasks.py (triggered on assessment, or admin action)
    matching engine: needed_skills × volunteer.skills × haversine(km)
                     × availability → ranked list (score 0–100).
    Creates Task(sos_id, volunteer_id, status="assigned").
    Emits WS `task.assigned`. Volunteer notified (in-app + SMS-style template
    in their language — template only in demo, no real SMS gateway).
 5. VOLUNTEER — /volunteer task view: accept / decline → en-route → complete
    (photo proof optional). Each transition: PATCH /api/tasks/{id},
    audit-logged, WS `task.updated`, SOSReport status advances:
    reported → verified → help_on_way → resolved.
    (Verification: photo-hash dedup + admin verify queue; see safety module.)
 6. ALERTS — admin (or auto rule: district risk > 85) → POST /api/alerts/broadcast
    ai-engine/alerts.py renders one alert → 10-language SMS-length messages
    (ground-truth templates in data/alert-templates/, LLM for novel alerts).
    Persisted per language; WS `alert.broadcast`; /alerts feed updates.
 7. ADMIN — /admin command dashboard (role-gated via SAHAYTA_ADMIN_KEY):
    live SOS map + severity heatmap, district risk panel, volunteer availability
    board, broadcast composer, incident timeline, PDF incident export.
```

### 1.4 Early-warning flow

```
 weather-ingest worker (every 15 min, asyncio)
   → GET open API (Open-Meteo, no key) for tracked districts
   → on failure: fall back to SIMULATED feed, response tagged
     {"source": "simulated", "label": "DEMO DATA"} — never silent
   → store raw series (DistrictWeatherSample)
   → risk.py: weather series → risk 0–100 + contributing factors
   → persist DistrictRisk; WS `risk.updated`
   → threshold rules: risk > 70 → advisory alert draft; risk > 85 →
     warning alert draft → admin approve (1 click) → broadcast (flow §1.3.6)
```

### 1.5 Offline sync flow

```
 online:  normal REST + WS.
 offline: Service Worker intercepts POST /api/sos → IndexedDB outbox.
          UI badge: "2 reports queued".
 reconnect: background sync replays outbox in order, server dedups by
          client_report_id (UUID generated at draft time) → idempotent.
          WS reconnect with last_event_id → missed events replayed.
```

### 1.6 Security boundaries

- Trust boundary 1 (client → server): never trust client severity/category; server
  re-runs assessment. Rate limit: 20 SOS/hour per device UUID, 100/hour per API key.
- Trust boundary 2 (server → LLM): prompt-injectable citizen text never reaches a
  shell or SQL; LLM output is parsed as JSON with schema validation and clamped
  (severity forced into 1–5 int; unknown → fallback path).
- Trust boundary 3 (uploads): photo stored with random filename, content-type
  allowlist (jpeg/png/webp), 8 MB cap, EXIF stripped, perceptual hash for dedup.
- Admin routes require `X-Admin-Key == SAHAYTA_ADMIN_KEY`; wrong key → 403,
  logged to audit log. Demo mode uses a documented dummy key (`demo-admin-key`)
  and the UI banners "DEMO MODE".

---

## 2. Architecture Variants — Compared

Three candidate architectures were evaluated against the six hard constraints in §0.
Scoring: ++ strong fit, + adequate, − weak, −− disqualifying risk.

### Variant A — Modular monolith + offline-first PWA (CHOSEN)

One FastAPI process (routers + in-process packages + asyncio workers), one Next.js
PWA, one database URL. Internal packages (`ai-engine`, `simulation`) are imported
Python modules with clean interfaces — not network services.

### Variant B — Microservices (sos-service, ai-service, volunteer-service, alert-service, gateway)

Each capability a separately deployed service with its own DB, behind an API gateway;
async via a message broker (Redis Streams / RabbitMQ).

### Variant C — Serverless / JAMstack (Next.js API routes + serverless functions + BaaS)

Frontend and API as serverless functions; DB via hosted Postgres (Supabase/Neon);
realtime via a third-party pub/sub (Pusher/Ably); background jobs via cron triggers.

### Comparison matrix

| Criterion | A: Modular monolith | B: Microservices | C: Serverless/BaaS |
|---|---|---|---|
| Build velocity (9 days, agent waves) | ++ one repo, one deploy, contracts are function signatures + REST | −− service scaffolding, broker ops, contract drift across repos | + fast start, but function limits complicate WS + workers |
| Integration risk between waves | ++ shared Pydantic models; `pipeline.py` is one call | −− network boundaries multiply failure modes agents must mock | − cold starts + BaaS quotas hit the live demo |
| Offline-first PWA | ++ SW + outbox is frontend-local, backend-agnostic | + same, but more endpoints to queue against | + same, but replay targets are ephemeral functions |
| Realtime (WS live board) | ++ in-process WS hub, trivial fan-out | − needs broker + sticky sessions | −− serverless WS requires external pub/sub (extra vendor) |
| Background workers (weather/risk) | ++ asyncio in-process, zero infra | + dedicated worker service (more deployables) | − cron-triggered functions; 15-min cadence is awkward |
| Deterministic demo (demo director) | ++ replays against local API, fixed seed | − timing across services is nondeterministic | − cold starts make video takes flaky |
| Ops burden for solo dev | ++ `uvicorn` + one DB | −− N services, broker, gateway config | + managed, but vendor lock + usage caps |
| Cost (hackathon = $0 budget) | ++ runs on any free tier / laptop | − needs always-on infra | + free tiers exist, but WS/push vendors cost |
| Technical-craft story for judges | + "boring technology, deep AI" — craft lives in ai-engine | + impressive on paper, thin in 9 days | − looks like glued-together SaaS |
| Testability | ++ pytest over the whole loop in one process | − contract tests across services | − mocking BaaS SDKs everywhere |

### Verdict

**Variant A wins on every constraint that matters for this build.** The moat of Sahayta
is not infrastructure topology — it is the multi-agent AI pipeline (severity + triage +
multilingual alerts + risk scoring) and the synthetic disaster dataset. Variant A puts
all engineering hours into those two, while keeping deployment to "one backend, one
frontend, one database URL" — something a solo student can demo from a laptop with no
network at all. Variants B and C spend the 9 days on plumbing (brokers, gateways, vendor
quotas, cold starts) and introduce exactly the nondeterminism that would kill the
2–3 minute demo video.

**What we deliberately give up:** independent scaling of the AI pipeline and
per-service deploys. Mitigation: `packages/ai-engine` has a strict interface
(`pipeline.py::assess_and_route`) with no backend imports, so it can be extracted
into a service later without changing callers — the seam is documented in §3.

---

## 3. Module Map & Dependency Rules

```
frontend/                  Next.js 14 App Router + Tailwind + TypeScript
  app/                     routes: /, /report, /board, /volunteer, /alerts, /admin
  components/              Map, SOSCard, SeverityBadge, TaskList, AlertComposer, ...
  lib/api.ts               typed client — MUST match docs/api-contracts.md exactly
  lib/i18n/                10-language dictionaries (Wave 4 completes)
  public/sw.js             service worker: shell cache + SOS outbox + bg sync
  public/manifest.webmanifest

backend/                   FastAPI — single deployable
  app/main.py              app factory, CORS, WS hub, worker startup
  app/routers/             sos.py, assess.py, volunteers.py, tasks.py,
                           shelters.py, districts.py, alerts.py, admin.py,
                           safety.py, warnings.py
  app/models/              SQLAlchemy models (see docs/data-models.md)
  app/schemas/             Pydantic request/response (see docs/data-models.md)
  app/core/                config (env), auth, rate-limit, audit log
  app/workers/             weather_ingest.py, risk_recompute.py
  app/safety/              dedup.py, misinfo.py, spam.py
  tests/                   pytest — every route covered (Wave 2 Agent 5)
  alembic/                 migrations
  scripts/seed.py          loads data/ into a fresh DB

packages/ai-engine/        NO backend imports. Pure functions + one HTTP client.
  severity.py  triage.py  alerts.py  risk.py  pipeline.py  llm_client.py
  tests/  (mocked LLM + fixture tests vs data/severity-labels.csv)

packages/simulation/       scenario_gen.py, load_sim.py, demo_director.py
  SIMULATION_REPORT.md

data/                      synthetic seed data + DEMO_DATA_README.md
  sos-reports.json  severity-labels.csv  shelters.json  alert-templates/
  volunteers.json  weather-sample.json  scenarios/ (sample)

docs/                      architecture.md (this file), api-contracts.md,
                           data-models.md, demo-scenario.md, design-system.md,
                           wireframes/, demo-storyboard.md, i18n-coverage.md,
                           safety.md, launch/
```

**Dependency rules (enforced by code review in Wave 5):**

1. `frontend → backend` only via `lib/api.ts` (typed, matches api-contracts.md).
2. `backend → packages/ai-engine` only via `pipeline.assess_and_route`,
   `alerts.render_multilingual`, `risk.score_district`. Never import LLM client directly.
3. `packages/ai-engine →` nothing inside `backend/`. Only stdlib + `httpx` + `pydantic`.
4. `packages/simulation →` backend only via public REST API (it is a client, like the frontend).
5. `data/` is read by seed scripts and ai-engine fixture tests; never mutated at runtime.

---

## 4. Data Stores & Env-Driven Configuration

- **Primary DB:** `SAHAYTA_DATABASE_URL` — SQLite (`sqlite+aiosqlite:///./sahayta.db`)
  for dev/demo; PostgreSQL (`postgresql+asyncpg://…`) for prod. Same SQLAlchemy models.
- **Object storage for photos:** local `backend/media/` in dev (git-ignored);
  `SAHAYTA_MEDIA_DIR` override; S3-compatible via `SAHAYTA_S3_*` in prod (Wave 5 notes).
- **LLM:** `SAHAYTA_LLM_BASE_URL` + `SAHAYTA_LLM_MODEL` (+ optional
  `SAHAYTA_LLM_API_KEY`). Unset → rule-based fallback everywhere; the app must boot
  and demo cleanly with no LLM configured.
- **Weather:** `SAHAYTA_WEATHER_API_URL` (default Open-Meteo, keyless) with
  `SAHAYTA_WEATHER_MODE=live|simulated`; failures auto-fall back to simulated and
  are labeled in the UI.
- **Secrets:** `SAHAYTA_ADMIN_KEY`, `SAHAYTA_API_KEY` (optional service key).
  See `.env.example` — never commit real values.

## 5. Non-Goals (v1)

Real SMS gateway integration (templates only, clearly labeled); real-time GPS tracking
of volunteers (last-known location only); payments/donations; native mobile apps
(PWA only); multi-tenancy across countries (India-first schema, district = the
operational unit).
