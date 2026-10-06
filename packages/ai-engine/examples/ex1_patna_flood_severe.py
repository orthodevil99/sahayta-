"""Worked example 1/3 — Patna monsoon flood (severe).

The canonical demo-scenario input, run end-to-end through
``pipeline.assess_and_route`` on the deterministic rule path.
Expected: severity 4, category rescue, priority critical,
skills [rescue, driving], one-line Hindi rationale.

Usage:  python3 ex1_patna_flood_severe.py
Writes: traces/ex1_patna_flood_severe.json
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
    os.environ.pop(var, None)  # deterministic rule path for the worked example

from pipeline import assess_and_route  # noqa: E402

DESCRIPTION = (
    "पटना के कंकड़बाग इलाके में घुटनों तक पानी भर गया है। "
    "दो गलियों में घरों में पानी घुस गया है, बुजुर्ग छत पर हैं। "
    "तुरंत मदद चाहिए।"
)
LAT, LON = 25.5941, 85.1376  # Kankarbagh, Patna


def main() -> dict:
    # Mirrors backend/tests/test_sos.py::test_assess_endpoint_demo_fixture_scores_4:
    # the guarded contract posts the Hindi description with NO photo_description.
    result = assess_and_route(
        description=DESCRIPTION,
        language="hi",
        lat=LAT,
        lon=LON,
        photo_description=None,
        photo_path=None,
    )
    # Acceptance assertions (demo-scenario Act 2, exact).
    assert result["severity"] == 4, result
    assert result["category"] == "rescue", result
    assert result["priority"] == "critical", result
    assert result["suggested_skills"] == ["rescue", "driving"], result
    assert result["area_tags"] == ["road_submerged", "residential"], result
    assert "\n" not in result["rationale"], result
    assert result["model"] == "rule-fallback-v1", result

    out = _HERE / "traces" / "ex1_patna_flood_severe.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("== Ex1: Patna monsoon flood (severe) ==")
    print(f"severity      : {result['severity']}/5")
    print(f"rationale     : {result['rationale']}")
    print(f"rationale_en  : {result['rationale_en']}")
    print(f"category      : {result['category']} | priority: {result['priority']}")
    print(f"skills        : {', '.join(result['suggested_skills'])}")
    print(f"area_tags     : {', '.join(result['area_tags'])}")
    print(f"route channel : {result['route']['recommended_channel']}")
    print(f"alert preview : {result['notify_preview']['messages']['hi'][:110]}...")
    print(f"model         : {result['model']} | latency {result['latency_ms']}ms | "
          f"cost ${result['cost_usd_estimate']}")
    print(f"trace written : {out}")
    return result


if __name__ == "__main__":
    main()
