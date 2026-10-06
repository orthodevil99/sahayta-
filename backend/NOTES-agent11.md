# NOTES — Agent 11 (Admin Command Dashboard, Wave 4)

## What was built

The district-official view is now complete — `frontend/app/admin/page.tsx`
rewritten from Agent 4's shell, plus a real server-side PDF export.

### Frontend (`frontend/`)
- **`app/admin/page.tsx`** (rewritten): KPI row, tabbed map/verify/flags views,
  live SOS map + heatmap (reused `SosMap`) with text-list mirror, risk panel
  (`RiskGauge` + factor bars + `SimulatedFeedChip`), volunteer board with
  **on-task mapping** (from `listTasks`), skill chips, reputation stars,
  `BroadcastComposer` (unchanged — already complete), verify queue with
  **machine-readable reason + reporter trust tier** (Agent 10) and
  **duplicate-of input** for merge, safety-flag **resolve UI** (resolution
  select: confirmed / confirmed_duplicate / false_alarm + note), incident
  timeline from the audit log, JSON export, and a **working PDF export
  button** (was disabled with "ships in Wave 4" tooltip).
- **`lib/pdf.ts`** (new): client-side incident-report PDF via pdf-lib —
  the demo-mode path (static export, no backend) for the video. Same
  sections as the server report: banner, title, risk snapshot, SOS list
  (top 50), tasks, broadcasts (hi+hing first), timeline, footer.
- **`lib/api.tsx`**: `SahaytaApi.exportIncidentPdf(district)` added;
  `RestApiClient` downloads the server-rendered PDF (admin key);
  `DemoApiClient` builds the bundle from seed data + localStorage and
  renders client-side. pdf-lib is lazy-loaded (`await import("./pdf")`)
  so the main bundle never pays for it.
- **`lib/types.ts`**: `SOSReport` gained optional `reason` and
  `reporter_trust_tier` (verify-queue extras, additive).
- **i18n**: new `admin.*` keys (`pdf_done`, `flag_resolution`,
  `flag_note_ph`, `dup_of_ph`, `trust_tier`, `resolve_done`) in
  hi.json + hing.json; other languages fall back to Hindi per the
  established chain. The stale `admin.pdf_tooltip`
  ("PDF Wave 4 में आएगा") is no longer referenced by any component.

### Backend (`backend/`)
- **`app/services/pdf_report.py`** (new): `build_incident_pdf(bundle)` —
  reportlab Platypus report: DEMO DATA banner, title/meta, risk snapshot
  with factor table, SOS table (top 50, severity-colored), task table,
  broadcasts (hi+hing first, then rest), audit timeline, footer with page
  numbers. Honest labeling on every page.
- **`app/routers/admin.py`**: `GET /api/admin/incidents/{id}/export?format=pdf`
  now returns a **real PDF** (was 501). Builds a richer bundle than the
  frozen JSON shape (adds audit timeline + rendered broadcast messages;
  JSON shape untouched). `selectinload(Task.volunteer)` added to avoid an
  async lazy-load. Export audit-logged with byte count.
- **`requirements.txt`**: `reportlab==5.0.1` pinned (installed in `.venv`).
- **`app/assets/fonts/`**: bundled subsets — Noto Sans Devanagari
  (deva-*.ttf, SIL OFL) + DejaVu Sans (sans-*.ttf, Bitstream Vera).
  The upstream Devanagari font ships **no Latin letters**, hence the pair.
  GSUB/GPOS deliberately dropped (keeps ToUnicode 1:1; avoids ligature
  artifacts). See `assets/fonts/README.md`.
- **`frontend/public/fonts/`**: same four subsets for the client-side path.

### Font/shaping notes (for Agent 12+)
Text is segmented by script at render time: Devanagari runs → Deva font,
everything else → Sans, in both renderers. Neither reportlab nor the
client path does Indic complex-text shaping — conjuncts render as
constituent codepoints (readable, not perfect). Verified by extracting
text from both PDFs with pypdf: Latin + Devanagari all selectable.

## Tests
- Backend: **79/79 green** (was 78; +1 new `test_incident_export_pdf_guards`,
  rewrote the old `..._pdf_501` test to assert a real PDF: 200,
  `application/pdf`, `%PDF` header, content-disposition filename,
  >5 KB body; plus 404/403 guards).
- Frontend: `tsc` clean, 5/5 test files pass, `next build` clean (9 routes).
- Smoke-verified both PDFs end-to-end (reportlab + pdf-lib) with pypdf
  text extraction: banner, Hindi copy, risk 82, Ravi Kumar, timeline —
  all present and selectable.

## Demo-scenario Act 5 coverage
| Panel | Source | Status |
|---|---|---|
| SOS map ≥1 Kankarbagh pin, red sev-4 badge | `listSOS` + `SosMap` | ✅ (shell, kept) |
| Severity heatmap hot zone | `showHeatmap` | ✅ (shell, kept) |
| SOS counts | `adminOverview` | ✅ (shell, kept) |
| District risk ≥70 + factors incl. rainfall_24h_mm | `getDistrictRisk` | ✅ (shell, kept) |
| Volunteer board with Ravi | `listVolunteers` + on-task tasks | ✅ enhanced |
| Incident timeline in order | `adminAudit` | ✅ (shell, kept) |
| PDF export | new | ✅ shipped (both modes) |

## Known limitations
- Admin page is online-only by design (wireframe: full-screen
  "needs connection" offline) — the client-side PDF fetches fonts from
  `/fonts/`, so it needs connectivity too. Acceptable per spec.
- `?demo=0` + REST PDF path is code-complete; exercised via pytest
  (ASGI), not against a separately deployed backend.
- The demo-mode verify queue shows seeded reports; `playPatnaDemo`
  (Agent 9's director) is the deterministic video path.
