# Agent 1 — Design Decision Log (Wave 1, Product Architect)

Why the system looks the way it does. Later agents: read this before deviating.

## 1. Modular monolith, not microservices or serverless

The moat is the AI pipeline + dataset, not infrastructure topology. A single
FastAPI process with in-process packages keeps every Wave-2/3 integration a
function call instead of a network boundary, makes the demo deterministic
(no cold starts, no broker timing), and deploys as "one backend, one DB URL".
`packages/ai-engine` has a strict seam (`pipeline.assess_and_route`,
`alerts.render_multilingual`, `risk.score_district`) with zero backend imports,
so it can be extracted into a service later without touching callers.

## 2. Synchronous AI inside POST /api/sos — with a never-fail guarantee

Severity estimation runs inside the intake request (target p95 < 3 s LLM,
< 300 ms rule fallback) because the demo video needs the severity badge to
appear immediately. But intake NEVER fails because AI failed: on pipeline
error the report persists with `severity: null, needs_review: true`. The
`model` field on every assessment honestly reports which path ran — judges
punish hidden fallbacks.

## 3. Idempotency key = offline correctness

`client_report_id` (client-generated UUID at draft time) makes the offline
outbox replay safe: replays return the existing report instead of creating
duplicates. This is the single most important field for the "networks die in
disasters" story — get it wrong and the demo shows double SOS pins.

## 4. Assessment history, not just a severity column

`severity_assessments` is a separate table (one row per assessment) rather than
columns on `sos_reports`. Reasons: audit trail of AI decisions (which model?
how many tokens? how slow?), re-assessment without losing history, and fixture
tests in Wave 2 can assert accuracy against `data/severity-labels.csv`.

## 5. Rule-based fallback is a first-class citizen, not an afterthought

Every AI module ships a deterministic fallback because: (a) the demo must run
with zero credentials; (b) the Patna fixture is tuned so the fallback ALSO
yields severity 4 (Hindi flood keywords scored explicitly); (c) "works with no
API key" is a Feasibility-criterion win. The LLM is an upgrade path, not a
dependency.

## 6. Synthetic data is labeled at the data layer, not just the UI

`is_demo_data` is a column on every seeded table, and `weather_source`
(`live|simulated`) travels with every risk response. The UI badge is then a
trivial render of a backend truth — impossible to "forget" to label, and the
Wave 5 honesty pass can grep for it.

## 7. Frozen matching formula

The volunteer scoring weights (0.45 skill / 0.30 distance / 0.15 availability /
0.10 reputation) are frozen in `api-contracts.md` so Wave 3 Agent 8's engine and
the demo-director's expected match (Ravi Kumar, score ≥ 80) can't drift apart.
Tune constants later only via a migration note.

## 8. WebSocket envelope + replay buffer

All realtime events share `{event_id, type, ts, data}`. `last_event_id` resume
with a 500-event server buffer means a dropped connection during the demo
recovers without a page refresh. The frontend still polls `?since=` as the
ultimate fallback — realtime is progressive enhancement, not a requirement.

## 9. No passwords in v1 (deliberate scope cut)

Identity = device UUID; officials = admin key. Real auth (OTP, sessions) is
listed as a non-goal with a pointer for Wave 4's `docs/safety.md` to document
honestly. For a 9-day hackathon demo this is the right trade; pretending
otherwise would be dishonest to judges.

## 10. Ten language codes, Hinglish included

`hing` (Latin-script Hindi) is a first-class lang code because real SOS text
in India is heavily Hinglish. The severity-labels dataset (Wave 1 Agent 2)
must include Hinglish samples or the triage classifier will underperform on
the most common real-world input style.

## 11. What I deliberately left for later waves

- PDF incident export: specced as `501` until Wave 4 (never ship a fake PDF).
- Exact safety-flag visibility policy: Wave 4 Agent 10 decides and documents.
- Translation file contents: Wave 4 Agent 12 (templates exist in data/).
- Alembic migration specifics: Wave 2 Agent 5 (models are frozen here).
- Video script / Devpost copy: Wave 5 (this doc gives them the facts to cite).
