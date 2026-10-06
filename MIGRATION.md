# MIGRATION.md — additive contract changes

The API contracts (`docs/api-contracts.md`) are **frozen** since the end of
Wave 2. This file records every additive, backward-compatible change made
after the freeze, per the freeze notice (§12): no renames, no removed fields,
no changed enum values. Existing clients keep working byte-for-byte.

## v1.1 → v1.2 (Wave 3, Agent 8 — Volunteer Coordination)

### New endpoints (purely additive)

1. **`GET /api/volunteers/{volunteer_id}/reputation`** → `200`
   ```json
   { "volunteer_id": "…", "reputation": 52, "tasks_completed": 1,
     "tasks_declined": 0, "avg_response_min": 4.2,
     "reliability_pct": 100.0, "tier": "helper" }
   ```
   `404` for unknown ids. `tier ∈ {"guardian","responder","helper","newcomer"}`.
   Formula documented in `backend/app/services/reputation.py`.

2. **`GET /api/tasks/{task_id}/notifications?lang=hi`** → `200`
   ```json
   { "task_id": "…", "lang": "hi",
     "messages": { "assigned": "…", "accepted": "…", "en_route": "…",
                   "completed": "…", "declined": "…" } }
   ```
   SMS-length (≤ 160 chars) per-language preview of the task lifecycle
   notifications. **Demo/preview only — v1 sends no real SMS.**
   `404` for unknown ids; unknown `lang` falls back to `hi`.

### New optional field (additive)

3. **`VolunteerMatchRead.score_breakdown`** (nullable object, `POST /api/tasks/match`):
   ```json
   "score_breakdown": { "skill": 1.0, "distance": 0.916,
                        "availability": 1.0, "reputation": 0.5 }
   ```
   The 0–1 components feeding the frozen formula
   (`score = 0.45·skill + 0.30·distance + 0.15·availability + 0.10·reputation`).
   `null` is never returned by the current backend; the field is optional so
   older typed clients ignore it safely.

### Behavior additions (no shape changes)

4. **Decline re-offer:** declining a task (`POST /api/tasks/{id}/decline`) now
   auto-creates one new `assigned` task for the next-ranked eligible volunteer
   (decliner excluded, volunteers with active tasks on the SOS excluded, SOS
   must be non-terminal). Emits a second `task.assigned` WS event with
   `"reoffer": true` and writes a `task.reoffered` audit entry. If no eligible
   volunteer exists, nothing is created. Rationale: a declined task should keep
   moving, not die silently.

5. **Registration validation hardening** (`POST /api/volunteers`,
   `PATCH /api/volunteers/{id}`): `languages` must be known codes (the 10 UI
   locales + `en`); `availability` windows must be `{day, start, end}` with a
   valid weekday and `HH:MM` bounds with `start < end`; `lat`/`lon` must be
   provided together or not at all. Violations → `422`. Previously, invalid
   values in these fields were silently accepted — no valid request changes
   behavior.

6. **Matching tie-breakers** (`POST /api/tasks/match` ordering only):
   `score desc → reputation desc → distance asc → volunteer id asc`.
   The scoring formula itself is untouched (still frozen).

### Incidental fix (not a contract change)

7. `app/main.py` no longer does `from warnings import scheduler` (which could
   never resolve — the stdlib `warnings` module is pre-cached in
   `sys.modules`, so the import raised `ImportError` in every interpreter and
   the whole backend, including all tests, failed to boot). It now loads
   `backend/warnings/scheduler.py` by file location as `sahayta_warnings`.
   `backend/tests/test_warnings.py` imports from the same alias. No behavior
   change — this only repairs the import.

## v1.2 → v1.3 (Wave 4, Agent 10 — Safety & Guardrails)

All changes additive. No renames, no removed fields, no changed enum values
(except widening `FlagResolveBody.resolution`, which accepts everything it did
before).

### Behavior additions (no shape changes)

1. **Intake guardrails** (`POST /api/sos`): photo dedup now requires hash +
   24 h window + 5 km proximity (was: hash match only); new
   `conflicting_reports` heuristic (severity ≥ 4 vs ≥ 3 mild reports within
   2 km / 6 h, or vice versa); new spam-burst throttle (≥ 5 reports per device
   per 10 min → `429` with `Retry-After`; already-filed reports untouched).
   All thresholds env-tunable (`SAHAYTA_SAFETY_*`). Nothing is silently dropped.
2. **Upload hardening**: magic-byte sniffing on `POST /api/media` and the
   multipart `POST /api/sos` path — bytes must match the claimed image type
   (new `422` detail: "file bytes do not match the claimed image type").
3. **Duplicate-merge semantics**: resolving a flag as `confirmed_duplicate`
   (or a `duplicate` verification verdict) now persists `duplicate_of` on the
   newer report and sets its status to `duplicate`. Both reports stay visible.
   New Alembic revision `c7a10f3e2b91` adds the nullable
   `sos_reports.duplicate_of` column.
4. **Route de-duplication (incidental fix):** `GET /api/safety/flags` was
   defined twice — the admin-only copy in `routers/admin.py` shadowed the
   role-scoped copy in `routers/safety.py` (first-registered wins), so guests
   could never reach the anonymized-counts view. The admin copy is removed;
   the role-scoped version (admin full / reporter `?mine=true` / guest counts)
   is now the live one. No client-visible change for admins.

### New optional fields / params (additive)

5. **`GET /api/safety/flags?mine=true`** — reporter's own flags (type, status,
   resolution note, timestamps, own report IDs only).
6. **`SOSRead.duplicate_of`** (nullable string) and
   **`SOSRead.reporter_trust_tier`** (nullable, verify-queue context only:
   `trusted|standard|new|flagged`).
7. **`FlagResolveBody.resolution`** widens: `"confirmed_duplicate" |
   "confirmed" | "false_alarm"` (`"confirmed"` = confirmed spam/conflict).
8. **New WS event `safety.flag_raised`** → `{ type, sos_id, district_id }`.
