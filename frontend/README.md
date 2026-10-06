# Sahayta Frontend (Wave 2 — Agent 4)

Offline-first disaster-response PWA. Next.js 14 (App Router) + Tailwind + Leaflet.
Builds to `docs/api-contracts.md` (typed client in `lib/api.tsx`) and
`docs/design-system.md` (frozen tokens in `tailwind.config.ts` / `app/globals.css`).

## Quickstart

```bash
cd frontend
npm install
npm run dev          # → http://localhost:3000 (demo mode by default)
```

**Demo mode (no backend needed — the video path):** open `http://localhost:3000/?demo=1`
or just leave `NEXT_PUBLIC_API_URL` unset. The app serves the bundled synthetic data
from `public/demo-data/` and runs the full Patna flood scenario in-browser.
Click **▶ Play Patna flood demo** in the striped banner.

**REST mode (real backend, Agent 5):**
```bash
cp .env.example .env.local   # set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```
Add `?demo=0` to force REST when a backend URL is configured.

## Scripts

| Command | What |
|---|---|
| `npm run dev` | dev server |
| `npm run build` | static export → `out/` (deploy anywhere) |
| `npm run typecheck` | `tsc --noEmit` |
| `npm test` | compiles `lib/` + runs 4 node test files (geo, severity rules, format, data-contract guard) |
| `npm run prepare-demo-data` | copies repo `data/*.json` → `public/demo-data/` (committed) |

## Structure

```
app/            / /report /board /volunteer /alerts /admin (+ layout, globals.css)
components/     16 frozen design-system components (SeverityBadge, SOSCard, …)
lib/
  api.tsx       SahaytaApi interface + RestApiClient + ApiProvider/useApi
  demo.ts       DemoApiClient (seeded demo backend) + playPatnaDemo director-lite
  demo-assess.ts  rule-based severity estimator (demo twin of ai-engine rule fallback)
  i18n.tsx / i18n/*.json   10-language dictionaries, hi fallback chain
  outbox.ts     IndexedDB offline queue (client_report_id idempotency)
  sync.ts       outbox replay on boot + 'online'
  geo.ts / format.ts        pure helpers (tested)
  __tests__/    4 test files
public/
  demo-data/    bundled synthetic data (committed — the static export is self-contained)
  sw.js         service worker (app-shell cache + offline fallback)
  manifest.json + icons/    PWA install assets
scripts/        prepare-demo-data.mjs, make-icons.mjs, run-tests.mjs
```

## Key behaviors

- **Zero hardcoded UI strings** outside `hi` — everything via `t('key')`; missing
  keys fall back to Hindi (never English).
- **Offline-first:** SOS reports + volunteer actions queue in IndexedDB and replay
  with the original `client_report_id` (server dedups replays → no duplicates).
- **Honesty chips:** `DEMO DATA` / `SIMULATED FEED` render wherever synthetic data
  appears, in the current language.
- **Low-bandwidth mode** (`📶` in header): hides map tiles/photos, forces the
  list variant; every map pin has a text-list mirror (a11y).
- **Admin** (`/admin`): role-gated shell — KPI row, SOS map + verify queue +
  safety flags, risk gauge, volunteer board, broadcast composer, incident
  timeline, JSON export. PDF export is **disabled with tooltip** until Wave 4
  (contracts: 501 before then — never a fake download).

## Contract notes for Agent 5

See `frontend/NOTES-agent4.md` § "Contract issues (DRAFT → freeze)" — 9 flagged
items, including a proposed `POST /api/media` endpoint and `?lang=all` for alerts.
