# NOTES — Agent 2 (Data Foundry)

## Decisions

1. **District list (20 slugs).** Agent 1's docs named only 6 slugs explicitly
   (`.env.example`: patna, vaishali, gaya, muzaffarpur, darbhanga, bhagalpur) and
   said "20 districts in v1" without enumerating them. I kept those 6 and added
   14 flood/cyclone/heatwave-prone districts (4 more in Bihar, 3 in UP, 2 in
   Assam, 2 in West Bengal, plus puri, nagpur, chennai) with approximate real
   lat/lng centers. `data/districts.json` is now the canonical list — all later
   agents MUST use these slugs verbatim. If Agent 1's intent differed, the fix
   is to edit `districts.json` and re-run the generators (they key off it).
2. **Ravi Kumar skills.** My brief said "rescue+medical"; `docs/demo-scenario.md`
   (the acceptance test) says `["rescue","driving"]` and expects the pipeline's
   `suggested_skills` to be `["rescue","driving"]`. I used the demo-scenario
   version (`["rescue","driving"]`) since it is the frozen acceptance test.
   Anchor id `vol-ravi-kumar-patna`, 2.09 km from the SOS pin (25.5941, 85.1376),
   languages `["hi","hing"]`, `availability: "anytime"`, reputation 50,
   tasks_completed 0 — matches the scenario exactly.
3. **Severity distributions** are realistic: sos-reports skew 1–3
   (829/922/682 vs 397/170 for 4/5); severity-labels similar. Patna gets a
   severity bump in the last 24h of the event (flood peak), yielding 145 Patna
   severity-4 reports including 25 forced anchors in the final 12h — three of
   them near-verbatim mirrors of the demo fixture Hindi text.
4. **Timestamps** are a fixed simulated window: 2026-10-03T00:00Z →
   2026-10-06T00:00Z (72h), report volume ramping toward the peak. Status mix
   correlates with age (old → mostly resolved, recent → mostly reported).
5. **Weather** is daily × 30 days × 20 districts (600 records) with scripted
   extremes: Patna rain 80→137→185 mm/day + river rising to ~50.3 m (supports
   the demo's risk-82/high target; `seed_hints.patna` documents it for the
   backend seed script), Nagpur 43.5–46°C heatwave (7d), Puri/Chennai 95–115
   kph cyclone winds (2d).
6. **Alert templates** are hand-written (not generated) in 10 languages, native
   scripts, each rendering ≤ ~160 chars with district="Patna", helpline="1078",
   temp="45", wind="110". Placeholders: `{district}`, `{helpline}` (+`{temp}` /
   `{wind}`). Verified programmatically in `verify.py`.
7. **Phones/names are fake** (`+91-` + random digits; template names). Stated in
   `DEMO_DATA_README.md` and in every file's `meta.note`.

## Reproducibility

- Fixed seeds (`SEED = 20261006` + per-generator salt in `common.py`).
- Regenerate: `cd data/generators && for f in gen_sos_reports gen_severity_labels gen_shelters gen_volunteers gen_weather; do python3 $f.py; done && python3 verify.py`
- `verify.py` checks: 20 unique districts; 3000 SOS rows with valid enums and
  ≥25 Patna sev-4 anchors; 5000 label rows (>4500 unique descriptions);
  500 shelters (50 × 10 districts, occupied ≤ capacity, all `is_demo_data`);
  1000 volunteers with the Ravi anchor at ~2.1 km; 20×30 weather with the Patna
  spike; 3 alert types × 10 languages with length checks.

## Row counts

| File | Rows |
|---|---|
| `districts.json` | 20 districts |
| `sos-reports.json` | 3,000 reports |
| `severity-labels.csv` | 5,000 labeled pairs |
| `shelters.json` | 500 shelters |
| `volunteers.json` | 1,000 volunteers |
| `weather-sample.json` | 600 daily records (20 × 30) |
| `alert-templates/` | 3 disaster types × 10 languages |

## Known limitations (for later waves)

- SOS text templates are flood-leaning even for heatwave/cyclone districts
  (the brief scoped the event as a 72-hour flood); heatwave/cyclone variety
  lives mainly in `photo_description` and `severity-labels.csv`.
- `photo_url`/`photo_hash` are null in sos-reports (no binary fixtures; the
  real demo photo fixture lands in `data/demo/patna-flood/` in Wave 2).
- `other`-language SOS templates (ta/te/mr/gu/kn/ml/pa) are single generic
  templates per language — enough for language-coverage tests, not linguistic
  depth. Alert templates for those languages are fully hand-written.
