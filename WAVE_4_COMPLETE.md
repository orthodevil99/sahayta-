# WAVE 4 COMPLETE — Trust & Polish (Agents 10–12)

All three Wave 4 agents finished. The system now has real guardrails, a
district-official command dashboard with working PDF export, and 100%
10-language UI coverage with an accessibility pass.

## Agent 10 — Safety & Guardrails (`4187f6b`)
- `backend/app/services/safety.py` (new): `raise_flag` (dedupes identical open
  flags), `check_duplicate_photo` (SHA-256 + 24h window + 5 km geo),
  `check_conflicting_reports` (sev ≥4 vs ≥3 mild within 2 km/6h; sev 3 never
  triggers), `check_spam_burst` (≥5 reports/device/10 min), `reporter_trust`
  (lifetime outcomes → trusted/standard/new/flagged).
- Extended: `routers/sos.py` (spam throttle at intake, dedup/conflict wiring,
  `reason` on create, verify persists `duplicate_of`), `routers/admin.py`
  (real duplicate-merge in `resolve_flag`; removed dead shadowed
  `GET /api/safety/flags` route), `routers/safety.py` (reporter `?mine=true`),
  `routers/uploads.py` + `media.py` (magic-byte sniffing), `schemas.py`,
  `config.py` + `.env.example` (`SAHAYTA_SAFETY_*` tunables),
  `frontend/lib/api.tsx` (canonical flags path).
- **Visibility policy defined:** admin = full flag records; reporter
  (`?mine=true`) = own reports' flags only (no detection internals — don't
  leak the detection surface); guest = anonymized district counts
  (`?district=` required).
- Alembic `c7a10f3e2b91` adds nullable `sos_reports.duplicate_of`.
- Contracts → **v1.3** (`MIGRATION.md`, all additive).
- `docs/safety.md`: honest capability model — what's automated, what needs a
  human, what we deliberately don't do.
- **10/10 new tests pass; full suite 78/78** (incl. demo-scenario failure
  injection #4: duplicate photo → `possible_duplicate`, marked for review,
  never silently dropped). Fixed 2 pre-existing tests + 1 real bug (create
  response omitted `reason`).
- Honest limitations documented (dHash misses heavy crops; in-memory rate
  limits; client-generated device IDs rotatable).

## Agent 11 — Admin Command Dashboard (`cbaeed7`)
- `frontend/app/admin/page.tsx` rewritten: KPI row, tabbed map/verify/flags,
  live SOS map + heatmap with text-list mirror, risk panel (RiskGauge + factor
  bars + SIMULATED FEED chip), volunteer board with on-task mapping + skills +
  reputation, verify queue (machine-readable reason + reporter trust tier +
  duplicate-of input), safety-flag resolve UI, incident timeline from audit log,
  JSON export — and the **PDF button now works**.
- **PDF export is real:** server = `backend/app/services/pdf_report.py`
  (reportlab + embedded Noto Sans Devanagari/DejaVu subsets; DEMO DATA banner;
  risk snapshot, SOS table, tasks, broadcasts, audit timeline; verified via
  pypdf text extraction); demo/static-export = `frontend/lib/pdf.ts`
  (pdf-lib, same subsets). Both verified end-to-end with real content.
- `GET /api/admin/export?format=pdf` returns a real PDF (was 501).
- Act 5 acceptance satisfied: map pins/heatmap, SOS counts, risk ≥70 with
  `rainfall_24h_mm` factor, Ravi on the volunteer board, ordered timeline —
  all live over WS, panels fail independently.
- **79/79 backend tests green**; frontend `tsc` clean, 5/5 test files,
  `next build` clean (9 routes).
- Known limits: admin is online-only by design; no Indic complex shaping
  (readable, not perfect); REST PDF path tested via ASGI pytest only.

## Agent 12 — i18n & Accessibility (`db444be`)
- **All 10 locales at 100%: 311/311 keys**, placeholder-parity enforced
  (computed by committed `scripts/i18n-coverage.mjs`). The 8 partial locales
  went 192 → 311 keys — full parity incl. admin, reputation, availability,
  and new `demo.*` namespace. Hand-written native-script translations; CTAs
  ≤6 words.
- **7 hardcoded-string audit findings fixed** (DemoModeBanner ×5, board
  view-toggle aria-label, header queue badge, admin KPI title). **Zero
  hardcoded UI strings remain** (sweep verified). Fallback chain:
  requested → Hindi → key name (never English, never blank).
- SMS templates: all 30 ≤160 chars (fixed 1 Malayalam violation 171→145).
- Voice input: verified implementation (48px mic, keyed aria-label,
  `recognition.lang` mapped per locale, interim results, honest fallback
  toast) — **not tested against live speech** (no mic in sandbox); documented
  as progressive enhancement.
- a11y: map text-mirror on all routes, `role="status"` + `aria-live="polite"`
  on board header, global `:focus-visible`, no positive tabindex, logical
  properties (RTL-safe), high-contrast + font-size controls verified real.
- **6/6 frontend tests green** (new `i18n.test.ts`: parity ×10, fallback
  chain, SMS length), `tsc` clean, `next build` clean.
- `docs/i18n-coverage.md` with honest percentages + limitations (translations
  not native-speaker reviewed; district transliteration deferred).

## Handoffs to Wave 5 (binding)
- **Agent 13 (Demo Video):** run `packages/simulation/demo_director.py
  --scenario patna-flood` for deterministic takes (14/14 PASS); frontend
  `?demo=1` / `playPatnaDemo()` for UI takes; `docs/demo-storyboard.md` has
  the 8 beats. Deliver 3 script variants + shot list + TTS-ready voiceover.
- **Agent 14 (Devpost & Docs):** everything is real and measured — use the
  numbers in `packages/simulation/load_results.json`,
  `backend/warnings/BACKTEST_REPORT.md`, `docs/i18n-coverage.md`, test counts
  (backend 79, engine 65, frontend 6 files). No invented metrics.
- **Agent 15 (Submission Ops):** re-run the demo-director sign-off checklist
  from `docs/demo-scenario.md` verbatim; verify no API keys in repo; run all
  three test suites; record results.

## Known issues carried forward
1. Early-warning backtest 0.0/0.0 — documented limitation, demo unaffected.
2. Translations not native-speaker reviewed — recommend a pass pre-submission.
3. Voice input untested against live speech — fallback path is the tested one.
