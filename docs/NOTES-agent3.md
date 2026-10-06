# NOTES — Agent 3 (UX/Design)

Decisions later waves should know. Read before building screens.

## For Agent 4 (Frontend PWA)
1. **Route ↔ wireframe map:** `/` → `wireframes/landing.md`, `/report` →
   `report-sos.md`, `/board` → `sos-board.md` (TWO variants: map-first ≥1024px,
   list-first below + forced in low-bandwidth), `/volunteer` → `volunteer-tasks.md`,
   `/alerts` → `alerts-feed.md`, `/admin` → `admin-dashboard.md` (Agent 11 owns
   this route's build, but the wireframe is the spec — don't redesign it).
2. **Component names are the contract:** implement `SeverityBadge`, `CategoryChip`,
   `StatusPill`, `SOSCard`, `TaskCard`, `BottomSheet`, `Toast`, `OfflineBanner`,
   `QueueBadge`, `StatTile`, `RiskGauge`, `HeatmapLegend`, `BroadcastComposer`,
   `LanguageSwitcher`, `DemoModeBanner` with the exact props implied by the
   design system. If a prop is missing, add it — don't rename the component.
3. **Severity scale is frozen** (design-system §1.1): sev-5 keeps its striped
   edge; badge colors identical in dark mode. Never invent a 6th level.
4. **`btn-sos` style is reserved** for filing an SOS only (report wizard step 4).
   Nothing else may use alert-600 + 64px. This is a safety affordance, not branding.
5. **Low-bandwidth = `body.low-bandwidth`:** hide map tiles + photos, force the
   list variant, system fonts, no animation. Every map pin MUST have a text-list
   mirror (a11y + low-bandwidth requirement — demo-scenario Act 6 checks this).
6. **Demo mode:** `?demo=1` or `X-Admin-Key: demo-admin-key` → `DemoModeBanner` +
   `▶ Play Patna flood demo` button on landing. This button is the video's entry
   point — make it impossible to miss.
7. **Offline queue UX:** `client_report_id` minted when the report wizard OPENS
   (not on submit). Outbox count → `QueueBadge` on nav. Queued cards render
   `⏳ Queued` and flip to live cards on sync — no duplicates, ever (arch §1.5).

## For Agent 11 (Admin Dashboard)
8. The admin wireframe is deliberately dense — that's the Feasibility pitch
   ("a real district office could use this"). Panels fail independently
   (per-panel `⚠ Retry`, never a blank dashboard).
9. **Broadcast composer confirm modal is mandatory** — mis-tap on a 12,400-person
   alert is the nightmare scenario. Show rendered Hindi + recipient estimate.
10. PDF export button stays **disabled with tooltip** until your backend lands it
    (contracts §7: 501 before Wave 4 — never ship a fake PDF).
11. Always render the `SIMULATED FEED` chip when `weather_source == "simulated"`
    and the `DEMO DATA` badge when `is_demo_data`. The storyboard calls these out
    on camera — honesty is graded.

## For Agent 12 (i18n & Accessibility)
12. `docs/i18n-ux-plan.md` is your spec: switcher behavior, zero-hardcoded-strings
    rule, ICU plurals, SMS anatomy, voice input, font-size + high-contrast.
    Translator brief must enforce the **6-word CTA cap** per language.
13. Fallback language is **Hindi, not English**. `hing` uses `hi-IN` for speech.
14. The 4 theme combos (light/dark × normal/high-contrast) must all pass 4.5:1 —
    severity badge bg colors are FIXED across themes (§1.1), tints adapt.
15. Screen-reader source of truth for the map is the adjacent list, not the pins.

## Deliberate cuts / open questions
- **No native apps** (PWA only) — install prompt via `beforeinstallprompt`, nothing more.
- **No RTL locale in v1**, but logical CSS properties are required now (cheap insurance).
- **Map tile provider** not pinned: Leaflet + OSM default, CartoDB dark_matter for
  dark mode. Agent 4 picks; offline tile caching is nice-to-have, not required.
- **Notification channel** is in-app + WS only in v1 (no FCM/SMS gateway) — the
  "via SMS ✓" line on alert cards refers to the SMS-*length* format, and the UI
  copy must not imply real SMS delivery. Agent 12: keep this wording honest in
  all 10 languages.
- Open for Wave 2: exact empty-state illustration style (line icons specced;
  Agent 4 may use a consistent open-source set, e.g. Lucide, instead of emoji —
  emoji in wireframes are placeholders for icon meaning, not the final asset).
