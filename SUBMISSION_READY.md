# SUBMISSION_READY.md — Sahayta, WarriorHacks 2.0 (HACKATHON track)

**Build status: COMPLETE and verified** (Agent 15 sign-off, Oct 6 2026).
Repo: `~/workspace/warriorhacks-sahayta/sahayta/` · branch `master` · all work
committed locally, nothing pushed (no credentials on the build machine).

## Verification summary (Agent 15, this run)

| Check | Result |
|---|---|
| Backend pytest | **79/79 pass** |
| AI engine tests | **65/65 pass** |
| Frontend tests | **6/6 files pass** (`contracts, demo-assess, format, geo, i18n, reputation`) |
| Frontend `tsc --noEmit` | clean |
| Demo-director sign-off (`demo_director.py --scenario patna-flood`, fresh seed) | **14/14 PASS, exit 0** |
| Secrets sweep (repo minus node_modules/.venv/.git) | **clean** — zero keys/tokens/passwords (2 false-positive hits on the word "recompute" in docs diagrams) |
| `.env.example` completeness | all `SAHAYTA_*` vars used in code present (added missing `SAHAYTA_LLM_VISION`); `NEXT_PUBLIC_API_URL` in `frontend/.env.example` |
| Repo hygiene | removed `frontend/.test-build/`, `frontend/out/` (regenerable), stray smoke script; `.gitignore` covers node_modules, .venv, .next, out/, `*.db`, media uploads |
| Contracts | **v1.3 FROZEN** (additive only, `MIGRATION.md`) |

## Devpost fields → what to paste

Full field-by-field mapping: [`docs/launch/devpost-fields.md`](docs/launch/devpost-fields.md)
(10 fields in order). Copy source: [`docs/launch/devpost-copy.md`](docs/launch/devpost-copy.md)
(5 title options, tagline, full description pre-mapped to judging criteria).
Video assets: [`docs/launch/video-script.md`](docs/launch/video-script.md) (3 variants —
**record Variant A, 2:30**), [`docs/launch/voiceover-only.txt`](docs/launch/voiceover-only.txt),
[`docs/launch/shot-list.md`](docs/launch/shot-list.md) (8 screenshots),
[`docs/launch/recording-checklist.md`](docs/launch/recording-checklist.md).

> ### ⚠️ GOOGLE FORM TRACK SELECTION — PRAKHAR'S MANUAL ACTION
> Track selection happens in a **separate Google Form** (not on Devpost).
> Select the **HACKATHON** track (code required) — NOT ideathon.
> **Agents must not attempt this step** — it requires prakhar's Google account.
> Do it before submitting on Devpost.

## Prakhar's remaining actions (in order)

- [ ] **1. Create the GitHub repo + push.** Create a **public** repo named
      `sahayta` on GitHub, then:
      ```bash
      cd ~/workspace/warriorhacks-sahayta/sahayta
      git remote add origin https://github.com/<your-username>/sahayta.git
      git push -u origin master
      ```
      Verify: repo is public, README renders, no `.env` file present.
- [ ] **2. Deploy the frontend (Vercel).** Import the repo in Vercel, set
      **Root Directory = `frontend`**, framework Next.js, deploy. Demo link =
      `<deployed-url>/?demo=1` (zero-backend demo mode — judges click
      "▶ Play Patna flood demo" with no setup).
- [ ] **3. Record the 2–3 min video** per `docs/launch/video-script.md`
      (Variant A) and `docs/launch/recording-checklist.md`. Upload to YouTube
      as **Unlisted** (or Public). Copy the URL → `<YOUTUBE_URL>`.
- [ ] **4. Capture the 8 screenshots** per `docs/launch/shot-list.md`
      (from `http://localhost:3000/?demo=1`, fresh incognito window).
- [ ] **5. Fill the Google Form** → select **HACKATHON** track. (Manual — see warning above.)
- [ ] **6. Submit on Devpost** using `docs/launch/devpost-fields.md`
      (paste `<YOUTUBE_URL>`, `<REPO_URL>`, `<FRONTEND_URL>/?demo=1`).
      Final gate: `docs/launch/pre-submit-checklist.md`.
- [ ] **7. After submitting**, follow `docs/launch/after-submit.md`.

**Deadlines:** Devpost closes **Oct 14, 2026, 12:45 AM EDT (10:15 AM IST)**.
Internal hard deadline: **Oct 13, 2026, end of day IST.**

## Known limitations (stated honestly in the repo)

1. Early-warning backtest precision/recall 0.0/0.0 — the v1 risk formula caps
   pure-flood risk at 82, below the 85 warning band (`backend/warnings/BACKTEST_REPORT.md`).
   Demo unaffected (Patna shows 82/high as specced).
2. Translations not native-speaker reviewed (`docs/i18n-coverage.md`).
3. Voice input untested against live speech — fallback path is the tested one.
4. No real SMS delivery — alert "broadcasts" are rendered previews (labeled).
5. Weather defaults to the clearly-labeled simulated feed; live Open-Meteo is
   keyless and best-effort.
