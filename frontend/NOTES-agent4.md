# NOTES — Agent 4 (Frontend PWA, Wave 2)

## What was built

Next.js 14 static-export PWA (`frontend/`): 6 routes (`/`, `/report`, `/board`,
`/volunteer`, `/alerts`, `/admin`), 16 design-system components with the exact
frozen names, typed `SahaytaApi` client (`lib/api.tsx`) + `RestApiClient`
implementing `docs/api-contracts.md` verbatim, and a seeded `DemoApiClient`
(`lib/demo.ts`) so the demo video records with **no backend**. Service worker,
10-language dictionaries (hi/hing complete; 8 languages core coverage, hi
fallback), Leaflet map + severity heat layer + shelter markers, offline outbox
with `client_report_id` idempotency, low-bandwidth + high-contrast + font-size
+ dark-mode controls.

Verification: `npx tsc --noEmit` clean, `npm test` 4/4 files pass (geo,
severity-rule tuning incl. the exact demo fixture → severity 4, format,
data-contract guard over `data/*.json`), `next build` clean (6 static routes),
smoke-tested the `out/` export over HTTP (all routes + demo-data + sw.js 200).

## How demo mode works

- Mode resolution (`lib/api.tsx`): `?demo=1` or `localStorage sahayta.demo=1`
  forces demo; else `NEXT_PUBLIC_API_URL` set → REST; unset → demo (safe default).
- `DemoApiClient` lazy-loads (`import("./demo")`) so REST bundles never ship the
  3.2 MB dataset. Reads `public/demo-data/*.json` (copied by
  `scripts/prepare-demo-data.mjs`, **committed**), persists mutations as
  localStorage deltas, emits WS-shaped events on a local emitter.
- `playPatnaDemo()` (demo-director lite): creates the fixture SOS (exact Hindi
  text from `docs/demo-scenario.md`) → `assessSeverity` → severity 4 →
  matches Ravi Kumar (`vol-ravi-kumar-patna`, score ≥ 80 by the frozen formula) →
  verify → accept → en-route (SOS → `help_on_way`) → complete (SOS →
  `resolved`, Ravi +2 rep) → Hindi+Hinglish broadcast. ~35 s, step callbacks for
  the progress sheet.
- The client-side severity scorer (`lib/demo-assess.ts`) is tuned so the fixture
  scores exactly 4: strongest-depth-wins + one people-at-risk bucket + urgency
  (1+1+1+1). "बुजुर्ग" was deliberately removed from the *medical* keyword list —
  elderly on a rooftop is a rescue signal, and the fixture must categorize
  `rescue` per the acceptance test.

## Contract issues for Agent 5 (DRAFT → freeze at end of Wave 2)

1. **`GET /api/alerts` omits the full `messages` map** (only on `GET /api/alerts/{id}`).
   The per-alert 10-language switcher currently needs N+1 detail fetches.
   PROPOSAL (additive): `GET /api/alerts?lang=all` includes the full map in list items.
2. **No media upload endpoint.** `POST /api/tasks/{id}/complete` takes
   `proof_photo_id` and `POST /api/assess` takes `photo_id`, but nothing mints a
   `photo_id`. PROPOSAL: `POST /api/media` (multipart) → `{photo_id, url, photo_hash}`.
   Frontend currently sends `photo_description` in text mode; photo bytes need this.
3. **`PATCH /api/volunteers/{id}` request shape unspecified.** Frontend sends a
   partial volunteer object; please document the accepted patch fields.
4. **i18n plan references `PATCH /users/me {preferred_lang}`** but contracts have
   no users endpoint. Frontend stores language in `localStorage` only. PROPOSAL:
   add `PATCH /api/users/me` or drop the reference.
5. **`GET /api/sos?sort=severity` direction unspecified** — frontend assumes
   descending (most severe first). Please document.
6. **`GET /api/admin/overview` `sos_by_severity` uses string keys `"1"`–`"5"`** —
   frontend handles string keys; keep them frozen as strings.
7. **WS `admin_key` query param** is demo-only per the doc — fine for v1, but a
   real deployment should use a proper auth ticket (noted, not blocking).
8. **`POST /api/sos` JSON variant** — frontend relies on `photo_description`
   for text/demo mode; confirmed workable.
9. **`GET /api/admin/verify-queue`** returns plain SOS list (not wrapped with
   `needs_review` reason) — frontend filters client-side; fine, but a `reason`
   field would help the UI.

## Deliberate decisions / deviations

- **Static export** (`output: "export"`): the PWA deploys anywhere (Vercel,
  GitHub Pages, plain CDN) and the Devpost demo link works with zero server.
  `useSearchParams` pages are Suspense-wrapped (static-export requirement).
- **SW does not replay POSTs.** Outbox replay is app-level (`lib/sync.ts`, on
  boot + `online`), which works identically for demo and REST. The SW handles
  app-shell precache + runtime caching + `/offline.html` fallback only — this
  avoids double-submit races; idempotency rests on `client_report_id` regardless.
- **Heat layer** is stacked severity-weighted `L.circle`s (no leaflet.heat
  dependency); gradient fixed `#22C55E→#EAB308→#F97316→#DC2626` at 0.22 opacity
  per the design system. Dark mode swaps to CartoDB `dark_matter`.
- **Shelter pins** use a ⛺ divIcon (Lucide has no map-marker tent suitable for
  divIcon HTML; the icon font is decorative — the adjacent list is the a11y
  source of truth per the design system).
- **District names in alerts** render in Hindi for hi/mr and English otherwise
  in demo mode (full 10-script transliteration map deferred — documented in
  `demo.ts`).
- **Broadcast composer preview** is client-side template mirroring; the final
  render belongs to the backend (`ai-engine/alerts.py`). Char counter enforces
  ≤ 480.
- **PDF export button** is disabled with the "ships in Wave 4" tooltip —
  never a fake download (contracts §7).

## i18n coverage (honest)

- `hi`: 100% (default + fallback). `hing`: 100%.
- `bn/ta/te/mr/gu/kn/ml/pa`: core UI strings (~150 keys: nav, common, landing,
  report, board, volunteer, alerts, admin essentials, severity/status/category/
  priority/type/risk names, toasts). Extended admin/alert-composer/a11y strings
  fall back to Hindi — never English. Each file's `_meta.coverage` says so.
- **Agent 12** owns completing these + `docs/i18n-coverage.md` percentages.

## Known gaps (later waves own these)

- Admin dashboard is the **shell** per my brief — Agent 11 (Wave 4) fleshes out
  panels, PDF export, and the safety-flag policy.
- Voice input (Web Speech API) is progressive enhancement with an honest
  fallback toast; not tested against real speech here.
- `?demo=0` + `NEXT_PUBLIC_API_URL` REST path is code-complete but
  **untested against a live backend** (Agent 5 doesn't exist yet).
- Map tile offline caching is nice-to-have (NOTES-agent3) — not implemented;
  low-bandwidth mode covers the offline-map story via the text list.
