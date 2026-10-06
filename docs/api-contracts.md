# Sahayta — API Contracts

**Version:** 1.3 (Wave 4 — Agent 10; see `MIGRATION.md` for the v1.2 → v1.3 delta)
**Status:** **FROZEN** as of end of Wave 2. After freezing: no renames, no
removed fields, no changed enum values. Additive, backward-compatible changes
(new optional fields, new endpoints) are allowed only with a `MIGRATION.md`
note in the wave summary and a version bump of this document.
Waves 3–5 implement these verbatim: same paths, same field names, same shapes.
The frontend typed client (`frontend/lib/api.tsx`) is generated against this
document.

## 0.0 Wave 3 amendments (changelog — Agent 8, additive only)

1. **NEW `GET /api/volunteers/{volunteer_id}/reputation`** → `200`
   `{"volunteer_id","reputation","tasks_completed","tasks_declined",
   "avg_response_min","reliability_pct","tier"}`; `tier ∈
   {"guardian","responder","helper","newcomer"}`. Formula in
   `backend/app/services/reputation.py`.
2. **NEW `GET /api/tasks/{task_id}/notifications?lang=hi`** → `200`
   `{"task_id","lang","messages":{"assigned","accepted","en_route",
   "completed","declined"}}` — SMS-length (≤ 160 chars) per-language preview
   of task lifecycle notifications. Demo/preview only — v1 sends no real SMS.
   Unknown `lang` falls back to `hi`.
3. **`VolunteerMatchRead` gains optional `score_breakdown`**
   `{"skill","distance","availability","reputation"}` — the 0–1 components of
   the frozen match formula.
4. **Decline re-offer:** `POST /api/tasks/{id}/decline` auto-creates one new
   `assigned` task for the next-ranked eligible volunteer (decliner + busy
   volunteers excluded; SOS must be non-terminal), emits `task.assigned` with
   `"reoffer": true`, and audit-logs `task.reoffered`. No-op when no eligible
   volunteer exists.
5. **Registration validation:** `languages` restricted to known codes (10 UI
   locales + `en`); availability windows validated (`day`/`HH:MM`/`start<end`);
   `lat`/`lon` both-or-neither → `422` on invalid (previously accepted).
6. **Match ordering tie-breakers:** score desc → reputation desc → distance
   asc → volunteer id asc. Formula untouched.

## 0.0 Wave 2 amendments (changelog — Agent 5)

All 9 contract issues raised by Agent 4 (frontend) are resolved; each is marked
with its issue number. Everything below is additive except where noted.

1. **`GET /api/alerts?lang=all`** — list items now include the full per-language
   `messages` map (previously detail-only). `message` still carries the
   `?lang=`-requested text (default `hi`).
2. **NEW `POST /api/media`** — `multipart/form-data` with a `photo` file
   (jpeg/png/webp, ≤ 8 MB) → `201 {"photo_id","url","photo_hash"}`. This mints
   the `photo_id` that `POST /api/assess` and task proof photos reference.
   Uploaded photos are served at the returned `url` (`/media/...`).
3. **`PATCH /api/volunteers/{id}`** — accepted fields now documented: `name`,
   `phone`, `district_id`, `lat`, `lon`, `skills`, `languages`, `availability`,
   `active`. Owner device or admin.
4. **NEW `PATCH /api/users/me`** — device-anchored user preferences:
   `{"preferred_lang","display_name","phone"}` (all optional). The i18n plan's
   referenced endpoint now exists instead of being dropped.
5. **`GET /api/sos?sort=severity`** — documented as **descending** (most severe
   first; nulls last). `sort=priority` orders critical > high > medium > low.
6. **`GET /api/admin/overview` `sos_by_severity`** — string keys `"1"`–`"5"`
   confirmed frozen (frontend already handles them).
7. **WS `?admin_key=`** — stays as the documented demo-only convenience; a real
   deployment must use a proper auth ticket (Wave 4 owns the design).
8. **`POST /api/sos` JSON variant** — `photo_description` confirmed workable;
   additionally accepts `photo_id` to link an upload minted by `POST /api/media`.
9. **`GET /api/admin/verify-queue`** — items gain a machine-readable `reason`:
   `awaiting_verification | flagged_for_review | assessment_failed |
   possible_duplicate | reporter_flagged | seed_flagged`.

Further Wave-2 clarifications (additive):
- `POST /api/tasks` auth: admin, **or the SOS reporter's device** (the
  "auto-system" path — the pipeline assigns on the reporter's behalf).
- `GET /api/safety/flags`: admins see the full list; guests must pass
  `?district=` and receive anonymized open-flag counts for that district.
- WS client→server also accepts `{"type":"resync","last_event_id":n}` (the
  form the frontend uses) in addition to the `?last_event_id=` query param.
- `SOSReport` carries an internal `needs_review_reason` backing the
  verify-queue `reason` (not exposed elsewhere).
- Rate limits are enforced per rolling hour: guest 20 `POST /api/sos`/hr and
  200 other/hr; service/admin 1000/hr → `429` with `Retry-After`.

Base URL (dev): `http://localhost:8000`
All request/response bodies: JSON, UTF-8, unless noted (photo upload = multipart).
Timestamps: ISO 8601 UTC (`2026-10-06T12:34:56Z`). IDs: UUID v4 strings.

---

## 0. Global Conventions

### 0.1 Language codes

UI + alerts support 10 Indian languages:

| Code | Language | Script |
|---|---|---|
| `hi` | Hindi | Devanagari |
| `hing` | Hinglish | Latin |
| `bn` | Bengali | Bengali |
| `ta` | Tamil | Tamil |
| `te` | Telugu | Telugu |
| `mr` | Marathi | Devanagari |
| `gu` | Gujarati | Gujarati |
| `kn` | Kannada | Kannada |
| `ml` | Malayalam | Malayalam |
| `pa` | Punjabi | Gurmukhi |

`en` (English) is accepted as a fallback input/output language on text fields but is
NOT one of the 10 shipped UI locales. `?lang=` defaults to `hi` for alerts.

### 0.2 Auth

| Mode | Header | Capabilities |
|---|---|---|
| Guest (citizen/volunteer) | `X-Device-Id: <uuid>` (client-generated, persisted) | file SOS, register volunteer, manage own tasks |
| Service key (optional) | `X-API-Key: <SAHAYTA_API_KEY>` | same as guest, higher rate limits |
| Admin (district official) | `X-Admin-Key: <SAHAYTA_ADMIN_KEY>` | verify, broadcast, admin dashboard, export |

Missing/invalid credentials → `401`. Valid credentials, insufficient role → `403`.
Demo mode uses `X-Admin-Key: demo-admin-key`; the UI must banner "DEMO MODE".

### 0.3 Rate limits

- Guest: `20 POST /api/sos` per hour per device; `200` other requests/hour.
- Admin/service: `1000` requests/hour.
- Exceeded → `429` with `{"detail": "rate limit exceeded", "retry_after": 42}`.

### 0.4 Pagination

List endpoints accept `limit` (default 20, max 100) and `offset` (default 0) and return:

```json
{
  "items": [ ... ],
  "total": 137,
  "limit": 20,
  "offset": 0
}
```

### 0.5 Errors

```json
{ "detail": "human-readable message" }
```

- `400` invalid state transition / bad business-logic request
- `401` missing or invalid credentials
- `403` insufficient role
- `404` unknown id
- `409` duplicate (e.g. duplicate `client_report_id` replay — returns the existing resource)
- `422` validation error → FastAPI default body: `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`
- `429` rate limited

### 0.6 Enumerations (shared)

```text
Severity:        1 | 2 | 3 | 4 | 5            (1 = minor, 5 = catastrophic)
SOSStatus:       "reported" | "verified" | "help_on_way" | "resolved" | "duplicate" | "rejected"
SOSCategory:     "medical" | "rescue" | "food" | "shelter" | "infrastructure" | "other"
Priority:        "low" | "medium" | "high" | "critical"
TaskStatus:      "assigned" | "accepted" | "declined" | "en_route" | "completed" | "cancelled"
AlertType:       "flood" | "heatwave" | "cyclone" | "custom"
RiskLevel:       "low" | "moderate" | "high" | "severe"      (risk 0–39 / 40–69 / 70–84 / 85–100)
WeatherSource:   "live" | "simulated"
VolunteerSkill:  "medical" | "rescue" | "driving" | "cooking" | "shelter_mgmt" |
                 "translation" | "logistics" | "counseling" | "engineering"
```

---

## 1. SOS Intake & Triage

### POST /api/sos — file an SOS report

Auth: guest+. Idempotent on `client_report_id` (replay returns `200` with existing report
instead of `201`; this is what the offline outbox relies on).

**multipart/form-data:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `photo` | file | no | jpeg/png/webp, ≤ 8 MB |
| `description` | string | yes | 10–2000 chars, any supported language |
| `lat` | float | yes* | −90…90 (*required unless `district_id` given) |
| `lon` | float | yes* | −180…180 |
| `district_id` | string | no | slug, e.g. `patna` |
| `language` | string | no | lang code, default auto |
| `reporter_name` | string | no | ≤ 120 chars |
| `reporter_phone` | string | no | E.164-ish, stored as given |
| `client_report_id` | string (uuid) | yes | generated client-side at draft time |

JSON variant (`Content-Type: application/json`, no photo) accepts the same fields
minus `photo`, plus optional `photo_description` (string) for the demo/text mode
and optional `photo_id` (string) to link a photo already uploaded via
`POST /api/media`.

**Response `201` (or `200` on idempotent replay):**

```json
{
  "id": "3f9c2a1e-…",
  "client_report_id": "…",
  "description": "…",
  "language": "hi",
  "category": "rescue",
  "severity": 4,
  "severity_rationale": "Waist-deep water across two lanes; residents on rooftops.",
  "priority": "critical",
  "status": "reported",
  "lat": 25.5941, "lon": 85.1376,
  "district_id": "patna",
  "photo_url": "/media/sos/3f9c….jpg",
  "photo_hash": "a1b2c3…",
  "reporter_name": "…", "reporter_phone": "…",
  "needed_skills": ["rescue", "driving"],
  "created_at": "2026-10-06T…Z",
  "updated_at": "2026-10-06T…Z",
  "assessment": {
    "id": "…", "severity": 4,
    "rationale": "Waist-deep water across two lanes; residents on rooftops.",
    "area_tags": ["road_submerged", "residential"],
    "model": "glm-4-flash (rule-fallback)",
    "assessed_at": "2026-10-06T…Z"
  }
}
```

Severity estimation runs **synchronously inside this call** (target p95 < 3 s with LLM,
< 300 ms on rule fallback). If the AI pipeline fails, the report is still created with
`severity: null, category: "other", priority: "medium"` and a `needs_review: true` flag —
intake must never fail because AI failed.

Errors: `422` (bad coords/text), `429`, `413` (photo too large).

### GET /api/sos — list / filter SOS reports

Auth: guest+. Query params: `district`, `severity_min`, `severity_max`, `status`,
`category`, `priority`, `q` (full-text on description), `verified_only` (bool),
`since` (ISO ts), `limit`, `offset`, `sort` (`-created_at` default | `severity` — **descending**, most severe first |
`priority` — critical > high > medium > low). Response: paginated list of SOSReport objects (shape as above, without
nested `assessment` — use `GET /api/sos/{id}` for the full object).

### GET /api/sos/{id}

Auth: guest+. `200` full SOSReport (with nested `assessment` and `tasks` summary).
`404` unknown.

### PATCH /api/sos/{id} — status transition

Auth: reporter device (`X-Device-Id` matching the report) or admin.

```json
{ "status": "verified", "note": "Field team confirmed water at waist level" }
```

Allowed transitions:

```text
reported   → verified | duplicate | rejected
verified   → help_on_way | resolved | rejected
help_on_way→ resolved
resolved   → (terminal)
duplicate  → (terminal)   rejected → (terminal)
```

Illegal transition → `400 {"detail": "illegal transition reported → resolved"}`.
Every transition writes an audit-log entry and emits WS `sos.status_changed`.
Response `200`: updated SOSReport.

### POST /api/sos/{id}/verify — admin verification

Auth: admin only.

```json
{ "verdict": "verified", "duplicate_of": null, "note": "…" }
```

`verdict ∈ {"verified","rejected","duplicate"}`; `duplicate_of` required when
`verdict == "duplicate"`. Response `200`: updated SOSReport. `403` non-admin.

### POST /api/media — upload a photo, mint a photo_id (Wave 2 addition)

Auth: guest+. `multipart/form-data` with field `photo` (jpeg/png/webp, ≤ 8 MB).

```json
// response 201
{ "photo_id": "…", "url": "/media/sos/….jpg", "photo_hash": "a1b2c3…" }
```

`photo_hash` is a 64-bit perceptual dHash (hex) when the image decodes, else
`sha256:<hex>` (exact-match only — the prefix marks the semantics honestly).
The `url` is served by the backend's `/media` static mount.

### POST /api/assess — standalone severity estimation

Auth: guest+. Lets the frontend (or demo director) score a photo/description
without filing a report.

```json
// request
{ "description": "…", "language": "hi", "lat": 25.59, "lon": 85.13,
  "photo_id": "…" /* optional: id of an already-uploaded photo */ }
// response 200
{ "severity": 4,
  "rationale": "…",
  "area_tags": ["road_submerged"],
  "category": "rescue",
  "priority": "critical",
  "suggested_skills": ["rescue", "driving"],
  "model": "glm-4-flash | rule-fallback",
  "latency_ms": 812 }
```

---

## 2. Shelters

### GET /api/shelters

Auth: guest+. Query: `district`, `q` (name/area search), `has_capacity` (bool),
`facility` (repeatable: `drinking_water`, `medical`, `food`, `pet_friendly`,
`wheelchair_access`, `power_backup`), `limit`, `offset`.

```json
{ "items": [{
    "id": "…", "name": "Patna High School Relief Camp",
    "district_id": "patna", "area": "Kankarbagh",
    "lat": 25.60, "lon": 85.14,
    "capacity": 500, "occupied": 132,
    "facilities": ["drinking_water", "medical", "food"],
    "contact_name": "…", "contact_phone": "…",
    "is_demo_data": true,
    "updated_at": "…"
  }], "total": 48, "limit": 20, "offset": 0 }
```

`is_demo_data` is ALWAYS `true` in v1 (all shelters are synthetic). The frontend
renders a "DEMO DATA" badge whenever this flag is true.

### GET /api/shelters/{id} — `200` / `404`.

---

## 3. Districts & Risk

### GET /api/districts

Auth: guest+. Returns all tracked districts with current risk snapshot:

```json
[{ "id": "patna", "name": "Patna", "state": "Bihar",
   "lat": 25.5941, "lon": 85.1376, "population": 5800000,
   "risk": 82, "risk_level": "high",
   "active_sos": 14, "active_volunteers": 61,
   "updated_at": "…" }]
```

### GET /api/districts/{id}

`200` district detail: as above + `risk_factors` (see below) + `weather_source`.

### GET /api/districts/{id}/risk

```json
{ "district_id": "patna",
  "risk": 82, "risk_level": "high",
  "factors": [
    { "name": "rainfall_24h_mm", "value": 187.5, "weight": 0.35,
      "contribution": 28.9, "note": "187.5 mm in 24h (severe)" },
    { "name": "river_level_trend", "value": "rising", "weight": 0.25,
      "contribution": 21.0, "note": "Ganga rising 0.4 m/6h at Gandhi Ghat" }
  ],
  "computed_at": "…", "weather_source": "simulated",
  "advisory": "Heavy flooding likely in low-lying wards within 12h." }
```

`weather_source` tells the UI whether to show the "SIMULATED FEED" label.

### GET /api/districts/{id}/forecast — 72-hour view

```json
{ "district_id": "patna", "weather_source": "simulated",
  "hours": [
    { "ts": "…", "rain_mm": 12.4, "temp_c": 31.2, "humidity": 88,
      "wind_kph": 22, "risk": 82, "risk_level": "high" }
    /* 72 entries, 1-hour steps */
  ] }
```

---

## 4. Volunteers

### POST /api/volunteers — register

Auth: guest+ (the `X-Device-Id` becomes the volunteer's owner device).

```json
// request
{ "name": "Asha Devi", "phone": "+91…", "district_id": "patna",
  "lat": 25.61, "lon": 85.15,
  "skills": ["medical", "translation"],
  "languages": ["hi", "hing"],
  "availability": "anytime",
  "active": true }
// availability: "anytime" | [{"day": "mon", "start": "09:00", "end": "18:00"}]
// response 201
{ "id": "…", "name": "Asha Devi", "district_id": "patna",
  "skills": ["medical", "translation"], "languages": ["hi", "hing"],
  "availability": "anytime", "active": true,
  "reputation": 50, "tasks_completed": 0, "avg_response_min": null,
  "created_at": "…" }
```

`reputation`: 0–100, starts at 50; +2 per completed task (cap 100), −5 per
declined-after-accept (floor 0). Computed server-side; never client-set.

### GET /api/volunteers — `?district=&skill=&language=&available_now=&active=&limit=&offset=`

### GET /api/volunteers/{id} — `200` / `404`.

### PATCH /api/volunteers/{id} — update own profile (owner device or admin).

Accepted fields (Wave 2): `name`, `phone`, `district_id`, `lat`, `lon`,
`skills`, `languages`, `availability`, `active`. Partial object; `200` returns
the updated Volunteer. `403` for non-owners.

---

## 5. Tasks (Volunteer Coordination)

### POST /api/tasks/match — preview ranked volunteers for an SOS

Auth: guest+.

```json
// request
{ "sos_id": "…", "max_results": 5, "max_distance_km": 25 }
// response 200
{ "sos_id": "…",
  "matches": [{
    "volunteer": { /* Volunteer object */ },
    "score": 87.5,
    "distance_km": 3.2,
    "reasons": ["skill match: rescue", "3.2 km away", "available now", "reputation 78"]
  }] }
```

Scoring (Wave 3 Agent 8 implements; formula frozen here):
`score = 0.45*skill_match + 0.30*distance_score + 0.15*availability + 0.10*reputation_norm`,
`distance_score = max(0, 1 − distance_km/max_distance_km)`.

### POST /api/tasks — assign

Auth: admin, or the SOS reporter's device (auto-system path — the pipeline
assigns on the reporter's behalf; same shape).

```json
// request
{ "sos_id": "…", "volunteer_id": "…", "note": "Nearest rescue volunteer" }
// response 201
{ "id": "…", "sos_id": "…", "volunteer_id": "…",
  "status": "assigned", "note": "…",
  "assigned_at": "…", "accepted_at": null, "completed_at": null,
  "proof_photo_url": null, "created_at": "…", "updated_at": "…" }
```

`409` if an active (non-terminal) task already exists for the sos+volunteer pair.

### GET /api/tasks — `?volunteer_id=&sos_id=&status=&district=&limit=&offset=`

### GET /api/tasks/{id} — `200` / `404` (includes nested volunteer + sos summary).

### POST /api/tasks/{id}/accept — owner volunteer device or admin → `status: accepted`. `200`.

### POST /api/tasks/{id}/decline — `{ "reason": "…" }` → `status: declined`. `200`.

### POST /api/tasks/{id}/enroute — → `status: en_route`. Also flips parent SOS to `help_on_way` (first task to go en-route wins). `200`.

### POST /api/tasks/{id}/complete — `{ "note": "…", "proof_photo_id": "…" }` → `status: completed`; bumps volunteer reputation; if no other active tasks on the SOS, SOS → `resolved`. `200`.

### POST /api/tasks/{id}/cancel — admin only → `status: cancelled`. `200`.

Illegal lifecycle transition → `400`.
Lifecycle: `assigned → accepted | declined | cancelled`; `accepted → en_route | declined | cancelled`; `en_route → completed | cancelled`; terminal: `completed, declined, cancelled`.

---

## 6. Alerts (Multilingual Broadcast)

### POST /api/alerts/broadcast — compose & send

Auth: admin only.

```json
// request
{ "district_ids": ["patna", "vaishali"],
  "type": "flood",
  "title": "Flood warning: Ganga rising",
  "body": "Water rising in low-lying wards of Patna. Move to higher ground. Relief camps open at …",
  "severity": 4,
  "languages": ["hi", "hing", "bn"],   // default: all 10
  "scheduled_at": null                  // ISO ts or null = send now
}
// response 202
{ "broadcast_id": "…",
  "status": "sent",
  "rendered": {
    "hi":   "बाढ़ चेतावनी: पटना के निचले इलाकों में पानी बढ़ रहा है…",
    "hing": "Flood warning: Patna ke neeche ilakon me paani badh raha hai…",
    "bn":   "…"
  },
  "recipient_estimate": 12400,
  "created_at": "…" }
```

Each rendered message is SMS-length (≤ 480 chars / 3 SMS segments). Rendering uses
`ai-engine/alerts.py` with `data/alert-templates/` as ground truth. Emits WS
`alert.broadcast`. Every broadcast is audit-logged.

### GET /api/alerts — `?district=&type=&lang=&limit=&offset=` → paginated alert feed.

```json
{ "items": [{ "id": "…", "district_ids": ["patna"], "type": "flood",
   "severity": 4, "languages": ["hi","hing","bn"],
   "message": "…",            // in requested ?lang= (default hi)
   "messages": {"hi": "…"},   // full map on GET /api/alerts/{id}, or on list with ?lang=all
   "created_at": "…" }], "total": 9, "limit": 20, "offset": 0 }
```

### GET /api/alerts/{id} — `200` with full per-language `messages` map / `404`.

---

## 7. Admin (Command Dashboard)

Auth: **admin only** for all routes in this section.

### GET /api/admin/overview — district command snapshot

```json
// ?district=patna (optional; omit = all districts)
{ "district_id": "patna",
  "sos_by_status": {"reported": 6, "verified": 4, "help_on_way": 3, "resolved": 12},
  "sos_by_severity": {"1": 2, "2": 5, "3": 8, "4": 7, "5": 3},
  "active_tasks": 7, "volunteers_active": 61, "volunteers_on_task": 9,
  "shelters_open": 12, "shelter_occupancy_pct": 34.5,
  "district_risk": 82, "risk_level": "high",
  "pending_verifications": 6, "open_safety_flags": 2,
  "generated_at": "…" }
```

### GET /api/admin/verify-queue — SOS reports with `needs_review` or status `reported`, oldest first. Paginated. Each item carries a machine-readable `reason` (`awaiting_verification | flagged_for_review | assessment_failed | possible_duplicate | reporter_flagged | seed_flagged`).

### GET /api/safety/flags — open misinformation/duplicate flags (admin view):

```json
[{ "id": "…", "type": "possible_duplicate | conflicting_reports | spam_burst",
   "sos_ids": ["…", "…"], "district_id": "patna",
   "evidence": "photo_hash match a1b2…; filed 11 min apart",
   "status": "open", "created_at": "…" }]
```
Admins call the role-scoped `GET /api/safety/flags` (contracts §8); the former
`/api/admin/safety/flags` duplicate was removed in v1.3 (see MIGRATION.md).

### POST /api/admin/safety/flags/{id}/resolve — `{ "resolution": "confirmed_duplicate | confirmed | false_alarm", "note": "…" }` → `200`. `confirmed_duplicate` merges: newest report → `status: "duplicate"` with persisted `duplicate_of` link; both stay visible.

### GET /api/admin/audit — `?limit=&offset=&actor=` → audit entries:

```json
[{ "id": "…", "ts": "…", "actor": "admin:demo | device:<uuid> | system",
   "action": "sos.status_changed | task.assigned | alert.broadcast | …",
   "target_type": "sos", "target_id": "…",
   "details": {"from": "reported", "to": "verified"} }]
```

### GET /api/admin/incidents/{district_id}/export — `?format=json|pdf`

- `format=json` (always works): full incident bundle (SOS list, tasks, alerts, risk
  timeline) as a downloadable JSON file.
- `format=pdf` (shipped Wave 4, Agent 11): real server-rendered incident report
  PDF (reportlab; banner, risk snapshot, SOS/tasks/broadcasts/timeline) as a
  downloadable file. Never a fake PDF.

---

## 8. Safety

### POST /api/sos/{id}/flag — any authed user flags a report

```json
{ "reason": "duplicate | misinformation | spam | other", "note": "…" }
// 201 { "id": "…", "status": "received" }
```

### GET /api/safety/flags — `?district=&status=&mine=&limit=` (role-scoped visibility, finalized Wave 4 — see `docs/safety.md`)

- **Admin:** full flag records (all fields, all statuses).
- **Reporter** (`?mine=true`, guest): flags touching their own reports
  (matched by device ID) — type, status, resolution note, timestamps; only
  their own report IDs.
- **Guest:** `?district=` required; anonymized open-flag counts by type only.

### Flag lifecycle (Wave 4, Agent 10)

- Intake guardrails raise flags automatically: `possible_duplicate` (same
  photo hash within 24 h / 5 km), `conflicting_reports` (severity ≥ 4 vs ≥ 3
  severity ≤ 2 reports within 2 km / 6 h, or vice versa — triage aid only),
  `spam_burst` (≥ 5 reports/device/10 min → `429` on `POST /api/sos` with
  `Retry-After`). Nothing is ever silently dropped.
- `POST /api/admin/safety/flags/{id}/resolve`
  `{ "resolution": "confirmed_duplicate" | "confirmed" | "false_alarm", "note": "…" }`
  → `confirmed_duplicate` additionally **merges**: the newest report in the
  flag gets `status: "duplicate"` with a persisted `duplicate_of` link to the
  oldest; both stay visible and queryable.
- `SOSRead` gains two nullable fields: `duplicate_of` (string, set on merged
  duplicates) and `reporter_trust_tier` (`trusted|standard|new|flagged`,
  verify-queue context only — reporter weighting for admins).
- New WS event: `safety.flag_raised` → `{ type, sos_id, district_id }`.

### PATCH /api/users/me — update own user preferences (Wave 2 addition)

Auth: guest+ (device-anchored user, auto-provisioned).

```json
// request — all fields optional
{ "preferred_lang": "bn", "display_name": "…", "phone": "…" }
// response 200 — the updated user
{ "id": "…", "device_id": "…", "role": "citizen",
  "display_name": "…", "phone": "…", "preferred_lang": "bn", "created_at": "…" }
```

---

## 9. Warnings Worker Status

### GET /api/warnings/status — health of the early-warning pipeline (guest+):

```json
{ "enabled": true,
  "mode": "live | simulated",
  "weather_api": "https://api.open-meteo.com/v1/forecast",
  "districts_tracked": 20,
  "last_ingest_at": "…", "last_ingest_ok": true,
  "last_risk_recompute_at": "…",
  "next_ingest_at": "…" }
```

---

## 10. Realtime — WS /api/stream

**Connect:** `ws://localhost:8000/api/stream?device_id=<uuid>&last_event_id=<n>`
(auth: guest+; admin events require `X-Admin-Key` as a query param `admin_key=` —
documented, demo-only convenience).

**Server → client envelope (all events):**

```json
{ "event_id": 1042, "type": "sos.created", "ts": "2026-10-06T…Z",
  "data": { /* event payload, shapes below */ } }
```

| Event | Payload `data` | Emitted when |
|---|---|---|
| `sos.created` | SOSReport (compact, no assessment) | POST /api/sos persisted |
| `sos.assessed` | `{sos_id, severity, category, priority, rationale}` | AI pipeline finishes |
| `sos.status_changed` | `{sos_id, from, to, note}` | PATCH /api/sos/{id}, verify, task en-route |
| `task.assigned` | Task + volunteer summary | POST /api/tasks |
| `task.updated` | `{task_id, sos_id, from, to}` | accept/decline/enroute/complete/cancel |
| `alert.broadcast` | `{broadcast_id, district_ids, type, severity, languages}` | broadcast sent |
| `risk.updated` | `{district_id, risk, risk_level, weather_source}` | risk recompute |
| `volunteer.registered` | Volunteer (compact) | POST /api/volunteers |

**Client → server:** `{ "type": "ping" }` → `{ "type": "pong", "ts": … }`;
`{ "type": "subscribe", "districts": ["patna"] }` → server filters subsequent events
to those districts (`{ "type": "subscribed", "districts": [...] }`);
`{ "type": "resync", "last_event_id": 1040 }` → server replays missed events
(alternative to the `?last_event_id=` query param — the form the frontend uses).

**Reconnect:** client sends `last_event_id`; server replays missed events (buffer:
last 500 per connection window, then client falls back to REST `?since=`).

---

## 11. Health & Meta

- `GET /api/health` → `{ "status": "ok", "version": "1.0.0-wave2", "db": "ok", "llm": "configured|fallback", "weather": "live|simulated", "ts": "…" }`
- `GET /api/meta/languages` → `{ "languages": [ {code, name, native_name} × 10 ] }`
- `GET /openapi.json` — auto-generated; must stay consistent with this doc (Wave 5 verifies).

---

## 12. Contract Freeze Notice

> These contracts are **DRAFT through the end of Wave 2** and **FROZEN afterwards**.
> After freezing: no renames, no removed fields, no changed enum values. Additive,
> backward-compatible changes (new optional fields, new endpoints) are allowed only
> with a `MIGRATION.md` note in the wave summary and a version bump of this document.
> The frontend `lib/api.ts` and the simulation package (which drives the API as a
> client) both depend on byte-level stability of these shapes.
