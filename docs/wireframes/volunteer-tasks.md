# Wireframe — Volunteer Tasks (`/volunteer`)

**Route:** `/volunteer` · **Audience:** registered volunteers (e.g. Ravi Kumar in the demo)
**Goal:** see my tasks, accept, go en-route, complete — the dispatch half of the hero loop.

## Layout

```
NOT REGISTERED → registration card:
┌──────────────────────────────────────────┐
│ ← Volunteer                              │
│  🙋 Become a volunteer                   │
│  Name [____________]  Phone [__________] │
│  District [Patna ▾]                      │
│  Skills: [🛟 rescue] [✚ medical] [🚗 …]  │  multi-select chips (9 skills)
│  Languages: [हिन्दी] [Hinglish] …        │  multi-select (10)
│  Available: (•) Anytime ( ) Set hours    │
│  ┌────────────────────────────────────┐  │
│  │        ✓ Register                  │  │  POST /api/volunteers
│  └────────────────────────────────────┘  │

REGISTERED → home:
┌──────────────────────────────────────────┐
│ ← Hi, Ravi Kumar · ★ 52 (1 done)   [🌐]  │  reputation + tasks_completed
│  🟢 Available now  [toggle]               │  flips Volunteer.active
│  📍 Patna · 🛟🚗 · हिन्दी, Hinglish      │
├──────────────────────────────────────────┤
│  MY TASKS                    [+ task log]│
│  ┌────────────────────────────────────┐  │
│  │ ◆ 4 · SEVERE · 🛟 rescue           │ │  TaskCard — status: assigned
│  │ Knee-deep water, Kankarbagh        │ │
│  │ 📍 2.1 km · ⏱ assigned 4 min ago   │ │
│  │ [✓ Accept]      [✕ Decline]        │ │  POST …/accept | …/decline
│  └────────────────────────────────────┘  │
│  ┌────────────────────────────────────┐  │
│  │ ▲ 3 · SERIOUS · ✚ medical          │ │  TaskCard — status: en_route
│  │ 🧭 EN ROUTE · started 12 min ago   │ │
│  │ [📷 Complete task]                 │ │  POST …/complete (+photo opt)
│  └────────────────────────────────────┘  │
│  ── Done ──                              │
│  ✓ Flood rescue · +2 ★ · 32 min         │  compact history rows
├──────────────────────────────────────────┤
│  🔔 New assignments appear here live     │
└──────────────────────────────────────────┘
```

## Interaction notes
- Task lifecycle buttons map exactly to the API: `accept → accepted`,
  `decline → declined` (asks one-tap reason chips: `too far / busy / not skilled`),
  `enroute → en_route`, `complete → completed` (optional note + photo proof).
- **Accept** is the volunteer's commitment: SOS flips to `help_on_way` on first
  `enroute` (backend rule — UI shows "Help is on the way" on the board).
- **Live:** WS `task.assigned` → new TaskCard slides to top + notification toast
  `🛟 New task near you (2.1 km)`; `task.updated` refreshes states.
- Availability toggle → `PATCH /api/volunteers/{id}` `{active}`; when off, the
  volunteer disappears from matching and the board shows `⚪ Off duty`.
- Reputation: `★ N` with tooltip "completed tasks & response time set this —
  you can't edit it" (server-managed, per contracts).
- **Demo path (Ravi):** task card appears on accept → en-route → complete with the
  exact `vol-ravi-kumar-patna` seed; after complete, SOS → `resolved` on the board.

## States
- **Loading:** skeleton TaskCards.
- **Empty (no tasks):** `🛟 No tasks yet — we'll notify you when help is needed nearby`
  + `🔔 notification permission` nudge (in-app only in v1).
- **Offline:** tasks cached; accept/decline/enroute/complete **queue locally** and
  sync on reconnect (same outbox pattern as SOS); banner explains "actions will sync".
- **Error:** failed action → toast `⚠ Couldn't update — will retry` + card keeps
  prior state (never show a state the server didn't confirm).
