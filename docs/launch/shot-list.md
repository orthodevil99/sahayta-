# Sahayta — Screenshot Shot List (8 shots)

For prakhar. Capture in a **fresh incognito window** at 1440×900 (or 1920×1080),
`?demo=1` appended to every URL. Browser chrome visible is fine for Devpost
(it reads as "real app"), but **crop out** bookmarks bars, extensions, and any
personal tabs. DEMO DATA / SIMULATED FEED chips must stay IN frame — never crop
the honesty labels.

Pre-flight (once): `cd packages/simulation && python demo_director.py
--scenario patna-flood` → 14/14 PASS. Then `cd frontend && npm run dev -p 3000`
(or serve the static `out/` build).

---

## Shot 1 — Landing hero
- **URL:** `http://localhost:3000/?demo=1`
- **Steps:** Load → wait for hero + stat tiles to render → hover (don't click)
  **▶ Play Patna flood demo** so the button shows its hover state.
- **Must be visible:** headline, 4-step how-it-works, live stat tiles from seed
  data, the demo button, DEMO MODE banner.
- **Crop out:** nothing required; full hero is the shot.

## Shot 2 — Report-SOS wizard with photo
- **URL:** `http://localhost:3000/report?demo=1`
- **Steps:** Language switcher → Hindi. Step 1: choose
  `data/demo/patna-flood/flood-photo.jpg`. Step 2: paste the exact Hindi
  fixture text. Step 3: drop the pin at Kankarbagh. Screenshot on the
  **review step**, before tapping SEND.
- **Must be visible:** the uploaded flood photo, Hindi description text,
  map with pin, the red **भेजें · SEND SOS** button, 4 progress dots.
- **Crop out:** file-picker dialog (screenshot after it closes).

## Shot 3 — AI severity-4 badge
- **URL:** same as Shot 2, continued.
- **Steps:** Tap **भेजें** → wait for the success screen → hover the assessment
  line until `model: rule-fallback-v1` appears → screenshot.
- **Must be visible:** **◆ 4 · SEVERE** badge, one-line Hindi rationale,
  category chip **rescue**, priority **critical**, the `model:` label.
- **Crop out:** nothing — the model label is the point of this shot.

## Shot 4 — SOS board with Patna pin
- **URL:** `http://localhost:3000/board?demo=1` (district filter → Patna)
- **Steps:** After Shot 3, open the board → set district filter to Patna →
  wait for the red pin to drop on the Kankarbagh heatmap → screenshot.
- **Must be visible:** heatmap hot zone, red severity-4 pin, the SOS list card
  with badge + category + priority, DEMO DATA chip.
- **Crop out:** other districts' pins if they clutter (zoom to Patna).

## Shot 5 — Volunteer task accepted
- **URL:** `http://localhost:3000/volunteer?demo=1`
- **Steps:** Run **▶ Play Patna flood demo** from the landing page first (it
  creates the task), then open the volunteer view → accept the task card →
  screenshot the **accepted** state showing Ravi Kumar's card + reputation.
- **Must be visible:** task card with SOS summary, **Accepted** status,
  Ravi Kumar name, reputation score, task lifecycle buttons.
- **Crop out:** empty-state illustrations if present elsewhere on the page.

## Shot 6 — Hindi broadcast alert
- **URL:** `http://localhost:3000/alerts?demo=1`
- **Steps:** From `/admin?demo=1`, send the broadcast (district Patna, flood,
  severity 4, title **बाढ़ चेतावनी**) → open `/alerts` → screenshot the alert
  at the top in **Devanagari**, then open "View in" and screenshot the
  bottom sheet mid-scroll through the 10 languages (take both; pick the
  better one).
- **Must be visible:** Devanagari message readable at screenshot resolution,
  language count (10), district + severity metadata.
- **Crop out:** the composer (this shot is the received alert, not the form).

## Shot 7 — Admin dashboard command view
- **URL:** `http://localhost:3000/admin?demo=1` (district → Patna)
- **Steps:** After the demo play-through: open admin → wait for all panels →
  screenshot the full viewport.
- **Must be visible:** KPI row, SOS map + heatmap, risk panel, volunteer board
  (Ravi "on task"), incident timeline in order, DEMO MODE banner.
- **Crop out:** nothing — this is the "real district office" money shot.
  If the viewport is short, take two overlapping shots (top KPIs+map,
  bottom timeline+board).

## Shot 8 — Risk 82/HIGH panel with SIMULATED FEED chip
- **URL:** same as Shot 7.
- **Steps:** Scroll to the risk panel → hover the **SIMULATED FEED** chip →
  screenshot tight on the panel.
- **Must be visible:** **risk 82 · HIGH**, factor bars (rainfall_24h_mm top),
  the SIMULATED FEED chip with hover tooltip, `weather_source` labeling.
- **Crop out:** surrounding panels — tight crop on the risk card only.

---

## Between takes
- **Reset:** clear site data for localhost (DevTools → Application → Clear
  storage) or open a new incognito window. `playPatnaDemo()` replays mint a
  fresh SOS each run, so replays never collide.
- **If a take breaks:** don't improvise around it. Reset, re-run
  `demo_director.py --scenario patna-flood`, confirm 14/14 PASS, re-shoot.
- **File naming:** `sahayta-01-landing.png` … `sahayta-08-risk.png`,
  PNG, committed under `docs/launch/shots/` (create the dir when capturing).
