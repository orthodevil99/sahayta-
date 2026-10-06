# Sahayta — i18n Coverage Report (Agent 12, Wave 4)

**Method:** `node scripts/i18n-coverage.mjs` (committed) counts, per locale vs
`hi.json` (the default locale): keys present, non-empty values, and
`{placeholder}` parity. Raw output: `scripts/i18n-coverage.json`.
Fallback chain (tested in `frontend/lib/__tests__/i18n.test.ts`):
**requested → Hindi → key name**. Never English, never blank.

## Per-language completion

| Language | Native | Keys | Non-empty | Placeholder parity | Coverage |
|----------|--------|------|-----------|--------------------|----------|
| Hindi (hi) — default | हिन्दी | 311/311 | 311 | 311 | 100% |
| Hinglish (hing) | Hinglish | 311/311 | 311 | 311 | 100% |
| Bengali (bn) | বাংলা | 311/311 | 311 | 311 | 100% |
| Tamil (ta) | தமிழ் | 311/311 | 311 | 311 | 100% |
| Telugu (te) | తెలుగు | 311/311 | 311 | 311 | 100% |
| Marathi (mr) | मराठी | 311/311 | 311 | 311 | 100% |
| Gujarati (gu) | ગુજરાતી | 311/311 | 311 | 311 | 100% |
| Kannada (kn) | ಕನ್ನಡ | 311/311 | 311 | 311 | 100% |
| Malayalam (ml) | മലയാളം | 311/311 | 311 | 311 | 100% |
| Punjabi (pa) | ਪੰਜਾਬੀ | 311/311 | 311 | 311 | 100% |

**What was completed this wave:** the 8 non-Hindi/Hinglish locales went from 192
(core UI) to 311 keys — full parity, including the new `demo.*` namespace (12
keys), `a11y.toggle_view`, `admin.panel_kpis`, and `common.outbox_n`, plus all
admin-verify-queue, reputation-tier, and availability-window keys added by
Agents 8/11. Translations are hand-written in native scripts (not MT output);
CTA strings kept ≤ 6 words per the UX plan.

**Honest caveats:**
- Translation *quality* (naturalness, dialect) was not reviewed by native
  speakers — flagged for the user as pre-submission polish if a speaker is
  available. Nothing is machine-translation word salad by construction, but a
  native pass would still help.
- `hing` (Hinglish) intentionally mirrors English-heavy Latin-script phrasing —
  that is the lect's nature, not a fallback leak.
- District names in alerts render in Hindi for hi/mr and English otherwise in
  demo mode (full 10-script transliteration map deferred — noted in
  `frontend/lib/demo.ts`).

## Hardcoded-string audit (this wave)

Swept `app/` + `components/` for JSX text nodes and `title=`/`aria-label=`/
`placeholder=`/`confirm()` literals. **Found and fixed 7:**
- `DemoModeBanner.tsx`: "Go live", `confirm("Reset demo data?")`,
  `title`/`aria-label` "Reset demo", 8 demo step labels, the "Demo complete — …"
  paragraph → all keyed under new `demo.*` namespace (all 10 locales).
- `app/board/page.tsx`: `aria-label="toggle view"` → `a11y.toggle_view`.
- `components/Header.tsx`: `title="queued"` → `common.outbox_n` (with count).
- `app/admin/page.tsx`: `title="KPIs"` → `admin.panel_kpis`.

**Remaining hardcoded English outside dictionaries: none.** (`t("error", …)` /
`t("success", …)` call sites are toast *variant* names, not translation keys.)

## SMS-fallback templates

`data/alert-templates/{flood,heatwave,cyclone}.json` — all 30 templates verified
≤ 160 chars (one was 171: Malayalam flood — shortened to 145, kept ZWNJ
orthography). Anatomy per the UX plan: `[TYPE] + [PLACE] + [WHAT] + [ACTION] +
[HELPLINE]`, placeholders substituted post-translation. The alerts feed renders
per-language `messages` with the per-alert language switcher (the judges'
10-language proof moment).

## Voice input (SOS form) — honest status

Implemented by Agent 4, verified by Agent 12: 48px mic button beside the
description textarea, `aria-label` + `aria-pressed`, `recognition.lang` mapped
from the UI locale (`hi→hi-IN`, `bn→bn-IN`, …, `hing→hi-IN`), interim results
streamed into the textarea (editable after), and the honest fallback toast
(`toast.voice_unavailable`) when the API is absent, errors, or throws.
**Not verified against live speech** — no microphone or speech engine exists in
this build sandbox. It is progressive enhancement: the form never requires it,
and the fallback path is the tested one.

## Accessibility pass (this wave)

- **Map text mirror:** verified — `SosMap` is `aria-hidden`; every pin renders
  as an `SOSCard` in the adjacent list (`aria-label=a11y.map_list`) on all
  routes that use the map (board, report location step, admin).
- **Live updates:** board's "● Live · N reports" header is now
  `role="status"` + `aria-live="polite"`; toasts were already `aria-live`.
- **Keyboard:** global `:focus-visible` 3px outline exists; all interactive
  elements are native buttons/links; tab order follows DOM order on all 6
  routes (verified by reading each page — no positive tabindex anywhere).
- **High-contrast + font-size:** both real (CSS rules, not decorative) —
  `body.high-contrast` redefines the palette incl. dark-mode combo;
  font-size cycles 100/112.5/125% on the root. Layout spot-checked at 125% in
  the static export (no overflow on header/nav).
- **RTL readiness:** the only 3 physical-direction utilities in the codebase
  (`left-3`, `mr-1`, `right-1`) were converted to logical (`start-3`, `me-1`,
  `end-1`); `[dir="rtl"] .flip-rtl` icon flipping and `.num-ltr` isolation were
  already in place. None of the 10 v1 locales are RTL.
- **Severity:** always number + name + icon, never color alone (design-system
  rule, verified in `SeverityBadge`).

## Test results

`frontend/lib/__tests__/i18n.test.ts` (new): key parity × 10 locales, no empty
strings, placeholder parity, fallback-chain (requested → Hindi → key name),
interpolation, SMS ≤ 160 + flood placeholder presence — **PASS**.
Full frontend suite: **6/6 files PASS** (`npm test`), `tsc --noEmit` clean.
