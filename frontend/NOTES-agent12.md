# NOTES — Agent 12 (i18n & Accessibility, Wave 4)

## What was done

- Completed all 10 locale dictionaries to **311-key parity** (bn/ta/te/mr/gu/kn/ml/pa
  went 192 → 311). Merge machinery committed: `scripts/i18n_fill.py` +
  `scripts/i18n_fill/{bn_ta,te_mr,gu_kn,ml_pa}.py` (re-runnable, idempotent).
- New `demo.*` namespace (12 keys) + `a11y.toggle_view`, `admin.panel_kpis`,
  `common.outbox_n` added to hi/hing and all 8 locales.
- Fixed 7 hardcoded English strings (DemoModeBanner ×5, board toggle aria-label,
  header queue-badge title, admin KPIs panel title). Zero remain.
- Fixed 1 SMS template over 160 chars (Malayalam flood 171 → 145).
- a11y: board live header → `role="status"` + `aria-live="polite"`;
  3 physical-direction utilities → logical properties.
- Committed: `scripts/i18n-coverage.mjs` (+ `scripts/i18n-coverage.json`),
  `docs/i18n-coverage.md`, `frontend/lib/__tests__/i18n.test.ts`.

## Decisions / conventions for later waves

- **hi.json is the key authority.** Any new UI string: add the key to hi.json
  first (Hindi), then hing, then run the fill/coverage scripts. The coverage
  script exits 1 if any locale < 100%.
- **Fallback chain is requested → Hindi → key name.** Never add English
  fallbacks; `hing` is a real locale, not a fallback.
- **Placeholders are contractual.** `{n}`, `{t}`, `{district}`, `{helpline}`,
  `{temp}`, `{wind}` must survive translation byte-for-byte; the test enforces it.
- **New keys go in hi.json order.** `ordered_like_hi` in the fill script keeps
  files tidy; do not hand-edit ordering.
- `_meta.complete` is machine-managed by the fill script — don't hand-edit.

## Known limitations (honest)

- Translations are hand-written but **not native-speaker reviewed** — recommend a
  native pass before submission if a speaker is available.
- Voice input **not tested against live speech** (no mic/engine in sandbox);
  the fallback path is the tested one.
- District-name transliteration across all 10 scripts deferred (hi/mr use
  Devanagari, others English in demo mode) — documented in `frontend/lib/demo.ts`.
