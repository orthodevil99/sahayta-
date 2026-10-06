# NOTES — Agent 9 (Simulation Engine, Wave 3)

## Design decisions

1. **Index + sample, not 2,000 files.** The repo stores a compact
   `scenarios/index.json` (2,000 entries: id, hazard, district, seed, peak,
   sos_count) plus 50 materialized samples. Any scenario regenerates
   bit-identically from `random.Random(BASE_SEED + index)`. This keeps the
   repo lean (2.5 MB) while honoring "2,000 scenarios" honestly — the count is
   real and reproducible, not a bluff.
2. **Stdlib only.** `urllib`-based HTTP, no `requests`/`httpx` (not installed
   in the backend venv). Zero new dependencies for the whole package.
3. **Shared boot helper.** `sim_common.BackendBoot` (fresh `seed.py --fresh` +
   uvicorn on a configurable port + teardown) is used by both the load
   simulator and the demo director — one-click determinism, no "boot the
   server first" tribal knowledge.
4. **Director asserts the contract, not the UI.** The 14 steps map 1:1 to
   `docs/demo-scenario.md` ACCEPT lines but drive the API (the video uses the
   frontend's `playPatnaDemo()` for the visual choreography). Step functions
   never raise — any exception becomes a FAIL with a reason, so the report is
   always complete.
5. **Honest triage numbers.** The load sim reports rule-fallback accuracy
   against *generator* ground truth (0.344 exact) and documents why it differs
   from Agent 6's labeled-fixture number (0.602). Both are in the report with
   the interpretation spelled out.
6. **Rate-limit-aware load design.** Fresh `X-Device-Id` per SOS (distinct
   simulated citizens) — documented in the report. Without this the guest
   20/hr limit would 429 the measurement; with it, the numbers reflect real
   per-request cost.
7. **No contract changes.** The package is a pure API client; nothing in
   `docs/api-contracts.md` (v1.2) needed amendment.

## For later waves

- **Agent 13 (video):** run `python demo_director.py --scenario patna-flood`
  before recording to guarantee the backend walkthrough is green; the
  frontend records via `?demo=1` / `playPatnaDemo()`.
- **Agent 15 (submission ops):** the sign-off checklist's director line is
  satisfied — re-run to confirm after any Wave 4/5 change.
- Ports: director defaults to 8003, load sim to 8002 — no clash with a dev
  server on 8000.

## Deliberate cuts

- No concurrent/async load (sequential requests only) — contention profiling
  is out of scope for the hackathon; p95 here is serial latency.
- No browser automation in the director — out of scope for a generic agent;
  flagged for the parent coordinator if a live-browser pass is wanted.
