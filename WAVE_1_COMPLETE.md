# WAVE 1 COMPLETE — Foundation (Agents 1–3)

All three Wave 1 agents finished, outputs merged and committed. The repo now has
a frozen design baseline that Waves 2–5 build on verbatim.

## Agent 1 — Product Architect (`4ea21c9`)
- `docs/architecture.md` — system text diagram (frontend ↔ backend ↔ AI engine ↔
  simulation), SOS hero-loop / early-warning / offline data flows, security
  boundaries; 3 variants compared (modular monolith vs microservices vs
  serverless) — **modular monolith chosen**.
- `docs/api-contracts.md` — every REST endpoint + `WS /api/stream` with exact
  JSON shapes, status codes, auth, pagination, enums. **DRAFT through Wave 2,
  frozen after.**
- `docs/data-models.md` — SQLAlchemy 2.0 + Pydantic v2: User, SOSReport,
  SeverityAssessment, Volunteer, Task, Shelter, Alert, DistrictRisk (+ District,
  WeatherSample, AuditLog, SafetyFlag); indexes, relationships, seed mapping.
- `docs/demo-scenario.md` — "Monsoon flood in Patna" as a 14-step acceptance
  test every later agent must satisfy (severity 4, Ravi Kumar match ≥ 80, Hindi
  broadcast, district risk ≥ 70) + failure-injection cases.
- `.env.example`, `README.md` (10-line stub — Wave 5 fills it),
  `docs/NOTES-agent1.md` (design-decision log).
- Key decisions: AI runs synchronously inside `POST /api/sos` but intake never
  fails (persists report with `severity: null, needs_review: true`);
  `client_report_id` idempotency key for offline-outbox replay; rule-based
  fallback is first-class and every assessment honestly reports its `model`
  path; `is_demo_data` / `weather_source` are data-layer columns; volunteer
  matching formula frozen in contracts; no passwords in v1 (device UUID +
  admin key) — deliberate scope cut.

## Agent 2 — Data Foundry (`67fa9c9`) — 4.3 MB, all synthetic, `verify.py` all green
- `data/districts.json` — **20 canonical districts** (Agent 1's docs named only
  6; Agent 2 kept those 6 and added 14 disaster-prone ones). This file is now
  canonical — every dataset references its slugs (verifier enforces).
- `data/sos-reports.json` — 3,000 SOS reports across a simulated 72h flood
  window; severity skew 829/922/682/397/170 (1–5); 145 Patna severity-4 reports
  incl. 25 forced anchors in the final 12h and 3 near-verbatim demo-fixture texts.
- `data/severity-labels.csv` — 5,000 photo-description → severity + rationale rows.
- `data/shelters.json` — 500 shelters (50 each across 10 districts), occupied ≤ capacity.
- `data/volunteers.json` — 1,000 profiles; anchor `vol-ravi-kumar-patna`,
  skills `["rescue","driving"]` (demo-scenario wins over the original brief),
  2.09 km from the demo SOS pin.
- `data/weather-sample.json` — 600 records (20 districts × 30d); Patna flood
  spike (rain ~80→137→185 mm/day, river ~50.3 m); Nagpur heatwave 43.5–46 °C;
  Puri/Chennai cyclone winds 95–115 kph; `seed_hints.patna = {risk: 82, high}`.
- `data/alert-templates/{flood,heatwave,cyclone}.json` — hand-written, 10
  languages, native scripts, SMS-length with `{district}`, `{helpline}`,
  `{temp}`, `{wind}` placeholders.
- `data/DEMO_DATA_README.md` (synthetic-data statement),
  `data/NOTES-agent2.md`, `data/generators/` (common.py + 5 generators + verify.py).

## Agent 3 — UX/Design (`6fc22fa`)
- `docs/design-system.md` — frozen visual language: severity 1–5 badge scale
  (hex, tints, icons; sev-5 striped edge), status pills, brand/neutral/dark
  palettes, Noto-based Indic type scale, 4-pt spacing, **16 components specced**
  (SeverityBadge, SOSCard, TaskCard, RiskGauge, BroadcastComposer,
  LanguageSwitcher…), 48px touch targets, low-bandwidth styles, motion + a11y.
- `docs/wireframes/*.md` — 6 screens (landing, report-sos, sos-board,
  volunteer-tasks, alerts-feed, admin-dashboard), ASCII layouts + interaction
  notes + empty/loading/offline/error states. **SOS board has 2 variants**:
  map-first (desktop) vs list-first (mobile/low-bandwidth).
- `docs/demo-storyboard.md` — 2:30 video, 8 timestamped beats, each mapped to
  Impact / Feasibility / UX / Technical Craft, with production notes.
- `docs/i18n-ux-plan.md` — 10-language switcher (instant, Hindi default/fallback),
  zero hardcoded strings, SMS anatomy with real hi/hing examples, RTL-safe
  logical properties, voice input, font-size + high-contrast controls.
- `docs/NOTES-agent3.md` — decision log for Agents 4/11/12 (route↔wireframe map,
  frozen component names, `btn-sos` style reserved for SOS filing only).
- Key decisions: severity = color + icon + number + text (never color alone);
  red 64px SOS button reserved exclusively for filing an SOS; low-bandwidth
  forces list variant, every map pin has a text-list mirror; offline is a
  first-class state (outbox queue, honest "queued" vs "sent"); honesty badges
  (DEMO DATA / SIMULATED FEED) are translated strings; wireframe emoji are
  icon placeholders — Agent 4 swaps in Lucide line icons.

## Handoffs into Wave 2 (binding)
1. API contracts are **DRAFT** — Agents 4/5/6 may propose amendments; all
   changes get documented in `WAVE_2_COMPLETE.md`, then contracts freeze.
2. Canonical district slugs live in `data/districts.json` — not in Agent 1's docs.
3. Ravi Kumar's skills are `["rescue","driving"]` (demo-scenario is the
   acceptance test; it wins).
4. Volunteer matching formula is frozen in `api-contracts.md` — engine and
   demo-director must not drift from it.
5. Demo data is always labeled synthetic — `is_demo_data` / `weather_source`
   columns exist so the UI can never forget the honesty chips.
6. Safety-flag visibility policy is deferred to Wave 4 Agent 10.

## Known gaps (Wave 2+ owns these)
- No backend or frontend code exists yet — Wave 2 builds both.
- No LLM wired — Wave 2 Agent 6, env-configured, rule-based fallback first-class.
- Weather ingestion is simulated-feed only until Wave 3 Agent 7.
