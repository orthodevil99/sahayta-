# Sahayta AI Engine

Provider-agnostic disaster-intelligence modules for Sahayta (WarriorHacks 2.0).
Zero runtime dependencies — standard library only.

## Modules

| Module | Does |
|---|---|
| `pipeline.py` | **Backend seam**: `assess_and_route(...)` — assess → triage → route → notify in one call |
| `severity.py` | Photo/description → severity 1–5 + one-line rationale + area tags (LLM + rule fallback) |
| `triage.py` | SOS → category + priority + suggested volunteer skills (LLM + rule fallback) |
| `alerts.py` | One alert → 10-language SMS-length messages (template ground truth + LLM for novel) |
| `risk.py` | Weather series → district risk 0–100 with contributing factors (deterministic) |
| `llm.py` | OpenAI-compatible chat client + token accounting + cost estimates |
| `config.py` | Env-driven config (`SAHAYTA_LLM_BASE_URL`, `SAHAYTA_LLM_MODEL`, …) |

## Honest model labels

Every result reports `model`: `"llm:<model-id>"` when a real model answered,
`"rule-fallback-v1"` when deterministic rules did (including LLM failure —
the reason lands in `notes`).

## Quickstart

```bash
cd packages/ai-engine
python3 -m pytest tests/ -q          # 65 tests
python3 examples/ex1_patna_flood_severe.py      # worked examples + traces
```

```python
import sys; sys.path.insert(0, "packages/ai-engine")
from pipeline import assess_and_route
r = assess_and_route("घुटनों तक पानी; बुजुर्ग छत पर हैं। तुरंत मदद चाहिए।", "hi")
# {'severity': 4, 'category': 'rescue', 'priority': 'critical', ...}
```

Set `SAHAYTA_LLM_BASE_URL` + `SAHAYTA_LLM_MODEL` (e.g. GLM endpoint) to enable
the LLM path; without them the engine runs the deterministic rule fallback.
See `NOTES-agent6.md` for design decisions and known limitations.
