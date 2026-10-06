# Sahayta — Devpost Submission Copy

**Voice:** sincere student-builder. No hype, no invented metrics — every number
below is measured and names its source file. Judging criteria key:
**[I]** Impact · **[F]** Feasibility · **[UX]** User Experience ·
**[T]** Technical Craft.

---

## Title options (pick one)

1. **Sahayta — When Disaster Strikes, Help Finds You** *(recommended: the pitch is the title)*
2. Sahayta: A Disaster-Response OS for India
3. Sahayta — From a Flood Photo to a Rescue Team in Minutes
4. Sahayta: Offline-First Disaster Coordination in 10 Indian Languages
5. Sahayta — AI SOS Triage and Volunteer Dispatch for Floods, Heatwaves, Cyclones

## Tagline

A disaster-response OS for India: photo-based SOS triage, AI severity
estimation, volunteer dispatch, and multilingual alerts — offline-first,
because networks die in disasters.

## Short description (for listings)

Sahayta is a disaster-response coordination system for India. A citizen uploads
a photo of rising floodwater; AI estimates severity and files a verified SOS;
volunteers are matched by skill and distance and dispatched; district officials
watch it all on a live command dashboard; and one alert goes out in ten Indian
languages. It works offline, runs with zero API keys, and every demo-data
surface is honestly labeled.

## Full description

### Problem statement [I]

Every monsoon, floods hit India. Heatwaves and cyclones fill the gaps between
them. When they do, the failure is rarely a lack of willing helpers — it is a
lack of coordination. Phones work but networks don't. A stranded family can't
reach the control room; the control room can't see the stranded family; and
warnings, when they come, come in one language to a country with twenty-two
official ones.

Existing tools solve slices of this: a weather app, a helpline number, a
WhatsApp group. Nobody owns the loop — report → assess → dispatch → warn →
resolve — as one system, in the languages people actually speak, on the
networks disasters leave behind. **[I]** That missing loop is what Sahayta is.

### Target users [I] [UX]

Three people, one loop:

- **The citizen in the water.** She speaks Hindi, not English. She has a
  shaky 2G connection and sixty seconds. She gets a 4-step SOS wizard —
  photo, her own words (typed or spoken), a pin on the map — with no account,
  no manual, and an offline queue that syncs without duplicates when the
  network returns. **[UX]**
- **The volunteer nearby.** He gets matched on skills × distance ×
  availability with inspectable reasons ("skill match: rescue · 2.1 km away"),
  not a black box — and a task lifecycle (accept → en-route → complete with
  photo proof) that builds a reputation score. **[F]**
- **The district official.** She gets one screen: live SOS map with severity
  heatmap, district risk with contributing factors, volunteer availability,
  a one-click multilingual broadcast composer, an incident timeline, and a
  real PDF incident export. **[F]**

### Technical approach and components [T] [F]

**Architecture.** A modular monolith plus an offline-first PWA: one FastAPI
backend, one Next.js 14 frontend, one database URL. We evaluated microservices
and serverless and rejected both — nine days, one developer, and a demo video
that must be deterministic don't survive broker ops and cold starts. The
engineering hours went into the AI pipeline and the dataset instead, and the
AI engine keeps a strict seam (`pipeline.assess_and_route`) so it can be
extracted into a service later. **[T]**

**The multi-agent AI pipeline** (the technical-craft centerpiece) **[T]**:

- `severity.py` — photo/description → severity 1–5 + one-line rationale +
  affected-area tags. Provider-agnostic (env-configured GLM/Zhipu,
  OpenAI-compatible); with no keys set it runs a tuned rule-based fallback
  that *says so* (`model: rule-fallback-v1`) — because in a disaster you
  can't depend on an API key.
- `triage.py` — category (medical/rescue/food/shelter/infrastructure) +
  priority + suggested volunteer skills.
- `alerts.py` — one alert → ten-language SMS-length messages, rendered from
  hand-written native-script templates, LLM only for novel alerts.
- `risk.py` — weather series → district risk 0–100 with contributing factors.
- `pipeline.py` — orchestrates assess → triage → route → notify as one call
  the backend uses, with per-call token accounting.

**Measured, not claimed** (sources in the repo) **[T]**:

- Backend 79/79 tests, AI engine 65/65, frontend 6/6 test files, simulation
  12/12 (`backend/tests`, `packages/ai-engine/tests`, `frontend/lib/__tests__`,
  `packages/simulation/tests`).
- Load: 275 requests, 0 errors, 16.8 req/s, p95 107.0 ms on a localhost VM
  (`packages/simulation/load_results.json`).
- Severity estimator: 0.60 exact / 1.00 within-one on a seeded 600-row sample
  of the 5,000 hand-labeled fixtures (`packages/ai-engine/NOTES-agent6.md`).
- Demo director replays the full 14-step acceptance scenario: **14/14 PASS**
  (`packages/simulation/SIMULATION_REPORT.md`).
- UI strings: 10/10 locales × 311 keys = 100% computed coverage
  (`docs/i18n-coverage.md`).

**The dataset moat.** 3,000 synthetic SOS reports across a 72-hour flood,
5,000 severity-labeled photo descriptions, 500 shelters, 1,000 volunteers,
20 districts × 30 days of weather, and a 2,000-scenario generator producing
271,513 synthetic SOS events — all committed with generator scripts, all
labeled synthetic, never presented as real (`data/`, `data/DEMO_DATA_README.md`).
**[T]**

**Trust engineering.** Disasters attract misinformation, so guardrails are
first-class: photo-hash dedup, conflicting-report triage, spam throttling,
magic-byte upload validation, reporter trust tiers, a full audit log — and an
honest capability document (`docs/safety.md`) that says what is automated,
what needs a human, and what we deliberately don't do (no AI photo moderation
claims, no truth detection, no silent drops). Safety flags have a defined
visibility policy: admins see everything, reporters see their own, the public
sees anonymized counts. **[F]**

**Feasibility proof.** The whole loop runs on a laptop with no network: the
frontend's `?demo=1` mode serves the scenario from bundled data, the backend
seeds from JSON in one command, and the demo-director replays the acceptance
test deterministically. A district office could run this — that was the design
bar for the admin screen. **[F]**

**Honest limits** (we'd rather you read them here than find them) **[F]**:
all data is synthetic; the early-warning backtest measured 0.0
precision/recall because the v1 risk formula caps flood-only risk at 82,
below the >85 warning band — the mechanics work, the predictive skill is
unvalidated (`backend/warnings/BACKTEST_REPORT.md`); translations aren't
native-speaker reviewed; there is no real SMS gateway (templates only,
labeled); voice input is progressive enhancement, untested against live
speech.

### Real-world impact [I]

Sahayta doesn't ask a drowning district to adopt new hardware, new accounts,
or a new language. It meets the citizen in Hindi on a 2G phone, the volunteer
two kilometers away with the right skills, and the official with a single
screen that turns chaos into a queue. The impact story is the last mile:
**one photo in, one rescue team out, ten languages warned** — on infrastructure
a student can actually deploy.

The meta-story is deliberate: a coordination system for humans, built by a
coordinated system of agents — 15 of them, one per module, each building on
frozen contracts, each tested, each committed. The repo is the receipt.

---

## Built-with tags

`Next.js 14` · `FastAPI` · `Leaflet` · `Python` · `TypeScript` · `Tailwind CSS` ·
`SQLite` · `Alembic` · `pdf-lib` · `reportlab`

## Links (fill at submission)

- Demo video (2:30, Variant A): `<YOUTUBE_URL>`
- GitHub repo: `<REPO_URL>` (public)
- Live demo: `<FRONTEND_URL>/?demo=1` (zero-backend demo mode)
