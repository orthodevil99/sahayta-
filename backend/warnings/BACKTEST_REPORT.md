# Early-Warning Backtest Report

- **Data:** `data/weather-sample.json` — 20 districts × 30 days = 580 district-days (ALL SYNTHETIC)
- **SOS footprint:** `data/sos-reports.json` (severity-4+ counts per district-day)
- **Event rule:** rain_mm >= 150 OR >= 5 severity-4+ SOS/day; prediction = risk(day d-1, pure v1 formula, no seed hints)
- **Event days found:** 30

## Method

For each district-day d (d = 1..29), the pipeline scores the weather of day
d-1 with the **pure v1 risk formula** (`app.services.risk.score_district`,
**no seed hints** — this tests the formula, not the demo calibration).
A warning/advisory is 'predicted' for day d when that risk crosses 85 / 70.
Precision/recall are computed over district-days (predicted warning → event
within 24 h; event day → predicted warning in the preceding 24 h).
Deterministic: pure functions, no randomness — re-running gives identical numbers.

## Results

| Level | Threshold | TP | FP | FN | Precision | Recall |
|---|---|---|---|---|---|---|
| warning | risk > 85 | 0 | 0 | 30 | 0.0 | 0.0 |
| advisory | risk > 70 | 0 | 0 | 30 | 0.0 | 0.0 |

## Findings (read before the numbers)

The raw precision/recall are 0.0 at both levels — and the *reason* is the
finding, not a bug in the pipeline:

1. **The v1 formula caps flood-only risk below the warning band.**
   Theoretical maximum for a pure flood (300 mm rain, river rising,
   saturated air, no heat/cyclone): **risk = 82**.
   The `> 85` warning threshold is therefore *unreachable* for flood-only
   weather by construction — 'severe' (85–100) requires a heat or cyclone
   signal on top of the flood. The highest prev-day risk observed on any
   event day was **70**.
   → Recommendation (not applied — the formula is frozen/shared): either
   re-weight the flood components or define the warning threshold per
   hazard type instead of one global 85.
2. **Most 'event days' are SOS-defined, and SOS is a lagging indicator.**
   Of 30 event days, 29 fired on the SOS-footprint
   rule and only 1 on the rain rule. Prev-day risk histogram on event
   days (by decade):

   - risk  10-19 : #### (4)
   - risk  20-29 : ################ (16)
   - risk  30-39 : ###### (6)
   - risk  50-59 : ### (3)
   - risk  70-79 : # (1)

   The SOS generator ramps report volume toward the flood peak, so SOS-defined
   event days cluster on days whose *weather* was still moderate — a
   weather-only predictor cannot catch them, and shouldn't be expected to.
   The rain-driven event days (the independent half of the rule) are the
   fair test of the formula; they sit at prev-day risk 60–70, just under the
   advisory threshold — consistent with finding 1.
3. **Pipeline mechanics verified.** Ingest → score → threshold → broadcast
   all execute deterministically on the replay (no crashes, no NaNs,
   identical numbers on re-run). What the backtest cannot validate is
   real-world predictive skill — see caveats.

## Event days (ground truth)

- 2026-10-04 **bhagalpur** — 6 sev-4+ SOS >= 5 (risk from prior day: 39)
- 2026-10-05 **bhagalpur** — 13 sev-4+ SOS >= 5 (risk from prior day: 19)
- 2026-10-05 **chennai** — 5 sev-4+ SOS >= 5 (risk from prior day: 26)
- 2026-10-04 **darbhanga** — 9 sev-4+ SOS >= 5 (risk from prior day: 23)
- 2026-10-05 **darbhanga** — 22 sev-4+ SOS >= 5 (risk from prior day: 51)
- 2026-10-05 **dibrugarh** — 6 sev-4+ SOS >= 5 (risk from prior day: 39)
- 2026-10-05 **gaya** — 8 sev-4+ SOS >= 5 (risk from prior day: 22)
- 2026-10-05 **guwahati** — 7 sev-4+ SOS >= 5 (risk from prior day: 29)
- 2026-10-03 **katihar** — 5 sev-4+ SOS >= 5 (risk from prior day: 25)
- 2026-10-04 **katihar** — 10 sev-4+ SOS >= 5 (risk from prior day: 24)
- 2026-10-05 **katihar** — 20 sev-4+ SOS >= 5 (risk from prior day: 29)
- 2026-10-05 **kolkata** — 9 sev-4+ SOS >= 5 (risk from prior day: 21)
- 2026-10-05 **lucknow** — 5 sev-4+ SOS >= 5 (risk from prior day: 18)
- 2026-10-04 **muzaffarpur** — 9 sev-4+ SOS >= 5 (risk from prior day: 38)
- 2026-10-05 **muzaffarpur** — 23 sev-4+ SOS >= 5 (risk from prior day: 55)
- 2026-10-05 **nagpur** — 8 sev-4+ SOS >= 5 (risk from prior day: 22)
- 2026-10-03 **patna** — 17 sev-4+ SOS >= 5 (risk from prior day: 27)
- 2026-10-04 **patna** — 46 sev-4+ SOS >= 5 (risk from prior day: 29)
- 2026-10-05 **patna** — 136 sev-4+ SOS >= 5 (risk from prior day: 59)
- 2026-10-06 **patna** — rain 185mm >= 150mm (risk from prior day: 70)
- 2026-10-05 **puri** — 6 sev-4+ SOS >= 5 (risk from prior day: 30)
- 2026-10-04 **purnia** — 10 sev-4+ SOS >= 5 (risk from prior day: 22)
- 2026-10-05 **purnia** — 18 sev-4+ SOS >= 5 (risk from prior day: 19)
- 2026-10-04 **samastipur** — 5 sev-4+ SOS >= 5 (risk from prior day: 26)
- 2026-10-05 **samastipur** — 20 sev-4+ SOS >= 5 (risk from prior day: 25)
- 2026-10-05 **sitamarhi** — 20 sev-4+ SOS >= 5 (risk from prior day: 23)
- 2026-10-03 **vaishali** — 6 sev-4+ SOS >= 5 (risk from prior day: 38)
- 2026-10-04 **vaishali** — 7 sev-4+ SOS >= 5 (risk from prior day: 31)
- 2026-10-05 **vaishali** — 28 sev-4+ SOS >= 5 (risk from prior day: 19)
- 2026-10-05 **varanasi** — 5 sev-4+ SOS >= 5 (risk from prior day: 24)

## Honest caveats

1. **Synthetic-on-synthetic.** The weather extremes and the SOS spikes were
   scripted by the same generator (`data/generators/`), so the weather↔SOS
   correlation is optimistic by construction. These numbers validate
   *pipeline mechanics* (ingest → score → threshold → would-broadcast),
   not real-world predictive skill.
2. The SOS-footprint half of the event rule reuses the generator's output as
   ground truth — circular if read as 'the model predicts reports'. The
   rain-only half of the rule is the independent check.
3. Seed hints are deliberately NOT applied here; the live demo keeps Patna
   at 82/high via hints (see `warnings/recompute.py`), which is a separate,
   disclosed calibration.
4. River trend in the replay comes from the synthetic series; the live
   worker carries forward the last stored reading (Open-Meteo has no river
   data) — documented in `warnings/README.md`.

_Generated by `python -m warnings.backtest` (backend cwd). Sample window: 2026-10-06 minus 30 days._
