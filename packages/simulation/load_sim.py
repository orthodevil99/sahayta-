"""Sahayta load simulator — replays synthetic scenarios against the real backend.

Boot: fresh-seeds the backend DB and starts uvicorn on localhost (unless
--no-boot, in which case it drives --base-url as-is).

Workload (defaults): sample 30 scenarios x 6 SOS events = 180 SOS filings
(JSON variant with photo_description), plus match/risk/shelter reads.
Each SOS is filed under a fresh X-Device-Id, simulating distinct citizens —
this is also what keeps the per-device guest rate limit (20 POST /api/sos/hr)
from 429-ing the measurement; the report documents this.

Metrics: total requests, throughput (req/s), p50/p95/max latency, error count,
and triage accuracy (response severity vs the scenario's expected severity:
exact-match and within-one).

Honest numbers only — this script measures, never invents.

Usage:
    python load_sim.py [--scenarios 30] [--sos-per-scenario 6] [--port 8002]
    python load_sim.py --no-boot --base-url http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sim_common import (  # noqa: E402
    ADMIN_KEY,
    SIM_DIR,
    BackendBoot,
    api_get,
    api_post,
)
from scenario_gen import generate_scenario  # noqa: E402

RESULTS_PATH = SIM_DIR / "load_results.json"


def _pct(data: list[float], q: float) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    k = (len(s) - 1) * q
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def run_load(
    base_url: str, n_scenarios: int = 30, sos_per_scenario: int = 6
) -> dict[str, Any]:
    latencies: list[float] = []
    errors = 0
    sos_requests = 0
    read_requests = 0
    exact = 0
    within_one = 0
    assessed = 0
    t0 = time.time()

    admin_h = {"X-Admin-Key": ADMIN_KEY}
    reader_h = {"X-Device-Id": "load-sim-reader"}

    for i in range(n_scenarios):
        sc = generate_scenario(i * 7 % 2000)  # deterministic spread across hazards
        events = sc["sos_stream"][: sos_per_scenario * 3 : 3]  # even spread
        for ev in events[:sos_per_scenario]:
            device = str(uuid.uuid4())
            headers = {"X-Device-Id": device}
            payload = {
                "description": ev["description"],
                "language": ev["language"] if ev["language"] != "hing" else "hi",
                "lat": ev["lat"],
                "lon": ev["lon"],
                "district_id": ev["district_id"],
                "client_report_id": str(uuid.uuid4()),
                "photo_description": f"synthetic {sc['hazard']} scene",
            }
            start = time.time()
            try:
                status, resp = api_post(base_url, "/api/sos", payload, headers=headers)
            except Exception:
                status, resp = 0, None
            latencies.append((time.time() - start) * 1000.0)
            sos_requests += 1
            if status not in (200, 201) or not isinstance(resp, dict):
                errors += 1
                continue
            got = resp.get("severity")
            if isinstance(got, int):
                assessed += 1
                if got == ev["severity"]:
                    exact += 1
                if abs(got - ev["severity"]) <= 1:
                    within_one += 1

        # read traffic per scenario: match preview, risk, shelters
        for path in [
            f"/api/districts/{sc['district']['id']}/risk",
            f"/api/shelters?district={sc['district']['id']}&limit=5",
            "/api/sos?limit=5&sort=severity",
        ]:
            start = time.time()
            try:
                status, _ = api_get(base_url, path, headers=reader_h, timeout=15.0)
            except Exception:
                status = 0
            latencies.append((time.time() - start) * 1000.0)
            read_requests += 1
            if status != 200:
                errors += 1

    # a few match calls against real SOS ids (admin)
    status, listing = api_get(base_url, "/api/sos?limit=5", headers=admin_h, timeout=15.0)
    if status == 200 and isinstance(listing, dict):
        for item in listing.get("items", [])[:5]:
            start = time.time()
            try:
                st, _ = api_post(
                    base_url, "/api/tasks/match",
                    {"sos_id": item["id"], "max_results": 3}, headers=admin_h, timeout=15.0,
                )
            except Exception:
                st = 0
            latencies.append((time.time() - start) * 1000.0)
            read_requests += 1
            if st != 200:
                errors += 1

    elapsed = time.time() - t0
    total = sos_requests + read_requests
    return {
        "scenarios_replayed": n_scenarios,
        "sos_filed": sos_requests,
        "read_requests": read_requests,
        "total_requests": total,
        "errors": errors,
        "elapsed_s": round(elapsed, 2),
        "throughput_rps": round(total / elapsed, 2) if elapsed else 0.0,
        "latency_ms": {
            "p50": round(_pct(latencies, 0.50), 1),
            "p95": round(_pct(latencies, 0.95), 1),
            "max": round(max(latencies) if latencies else 0.0, 1),
        },
        "triage_accuracy": {
            "assessed": assessed,
            "exact_match": round(exact / assessed, 3) if assessed else 0.0,
            "within_one": round(within_one / assessed, 3) if assessed else 0.0,
            "note": "expected severity = scenario ground truth; backend runs rule-fallback-v1",
        },
        "rate_limit_note": "fresh X-Device-Id per SOS (distinct simulated citizens); "
                           "guest limit is 20 POST /api/sos/hr/device",
        "synthetic": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Sahayta load simulator")
    ap.add_argument("--scenarios", type=int, default=30)
    ap.add_argument("--sos-per-scenario", type=int, default=6)
    ap.add_argument("--port", type=int, default=8002)
    ap.add_argument("--no-boot", action="store_true")
    ap.add_argument("--base-url", default="")
    ap.add_argument("--out", default=str(RESULTS_PATH))
    args = ap.parse_args()

    if args.no_boot:
        base_url = args.base_url or "http://127.0.0.1:8000"
        results = run_load(base_url, args.scenarios, args.sos_per_scenario)
    else:
        with BackendBoot(port=args.port) as base_url:
            results = run_load(base_url, args.scenarios, args.sos_per_scenario)

    Path(args.out).write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(json.dumps(results, indent=1))
    return 0 if results["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
