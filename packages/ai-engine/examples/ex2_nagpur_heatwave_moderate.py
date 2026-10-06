"""Worked example 2/3 — Nagpur heatwave (moderate).

A non-flood disaster on the rule path: heat context with no intensifier and
no casualties scores severity 2 (medium). Shows the engine is not a
flood-only scorer.

Usage:  python3 ex2_nagpur_heatwave_moderate.py
Writes: traces/ex2_nagpur_heatwave_moderate.json
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PKG = _HERE.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))
for var in ("SAHAYTA_LLM_BASE_URL", "SAHAYTA_LLM_MODEL", "SAHAYTA_LLM_API_KEY"):
    os.environ.pop(var, None)

from pipeline import assess_and_route  # noqa: E402

DESCRIPTION = (
    "नागपुर के सीताबर्डी इलाके में तेज़ गर्मी पड़ रही है, तापमान 43 डिग्री। "
    "बाज़ार में लोग परेशान हैं, छाया की तलाश में हैं।"
)
LAT, LON = 21.1458, 79.0882  # Nagpur


def main() -> dict:
    result = assess_and_route(
        description=DESCRIPTION,
        language="hi",
        lat=LAT,
        lon=LON,
        photo_description="Harsh midday sun over a market street; vendors shading stalls.",
        photo_path=None,
    )
    assert result["severity"] == 2, result
    assert result["priority"] == "medium", result
    assert result["category"] == "medical", result  # heat -> medical triage
    assert "heat_affected" in result["area_tags"], result
    assert result["model"] == "rule-fallback-v1", result

    out = _HERE / "traces" / "ex2_nagpur_heatwave_moderate.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("== Ex2: Nagpur heatwave (moderate) ==")
    print(f"severity      : {result['severity']}/5")
    print(f"rationale     : {result['rationale']}")
    print(f"rationale_en  : {result['rationale_en']}")
    print(f"category      : {result['category']} | priority: {result['priority']}")
    print(f"skills        : {', '.join(result['suggested_skills'])}")
    print(f"area_tags     : {', '.join(result['area_tags'])}")
    print(f"route channel : {result['route']['recommended_channel']}")
    print(f"alert preview : {result['notify_preview']['messages']['hi'][:110]}...")
    print(f"model         : {result['model']} | latency {result['latency_ms']}ms")
    print(f"trace written : {out}")
    return result


if __name__ == "__main__":
    main()
