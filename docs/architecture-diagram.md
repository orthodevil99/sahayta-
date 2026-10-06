# Sahayta — Architecture Diagram (copy-pasteable)

Plain-text version of `docs/architecture.md` §1.1, formatted for Devpost
(code block) or slides. Modular monolith + offline-first PWA.

```
┌─────────────────────────────────────────────────────────────────┐
│ CLIENTS — phone browsers (citizens, volunteers, officials)      │
│ Low bandwidth · intermittent connectivity · low-literacy first  │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS (REST/JSON) + WSS (live events)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ FRONTEND — Next.js 14 PWA (App Router · Tailwind · TypeScript)   │
│                                                                 │
│  Screens:                    Cross-cutting:                     │
│   /         landing          ┌─────────────────────────────┐    │
│   /report   SOS wizard      │ Service Worker: app-shell    │    │
│   /board    SOS board       │ cache · SOS outbox queue ·   │    │
│   /volunteer task view      │ background sync on reconnect │    │
│   /alerts   alerts feed     └─────────────────────────────┘    │
│   /admin    command dash     Leaflet map (heatmap + pins)       │
│                              i18n: 10 languages · low-bandwidth  │
│  lib/api.ts — typed client (implements api-contracts.md)        │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST JSON │ WS /api/stream
                             ▼           ▼
┌─────────────────────────────────────────────────────────────────┐
│ BACKEND — FastAPI, Python (modular monolith, one deployable)     │
│                                                                 │
│  Routers:  sos · assess · volunteers · tasks · shelters          │
│            districts · alerts · admin · safety · warnings        │
│                                                                 │
│  Internal packages (imported, not services):                     │
│   packages/ai-engine  severity · triage · alerts · risk ·        │
│                       pipeline  (LLM + honest rule fallback)     │
│   packages/simulation scenario gen · load sim · demo director    │
│                                                                 │
│  Workers (asyncio, in-process):                                  │
│   weather-ingest → risk-recompute → thresholds → alerts          │
│                                                                 │
│  Auth: X-API-Key (officials) · guest device UUID (citizens)      │
└────────────────────────────┬────────────────────────────────────┘
                             │ SQLAlchemy 2.0 · Alembic
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ DATABASE — SQLite (demo) ⇄ PostgreSQL (prod), one URL env var   │
│ Seed script loads data/*.json (all synthetic, labeled)          │
└─────────────────────────────────────────────────────────────────┘

        ┌──────────────────────────────────────────────┐
        │ LLM PROVIDER (env-configured, OpenAI-compat) │
        │ default GLM (Zhipu); rule fallback always on │
        └──────────────────────────────────────────────┘
              ▲ called ONLY from packages/ai-engine
```

## The SOS hero loop (data flow)

```
1. CITIZEN  /report — photo + description (any of 10 langs) + geotag
             (GPS or map pin). Offline → Service Worker outbox queues it.
2. FRONTEND  → POST /api/sos (multipart or JSON; client_report_id = idempotent)
3. BACKEND   validates → persists SOSReport("reported")
             → ai-engine.pipeline.assess_and_route():
                 severity 1–5 + one-line rationale + area tags
                 category + priority + needed volunteer skills
             → persists SeverityAssessment → WS sos.created + sos.assessed
4. MATCHING  needed_skills × volunteer.skills × distance × availability
             → ranked list → Task(sos, volunteer, "assigned") → WS task.assigned
5. VOLUNTEER /volunteer — accept → en-route → complete (+ photo proof)
             SOS: reported → verified → help_on_way → resolved (audit-logged)
6. ALERTS    admin (or risk > 85 auto-rule) → POST /api/alerts/broadcast
             → one alert rendered into 10-language SMS-length messages
             → WS alert.broadcast → /alerts feed
7. ADMIN     /admin — live SOS map + heatmap, risk panel, volunteer board,
             broadcast composer, incident timeline, real PDF export
```

## Early-warning flow

```
weather-ingest (every 15 min, asyncio)
 → GET Open-Meteo (keyless) for 20 districts
 → on ANY failure: SIMULATED feed, labeled end-to-end (never silent)
 → risk.py: weather → risk 0–100 + contributing factors → DistrictRisk rows
 → WS risk.updated
 → risk > 70 → advisory draft · risk > 85 → warning draft → 10-lang broadcast
```

## Offline sync flow

```
online:   normal REST + WS
offline:  SW intercepts POST /api/sos → IndexedDB outbox ("N reports queued")
reconnect: background sync replays in order; server dedups by client_report_id
           → zero duplicates. WS resyncs missed events via last_event_id.
```
