# Wireframe — Report SOS (`/report`)

**Route:** `/report` · **Audience:** citizen in distress (possibly low-literacy, shaky hands)
**Goal:** photo + words + location → SOS filed in < 60 s. **This is the hero loop step 1.**

## Layout — 4-step wizard (one step per screen, big progress dots)

```
STEP 1/4 — PHOTO
┌──────────────────────────────────────────┐
│ ← Report SOS              ● ○ ○ ○        │
├──────────────────────────────────────────┤
│                                          │
│  ┌────────────────────────────────────┐  │
│  │                                    │  │
│  │        📷  Tap to add photo         │  │  220px tile, dashed border
│  │     (optional but helps AI)         │  │
│  │                                    │  │
│  └────────────────────────────────────┘  │
│  [📷 Take photo]  [🖼 Choose file]       │  two half-width buttons
│                                          │
│  Photo helps the AI judge how bad it is. │  one-line helper (≤ 25 words rule)
│                                          │
│  ┌────────────────────────────────────┐  │
│  │              Skip →                  │  │  text button
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘

STEP 2/4 — DESCRIBE
┌──────────────────────────────────────────┐
│ ← Report SOS              ● ● ○ ○        │
│  What is happening?                      │
│  ┌────────────────────────────────────┐  │
│  │                                    │  │
│  │  [type or speak…]            [🎤]   │  │  textarea ≥ 16px, mic button
│  │                                    │  │
│  └────────────────────────────────────┘  │
│  💡 Say: where, water depth, who is      │  hint chips (tap to insert):
│  at risk.                                │  [knee-deep water] [rooftop] …
│  ┌────────────────────────────────────┐  │
│  │           Continue →                 │  │  btn-primary 56px
│  └────────────────────────────────────┘  │

STEP 3/4 — LOCATION
┌──────────────────────────────────────────┐
│ ← Report SOS              ● ● ● ○        │
│  Where is this happening?                │
│  ┌────────────────────────────────────┐  │
│  │            MAP (Leaflet)           │  │  260px, pin-drop
│  │              📍                    │  │  low-bw → district dropdown
│  └────────────────────────────────────┘  │
│  ┌────────────────────────────────────┐  │
│  │  📡 Use my GPS location             │  │  btn-secondary
│  └────────────────────────────────────┘  │
│  District: [Patna ▾] (auto from pin)     │

STEP 4/4 — REVIEW & SEND
┌──────────────────────────────────────────┐
│ ← Report SOS              ● ● ● ●        │
│  ┌────────────────────────────────────┐  │
│  │ [thumb] knee-deep water… Kankarbagh │  │  summary card
│  │ 📍 Patna · just now                │  │
│  └────────────────────────────────────┘  │
│  Your name (optional) [____________]     │
│  Phone (optional)     [____________]     │
│  ┌────────────────────────────────────┐  │
│  │ 🚨  भेजें · SEND SOS                │  │  btn-sos 64px — the money button
│  └────────────────────────────────────┘  │
│  Works offline — will send when online.  │
└──────────────────────────────────────────┘

SENDING → SUCCESS
┌──────────────────────────────────────────┐
│         ✓  SOS received                  │
│   ┌───────────────────────────────┐      │
│   │ ◆ 4 · SEVERE                  │      │  SeverityBadge appears here —
│   │ rescue · critical priority    │      │  the AI verdict, < 3 s
│   │ "Waist-deep water… rooftops." │      │  rationale in reporter's lang
│   └───────────────────────────────┘      │
│   Volunteers nearby are being notified.  │
│   [Track on board →]  [Report another]   │
└──────────────────────────────────────────┘
```

## Interaction notes
- `client_report_id` UUID is minted when the wizard opens (draft time) — this is
  what makes offline replay idempotent (`api-contracts.md` §1).
- **Mic 🎤:** Web Speech API with `lang` = current UI language; transcript lands in
  the textarea; works offline in Chrome (on-device) where available.
- **GPS:** `navigator.geolocation`; on deny/fail, pin-drop is the fallback; on
  low-bandwidth, district dropdown only.
- Photo: 8 MB cap, jpeg/png/webp; EXIF stripped client-side notice ("location
  removed from photo for privacy" — one line).
- Send: `POST /api/sos` multipart (or JSON + `photo_description` in text mode).
  Severity comes back **in the same response** (synchronous pipeline) → success
  screen shows the badge immediately. This is the demo's "AI moment".
- **Offline send:** Service Worker intercepts → IndexedDB outbox → success screen
  shows `⏳ Queued — will send when you're back online` + QueueBadge count on nav.
  On reconnect: background sync replays; toast confirms; report appears on board.
- Back navigation preserves all inputs (draft in memory + localStorage).

## States
- **Loading:** sending state = button spinner + "Contacting Sahayta…" (≤ 3 s target).
- **Empty:** n/a (form is the empty state).
- **Offline:** amber banner + queued-success variant (above); map replaced by
  district select; photo still allowed (stored in outbox).
- **Error:** 422 → inline field errors ("Description needs 10+ characters");
  413 → "Photo too large — try under 8 MB"; 429 → "Too many reports — wait N min";
  network fail → falls back to offline-queue path, never a dead end.
- **AI degraded:** if pipeline fails, report still files (`severity: null`,
  `needs_review: true`) → success screen shows `🔍 Sent — awaiting review`
  instead of a severity badge (honest, per architecture §1.3).
