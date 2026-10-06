"""Worked example 3/3 — Puri cyclone landfall (critical).

Storm intensity tier (भयंकर -> tier 3) + people trapped (+1) + urgent (+1)
caps at severity 5. Trapped-people wording routes to rescue triage even
without flood keywords, and area tags capture power + wind damage.

Usage:  python3 ex3_puri_cyclone_critical.py
Writes: traces/ex3_puri_cyclone_critical.json
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
    "पुरी में भयंकर चक्रवात टकराया है: 110 किमी/घंटा की हवाएं, "
    "बिजली के तार टूट गए हैं, पेड़ गिर गए हैं, घरों की छतें उड़ गई हैं। "
    "कई लोग मलबे में फंसे हैं। तुरंत मदद चाहिए।"
)
LAT, LON = 19.8135, 85.8312  # Puri


def main() -> dict:
    result = assess_and_route(
        description=DESCRIPTION,
        language="hi",
        lat=LAT,
        lon=LON,
        photo_description="Uprooted trees and fallen power lines; houses with roofs torn off.",
        photo_path=None,
    )
    assert result["severity"] == 5, result
    assert result["priority"] == "critical", result
    assert result["category"] == "rescue", result  # trapped people -> rescue
    assert "power_outage" in result["area_tags"], result
    assert "wind_damage" in result["area_tags"], result
    assert result["route"]["recommended_channel"] == "sms+app+ivrs", result
    assert result["model"] == "rule-fallback-v1", result

    out = _HERE / "traces" / "ex3_puri_cyclone_critical.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("== Ex3: Puri cyclone landfall (critical) ==")
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
