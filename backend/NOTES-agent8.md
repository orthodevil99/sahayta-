# NOTES — Agent 8 (Wave 3: Volunteer Coordination)

## What I built
Volunteer registration hardening, matching explainability, the full decline
re-offer loop, a documented reputation engine, 10-language SMS notification
templates, and the volunteer task-board UI extensions — all on top of Agent 5's
routers, in place under `backend/app/` (no parallel trees).

## Key decisions

1. **Frozen formula untouched.** `services/matching.py::score_volunteer` is
   byte-identical in math. I only added (a) deterministic tie-breakers in
   `rank_volunteers` (score → reputation → distance → id) so the demo-director
   gets a stable order on ties, and (b) `score_breakdown()` exposing the 0–1
   components, surfaced as the optional `VolunteerMatchRead.score_breakdown`.

2. **Reputation centralized in `services/reputation.py`.** The +2/−5/50 numbers
   were inline in the tasks router; they're now named constants with a docstring
   stating the full formula (completion bonus, broken-commitment penalty,
   response-time running average, computed reliability, display tiers). The
   router calls `on_task_completed` / `on_decline_after_commit` /
   `record_response_time` — same arithmetic as Wave 2, so the demo acceptance
   (50 → 52) is preserved. New read surface: `GET
   /api/volunteers/{id}/reputation` (additive; see MIGRATION.md).

3. **Decline re-offers automatically.** On any decline, `_plan_reoffer` ranks
   volunteers for the SOS excluding the decliner and anyone already holding an
   active task on it, and creates one new `assigned` task for the winner. It's
   planned pre-commit (no expired-attribute access in async SQLAlchemy) and the
   `task.assigned` event (with `"reoffer": true`) emits after the decline's own
   events. One re-offer per decline, no recursion; skipped when the SOS is
   terminal or nobody is eligible. Instant declines stay reputation-free — the
   re-offer is the consequence, not a penalty.

4. **SMS templates are honest.** `services/notify_templates.py` holds 5 events ×
   10 languages, all ≤ 160 chars (asserted in tests, even with long names).
   The module docstring and the endpoint docs state plainly: v1 sends no real
   SMS; `GET /api/tasks/{id}/notifications` is a preview for the demo/video, and
   a real deployment would hand the text to a gateway.

5. **Registration validates sensibly.** Languages → known codes; availability
   windows → `{day, start, end}` with weekday + `HH:MM` + `start < end`;
   `lat`/`lon` both-or-neither. All `422`s; documented in MIGRATION.md as the
   only behavior tightening (invalid inputs only).

6. **Frontend builds on Agent 4's screens.** `/volunteer` keeps its structure:
   added an availability window builder (day + start/end + add/remove, client-
   and server-validated), a reputation detail card (tier chip, reliability bar,
   avg response — fetched from the new endpoint, demo-mode mirrored in
   `lib/reputation.ts`), and a complete-with-note + optional photo proof flow in
   `TaskCard` (`POST /api/media` → `proof_photo_id`). New i18n keys went into
   `hi`/`hing` only — other locales fall back to Hindi per the established
   chain; Agent 12 owns full coverage. Re-offered tasks show a 🔁 note banner.

## Pre-existing breakage found & fixed
`app/main.py` did `from warnings import scheduler` — unresolvable in every
interpreter because stdlib `warnings` is pre-cached in `sys.modules`, so the
entire backend (and every backend test) failed at import. `main.py` now loads
`backend/warnings/scheduler.py` by file location as `sahayta_warnings`, and
`tests/test_warnings.py` imports from that alias. No behavior change; see
MIGRATION.md §7. (Agent 7's `python -m warnings.backtest` docstring example
never worked either — out of scope, but the coordinator may want to note it.)

## Verification
- New: `backend/tests/test_volunteer_coordination.py` (19 tests).
- Full backend suite + frontend `npm test` + `tsc` run before commit.
- Demo Act 3 acceptance (Ravi top ≥ 80, lifecycle, +2 rep) re-verified via the
  existing `test_tasks.py` / `test_demo_scenario.py` — untouched and green.
