# Sahayta — Devpost Submission Fields (fill in order)

Every field on the Devpost submission form, with the exact text or file to
paste/upload. Placeholders in `<ANGLE BRACKETS>` are prakhar's manual actions.

## 1. Project title

Pick one (5 options in `docs/launch/devpost-copy.md`); recommended:

```
Sahayta — When Disaster Strikes, Help Finds You
```

## 2. Tagline (short pitch)

```
A disaster-response OS for India: photo-based SOS triage, AI severity
estimation, volunteer dispatch, and multilingual alerts — offline-first,
because networks die in disasters.
```

## 3. Description (full)

Paste the **Full description** from `docs/launch/devpost-copy.md`
(sections: Problem statement · Target users · Technical approach and
components · Real-world impact — each pre-mapped to the judging criteria).

## 4. Demo video URL (REQUIRED for eligibility)

```
<YOUTUBE_URL>   ← upload the 2:30 Variant A cut (see docs/launch/video-script.md);
                  set visibility to Public or Unlisted-with-link
```

## 5. Repository URL (REQUIRED — code track)

```
<REPO_URL>      ← public GitHub repo of ~/workspace/warriorhacks-sahayta/sahayta/
```

## 6. Live demo / "Try it out" link

```
<FRONTEND_URL>/?demo=1   ← zero-backend demo mode; judges click
                           "▶ Play Patna flood demo" with no setup
```

Backup (if hosting lags): note in the description that
`packages/simulation/demo_director.py --scenario patna-flood` replays the
full 14-step scenario deterministically (14/14 PASS).

## 7. Screenshots / pictures (≥3 recommended)

Capture from `http://localhost:3000/?demo=1` (fresh incognito window).
Exact capture steps: `docs/launch/shot-list.md` (8 shots). Minimum set:

1. `/report` in Hindi — SOS wizard with flood photo + map pin (UX proof)
2. Severity badge — ◆ 4 · SEVERE with Hindi rationale + `model:` label (craft proof)
3. `/board` — live SOS map + heatmap + red pin over Kankarbagh (impact proof)
4. Match panel — Ravi Kumar 92.5 with reasons (feasibility proof)
5. `/alerts` — 10-language bottom sheet open (multilingual proof)
6. `/admin` — KPI row + risk 82/HIGH + SIMULATED FEED chip + timeline (command proof)

## 8. Built with (tags)

```
Next.js 14, FastAPI, Leaflet, Python, TypeScript, Tailwind CSS, SQLite,
Alembic, pdf-lib, reportlab
```

## 9. Track selection (REQUIRED — separate Google Form)

> **prakhar does this manually.** Agents must NOT attempt it.
> Select the **HACKATHON** track (code required) — NOT ideathon.

## 10. Submit

- [ ] Video is public/unlisted and 2–3 min (Variant A = 2:30)
- [ ] Repo is public, no API keys anywhere (Agent 15 verifies)
- [ ] ≥3 screenshots uploaded
- [ ] Demo link opens and `?demo=1` plays without a backend
- [ ] HACKATHON track selected in the Google Form
- [ ] Submit before **Oct 14, 2026, 12:45 AM EDT (10:15 AM IST)**;
      internal hard deadline **Oct 13 EOD IST**
