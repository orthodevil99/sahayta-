# Sahayta — Demo Video Storyboard (2:30)

**Owner:** Agent 3 (UX/Design) · **Consumer:** Wave 5 Agent 13 (writes the shootable script)
**Format:** 2–3 min screen recording + voiceover. **Deterministic:** every take runs the
demo-director (`packages/simulation/demo_director.py --scenario patna-flood`), so the
severity is always 4, the volunteer is always Ravi Kumar, the alert copy is fixed.
Record at 1080p, UI language = Hindi for the citizen flow (shows i18n), captions on.

Judging criteria key: **[I]** Impact · **[F]** Feasibility · **[UX]** User Experience ·
**[T]** Technical Craft. Every beat below names the criterion it serves.

---

## Beat 0 — Hook (0:00–0:15) · [I]

| | |
|---|---|
| **On screen** | Full-bleed flood photo (demo fixture). Title card: "When disaster strikes, help finds you." Subtitle: "Sahayta — a disaster-response OS for India." |
| **Action** | Slow zoom on photo. Cut to landing page, `▶ Play Patna flood demo` highlighted. |
| **Voiceover** | "Every monsoon, floods hit India. Phones work, networks don't, and help can't find the people who need it. This is Sahayta." |
| **Why it scores** | [I] Opens on the human problem, not the tech. Names the nation-level issue from the theme. |

## Beat 1 — Citizen reports SOS (0:15–0:45) · [UX] [I]

| | |
|---|---|
| **On screen** | `/report` in Hindi. Photo upload → Hindi description pasted → map pin dropped at Kankarbagh → big red `🚨 भेजें · SEND SOS` tapped. |
| **Action** | Real-time wizard: 4 progress dots fill. Show the mic 🎤 button (voice input) briefly. |
| **Voiceover** | "A citizen in Patna photographs rising water. No English needed, no account, no reading a manual — photo, voice, a pin on the map. Sixty seconds, even on a shaky 2G connection." |
| **Why it scores** | [UX] Icon-first, low-literacy, 10-language flow. [I] Built for the actual affected user. |

## Beat 2 — AI severity in seconds (0:45–1:10) · [T] [UX]

| | |
|---|---|
| **On screen** | Success screen: `◆ 4 · SEVERE` badge slams in with rationale in Hindi ("waist-deep water… rooftops"), category `🛟 rescue`, priority `critical`. Cut to `/board?district=patna&severity_min=4`: red pin drops on the heatmap at Kankarbagh, card slides into the list. |
| **Action** | Pause 2 s on the badge. Hover the assessment: show `model: rule-fallback-v1` honestly ("works with zero API keys"). |
| **Voiceover** | "Sahayta's AI reads the photo and the Hindi text: severity 4 out of 5, rescue category, critical priority — in under three seconds. And it works with no API key at all, because in a disaster you can't depend on one." |
| **Why it scores** | [T] Multi-signal AI pipeline (vision + text + triage), honest fallback labeling. [UX] The verdict is instant and legible. |

## Beat 3 — Volunteer matched & dispatched (1:10–1:35) · [F] [UX]

| | |
|---|---|
| **On screen** | Admin clicks `🛟 Assign` → match panel: **Ravi Kumar — score 87.5**, "skill match: rescue · 2.1 km away · available now". Assign → switch to `/volunteer` as Ravi: task card → `✓ Accept` → `🧭 En route`. Back on `/board`: the SOS card pulses to amber `🚑 Help on way`. |
| **Action** | Show the match reasons (transparency). Show the live WS update — no refresh. |
| **Voiceover** | "Matching is skills times distance times availability — the nearest qualified volunteer, Ravi Kumar, 2.1 kilometers away. He accepts, he's en route, and everyone watching the board sees it happen live." |
| **Why it scores** | [F] This is the coordination a district office actually needs; the formula is inspectable. [UX] Live updates, zero refresh. |

## Beat 4 — Hindi alert broadcast (1:35–1:55) · [I] [UX]

| | |
|---|---|
| **On screen** | `/admin` → Broadcast composer: Patna, flood, severity 4, message typed once. Preview tabs flip: **Hindi (Devanagari) → Hinglish (Latin)** — linger on both. `📢 SEND` → confirm modal ("~12,400 people") → sent. Cut to `/alerts`: the alert sits at top in Hindi; tap "View in" → bottom sheet scrolls through all 10 languages. |
| **Action** | Type once, show ten. The Hinglish version must be readable on camera. |
| **Voiceover** | "One message typed once goes out in ten Indian languages — Hindi, Hinglish, Bengali, Tamil, and six more — each short enough for SMS, because that's what reaches people when data doesn't." |
| **Why it scores** | [I] Multilingual reach is the difference between a warning and a rumor. [UX] The 10-language sheet is the visual proof. |

## Beat 5 — Command dashboard (1:55–2:15) · [F] [T]

| | |
|---|---|
| **On screen** | `/admin` full view: KPI row (14 active SOS, 7 sev≥4, 61 volunteers, **risk 82 HIGH**), heatmap glowing over Kankarbagh, risk factor bars (rainfall 187 mm), volunteer board with Ravi "on task", incident timeline in order (reported → assessed → assigned → en-route → broadcast). |
| **Action** | Slow pan across panels. Hover the `SIMULATED FEED` label — call it out, don't hide it. |
| **Voiceover** | "The district official sees everything on one screen: live SOS map, a risk score of 82 with the reasons behind it, who's available, and a minute-by-minute incident timeline. Even the simulated weather feed is labeled — because trust is the feature." |
| **Why it scores** | [F] Looks like software a real district office could adopt. [T] Risk scoring with explainable factors, honest data labeling. |

## Beat 6 — Offline + early warning (2:15–2:25) · [T] [F]

| | |
|---|---|
| **On screen** | Toggle airplane mode → file an SOS → `⏳ Queued` → reconnect → `✓ sent, no duplicates`. Quick cut: 72-hour forecast chart for Patna, risk curve rising before the flood peak. |
| **Action** | Two 5-second demos back to back. Keep them snappy. |
| **Voiceover** | "Networks die in disasters — so reports queue offline and sync without duplicates. And the early-warning engine was already watching: risk climbing 72 hours before the water did." |
| **Why it scores** | [T] Offline-first sync + idempotency + forecasting pipeline. [F] Designed for the real failure mode. |

## Beat 7 — Close (2:25–2:30) · [I]

| | |
|---|---|
| **On screen** | Back to the flood photo, now with the resolved SOS card overlaid: `✓✓ Resolved — Ravi Kumar · +2 ★`. Title: "Sahayta — when disaster strikes, help finds you." |
| **Action** | Hold 4 s. End card: repo URL + "Built for WarriorHacks 2.0". |
| **Voiceover** | "One photo. One volunteer. One district that knew what was coming. That's Sahayta." |
| **Why it scores** | [I] Closes the loop on the human story from Beat 0. |

---

## Production notes (for Agent 13)
- Total runtime target: **2:30** (safe inside the 2–3 min requirement; leaves 30 s of slack).
- Record the citizen flow with UI language = **Hindi**; admin flow may stay in English
  (officials) — the contrast itself demonstrates i18n.
- Every on-screen number must come from the demo-director run (no staged screenshots).
- Burned-in captions in English for all Hindi UI moments.
- The `model: rule-fallback-v1` label MUST be visible in Beat 2 (honesty is graded).
- DEMO MODE banner visible in every admin shot.
