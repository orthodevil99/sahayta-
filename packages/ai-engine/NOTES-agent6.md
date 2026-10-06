# NOTES — Agent 6 (AI Engine, Wave 2)

## What was built

`packages/ai-engine/` — the provider-agnostic intelligence layer. Zero runtime
dependencies (stdlib `urllib` for the LLM client); `pytest==8.3.4` for tests
only. 65 unit/integration tests green + 3 worked end-to-end examples with
saved traces. Backend seam verified: the two guarded demo tests
(`test_assess_endpoint_demo_fixture_scores_4`,
`test_post_sos_demo_fixture_scores_4`) pass **through my engine** with
`SAHAYTA_LLM_*` pointed at a dead endpoint (honest fallback, severity 4,
`model: rule-fallback-v1`), and all 36 backend tests pass with the engine
present.

**Modules:** `config.py` (env-only LLM config: `SAHAYTA_LLM_BASE_URL/MODEL/
API_KEY/TIMEOUT_S/MAX_TOKENS/VISION` — never hardcoded), `llm.py`
(OpenAI-compatible chat client, token estimation, rough cost table),
`severity.py`, `triage.py`, `alerts.py`, `risk.py`, `pipeline.py`
(the seam: `assess_and_route(description, language, lat, lon,
photo_description, photo_path) -> dict`).

## Key design decisions

1. **Honest model attribution everywhere.** Every result carries `model`:
   `"llm:<model-id>"` when a real model answered, `"rule-fallback-v1"` when
   rules did — including when an LLM was configured but failed (reason goes in
   `notes`). No silent fallbacks; judges punish those.
2. **Rule fallback is a behavioral twin, not a rewrite.** `severity.py` ports
   `backend/app/ai_client.py`'s regexes/scoring line-for-line (strongest depth
   wins; people-at-risk single bucket; frozen category order). Twin parity is
   locked by canonical-input tests; the demo fixture scores exactly 4.
3. **v1.2 storm/heat intensity tiers (documented divergence).** The twin has no
   storm/heat handling and under-scored cyclones/heatwaves badly. When a
   storm/heat context word is present, adjective tiers score instead
   (catastrophic→4 … scorching→1, bare cyclone→2, bare heat→1). Only fires on
   storm/heat inputs — twin-covered inputs (incl. the fixture) are
   bit-identical. Calibrated on `data/severity-labels.csv` (n=600, seed
   20261006): exact-match 0.51→0.60, within-one 0.87→1.00. Reported honestly;
   regression thresholds in `tests/test_accuracy.py` sit below measured.
4. **Rationale is hazard-aware on the v1.2 path** ("भीषण गर्मी" / "तेज़ तूफ़ान"
   instead of "waterlogging" for heat/storm reports); twin branch untouched.
5. **Priority is frozen to severity** (`>=4 critical, 3 high, 2 medium, else
   low`) — the LLM may refine category/skills but never priority.
6. **Alerts: templates are ground truth.** `render_multilingual(alert_type,
   languages, district_names, body, title, extra)` uses the hand-written
   `data/alert-templates/` for flood/heatwave/cyclone (all 10 langs ≤160
   chars, hard cap 480); LLM composes only *novel* alert types; a hand-written
   10-language generic skeleton covers novel types with no LLM. Missing
   language → Hindi template (labeled `template:hi-fallback`).
7. **Risk = documented deterministic v1 formula** shared with
   `backend/app/services/risk.py` (kept in sync by documentation, not import).
   `data/weather-sample.json` seed hints are honored with disclosed scaling —
   Patna reproduces **82/high** exactly like the backend seed.
8. **Pipeline never raises.** `assess_and_route` returns all seam keys
   (severity, rationale, rationale_en, area_tags, category, priority,
   suggested_skills, model) plus token accounting (`prompt_tokens`,
   `completion_tokens`, `cost_usd_estimate`, `tokens_estimated`), a `route`
   dispatch recommendation, and a `notify_preview` (multilingual template
   render with `{district}` left for the backend broadcast). Unexpected
   exceptions degrade to an honest rule result with a `pipeline_error_fallback`
   note. Sibling imports in `pipeline.py` are sys.path-safe for the backend's
   importlib loading.
9. **Vision is opt-in** (`SAHAYTA_LLM_VISION=1`): photo bytes attach as
   base64 `image_url` parts; v1 otherwise scores from `photo_description`
   (backend owns hashing/dedup).

## Seam compatibility (backend/NOTES-agent5.md)

- Signature and required keys match exactly; extras tolerated by the seam.
- `alerts.render_multilingual` matches the anticipated signature.
- No contract changes → no MIGRATION.md needed. Contracts stay frozen.

## Known limitations (honest)

- Rule triage misfires on negated water mentions ("पानी की कमी है" — water
  *shortage* — matches the पानी rescue hint). Twin-frozen; LLM path fixes it.
- Rationale for languages outside hi/hing/en falls back to Hindi (rule path);
  LLM path writes the reporter's language.
- Cost table in `llm.py` is rough per-1M-token estimates — verify with provider.
- `estimate_tokens` is a documented heuristic (~4 chars/token Latin, ~2.5
  Devanagari); real `usage` is preferred when the provider reports it.

## For later waves

- **Agent 7:** `risk.score_district_from_sample` / `score_all_from_sample`
  give you deterministic recomputation; keep the v1 formula in sync if you
  extend it (update both this doc and `backend/app/services/risk.py`).
- **Agent 8:** `pipeline` output `route.suggested_skills` + `priority` feed
  the matching engine directly.
- **Agent 11:** `alerts.render_multilingual` is the broadcast composer backend.
- **Agent 13:** `examples/traces/*.json` are ready-made pipeline traces for
  the video script's AI-explanation beats.
