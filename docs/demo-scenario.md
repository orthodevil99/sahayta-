# Sahayta — Demo Scenario (Acceptance Test)

**"Monsoon flood in Patna district"** — the canonical end-to-end walkthrough.
Every agent in Waves 2–5 MUST keep this scenario working; it is the acceptance test
for the whole system and the backbone of the 2–3 minute demo video.

**Determinism rule:** the scenario runs identically every time. The demo-director
(Wave 3, Agent 9) replays it with fixed seeds: same photo fixture, same description
text, same expected severity (4), same matched volunteer, same Hindi alert copy.
Any agent whose change breaks a step below must fix it before marking their work done.

**Fixture inputs** (live in `data/demo/patna-flood/` after Wave 2):

- `flood-photo.jpg` — waist-deep water across a residential lane (synthetic/stock-style;
  clearly labeled demo fixture, NOT a real disaster photo).
- `description.txt` — Hindi text (exact):
  `पटना के कंकड़बाग इलाके में घुटनों तक पानी भर गया है। दो गलियों में घरों में पानी घुस गया है, बुजुर्ग छत पर हैं। तुरंत मदद चाहिए।`
  (Translation: "Knee-to-waist water has filled Kankarbagh, Patna. Water has entered
  homes in two lanes; elderly residents are on rooftops. Help needed immediately.")
- `volunteer.json` — the expected match: "Ravi Kumar", skills `["rescue","driving"]`,
  2.1 km from the SOS, languages `["hi","hing"]`, availability `anytime`, seeded by
  `scripts/seed.py` with a FIXED id `vol-ravi-kumar-patna`.

---

## Act 1 — Citizen reports (0:00–0:30 in the video)

**Step 1.** Citizen opens `/report` (language switcher set to Hindi).
UI shows: photo picker, description box, geotag (GPS button + Leaflet pin-drop map).

**Step 2.** Citizen uploads `flood-photo.jpg`, pastes the Hindi description, drops the
pin at **lat 25.5941, lon 85.1376** (Kankarbagh, Patna), taps "भेजें (Send SOS)".

**Step 3.** Frontend behavior:
- Online: `POST /api/sos` (multipart) with a fresh `client_report_id` (UUID).
- Offline (airplane-mode take): Service Worker queues to IndexedDB outbox, UI shows
  "कतार में — ऑनलाइन होते ही भेजा जाएगा (Queued — will send when online)".

**ACCEPT:** `201` (or `200` on replay with the same `client_report_id`).
Response contains `id`, `status: "reported"`, `district_id: "patna"`.
Offline take: outbox holds exactly 1 entry; on reconnect it syncs with zero duplicates.

## Act 2 — AI severity estimation (0:30–1:00)

**Step 4.** Backend runs `pipeline.assess_and_route` synchronously inside `POST /api/sos`.

**ACCEPT (exact):**

```json
{
  "severity": 4,
  "rationale": "…mentions waist/knee-deep water…residential…rooftops…",
  "area_tags": ["road_submerged", "residential"],
  "category": "rescue",
  "priority": "critical",
  "suggested_skills": ["rescue", "driving"]
}
```

- Rationale must be one line, in the reporter's language (Hindi), mentioning water
  depth and people at risk. (Rule-fallback path must ALSO produce severity 4 —
  keyword scoring on "घुटनों तक पानी/तुरंत मदद/छत" is tuned for this fixture.)
- `model` field honestly reports which path ran (`glm-4-flash` or `rule-fallback-v1`).
- WS event `sos.assessed` fires; `/board` shows the new pin with a **red severity-4
  badge** within 2 s of the POST completing.

**Step 5.** SOS appears on the triage board (`/board`): pin on the Leaflet heatmap at
Kankarbagh + list card showing severity badge, category chip ("rescue"), priority
("critical"), time-ago, and district filter preset to Patna.

**ACCEPT:** `GET /api/sos?district=patna&severity_min=4` includes the new report;
`GET /api/sos/{id}` returns the nested `assessment` object.

## Act 3 — Volunteer matched & dispatched (1:00–1:30)

**Step 6.** Matching: `POST /api/tasks/match {"sos_id": "<id>", "max_results": 5}`.

**ACCEPT:** top match is `vol-ravi-kumar-patna` with `score ≥ 80`,
`distance_km ≈ 2.1` (±0.5), and `reasons` containing "skill match: rescue".

**Step 7.** Dispatch: `POST /api/tasks {"sos_id": "<id>", "volunteer_id": "vol-ravi-kumar-patna"}`
→ `201`, `status: "assigned"`. WS `task.assigned` fires.

**Step 8.** Volunteer flow on `/volunteer` (as Ravi): task card appears →
**Accept** (`POST /api/tasks/{id}/accept` → `accepted`) →
**En route** (`POST /api/tasks/{id}/enroute` → `en_route`).

**ACCEPT:** parent SOS flips to `status: "help_on_way"`; WS `sos.status_changed`
fires; board card updates to amber "Help on way" state.

**Step 9.** **Complete** (`POST /api/tasks/{id}/complete {"note": "…"}` → `completed`).

**ACCEPT:** SOS → `status: "resolved"`; Ravi's `reputation` increases by 2
(50 → 52 on a fresh seed); `tasks_completed` = 1.

## Act 4 — Hindi alert broadcast (1:30–1:50)

**Step 10.** Admin opens `/admin`, composes broadcast:
district `patna`, type `flood`, title `बाढ़ चेतावनी`, body describing rising water in
Kankarbagh and open relief camps, severity 4, languages `[hi, hing]`.

**Step 11.** `POST /api/alerts/broadcast` → `202`.

**ACCEPT:** response `rendered.hi` is ≤ 480 chars, in Devanagari, mentions Patna/
Kankarbagh and safety action; `rendered.hing` is the Latin-script version;
WS `alert.broadcast` fires; `/alerts` feed shows both messages; audit log contains
`alert.broadcast` with `actor: "admin:demo"`.

## Act 5 — Command dashboard + risk spike (1:50–2:20)

**Step 12.** Admin dashboard (`/admin`) for Patna shows, all live (no refresh needed):

| Panel | Expected value |
|---|---|
| SOS map | ≥ 1 pin at Kankarbagh, red severity-4 badge |
| Severity heatmap | hot zone over Kankarbagh |
| SOS counts | `reported+verified+help_on_way+resolved` reflects Acts 1–3 |
| District risk | **risk ≥ 70** (`high` or `severe`), `weather_source` labeled |
| Risk factors | includes `rainfall_24h_mm` with a high contribution |
| Volunteer board | Ravi Kumar listed, status on-task/available |
| Incident timeline | report → assessed → assigned → accepted → en-route → completed → broadcast, in order |

**ACCEPT:** `GET /api/admin/overview?district=patna` returns all of the above;
`GET /api/districts/patna/risk` → `risk ≥ 70` with `factors[]` non-empty.
(The demo seed sets Patna's risk to **82/high** via `weather-sample.json`.)

## Act 6 — Offline + early warning (2:20–2:40, optional in video)

**Step 13.** Toggle low-bandwidth mode: map tiles and photos replaced by text list;
every map pin has a text mirror (a11y requirement).

**Step 14.** `GET /api/warnings/status` → `{"enabled": true, "districts_tracked": 20,
"last_ingest_ok": true}` and `GET /api/districts/patna/forecast` → 72 hourly entries.

**ACCEPT:** forecast hours each carry `risk` + `risk_level`; UI shows the
"SIMULATED FEED" label whenever `weather_source == "simulated"`.

---

## Failure Injections (for Wave 5 test pass — not in the video)

1. **No LLM configured:** unset `SAHAYTA_LLM_*` → Act 2 still yields severity 4 via
   rule fallback; `model` reads `rule-fallback-v1`.
2. **Weather API down:** `SAHAYTA_WEATHER_MODE=simulated` or blocked network →
   risk still computes; UI labels the feed simulated.
3. **Offline report:** airplane mode during Act 1 → outbox → reconnect → exactly
   one SOS (idempotent replay verified by `client_report_id`).
4. **Duplicate photo:** re-upload `flood-photo.jpg` → `photo_hash` matches →
   safety flag `possible_duplicate` raised, second report marked for review —
   NOT silently dropped.

## Sign-off Checklist (Wave 5 Agent 15 runs this verbatim)

- [ ] All 14 steps pass against a fresh seed (`scripts/seed.py` → demo mode).
- [ ] Demo-director replay (`packages/simulation/demo_director.py --scenario patna-flood`)
      completes with exit 0 and prints the 14 ACCEPT lines as PASS.
- [ ] No step requires an API key; no step hits a real external service
      except the optional live weather fetch (which has a labeled fallback).
- [ ] Every screen involved shows DEMO DATA labeling where synthetic data appears.
