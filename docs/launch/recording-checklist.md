# Sahayta — Video Recording Checklist (for prakhar)

## 1. Pre-flight (do once, ~10 min)

- [ ] **Backend determinism check:** `cd packages/simulation && python demo_director.py --scenario patna-flood` → **14/14 PASS, exit 0**. If anything FAILs, stop and fix — never record over red.
- [ ] **Fresh seed (only if recording `[LIVE]` takes):** `cd backend && .venv/bin/python seed.py --fresh && .venv/bin/python -m uvicorn app.main:app --port 8000`. Skip for `[UI]`/`[PLAY]` takes (no backend needed).
- [ ] **Frontend up:** `cd frontend && npm run dev -- -p 3000` (or `npm run build` for a static export — `out/` is git-ignored and regenerable, never committed).
- [ ] **Fixture at hand:** `data/demo/patna-flood/flood-photo.jpg` + the exact Hindi description text (copy from `data/demo/patna-flood/description.txt`).
- [ ] **Screen:** 1440×900 or 1920×1080. Close personal tabs; hide the bookmarks bar. Fresh **incognito window** for every take.
- [ ] **Pick your variant:** A (recommended, 2:30) in `docs/launch/video-script.md`. Print it or keep it on a second screen/phone.

## 2. Demo-mode URL params (bookmark these)

| Purpose | URL |
|---|---|
| Landing + auto-play | `http://localhost:3000/?demo=1` → **▶ Play Patna flood demo** |
| Report wizard | `http://localhost:3000/report?demo=1` |
| SOS board (Patna) | `http://localhost:3000/board?demo=1` → filter district = Patna |
| Volunteer view | `http://localhost:3000/volunteer?demo=1` |
| Alerts feed | `http://localhost:3000/alerts?demo=1` |
| Admin dashboard | `http://localhost:3000/admin?demo=1` → district = Patna |

`?demo=1` (or the safe default when no API URL is set) runs everything off
bundled synthetic data — the video never needs a backend or an API key.

## 3. Mic & audio tips

- [ ] Quiet room, door closed, fan/AC off if audible. Phone on silent.
- [ ] Mic 15–20 cm from mouth, slightly off-axis (avoids plosives). Do a 10-second test recording and listen back.
- [ ] Speak slower than feels natural — especially the Hindi words. Use the pronunciation hints in `docs/launch/voiceover-only.txt` (KUN-ker-bagh, BHEH-jayn, baadh CHET-av-nee).
- [ ] Record voiceover **separately** from the screen capture (cleaner audio, easier retakes), then sync in the edit. Clap once at the start of each take as a sync mark.
- [ ] Burned-in **English captions** for every Hindi UI moment (editors: YouTube auto-captions + manual fix is acceptable).

## 4. If a take fails

1. **Don't improvise around it.** Note the timestamp, stop the take.
2. **Reset state:** new incognito window (clears `sahayta.demo.*` localStorage deltas). Replays via `playPatnaDemo()` mint a fresh SOS each run — no manual cleanup.
3. **Re-verify:** re-run `demo_director.py --scenario patna-flood` → 14/14 PASS.
4. **Re-shoot the scene**, not the whole video — scenes are independent files in the edit.
5. Common gotchas:
   - Board pin missing → you filtered the wrong district, or recorded before the WS event fired (wait 2 s after SEND).
   - `model:` label not showing → hover and hold 2 full seconds.
   - Hindi text renders as boxes → the Noto fonts didn't load; check network once, then reload (graceful fallback still records, but fix it).
   - Match score differs from 92.5 → you're on a stale seed; fresh incognito + re-shoot.

## 5. Export & upload settings

- [ ] **Resolution:** 1080p (1920×1080). **Codec:** H.264 MP4. **Frame rate:** 30 fps. **Audio:** AAC 128 kbps+.
- [ ] **Length check:** 2:00–3:00 hard window (Devpost eligibility). Variant A = 2:30 with 30 s slack — if your edit runs over, trim B-roll first, never the honesty shots (`model:` label, DEMO DATA, SIMULATED FEED).
- [ ] **Upload:** YouTube as **Unlisted** (or Vimeo). Title: `Sahayta — When disaster strikes, help finds you (WarriorHacks 2.0 demo)`. Paste the URL into the Devpost "Video" field.
- [ ] **Screenshots:** export the 8 shots from `docs/launch/shot-list.md` as PNGs into `docs/launch/shots/` for the Devpost gallery.

## 6. Day-of sanity pass (5 min before upload)

- [ ] Watch the final cut once at 1×: every spoken number matches the honest-number list (275 req / 0 errors / p95 107 ms; 0.602 / 1.000; 92.5; 82 HIGH; 10 × 311).
- [ ] `model: rule-fallback-v1`, DEMO DATA chips, and SIMULATED FEED chip all visible at least once.
- [ ] No API keys, personal tabs, or passwords visible in any frame.
- [ ] Video is 2–3 min, public/unlisted link works in an incognito window.
