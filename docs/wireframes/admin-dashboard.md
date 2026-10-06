# Wireframe — Admin Command Dashboard (`/admin`)

**Route:** `/admin` · **Audience:** district official (role-gated via `X-Admin-Key`)
**Goal:** one screen to run the disaster: see everything, verify, dispatch, broadcast.
**Carries the Feasibility judging criterion — must look like a real district office tool.**

## Access
- Without admin key: `🔒 Official access — enter admin key` (password field, demo
  hint shows `demo-admin-key`; wrong key → 403 + audit-logged).
- With key: full dashboard + persistent slim `⚠ DEMO MODE` banner.

## Layout (desktop 3-col; mobile stacks: map → risk → volunteers → broadcast → timeline)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ← Command · Patna district        [district ▾]  ⚠ DEMO MODE      [🌐]    │
├──────────────────────────────────────────────────────────────────────────┤
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│ │SOS active│ │Sev ≥ 4   │ │Volunt.   │ │Risk      │ │Shelters  │  KPI row    │
│ │   14     │ │    7     │ │ 61 avail │ │ 82 HIGH  │ │ 34% full │  (overview) │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘            │
├──────────────────────────────────┬───────────────────────────────────────┤
│                                  │  DISTRICT RISK                        │
│      SOS MAP + HEATMAP           │  ┌──────────────────────────────┐     │
│      (Leaflet, live pins,        │  │        ╭───╮                 │     │
│       click pin → SOS detail     │  │       ╱ 82  ╲   HIGH        │     │
│       side panel)                │  │      ╰─────╯                 │     │
│                                  │  └──────────────────────────────┘     │
│  [heatmap toggle] [verify queue   │  Factors:                             │
│   (6)] [safety flags (2)]        │  ▓▓▓▓▓▓▓░░░ rainfall 24h 187mm (+28.9)│
│                                  │  ▓▓▓▓▓░░░░░ river rising (+21.0)      │
│                                  │  [SIMULATED FEED] · 72h forecast →    │
├──────────────────────────────────┼───────────────────────────────────────┤
│  VOLUNTEER AVAILABILITY          │  📢 BROADCAST COMPOSER                │
│  🟢 52 available · 🟡 9 on task  │  Districts: [Patna ✕][+ add]          │
│  ┌────────────────────────────┐  │  Type: [🌊 flood ▾]  Sev: [4 ◆]     │
│  │ Ravi Kumar · 🛟🚗 · 2.1km  │  │  Title [______________]             │
│  │ ★52 · on task (SOS #a1b2)  │  │  Body  [______________]  (n/480)   │
│  └────────────────────────────┘  │  Langs: [✓hi][✓hing][✓bn]…(10)       │
│  ┌────────────────────────────┐  │  [Preview: हिन्दी | Hinglish | …]   │
│  │ Asha Devi · ✚🌐 · 3.4km    │  │  👥 ~12,400 recipients              │
│  │ ★78 · available           │  │  ┌──────────────────────────────┐  │
│  └────────────────────────────┘  │  │ 📢 SEND BROADCAST            │  │
│  (sorted: on-task → available    │  └──────────────────────────────┘  │
│   → off-duty; match scores on    │  Confirm modal: shows rendered HI   │
│   hover for dispatch)            │  text + "This will alert ~12,400    │
├──────────────────────────────────┤  people in Patna." [Send][Cancel]   │
│  INCIDENT TIMELINE               │                                       │
│  12:04 SOS reported (#a1b2)      │  [Export: JSON] [Export: PDF]        │
│  12:04 AI severity 4 (rule-      │                                       │
│        fallback-v1)              │                                       │
│  12:06 Ravi Kumar assigned       │                                       │
│  12:09 → en route (SOS help_on_  │                                       │
│        way)                      │                                       │
│  12:21 completed → resolved ★+2  │                                       │
│  12:25 📢 broadcast sent (hi+    │                                       │
│        hing)                      │                                       │
└──────────────────────────────────┴───────────────────────────────────────┘
```

## Interaction notes
- **KPI row** = `GET /api/admin/overview?district=patna` (sos_by_status,
  sos_by_severity, volunteers_active/on_task, district_risk, shelter occupancy).
- **Map:** same Leaflet stack as `/board` + severity heatmap layer (toggleable) +
  shelter markers `⛺`. Pin click → SOS detail side panel with `Verify` /
  `Assign volunteer` / `Mark duplicate` actions.
- **Verify queue** tab: `GET /api/admin/verify-queue` — oldest first; each row has
  one-click `✓ Verify` / `⦸ Reject` / `⧉ Duplicate-of…` (POST `/api/sos/{id}/verify`).
- **Safety flags** tab: `GET /api/admin/safety/flags` — `possible_duplicate |
  conflicting_reports | spam_burst` with evidence strings; resolve actions.
- **Risk panel:** `GET /api/districts/{id}/risk` — gauge + factor bars +
  `weather_source` label (`SIMULATED FEED` chip when simulated) + link to 72h forecast.
- **Broadcast composer:** `POST /api/alerts/broadcast`; language checkboxes default
  all 10; live per-language preview tabs; char counter enforces ≤ 480; recipient
  estimate shown pre-send; confirm modal prevents mis-taps; every send audit-logged.
- **Incident timeline:** derived from audit log (`GET /api/admin/audit`) — the
  video's "everything happened in order" proof.
- **Export:** JSON always works (downloads incident bundle); PDF button calls
  `?format=pdf` — before Wave 4 it 501s, so the button is **disabled with tooltip
  "PDF export ships in Wave 4"** (never a fake download).
- All admin actions emit WS events; two officials see each other's changes live.

## States
- **Loading:** KPI skeletons + map shimmer + panel skeletons.
- **Empty (no SOS):** map shows district outline + `No active reports` + risk panel
  still live (early-warning works with zero SOS — that's the point).
- **Offline:** admin requires connection — full-screen `📶 Admin needs connection`
  with cached read-only overview if available (no actions enabled).
- **Error/403:** wrong key → `🔒 Invalid admin key` + audit entry; API error →
  per-panel `⚠ [Retry]` (panels fail independently, never a blank dashboard).
