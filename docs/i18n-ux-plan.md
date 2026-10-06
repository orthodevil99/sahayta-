# Sahayta — Multilingual UX Plan (10 languages)

**Owner:** Agent 3 (UX/Design) · **Implementer:** Wave 4 Agent 12 (full dictionaries)
**Source of truth for alert copy:** `data/alert-templates/*.json` (hand-written, verified ≤160 chars)
**Language codes (frozen, from `api-contracts.md` §0.1):**

| Code | Language | Native name | Script |
|------|----------|-------------|--------|
| `hi` | Hindi | हिन्दी | Devanagari |
| `hing` | Hinglish | Hinglish | Latin |
| `bn` | Bengali | বাংলা | Bengali |
| `ta` | Tamil | தமிழ் | Tamil |
| `te` | Telugu | తెలుగు | Telugu |
| `mr` | Marathi | मराठी | Devanagari |
| `gu` | Gujarati | ગુજરાતી | Gujarati |
| `kn` | Kannada | ಕನ್ನಡ | Kannada |
| `ml` | Malayalam | മലയാളം | Malayalam |
| `pa` | Punjabi | ਪੰਜਾਬੀ | Gurmukhi |

`en` is an accepted input/fallback language only — NOT a shipped UI locale.
Default UI language: `hi`. Default alert language: `hi`.

---

## 1. Language switcher behavior

- **Placement:** header on every screen — `🌐` globe icon + current language's native
  name (e.g. `🌐 हिन्दी`). 48px touch target.
- **Interaction:** opens a BottomSheet listing all 10 languages with native names;
  active language gets a ✓. Selecting applies **instantly, no reload** (next-intl
  locale swap + re-render); persists to `localStorage:sahayta.lang` AND
  `PATCH /users/me {preferred_lang}` when a device id exists (server default for
  future visits).
- **First run:** if `navigator.language` maps to one of the 10, offer it once via
  toast: `"Switch to বাংলা? [Yes] [Keep हिन्दी]"`. Never auto-switch without asking.
- **SOS form:** the description field accepts ANY language regardless of UI locale;
  the mic 🎤 button uses the current UI locale as the SpeechRecognition `lang`.
  The report's `language` is detected server-side; the severity rationale returns
  in the reporter's language.
- **Alerts feed:** global `?lang=` switcher + **per-alert** "View in: [language ▾]"
  (the 10-language proof moment for judges — see wireframe `alerts-feed.md`).
- **Admin broadcast composer:** 10 checkboxes (default: all checked); preview tabs
  render each selected language from `Alert.messages`.

## 2. String externalization rules (for Agent 12)

- **Zero hardcoded UI strings** outside the default-locale dictionary. Every literal
  goes through `t('key')`. Agent 12's `docs/i18n-coverage.md` must report
  per-language completion %; anything < 100% falls back to Hindi (NOT English),
  and the fallback is marked in the coverage doc.
- Dictionary structure (next-intl): `frontend/lib/i18n/{code}.json` with namespaced
  keys: `nav.*`, `landing.*`, `report.*`, `board.*`, `volunteer.*`, `alerts.*`,
  `admin.*`, `common.*` (buttons, states), `a11y.*` (aria labels), `sms.*` (fallback).
- **ICU MessageFormat** for plurals/selects: `{count, plural, one {# report} other {# reports}}`
  — each language file owns its own plural rules (Hindi/Bengali differ from English).
- Dynamic values (district names, helpline numbers) are **interpolated, never
  concatenated**: `"बाढ़ चेतावनी: {district} के…"` — word order differs per language.
- Severity/status names are proper nouns of the design system: each locale defines
  `severity.4.name` ("SEVERE" → "गंभीर") but the **number is always shown**
  (numbers cross literacy barriers).

## 3. SMS-fallback copy strategy

- Every broadcast message is **≤ 480 chars** (3 SMS segments); template ground truth
  is **≤ 160 chars** (1 segment) — see `data/alert-templates/flood.json`.
- Anatomy of every alert (all languages): `[TYPE] + [PLACE] + [WHAT'S HAPPENING] +
  [ACTION] + [HELPLINE]`. Example (Hindi, 1 segment):
  `बाढ़ चेतावनी: पटना के निचले इलाकों में पानी बढ़ रहा है। तुरंत ऊँची जगह जाएँ। राहत शिविर खुले हैं। हेल्पलाइन: 1078`
  Hinglish twin (Latin script — the one judges can read):
  `Flood warning: Patna ke neeche ilakon me paani badh raha hai. Turant unchi jagah jayein. Rahat shivir khule hain. Helpline: 1078`
- **Placeholders** (`{district}`, `{helpline}`, `{temp}`, `{wind}`) are substituted
  post-translation; district names render in the target script (पटना, not Patna,
  in Hindi — transliteration map lives in the locale files).
- LLM-rendered novel alerts are **length-checked server-side**: if > 480 chars,
  the renderer truncates at a sentence boundary and appends the helpline
  (never cut mid-word, never drop the helpline).
- The UI shows a live `n / 480` counter in the broadcast composer (design-system §5.14).

## 4. RTL-safe layout notes

- **None of the 10 v1 languages are RTL** — but the layout must not assume LTR:
  use CSS logical properties everywhere (`margin-inline-start`, `inset-inline`,
  `text-align: start`). This is a one-line-per-component discipline now that
  prevents a rewrite if Urdu/Arabic lands in v2.
- Icons that imply direction (back arrows ←, progress →) flip via
  `[dir="rtl"]` transform — implement the hook now, even with no RTL locale shipped.
- Numbers, phone numbers, and `client_report_id`s always render LTR
  (`unicode-bidi: isolate`) inside RTL contexts.

## 5. Voice input on the SOS form

- Mic button beside the description textarea (48px). Uses Web Speech API
  (`webkitSpeechRecognition` fallback) with `recognition.lang` = current UI locale
  code mapped to BCP-47 (`hi`→`hi-IN`, `bn`→`bn-IN`, `hing`→`hi-IN`, etc.).
- Interim results stream into the textarea (user can edit after); on `onerror`,
  toast the honest message: `"Voice input isn't available — please type."`
- Offline: Chrome/Android on-device recognition may work; if not, the same toast.
  Voice is progressive enhancement — the form never requires it.

## 6. Font-size controls & high-contrast mode

- **Font size:** header `A- A+` control cycling S (100%) / M (112.5%) / L (125%)
  root font-size; persists in localStorage. Layout must not break at 125%
  (wireframes tested mentally at L — Agent 4 to verify).
- **High-contrast mode:** header toggle `◐`; adds `body.high-contrast`:
  text → pure `#000`/`#FFF`, UI chrome borders → 2px solid currentColor,
  severity badges keep bg color but gain 2px solid border + bold label,
  map switches to high-contrast tiles, heatmap opacity → 0.85.
  Independent of dark mode (4 combos must all pass 4.5:1 — Agent 12 verifies).
- Both controls sit in the header next to the language switcher: the
  accessibility cluster is `🌐 | A± | ◐ | 📶`.

## 7. Low-literacy specifics

- Primary CTAs are icon + ≤ 6 words in EVERY language (translators must keep the
  6-word cap — noted in the translator brief Agent 12 writes).
- The SOS wizard's 4 steps are numbered dots + icons, not words.
- Severity is always number + name + icon (never name alone).
- Demo-data and simulated-feed badges get translated strings too
  (`demo_badge`, `simulated_feed`) — honesty must not be English-only.
