# Sahayta — Demo Video Script (3 variants)

**Owner:** Agent 13 (Wave 5) · **Source beats:** `docs/demo-storyboard.md` (Agent 3)
**Determinism:** every take is reproducible — backend via
`packages/simulation/demo_director.py --scenario patna-flood` (14/14 PASS),
UI via frontend `?demo=1` or `playPatnaDemo()`.
**Eligibility rule:** the video must be 2–3 minutes. Variants A and B target
2:30 (30 s of safety margin); Variant C is a 90-second cutdown.

Judging criteria key: **[I]** Impact · **[F]** Feasibility ·
**[UX]** User Experience · **[T]** Technical Craft.

## Take-source legend (used in every scene)

| Tag | Meaning | Command / URL |
|---|---|---|
| `[DIR]` | Backend determinism check (run BEFORE recording) | `cd packages/simulation && python demo_director.py --scenario patna-flood` → expect 14/14 PASS, exit 0 |
| `[UI]` | Frontend UI take, seeded demo data, no backend needed | `http://localhost:3000/?demo=1` (or the static `out/` build) |
| `[PLAY]` | Auto-choreography take | Landing page → **▶ Play Patna flood demo** (`playPatnaDemo()`, ~35 s) |
| `[LIVE]` | Live backend take (optional B-roll) | Backend on `:8000` (fresh `seed.py --fresh`), frontend with `NEXT_PUBLIC_API_URL=http://localhost:8000` |

**Pre-record ritual (all variants):** run `[DIR]` once. If any step FAILs, stop
and fix — never record over a red director. Then open a **fresh incognito
window** for `[UI]` takes so localStorage deltas don't leak between takes.

**Honest-number rule:** every number spoken on camera is measured, from
`packages/simulation/load_results.json`, `SIMULATION_REPORT.md`,
`backend/warnings/BACKTEST_REPORT.md`, or `docs/i18n-coverage.md`.
The early-warning backtest measured 0.0 precision/recall (documented
limitation: the v1 formula caps flood-only risk below the >85 warning band) —
so the script shows the forecast *curve* but never claims validated warning
precision.

---

# VARIANT A — "One Photo" (human-story led) · 2:30 · **RECOMMENDED**

*Angle:* follow one citizen, one volunteer, one district official through a
single flood. The system is the invisible scaffolding; the people are the story.
Strongest on **[I]** and **[UX]**, carries **[F]** and **[T]** inside the flow.

## A1 — Hook (0:00–0:15) · [I]

| | |
|---|---|
| **On screen** | Full-bleed `data/demo/patna-flood/flood-photo.jpg` (synthetic fixture, DEMO label visible in corner). Slow zoom. Title card fades in: **"When disaster strikes, help finds you."** Subtitle: *Sahayta — a disaster-response OS for India.* |
| **Action** `[UI]` | Open `http://localhost:3000/?demo=1`. Hold the photo 5 s, then cut to the landing page with **▶ Play Patna flood demo** highlighted (do not click yet). |
| **Voiceover** | "Every monsoon, floods hit India. Phones work, networks don't, and help can't find the people who need it. This is Sahayta — a disaster-response OS for India." |
| **Production** | Burned-in English captions throughout. The DEMO DATA chip must be legible on the photo — honesty is graded. |

## A2 — Report SOS (0:15–0:45) · [UX] [I]

| | |
|---|---|
| **On screen** | `/report?demo=1` with UI language set to **Hindi**. 4-step wizard: (1) photo picker → select `flood-photo.jpg`; (2) description box → paste the exact Hindi fixture text; mic button shown briefly; (3) Leaflet map → pin dropped at Kankarbagh (25.5941, 85.1376); (4) review → big red **भेजें · SEND SOS** tapped. |
| **Action** `[UI]` | Perform the wizard live at natural speed (~25 s). Progress dots fill. Do not rush the pin drop — the map is a judging moment. |
| **Voiceover** | "A citizen in Patna — Kankarbagh, pronounced KUN-ker-bagh — photographs rising water. No English needed. No account. No manual. A photo, her own words, a pin on the map — sixty seconds, even on a shaky 2G connection." |
| **Production** | UI stays in Hindi the whole scene; captions translate. Briefly hover the mic icon (voice input exists; we show it, we don't fake a transcription). |

## A3 — AI severity in seconds (0:45–1:15) · [T] [UX]

| | |
|---|---|
| **On screen** | Success screen: **◆ 4 · SEVERE** badge slams in with the one-line Hindi rationale (waist-deep water, rooftops), category chip **rescue**, priority **critical**, suggested skills rescue + driving. Hover to reveal `model: rule-fallback-v1`. Cut to `/board?demo=1&district=patna`: red pin drops onto the Kankarbagh heatmap, the SOS card slides into the list. |
| **Action** `[UI]` | Pause a full 2 s on the badge. The `model:` hover is mandatory — hold it 2 s. Then the board cut; no page refresh anywhere (WS live update). |
| **Voiceover** | "Sahayta's AI reads the photo and the Hindi text: severity 4 out of 5, rescue category, critical priority — in seconds. And notice the label: rule-fallback-v1. It works with zero API keys, because in a disaster you can't depend on one." |
| **Production** | The honest `model` label MUST be visible — Agent 3's storyboard marks this as graded. On the measured engine, the estimator scores 0.602 exact-match and 1.000 within-one on five thousand hand-labeled fixtures (say this only if time allows in the edit; it belongs to Variant B). |

## A4 — Volunteer matched & dispatched (1:15–1:35) · [F] [UX]

| | |
|---|---|
| **On screen** | Admin clicks **Assign** → match panel: **Ravi Kumar — score 92.5**, reasons *"skill match: rescue · 2.1 km away · available now"*. Assign → switch to `/volunteer?demo=1` as Ravi → task card → **Accept** → **En route**. Back on `/board`: the SOS card pulses amber **Help on way**. |
| **Action** `[UI]` | Show the match reasons list (transparency = the Feasibility argument). Every transition must visibly happen with no refresh — that is the shot. |
| **Voiceover** | "Matching is skills, times distance, times availability. The nearest qualified volunteer: Ravi Kumar, 2.1 kilometers away, match score 92.5. He accepts. He's en route. And everyone watching the board sees it happen live." |

## A5 — Hindi alert broadcast (1:35–1:55) · [I] [UX]

| | |
|---|---|
| **On screen** | `/admin?demo=1` → broadcast composer: district Patna, type flood, severity 4, title **बाढ़ चेतावनी** (baadh CHET-av-nee, "flood warning"), body typed once. Preview tabs flip **Hindi (Devanagari) → Hinglish (Latin)** — linger 3 s on each. **SEND** → confirm modal ("~12,400 people") → sent. Cut to `/alerts?demo=1`: the Hindi alert sits at top; open "View in" → bottom sheet scrolls all **10 languages**. |
| **Action** `[UI]` | Type the message once — the ten-language sheet is the visual proof. The Hinglish version must be readable on camera. |
| **Voiceover** | "One message, typed once, goes out in ten Indian languages — Hindi, Hinglish, Bengali, Tamil, Telugu, Marathi, Gujarati, Kannada, Malayalam, Punjabi — each short enough for SMS, because SMS is what reaches people when data doesn't." |

## A6 — Command dashboard (1:55–2:20) · [F] [T]

| | |
|---|---|
| **On screen** | `/admin?demo=1` full view: KPI row, live SOS map + severity heatmap glowing over Kankarbagh, **risk 82 · HIGH** with factor bars (rainfall 184.7 mm/24h the top contributor), **SIMULATED FEED** chip (hover it — call it out, don't hide it), volunteer board with Ravi "on task", incident timeline in order (reported → assessed → assigned → accepted → en-route → broadcast). Click **Export PDF** — the download is real. |
| **Action** `[UI]` | Slow pan across panels (~20 s). The SIMULATED FEED hover is mandatory. The PDF click shows a real generated report — never a fake download. |
| **Voiceover** | "The district official sees everything on one screen: the live SOS map, a risk score of 82 with the reasons behind it, who's available, and a minute-by-minute incident timeline. Even the simulated weather feed is labeled — because in a disaster, trust is the feature." |

## A7 — Offline + early warning (2:20–2:25) · [T] [F]

| | |
|---|---|
| **On screen** | Split 5-second demos: (1) airplane mode on → file an SOS → **Queued** → reconnect → **sent, no duplicates**; (2) 72-hour forecast chart for Patna, risk curve rising ahead of the flood peak. |
| **Action** `[UI]` | Keep both snappy — 5 s each. The forecast shot shows the curve; the voiceover makes no precision claim (see honest-number rule). |
| **Voiceover** | "Networks die in disasters — so reports queue offline and sync without duplicates. And the early-warning engine was already watching the sky." |

## A8 — Close (2:25–2:30) · [I]

| | |
|---|---|
| **On screen** | Back to the flood photo, now with the resolved SOS card overlaid: **✓ Resolved — Ravi Kumar · +2 ★**. Title: *"Sahayta — when disaster strikes, help finds you."* End card: repo URL + "Built for WarriorHacks 2.0". |
| **Action** `[UI]` | Hold 4 s. |
| **Voiceover** | "One photo. One volunteer. One district that knew what was coming. That's Sahayta." |

**Variant A runtime check:** 15+30+30+20+25+20+10 = **150 s = 2:30** ✓

---

# VARIANT B — "The Machine That Coordinates" (system-capability led) · 2:30

*Angle:* structured as four chapters, one per judging criterion. For judges who
score analytically — show each criterion being answered, in order. Same footage
sources as Variant A, different narration spine.

## B1 — Chapter 1: IMPACT (0:00–0:40) · [I]

| | |
|---|---|
| **On screen** | 0:00–0:12: flood fixture + title card (same as A1). 0:12–0:25: `/report?demo=1` in Hindi — photo, description, pin, SEND (fast-forward the wizard at 1.5×; the full-speed version lives in Variant A). 0:25–0:40: `/alerts?demo=1` 10-language bottom sheet scrolling. |
| **Action** `[UI]` | Quick, propulsive cutting. The impact argument is *reach*: the affected citizen first, the warned population last. |
| **Voiceover** | "Floods hit India every single monsoon. Sahayta is a disaster-response OS built for the people in the water — not the people in the control room. A citizen reports in Hindi, in sixty seconds. A district warns twelve thousand people in ten languages. That is the impact story: the last mile, covered." |

## B2 — Chapter 2: FEASIBILITY (0:40–1:15) · [F]

| | |
|---|---|
| **On screen** | 0:40–0:55: `/board?demo=1` — SOS triage queue, severity badges, filters. 0:55–1:05: match panel → Ravi Kumar 92.5 → Assign → Accept → En route → SOS flips to Help on way. 1:05–1:15: `/admin?demo=1` — KPI row, volunteer board, incident timeline, **Export PDF** clicked (real download). |
| **Action** `[UI]` | This chapter is one continuous coordination loop: report → triage → match → dispatch → resolve → export. No refreshes, no cuts that hide loading. |
| **Voiceover** | "Feasibility means a district office could actually run this. A triage queue that sorts itself. Volunteer matching on skills, distance, and availability — inspectable, not a black box. A full incident timeline that exports to a real PDF report. This is the coordination loop, end to end, with nothing staged." |

## B3 — Chapter 3: USER EXPERIENCE (1:15–1:50) · [UX]

| | |
|---|---|
| **On screen** | 1:15–1:28: `/report?demo=1` — language switcher flipped Hindi → Tamil → Bengali (UI re-renders instantly, zero hardcoded strings). Mic button hover. 1:28–1:38: low-bandwidth toggle → map becomes text list (every pin mirrored). 1:38–1:50: airplane mode → SOS queued → reconnect → sent, no duplicates; high-contrast + font-size controls. |
| **Action** `[UI]` | Each UX claim gets its 5-second visual proof. The language switch is the money shot — three scripts in ten seconds. |
| **Voiceover** | "Designed for the actual user: ten languages with zero hardcoded strings, voice input for low-literacy reporters, a text-first mode when bandwidth dies, and an offline outbox that syncs without duplicates. Accessibility isn't a checklist here — it's the product." |

## B4 — Chapter 4: TECHNICAL CRAFT (1:50–2:20) · [T]

| | |
|---|---|
| **On screen** | 1:50–2:00: severity badge + `model: rule-fallback-v1` hover; terminal overlay showing `demo_director.py --scenario patna-flood` → **14/14 PASS**. 2:00–2:10: risk panel — 82/HIGH, factor bars, SIMULATED FEED chip. 2:10–2:20: terminal overlay with the measured load numbers; `load_results.json` open. |
| **Action** `[DIR]` + `[UI]` | Two terminal inserts (director PASS, load numbers) over UI B-roll. The numbers on screen must match `load_results.json` exactly. |
| **Voiceover** | "Under the hood: a multi-agent AI pipeline — vision severity, triage, multilingual alerts, district risk scoring — with an honest rule-based fallback when no model is configured. Measured, not claimed: two hundred seventy-five requests, zero errors, p95 latency one hundred seven milliseconds. The severity estimator scores point-six-oh-two exact-match on five thousand hand-labeled fixtures. Two thousand simulated disaster scenarios back the load story. Deterministic end to end — the demo director passes fourteen of fourteen, every time." |

## B5 — Close (2:20–2:30) · [I]

| | |
|---|---|
| **On screen** | Flood photo + resolved card (same as A8). End card: repo URL + "Built for WarriorHacks 2.0". |
| **Action** `[UI]` | Hold 4 s. |
| **Voiceover** | "Impact you can see. Feasibility you can run. Craft you can measure. That's Sahayta." |

**Variant B runtime check:** 40+35+35+30+10 = **150 s = 2:30** ✓

---

# VARIANT C — "Ninety Seconds" (cutdown) · ~1:30

*Angle:* the same story at 1.7× density for judges skimming submissions, or as
a teaser cut. Every beat survives; only the lingering dies. Uses `[PLAY]`
(auto-choreography) for the middle section to compress wall-clock time.

## C1 — Hook (0:00–0:08) · [I]

| | |
|---|---|
| **On screen** | Flood fixture + title card (as A1, no slow zoom — straight cut). |
| **Voiceover** | "Every monsoon, floods hit India. Help can't find the people who need it. This is Sahayta." |

## C2 — Report + AI severity (0:08–0:23) · [UX] [T]

| | |
|---|---|
| **On screen** | `[UI]` `/report?demo=1` Hindi wizard at 1.5× speed → SEND → **◆ 4 · SEVERE** badge + Hindi rationale + `model: rule-fallback-v1` flash. |
| **Voiceover** | "A citizen in Patna reports in Hindi — photo, words, a pin. Sahayta's AI: severity 4 of 5, rescue, critical. In seconds, with zero API keys." |

## C3 — Match + dispatch (0:23–0:38) · [F]

| | |
|---|---|
| **On screen** | `[PLAY]` auto-choreography: match panel (Ravi Kumar, 92.5) → Accept → En route → board flips amber. |
| **Voiceover** | "Skills times distance times availability: Ravi Kumar, 2.1 kilometers away, accepts — and the whole district watches it happen live." |

## C4 — Broadcast (0:38–0:50) · [I]

| | |
|---|---|
| **On screen** | `[UI]` composer → Hindi → Hinglish preview → SEND → 10-language sheet scroll (fast). |
| **Voiceover** | "One message, ten languages, each short enough for SMS — because SMS reaches people when data doesn't." |

## C5 — Dashboard (0:50–1:05) · [F] [T]

| | |
|---|---|
| **On screen** | `[UI]` `/admin?demo=1` pan: KPIs, heatmap, **risk 82 HIGH** + factors + SIMULATED FEED chip, timeline. |
| **Voiceover** | "One screen for the district official: live map, risk 82 with reasons, who's on task — even the simulated feed labeled, because trust is the feature." |

## C6 — Offline + close (1:05–1:17) · [T] [I]

| | |
|---|---|
| **On screen** | `[UI]` airplane-mode queue → sent, no duplicates (4 s). Cut to resolved card + title (8 s). End card. |
| **Voiceover** | "Offline-first, so reports survive dead networks. One photo, one volunteer, one district that knew. That's Sahayta." |

**Variant C runtime check:** 8+15+15+12+15+12 = **~77–90 s** ✓ (safe under 2:00;
eligible range is 2–3 min, so ship A or B as the official entry and C as the teaser.)

---

## Production notes (all variants)

1. **Determinism first.** Run `[DIR]` before every recording session. The
   director boots its own backend on port 8003 with a fresh seed — it never
   touches your dev server on 8000.
2. **Clean takes.** Fresh incognito window per take; `?demo=1` forces demo mode
   (safe default when no API URL is set). `playPatnaDemo()` replays create a
   fresh SOS each run — no cleanup needed between `[PLAY]` takes.
3. **Language discipline.** Citizen flow in Hindi (shows i18n); admin flow may
   stay in English. Burned-in English captions for every Hindi UI moment.
4. **Mandatory honesty shots.** `model: rule-fallback-v1` hover (A3/B4),
   DEMO DATA chips, SIMULATED FEED chip hover (A6/B4/C5). Never crop these out.
5. **Numbers on camera** (only the measured ones): 275 requests / 0 errors /
   p95 107 ms (load, localhost VM); 0.602 exact / 1.000 within-one on 5,000
   labeled fixtures (estimator); 92.5 match score, 2.09 km; risk 82/HIGH;
   10 languages × 311 keys; 2,000 scenarios. Never claim early-warning
   precision — the backtest is a documented 0.0/0.0 limitation.
6. **No fake interactions.** The PDF export is real (both server and demo
   paths). The mic button is shown, never faked into a transcription. Voice
   input is progressive enhancement — say so if asked, not on camera.
7. **Pacing.** 2:30 with 30 s of slack inside the 2–3 min window. If a take
   runs long, trim B-roll first, never the honesty shots.
