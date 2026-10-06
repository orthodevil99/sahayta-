# Wireframe — SOS Board (`/board`)

**Route:** `/board` · **Audience:** citizens, volunteers, officials watching the crisis
**Goal:** live picture of who needs help, where, how badly. **Hero loop steps 2–3.**

Two visual variants ship (toggle in filter bar, persisted). Default: map-first on
≥ 1024px, list-first below that and in low-bandwidth mode.

## Variant A — Map-first (desktop default)

```
┌──────────────────────────────────────────────────────────────────┐
│ ← SOS Board                        [🌐] [📶] [List view ⇄]       │
├──────────────────────────────────────────────────────────────────┤
│ District [Patna ▾]  Sev ≥ [4 ▾]  Status [All ▾]  Cat [All ▾] [🔍] │  filter bar
│ ⚠ DEMO DATA                                                       │
├──────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────┐ ┌─────────────────────────┐ │
│ │                                  │ │ 🔴 LIVE · 14 reports    │ │
│ │     LEAFLET MAP + HEATMAP        │ ├─────────────────────────┤ │
│ │                                  │ │ ┌─────────────────────┐ │ │
│ │   ◆4  ●2   ◆4        ▲3          │ │ │ ◆ 4 · SEVERE  2m    │ │ │
│ │        ◆5         ●1              │ │ │ 🛟 rescue · critical│ │ │
│ │   (pins sized/colored by sev,    │ │ │ Knee-deep water…    │ │ │
│ │    heatmap glow underneath)      │ │ │ 📍 Kankarbagh, Patna│ │ │
│ │                                  │ │ └─────────────────────┘ │ │
│ │  [heatmap legend: ▬▬▬▬▬]         │ │ ┌─────────────────────┐ │ │
│ │  fewer ────────────→ more        │ │ │ ▲ 3 · SERIOUS  9m   │ │ │
│ └──────────────────────────────────┘ │ │ …                   │ │ │
│                                      │ └─────────────────────┘ │ │
│                                      │  (scrollable SOSCards,   │ │
│                                      │   newest/urgent first)  │ │
└──────────────────────────────────────────────────────────────────┘
```

- Pin tap → map flies to pin + matching card highlights (scroll-into-view).
- Card tap → BottomSheet with full SOS detail: photo, full description,
  assessment (severity + rationale + area tags + model used, e.g. `rule-fallback-v1`),
  status timeline (reported → verified → help_on_way → resolved), assigned volunteer,
  actions: `✓ Verify` (admin), `🛟 Assign volunteer` (admin), `🚩 Flag` (anyone).

## Variant B — List-first (mobile default, low-bandwidth forced)

```
┌──────────────────────────────────────────┐
│ ← SOS Board              [List|Map ⇄]    │
│ District [Patna ▾]  Sev ≥ [4 ▾]          │
│ [Status ▾] [Category ▾] [🔍 search]       │  collapsible filter row
├──────────────────────────────────────────┤
│ 🔴 LIVE · 14 reports · updated 12s ago   │
├──────────────────────────────────────────┤
│ ┌──────────────────────────────────────┐ │
│ │ ◆ 4 · SEVERE            2 min ago   │ │
│ │ 🛟 rescue · critical                │ │
│ │ Knee-deep water in Kankarbagh…      │ │
│ │ 📍 Patna · 🛟🚗 needed · DEMO        │ │
│ └──────────────────────────────────────┘ │
│ ┌──────────────────────────────────────┐ │
│ │ ▲ 3 · SERIOUS           9 min ago   │ │
│ │ …                                    │ │
│ └──────────────────────────────────────┘ │
│  (Map toggle opens full-screen map;      │
│   low-bandwidth hides the toggle)        │
└──────────────────────────────────────────┘
```

## Interaction notes
- **Live:** WS `/api/stream` events drive updates — `sos.created` slides a card in,
  `sos.assessed` adds the severity badge, `sos.status_changed` pulses the StatusPill.
  If WS drops: banner `reconnecting…` + silent REST poll `?since=` every 15 s.
- **Filters** map 1:1 to `GET /api/sos` query params (`district`, `severity_min`,
  `status`, `category`, `q`). Sort: `-created_at` default; toggle `severity`.
- **Severity ≥ filter** uses the mini SeverityBadge stepper (1–5).
- Deep-linkable: `/board?district=patna&severity_min=4` (the video uses this URL).
- **Demo anchor:** the Patna flood SOS pins at 25.5941, 85.1376 with red sev-4 badge.

## States
- **Loading:** skeleton SOSCards (3) + map shimmer.
- **Empty (filter matches nothing):** `🗺 No reports match — widen filters or [🚨 Report one]`.
- **Offline:** banner + cached list with `cached HH:MM` note; filters work on cache;
  new reports can't arrive (WS dead) — explicit, not silent.
- **Error:** `⚠ Couldn't load reports [Retry]`; retry preserves filters.
