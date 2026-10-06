# Sahayta — Safety & Trust Model

Disasters attract misinformation: reused photos, exaggerated claims, spam.
This document explains what Sahayta's guardrails **actually do**, what they
**don't do**, and where a human is required. No hype, no invented efficacy
numbers — every claim below is traceable to code in `backend/app/`.

## What is automated

| Guardrail | What it does | Code |
|---|---|---|
| Photo dedup | Same image re-uploaded (hash match within 24 h and 5 km) → `possible_duplicate` flag, report marked for review. The report is **never dropped**. | `services/safety.py:check_duplicate_photo` |
| Conflict triage | A severity ≥ 4 report contradicted by ≥ 3 severity ≤ 2 reports within 2 km / 6 h (or vice versa) → `conflicting_reports` flag. **Triage aid, not truth detection** — see limits. | `services/safety.py:check_conflicting_reports` |
| Spam throttle | ≥ 5 reports from one device in 10 minutes → `429` + `spam_burst` flag. Already-filed reports stay visible; nothing is deleted. | `services/safety.py:check_spam_burst` |
| Rate limits | 20 SOS posts/hour per guest device, 200 other requests/hour; 1000/hour for service/admin keys. In-memory sliding window. | `app/auth.py` |
| Upload validation | Content-Type allowlist (jpeg/png/webp), 8 MB cap, **magic-byte sniffing** (bytes must match the claimed type), empty-file rejection. | `app/media.py`, `routers/uploads.py` |
| Audit log | Every status change, verification verdict, flag resolution, duplicate merge, broadcast, and throttle writes an `AuditLog` row with actor + reason. | `routers/common.py:log_audit` |
| Reporter trust tiers | Verify-queue items carry a device trust tier (`trusted` / `standard` / `new` / `flagged`) computed from lifetime verification outcomes, so admins can prioritize. Advisory only. | `services/safety.py:reporter_trust` |

All thresholds are env-tunable (`SAHAYTA_SAFETY_*`, see `.env.example`).

## What needs a human (always)

- **Verification decisions.** No report is auto-verified or auto-rejected.
  The verify queue (`GET /api/admin/verify-queue`) is the only path from
  `reported` to `verified`; every verdict needs an admin key and a reason,
  and is audit-logged.
- **Conflict resolution.** A `conflicting_reports` flag means "a human should
  look", never "this report is false". During a real flood, the "three mild
  reports" could be the wrong ones.
- **Duplicate merges.** Only an admin resolving a flag as `confirmed_duplicate`
  (or a `duplicate` verification verdict) links reports. Merged duplicates
  keep `status: "duplicate"` with a persisted `duplicate_of` link — visible
  and queryable, never deleted.
- **Broadcasts.** Alert broadcasts are admin-composed and admin-sent.

## What the system deliberately does NOT do

- **No AI photo moderation.** We do not claim NSFW/violence detection. Upload
  checks are format, size, and magic bytes only. Malicious imagery is handled
  by human review via the verify queue.
- **No truth detection.** The conflict heuristic counts nearby severities; it
  cannot know which side is right, and severity-3 reports never trigger it
  (the murky middle is left alone).
- **No shadow-banning.** Throttled reporters get an explicit `429` with a
  `Retry-After` header and a plain-language message — never a silent fake
  success.
- **No silent drops.** A flagged duplicate, a throttled burst, a conflicting
  report — all remain visible with their status. The one exception is the
  offline outbox's idempotency replay (`client_report_id`), which returns the
  *already-accepted* report instead of creating a second one.
- **No cross-device identity.** Device IDs are client-generated UUIDs; a
  spammer can rotate them. Rate limits + spam bursts raise the cost of abuse,
  they don't eliminate it. Documented honestly, not oversold.

## Flag visibility policy

| Who | Sees |
|---|---|
| Admin (`X-Admin-Key`) | Full flag records: type, sos_ids, evidence, status, resolution, timestamps. |
| Reporter (guest, `?mine=true`) | Flags touching **their own** reports (matched by device ID): type, status, resolution note, timestamps. Only their own report IDs — never anyone else's. |
| Public / guest | Anonymized counts only: `?district=` is required; response is open-flag counts by type. No report IDs, no evidence, no reporter linkage. |

Rationale: publishing full evidence would let bad actors probe exactly which
reports were flagged and why, then tune around the guardrails. District-level
counts preserve community transparency without leaking the detection surface.
Reporters are told why *their* report is under review — that's a trust
requirement, not a leak.

## Failure modes we accept

- A reused photo from > 24 h ago or > 5 km away won't auto-flag (admins can
  still merge manually).
- The conflict heuristic needs location + severity; reports without either
  skip it silently.
- Perceptual hashing (dHash) catches re-encoded re-uploads; heavy crops or
  screenshots of the photo produce different hashes and won't match — exact
  SHA-256 is the fallback for undecodable bytes.
- In-memory rate limits reset on process restart (v1 monolith trade-off,
  documented in `app/auth.py`).
