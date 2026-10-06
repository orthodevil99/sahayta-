# Wireframe — Alerts Feed (`/alerts`)

**Route:** `/alerts` · **Audience:** citizens in affected districts (10 languages)
**Goal:** the official word, in my language, readable on a 2G phone.

## Layout

```
┌──────────────────────────────────────────┐
│ ← Alerts                   [🌐 हिन्दी]   │
│ District [Patna ▾]  Type [All ▾]         │
│ ⚠ DEMO DATA — sample alerts              │
├──────────────────────────────────────────┤
│ ┌──────────────────────────────────────┐ │
│ │ ◆ 4 · SEVERE · 🌊 FLOOD              │ │  severity badge + type chip
│ │ बाढ़ चेतावनी: पटना के निचले इलाकों   │ │  message in ?lang= (default hi)
│ │ में पानी बढ़ रहा है। तुरंत ऊँची      │ │  alert-sms 15px type
│ │ जगह जाएँ। राहत शिविर खुले हैं।       │ │
│ │ हेल्पलाइन: 1078                      │ │
│ │ ────────────────────────────────    │ │
│ │ 📍 Patna · 12 min ago · via SMS ✓   │ │  districts, time, channel note
│ │ [View in: हिन्दी ▾]                  │ │  per-alert language switcher
│ └──────────────────────────────────────┘ │
│ ┌──────────────────────────────────────┐ │
│ │ ▲ 3 · SERIOUS · 🌊 FLOOD             │ │
│ │ …(next alert)…                       │ │
│ └──────────────────────────────────────┘ │
└──────────────────────────────────────────┘

PER-ALERT LANGUAGE VIEW (tap "View in"):
  bottom sheet with the same alert rendered in all 10 languages,
  each ≤ 480 chars (3 SMS segments) — the multilingual proof for judges.
```

## Interaction notes
- Feed = `GET /api/alerts?district=&type=&lang=`; new broadcasts arrive via WS
  `alert.broadcast` and slide to top with a pulse.
- **Per-alert language switcher** is the multilingual wow-moment: one alert, 10
  native-script renderings, all from `Alert.messages` (ground-truth templates +
  LLM renderings, per `ai-engine/alerts.py`).
- Type chips: `🌊 flood` `🌡 heatwave` `🌀 cyclone` `📣 custom`.
- **Demo beat:** the Hindi broadcast from Act 4 appears here in Hindi + Hinglish
  tabs — the video lingers on the Hinglish Latin-script version (judges read it).
- Low-bandwidth: this screen is already text-first — it becomes the app's home
  when `.low-bandwidth` is on (nav reorders: Alerts first).

## States
- **Loading:** skeleton alert cards.
- **Empty:** `📣 No alerts for Patna right now — that's good news.` + risk gauge
  mini (`current district risk: 82 · high`) linking to forecast.
- **Offline:** cached alerts with `cached HH:MM`; banner notes new alerts need connection.
- **Error:** `⚠ Couldn't load alerts [Retry]`.
