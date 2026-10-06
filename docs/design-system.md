# Sahayta — Design System v1.0

**Owner:** Agent 3 (UX/Design, Wave 1) · **Implements:** `docs/architecture.md` §0 constraints
**Consumers:** Wave 2 Agent 4 (frontend), Wave 4 Agents 11 (admin), 12 (i18n/a11y)
**Status:** FROZEN for Wave 2 — visual changes after this need a wave-summary note.

Design principles (in priority order):
1. **Readable in panic.** A wet, shaking hand at 2 AM must file an SOS in < 60 s.
2. **Icon-first, text-second.** Low-literacy friendly: every primary action pairs a
   large icon with ≤ 6 words.
3. **Never color alone.** Every severity/status signal = color + icon + text label
   (colorblind-safe, screen-reader-safe).
4. **Honest data.** Synthetic content always carries a DEMO DATA badge; simulated
   feeds always carry a SIMULATED FEED badge. No exceptions.

---

## 1. Color palette

### 1.1 Severity language (the 1–5 badge scale — frozen)

| Sev | Name | Badge bg | Badge text | Tint (card bg) | Icon | Usage |
|-----|------|----------|------------|----------------|------|-------|
| 1 | Minor | `#16A34A` | `#FFFFFF` | `#DCFCE7` | ● circle | Routine reports |
| 2 | Moderate | `#65A30D` | `#FFFFFF` | `#ECFCCB` | ● circle | Watch |
| 3 | Serious | `#D97706` | `#FFFFFF` | `#FEF3C7` | ▲ triangle | Needs attention |
| 4 | Severe | `#DC2626` | `#FFFFFF` | `#FEE2E2` | ◆ diamond | Urgent (demo: Patna flood) |
| 5 | Catastrophic | `#7F1D1D` | `#FFFFFF` + striped edge | `#FECACA` | ■■ double-bar | Mass-casualty scale |

- Sev-5 badge has a diagonal-stripe border (`repeating-linear-gradient`) so it is
  distinguishable even in grayscale print.
- Text-on-tint (for tinted card labels): sev1 `#14532D`, sev2 `#365314`,
  sev3 `#78350F`, sev4 `#7F1D1D`, sev5 `#450A0A`. All pairs ≥ 4.5:1 contrast.

### 1.2 Status language (SOS / task lifecycle)

| Status | Pill bg | Text | Icon |
|--------|---------|------|------|
| `reported` | `#E2E8F0` | `#334155` | ✉ inbox |
| `verified` | `#DBEAFE` | `#1E40AF` | ✓ check |
| `help_on_way` | `#FEF3C7` | `#92400E` | 🚑 ambulance |
| `resolved` | `#DCFCE7` | `#14532D` | ✓✓ double-check |
| `duplicate` / `rejected` | `#F1F5F9` | `#64748B` | ⦸ crossed |
| Task `assigned` | `#DBEAFE` | `#1E40AF` | 📋 |
| Task `accepted`/`en_route` | `#FEF3C7` | `#92400E` | 🧭 |
| Task `completed` | `#DCFCE7` | `#14532D` | 🏁 |
| Task `declined`/`cancelled` | `#F1F5F9` | `#64748B` | ✕ |

### 1.3 Brand & neutrals (light mode default)

| Token | Hex | Use |
|-------|-----|-----|
| `--brand-600` | `#1D4ED8` | Primary buttons, links, active nav |
| `--brand-700` | `#1E40AF` | Primary hover / pressed |
| `--brand-100` | `#DBEAFE` | Selected tint |
| `--alert-600` | `#DC2626` | SOS send button, destructive actions, critical text |
| `--alert-700` | `#B91C1C` | SOS send hover |
| `--ink` | `#0F172A` | Headings, primary text |
| `--body` | `#334155` | Body text |
| `--muted` | `#64748B` | Secondary text, placeholders |
| `--line` | `#E2E8F0` | Borders, dividers |
| `--bg` | `#F8FAFC` | Page background |
| `--surface` | `#FFFFFF` | Cards, sheets |
| `--success` | `#16A34A` | Positive confirmations |
| `--info` | `#0284C7` | Informational banners |

### 1.4 Dark mode (map-safe)

| Token | Hex |
|-------|-----|
| `--bg` | `#0B1220` |
| `--surface` | `#111C30` |
| `--ink` | `#F1F5F9` |
| `--body` | `#CBD5E1` |
| `--muted` | `#94A3B8` |
| `--line` | `#1E293B` |
| `--brand-600` | `#3B82F6` |

Severity badge bg colors are IDENTICAL in dark mode (recognition > theme purity);
tints darken: sev4 tint `#450A0A` with text `#FECACA`, etc. Map tiles switch to
CartoDB `dark_matter`; the heatmap gradient is fixed in both modes
(`#22C55E → #EAB308 → #F97316 → #DC2626`) with 0.65 opacity so pins stay readable.

---

## 2. Typography

Font stack (broad Indic-script coverage — required for 10 languages):
`"Noto Sans", "Noto Sans Devanagari", "Noto Sans Bengali", "Noto Sans Tamil",
"Noto Sans Telugu", "Noto Sans Kannada", "Noto Sans Malayalam", "Noto Sans Gujarati",
"Noto Sans Gurmukhi", system-ui, sans-serif`.
Headings may use `"Noto Serif"` / `"Noto Serif Devanagari"` for the landing hero only.

| Token | Size / Line | Weight | Use |
|-------|-------------|--------|-----|
| `display` | 32px / 40px | 800 | Landing hero |
| `h1` | 28px / 36px | 700 | Screen titles |
| `h2` | 22px / 30px | 700 | Section heads |
| `h3` | 18px / 26px | 600 | Card titles |
| `body` | 16px / 24px | 400 | Default text |
| `body-strong` | 16px / 24px | 600 | Emphasis |
| `small` | 14px / 20px | 400 | Meta, timestamps |
| `caption` | 12px / 16px | 500 | Badges, overlines |
| `alert-sms` | 15px / 22px | 400 | Rendered alert messages |

- Inputs use **≥ 16px** (prevents iOS auto-zoom).
- Minimum UI text in a second language: keep Devanagari line-height at 1.6 for
  conjunct legibility.

## 3. Spacing & shape

4-pt grid: `4 / 8 / 12 / 16 / 24 / 32 / 48`. Page gutter 16px mobile, 24px desktop.
Card radius 16px, button radius 12px, pill/badge radius 999px, sheet radius 24px top.
Shadows: card `0 1px 3px rgb(15 23 42 / 0.08)`; sheet `0 -8px 32px rgb(15 23 42 / 0.18)`.

## 4. Touch & low-literacy rules

- Minimum touch target **48×48 px**; primary CTAs **56 px tall**, full-width on mobile.
- Primary actions: icon (24px) + ≤ 6-word label. Example: `🚨 भेजें · Send SOS`.
- SOS form is photo-first: the photo tile is the largest element; description has a
  **mic button** (voice input) beside it.
- No step in any flow requires reading more than ~25 words. Help text is a
  tappable `?` that opens a one-line tooltip, never a paragraph.
- Numbers that matter (severity, risk, distance) are always ≥ 28px bold.

## 5. Component specs

### 5.1 Buttons
- `btn-primary` (brand-600 bg, white, 56px h, radius 12, 600 wt) — normal actions.
- `btn-sos` (alert-600 bg, white, 64px h mobile, icon 🚨) — ONLY for filing an SOS.
  Nothing else in the app may use this exact style (it must scream "emergency").
- `btn-secondary` (white bg, 2px brand-600 border, brand-700 text).
- `btn-danger-ghost` (transparent, alert-600 text) — decline/cancel.
- Disabled: 40% opacity, no pointer events. Loading: spinner replaces icon, label stays.

### 5.2 SeverityBadge (frozen)
Pill: 44px min-height, severity number 20px/800 + name in caption caps
(e.g. `4 · SEVERE`). Colors per §1.1. Always paired with `aria-label="Severity 4, severe"`.

### 5.3 CategoryChip
Small pill with icon + label: medical `✚`, rescue `🛟`, food `🍲`, shelter `⛺`,
infrastructure `🏗`, other `⋯`. Neutral slate styling (category is not urgency).

### 5.4 SOSCard
Surface card, 16px radius: top row = SeverityBadge + time-ago + DEMO badge (if
`is_demo_data`); description (2-line clamp); row of CategoryChip + StatusPill;
footer = district name + distance (if known) + "needed: 🛟🚗" skill icons.
Tap → bottom sheet detail. Live-update: new cards slide in with `sos.created` WS
events; updated cards pulse once on `sos.status_changed`.

### 5.5 StatusPill
Per §1.2. 36px height, icon + label.

### 5.6 BottomSheet
Mobile-first detail container: 24px top radius, drag handle, 70% max height,
scrim `rgb(15 23 42 / 0.5)`. Used for SOS detail, volunteer match list, shelter detail.

### 5.7 Toast
Bottom-center (above nav), 48px, dark `#0F172A` bg / white text, auto-dismiss 4s.
Types: success (green left bar), error (red), offline (amber, persistent until online).

### 5.8 Skeleton loaders
Shimmer blocks matching card shape; used on first load of board/alerts/admin.
Never show a blank screen > 400 ms.

### 5.9 EmptyState
Centered: 64px line-icon, h3, one-line explanation, one primary action.
E.g. board with no SOS in filter: `🗺 "No reports here yet" / "Be the first to report" → btn-sos`.

### 5.10 OfflineBanner & QueueBadge
Persistent slim banner under the header when offline: amber bg `#FEF3C7`,
`📶 Offline — reports will queue`. QueueBadge on the report tab icon: count of
IndexedDB outbox entries (`client_report_id` list). On reconnect: toast
`✓ N queued report(s) sent`.

### 5.11 StatTile (landing)
Big number (32px/800, brand-700) + caption. Values from seed: 3,000 SOS reports ·
1,000 volunteers · 500 shelters · 20 districts. Each tile footnotes "demo data".

### 5.12 RiskGauge
0–100 semicircular gauge, needle + big number; color bands per risk_level
(low `#16A34A` 0–39, moderate `#EAB308` 40–69, high `#F97316` 70–84, severe `#DC2626`
85–100). Below: contributing-factor bars (factor name + contribution pts).

### 5.13 HeatmapLegend
Fixed gradient bar (green→red) labeled "fewer reports → more reports",
always visible when heatmap layer is on.

### 5.14 BroadcastComposer
Admin modal: district multi-select chips (20 districts), type select
(flood/heatwave/cyclone/custom), severity stepper 1–5 (uses SeverityBadge mini),
title + body fields with live **character counter** (`n / 480` per language note),
language checkboxes (10, default all), preview tabs per language rendering the
SMS-length message, big `📢 Send broadcast` (alert-600). Shows recipient estimate.

### 5.15 TaskCard (volunteer)
Volunteer task: SOS summary mini (severity badge + 1-line description + distance),
skill icons needed, action row changes by status: `assigned → [Accept] [Decline]`;
`accepted → [🧭 Start: En route]`; `en_route → [📷 Complete]` (photo proof optional);
terminal states show StatusPill + reputation delta `+2 ★`.

### 5.16 LanguageSwitcher
Header globe icon `🌐` + current language native name (e.g. `हिन्दी`);
opens bottom sheet with 10 languages (native names, checkmark on active).
Persists to `localStorage` + `User.preferred_lang`. Switching re-renders instantly
(no reload); map labels stay as-is (tiles), but all UI strings swap.

### 5.17 DemoModeBanner
When `X-Admin-Key: demo-admin-key` or `?demo=1`: full-width striped banner
(amber/black chevrons) — `⚠ DEMO MODE — all data synthetic`. One-click button:
`▶ Play Patna flood demo` seeds + runs the demo-director timeline.

## 6. Offline / low-bandwidth mode styles

- Toggle in header (`📶` icon) + auto-suggest when `navigator.connection.saveData`
  or 2G is detected: `body.low-bandwidth` class.
- `.low-bandwidth`: `img, .map-tiles { display: none }`; every map gets a
  **text-list mirror** (requirement: no information exists only on the map);
  system font stack only; animations disabled (`prefers-reduced-motion` respected too).
- Queued SOS drafts render in the report screen as cards with `⏳ Queued` status.

## 7. Motion

- Page transitions: 180 ms ease-out slide/fade. Live card insert: 240 ms slide-down.
- Status change pulse: badge scales 1→1.15→1 over 400 ms, once.
- Respect `prefers-reduced-motion`: disable all non-essential animation.

## 8. Accessibility baseline (Agent 12 expands)

- Contrast ≥ 4.5:1 text, ≥ 3:1 large text/UI.
- All icon-buttons have `aria-label`; severity/status always text-labeled.
- Focus ring: 3px `brand-600` outline offset 2px, always visible on keyboard nav.
- Map: every pin mirrored in an adjacent list; list is the screen-reader source of truth.
- Font-size control (S/M/L) scales root `font-size` 100%/112.5%/125%.
