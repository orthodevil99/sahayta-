# NOTES — Agent 10 (Safety & Guardrails, Wave 4)

## What was built

Trust layer for Sahayta, all under `backend/app/` (no parallel tree):

- **`services/safety.py`** (new): `raise_flag` (dedupes identical open flags),
  `check_duplicate_photo` (hash + 24 h window + 5 km geo — strengthened from
  hash-only), `check_conflicting_reports` (severity ≥ 4 vs ≥ 3 mild within
  2 km/6 h, or vice versa; severity 3 never triggers), `check_spam_burst`
  (≥ 5 reports/device/10 min), `reporter_trust` (lifetime verification
  outcomes → trusted/standard/new/flagged tiers).
- **Intake wiring** (`routers/sos.py`): spam check before creation (429 +
  flag, already-filed reports untouched); dedup + conflict checks after
  creation (flags only — never drops); create response now includes the
  machine-readable `reason` (was: `needs_review=true` with `reason=null`).
- **Duplicate-merge semantics** (`routers/admin.py::resolve_flag`): the
  `pass` placeholder is gone. `confirmed_duplicate` marks the newest report
  `status: "duplicate"` with a persisted `duplicate_of` link; both stay
  visible. New Alembic revision `c7a10f3e2b91` adds the nullable
  `sos_reports.duplicate_of` column (batch mode for SQLite; verified
  upgrade → downgrade → re-upgrade on scratch).
- **Route de-dup (bug fix):** `GET /api/safety/flags` existed twice; the
  admin-only copy shadowed the role-scoped one, so guests could never reach
  the anonymized view. Removed the admin copy; the role-scoped handler is now
  canonical. Frontend `lib/api.tsx` updated to the canonical path.
- **Visibility policy** (`routers/safety.py` + `docs/safety.md`): admin =
  full records; reporter (`?mine=true`) = own reports' flags (type/status/
  resolution, own IDs only); guest = anonymized district counts (`?district=`
  required). Rationale documented: don't leak the detection surface.
- **Upload hardening**: magic-byte sniffing in `media.py:sniff_ok`, enforced
  on both `POST /api/media` and multipart `POST /api/sos`.
- **Reporter weighting**: verify-queue items carry `reporter_trust_tier`
  (one grouped query, no N+1).
- **`docs/safety.md`**: honest capability model — what's automated, what
  needs a human, what we deliberately DON'T do (no AI photo moderation, no
  truth detection, no shadow-banning, no silent drops, no cross-device
  identity). No invented efficacy numbers.
- **Contracts → v1.3** (`docs/api-contracts.md` §7/§8 + `MIGRATION.md`):
  all additive. New WS event `safety.flag_raised`.

## Tests

`backend/tests/test_safety.py` — 10 tests, all green:
dedup failure-injection #4 (flag raised, 2nd report kept), dedup window
expiry, conflict heuristic + isolated-severe control, spam throttle (429 +
flag), audit coverage (actor + reason on verify), visibility policy
(admin/guest-422/guest-counts/reporter-mine), duplicate merge (link persisted,
both visible), magic-byte mismatch on both upload paths. Full suite: **78/78**.

Two pre-existing tests in `test_alerts_admin.py` referenced the removed
duplicate route — updated to the canonical path.

## Known limitations (honest)

- created_at has second precision; rapid re-uploads can tie → merge tiebreak
  is `(created_at, id)`, deterministic but direction-arbitrary on ties.
- dHash catches re-encoded re-uploads; heavy crops/screenshots of a photo
  won't match (SHA-256 fallback is exact-match only).
- Conflict heuristic needs location + severity; reports lacking either skip
  it silently. Severity-3 reports never trigger it.
- Rate limits are in-memory (reset on restart); device IDs are
  client-generated (rotatable). Documented in `docs/safety.md`.
- `reporter_flag` type is reserved for manual admin use; no automation
  creates it yet.
