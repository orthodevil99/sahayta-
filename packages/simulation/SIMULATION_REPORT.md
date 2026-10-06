# Sahayta Simulation Report (Wave 3, Agent 9)

All synthetic. All numbers measured, not invented. Generated 2026-10-06.

## 1. Scenario generator — 2,000 scenarios

- **2,000 full scenarios** indexed in `packages/simulation/scenarios/index.json`
  (flood / heatwave / cyclone × 20 districts, deterministic seeds).
- **50 materialized samples** in `packages/simulation/scenarios/sample/`
  (2.5 MB total); any scenario regenerates bit-identically via
  `python scenario_gen.py --scenario <id>`.
- **271,513 synthetic SOS events** across the index (72h timelines, severity
  1–5, cascading streams shaped per hazard: flood ramps mid-window, heatwave
  plateaus, cyclone spikes).
- Determinism verified by tests (same index → identical output; index entries
  match full generations).

## 2. Load simulator — measured against the real backend

Workload: 30 scenarios × 6 SOS filings (JSON variant) + 95 read requests
(risk, shelters, SOS list, task-match) = **275 requests** against a fresh-seeded
backend on localhost (uvicorn). Each SOS filed under a fresh `X-Device-Id`
(distinct simulated citizens; guest limit is 20 POST /api/sos/hr/device).

| Metric | Value |
|---|---|
| Total requests | 275 |
| Errors | **0** |
| Elapsed | 16.37 s |
| Throughput | **16.8 req/s** |
| Latency p50 | 65.8 ms |
| Latency p95 | **107.0 ms** |
| Latency max | 149.4 ms |

Raw results: `packages/simulation/load_results.json`.

**Triage accuracy** (response severity vs scenario ground truth, rule-fallback-v1):
exact-match **0.344**, within-one **0.722** (n=180). Read this correctly: it
measures how well *generator template text* encodes severity gradations — the
templates reuse similar phrasing across severity levels, so the keyword scorer
cannot separate them. The authoritative estimator accuracy is Agent 6's
**0.602 exact / 1.000 within-one** on the 5,000 hand-labeled
`data/severity-labels.csv` fixtures. Both numbers are honest; they measure
different things.

Methodology note: an early run showed 90/275 errors — all HTTP 401 on read
requests because the simulator omitted the `X-Device-Id` header (my bug, not
the backend's). Fixed; the numbers above are from the clean re-run (0 errors).

## 3. Demo director — 14/14 PASS, exit 0

`python demo_director.py --scenario patna-flood` (one-click: fresh seed + boot
+ replay + teardown) against the real backend:

| Step | Check | Result |
|---|---|---|
| 01 | api_health | PASS |
| 02 | sos_filed (201, reported, patna) | PASS |
| 03 | severity_assessed (4 / rescue / critical / [rescue, driving], Hindi rationale, model labeled) | PASS |
| 04 | board_lists_sos (filter + nested assessment) | PASS |
| 05 | volunteer_matched (Ravi Kumar, score 92.5 ≥ 80, 2.09 km, "skill match: rescue") | PASS |
| 06 | task_dispatched (201, assigned) | PASS |
| 07 | task_accepted | PASS |
| 08 | sos_help_on_way | PASS |
| 09 | task_completed (resolved, reputation 50→52, 1 task) | PASS |
| 10 | broadcast_sent (202, hi ≤ 480 chars Devanagari + hing Latin) | PASS |
| 11 | admin_overview (panels present, risk 82) | PASS |
| 12 | district_risk (82/high, factors non-empty, source labeled) | PASS |
| 13 | warnings_status (enabled, 20 districts, ingest ok) | PASS |
| 14 | forecast_72h (72 hours, risk + risk_level each) | PASS |

**14/14 PASS, exit code 0.** The video recording can run this verbatim.

## 4. Tests

`packages/simulation/tests/`: **12/12 pass** — generator determinism (7),
director structure + graceful failure without a server (4), helper checks (1).

## 5. Known limitations

- Load numbers are single-machine localhost (this VM); production throughput
  will differ. No concurrency beyond sequential requests was tested — p95
  reflects serial latency, not contention.
- Scenario SOS text is template-generated; linguistic variety is bounded
  (see triage note above).
- The director drives the API directly, not the browser UI — the frontend
  demo mode (`playPatnaDemo()`) covers the UI choreography for the video.
