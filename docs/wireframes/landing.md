# Wireframe — Landing (`/`)

**Route:** `/` · **Audience:** first-time visitor, potential volunteer, judge
**Goal in 30 s:** understand the problem, the loop, and that it is real software.

## Layout (mobile-first; desktop centers at max-w 1100px)

```
┌──────────────────────────────────────────┐
│ [🌐 हिन्दी]          SAHAYTA      [📶]    │  header: switcher, wordmark, bw toggle
├──────────────────────────────────────────┤
│ ⚠ DEMO MODE — all data synthetic         │  only when ?demo=1 / demo key
├──────────────────────────────────────────┤
│                                          │
│   WHEN DISASTER STRIKES,                 │  display 32/800
│   HELP FINDS YOU.                        │
│                                          │
│   Photo → AI severity → volunteer        │  body, ≤ 25 words
│   dispatched → alert out. Offline-first. │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │ 🚨  Report an SOS                   │  │  btn-sos, 64px
│  └────────────────────────────────────┘  │
│  ┌────────────────────────────────────┐  │
│  │ ▶  Play Patna flood demo (2 min)    │  │  btn-secondary → demo-director
│  └────────────────────────────────────┘  │
├──────────────────────────────────────────┤
│  HOW IT WORKS                            │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐             │
│  │ 📷 │ │ 🤖 │ │ 🛟 │ │ 📢 │             │  4 icon steps, horizontal scroll
│  │Report│ │ AI │ │Help│ │Alert│            │  mobile / 4-col grid desktop
│  └────┘ └────┘ └────┘ └────┘             │
├──────────────────────────────────────────┤
│  LIVE FROM THE NETWORK (demo data)       │
│  ┌────────┐ ┌────────┐                   │
│  │ 3,000  │ │ 1,000  │  StatTiles        │
│  │SOS reps│ │voluntrs│  (seed counts)    │
│  └────────┘ └────────┘                   │
│  ┌────────┐ ┌────────┐                   │
│  │  500   │ │  20    │                   │
│  │shelters│ │distrcts│                   │
│  └────────┘ └────────┘                   │
├──────────────────────────────────────────┤
│  🗺 Mini map: live SOS pins (Patna       │  Leaflet, read-only, 220px tall
│     heatmap preview, tap → /board)       │  low-bandwidth → text list
├──────────────────────────────────────────┤
│  Built for WarriorHacks 2.0 · demo data  │  footer
│  [Become a volunteer →]                  │
└──────────────────────────────────────────┘
```

## Interaction notes
- `▶ Play Patna flood demo` seeds the DB (if empty) and starts the demo-director
  timeline; it walks the visitor through report → severity → dispatch → alert →
  dashboard automatically (this is the video path too).
- Mini map is decorative-live: real pins from `GET /api/sos?limit=50`, tap-through
  to `/board`. Never auto-zooms on load (motion + data courtesy).
- Language switcher in header works on this screen (proves i18n instantly).
- `Become a volunteer` → `/volunteer?register=1`.

## States
- **Loading:** hero text renders immediately (static); StatTiles + map show skeletons.
- **Empty (fresh DB, no seed):** StatTiles show `0` with caption "seed the demo";
  hero CTA row adds `🌱 Load demo data` (calls seed endpoint / runs seed script).
- **Offline:** banner `📶 Offline — browsing cached data`; CTAs still work;
  `Report an SOS` queues (outbox), everything else reads cache/API-fallback.
- **Error (API down):** hero + explainer render; stats area shows
  `⚠ Couldn't reach the server — retry` button; map tile replaced by text list.
