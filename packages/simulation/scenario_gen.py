"""Deterministic disaster scenario generator for Sahayta.

Produces 2,000 full scenarios: flood / heatwave / cyclone x 20 districts x
severity timelines x cascading SOS streams. Every scenario regenerates
bit-identically from its (index, seed) — the repo stores the compact index
(``scenarios/index.json``) plus a 50-scenario materialized sample
(``scenarios/sample/``); the generator rebuilds any scenario on demand.

Usage:
    python scenario_gen.py --all            # write index + 50 samples
    python scenario_gen.py --scenario flood-patna-0013   # print one as JSON
    python scenario_gen.py --count          # verify 2000 entries exist

Determinism: ``random.Random(BASE_SEED + index)`` per scenario; no wall-clock,
no hash-randomization dependence (all iteration is over sorted structures).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sim_common import SIM_DIR, load_districts  # noqa: E402

HAZARDS = ["flood", "heatwave", "cyclone"]
N_SCENARIOS = 2000
BASE_SEED = 20261009
WINDOW_HOURS = 72
SAMPLE_COUNT = 50

SCENARIO_DIR = SIM_DIR / "scenarios"
SAMPLE_DIR = SCENARIO_DIR / "sample"

# ---------------------------------------------------------------------------
# Text pools — {area} is filled with a locality name. Kept flood-leaning for
# floods; heatwave/cyclone get their own vocabularies. Languages: hi/hing/en.
# ---------------------------------------------------------------------------

AREAS = [
    "Market Road", "Station Road", "Old Town", "Riverbank", "Ward 12",
    "Gandhi Chowk", "Bus Stand", "Civil Lines", "Shastri Nagar", "Lake View",
]

DESC_POOLS: dict[str, dict[str, list[str]]] = {
    "flood": {
        "rescue": [
            "पानी घरों में घुस गया है {area} में, बुजुर्ग छत पर हैं। तुरंत मदद चाहिए।",
            "Waist-deep water in {area}, two families trapped on rooftop. Need rescue boat.",
            "{area} me ghutno tak paani, ghar me paani ghus gaya. Help chahiye urgent.",
            "Flood water rising fast near {area}, elderly residents stuck on first floor.",
            "कमर तक पानी {area} में, बच्चे फंसे हैं। नाव चाहिए।",
        ],
        "food": [
            "{area} में बाढ़ से राशन खत्म, 40 परिवारों को खाना चाहिए।",
            "Food supplies washed away in {area}, need dry rations for 3 days.",
            "Bाढ़ ke kaaran {area} me khana khatm, langar chahiye.",
        ],
        "shelter": [
            "{area} के 25 परिवारों को राहत शिविर चाहिए, घरों में पानी भरा है।",
            "25 families in {area} need shelter, homes submerged.",
        ],
        "medical": [
            "{area} में बाढ़ के पानी से बुखार फैल रहा है, दवा चाहिए।",
            "Water-borne fever spreading in {area} relief camp, need medicines.",
        ],
        "infrastructure": [
            "{area} में सड़क धंस गई है, बिजली के खंभे गिरे हैं।",
            "Road caved in at {area}, power lines down after flooding.",
        ],
    },
    "heatwave": {
        "medical": [
            "{area} में लू से 6 लोग बेहोश, ORS और डॉक्टर चाहिए।",
            "Heatstroke cases in {area}, 6 collapsed near market. Need ORS and doctor.",
            "{area} me loo lagne se 3 bujurg behosh, turant medical help chahiye.",
            "Severe dehydration reported in {area}, need water tankers and shade tents.",
        ],
        "food": [
            "{area} में पानी की किल्लत, टैंकर चाहिए।",
            "Drinking water shortage in {area}, need tanker supply.",
        ],
        "shelter": [
            "{area} में cooling centre खोलने की मांग, तापमान 46 डिग्री।",
            "Demand for cooling centre in {area}, temperature 46C.",
        ],
        "infrastructure": [
            "{area} में transformer फेल, 8 घंटे से बिजली गुल।",
            "Transformer failure in {area}, 8-hour power outage in heatwave.",
        ],
    },
    "cyclone": {
        "rescue": [
            "तूफान में {area} में पेड़ गिरा, 2 लोग दबे हैं।",
            "Cyclone uprooted tree in {area}, 2 people trapped underneath.",
            "Toofan me {area} me chhat ud gayi, parivar khule me hai.",
        ],
        "shelter": [
            "{area} के 60 परिवारों के घरों की छतें उड़ गईं, शिविर चाहिए।",
            "Roofs blown off in {area}, 60 families need emergency shelter.",
        ],
        "medical": [
            "{area} में तूफान के बाद घायल 4 लोग, first aid चाहिए।",
            "4 injured in {area} after cyclone landfall, need first aid.",
        ],
        "infrastructure": [
            "{area} में बिजली के तार टूटे, सड़क पर पेड़ गिरे हैं।",
            "Power lines snapped across {area}, roads blocked by fallen trees.",
        ],
        "food": [
            "{area} में तूफान से दुकानें बंद, खाने का सामान चाहिए।",
            "Shops shut in {area} after cyclone, need food packets.",
        ],
    },
}

LANG_BY_TEMPLATE = ["hi", "en", "hing", "hi", "en"]

CATEGORY_WEIGHTS: dict[str, dict[str, float]] = {
    "flood": {"rescue": 0.35, "food": 0.2, "shelter": 0.2, "medical": 0.15, "infrastructure": 0.1},
    "heatwave": {"medical": 0.5, "food": 0.25, "shelter": 0.15, "infrastructure": 0.1},
    "cyclone": {"rescue": 0.25, "shelter": 0.3, "medical": 0.15, "infrastructure": 0.2, "food": 0.1},
}


def _pick_weighted(rng: random.Random, weights: dict[str, float]) -> str:
    total = sum(weights.values())
    roll = rng.random() * total
    acc = 0.0
    for key in sorted(weights):
        acc += weights[key]
        if roll <= acc:
            return key
    return sorted(weights)[-1]


def _timeline(rng: random.Random, hazard: str) -> tuple[list[int], int, int]:
    """72 hourly severities 1-5 shaped per hazard. Returns (timeline, peak_hour, peak)."""
    hours = list(range(WINDOW_HOURS))
    if hazard == "flood":
        base, peak_h, peak_v, width = 1.6, rng.randint(38, 56), rng.randint(3, 5), rng.uniform(9, 14)
    elif hazard == "heatwave":
        base, peak_h, peak_v, width = 2.0, rng.randint(30, 50), rng.randint(3, 4), rng.uniform(16, 24)
    else:  # cyclone: sharp spike
        base, peak_h, peak_v, width = 1.4, rng.randint(34, 48), rng.randint(4, 5), rng.uniform(5, 8)
    tl: list[int] = []
    for h in hours:
        bump = (peak_v - base) * math.exp(-((h - peak_h) ** 2) / (2 * width * width))
        noise = rng.uniform(-0.5, 0.5)
        tl.append(max(1, min(5, round(base + bump + noise))))
    peak = max(tl)
    peak_hour = tl.index(peak)
    return tl, peak_hour, peak


def _sos_stream(
    rng: random.Random, hazard: str, district: dict[str, Any], timeline: list[int]
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    weights = CATEGORY_WEIGHTS[hazard]
    for hour, sev in enumerate(timeline):
        lam = 0.25 + (sev ** 2) * 0.22  # expected events this hour
        count = 0
        # Poisson-ish draw via Knuth, capped for sanity
        l, p, k = math.exp(-lam), 1.0, 0
        while p > l and k < 12:
            k += 1
            p *= rng.random()
        count = max(0, k - 1)
        for _ in range(count):
            category = _pick_weighted(rng, weights)
            pool = DESC_POOLS[hazard][category]
            template = rng.choice(pool)
            lang = LANG_BY_TEMPLATE[pool.index(template) % len(LANG_BY_TEMPLATE)]
            area = rng.choice(AREAS)
            ev_sev = max(1, min(5, sev + rng.randint(-1, 1)))
            events.append(
                {
                    "t_hour": hour,
                    "severity": ev_sev,
                    "category": category,
                    "language": lang,
                    "description": template.format(area=f"{area}, {district['name']}"),
                    "lat": round(district["lat"] + rng.gauss(0, 0.045), 5),
                    "lon": round(district["lon"] + rng.gauss(0, 0.045), 5),
                    "district_id": district["id"],
                }
            )
    events.sort(key=lambda e: (e["t_hour"], e["severity"]))
    return events


def scenario_id_for(index: int, hazard: str, district_id: str) -> str:
    return f"{hazard}-{district_id}-{index:04d}"


def generate_scenario(index: int) -> dict[str, Any]:
    """Deterministically build scenario ``index`` (0-based, < 2000)."""
    if not 0 <= index < N_SCENARIOS:
        raise ValueError(f"index out of range: {index}")
    districts = sorted(load_districts(), key=lambda d: d["id"])
    hazard = HAZARDS[index % 3]
    district = districts[(index // 3) % len(districts)]
    rng = random.Random(BASE_SEED + index)
    timeline, peak_hour, peak = _timeline(rng, hazard)
    stream = _sos_stream(rng, hazard, district, timeline)
    return {
        "scenario_id": scenario_id_for(index, hazard, district["id"]),
        "index": index,
        "hazard": hazard,
        "district": {
            "id": district["id"], "name": district["name"],
            "state": district["state"], "lat": district["lat"], "lon": district["lon"],
        },
        "seed": BASE_SEED + index,
        "window_hours": WINDOW_HOURS,
        "peak_hour": peak_hour,
        "peak_severity": peak,
        "timeline": timeline,
        "sos_stream": stream,
        "sos_count": len(stream),
        "synthetic": True,
    }


def scenario_index_entry(index: int) -> dict[str, Any]:
    districts = sorted(load_districts(), key=lambda d: d["id"])
    hazard = HAZARDS[index % 3]
    district = districts[(index // 3) % len(districts)]
    rng = random.Random(BASE_SEED + index)
    timeline, peak_hour, peak = _timeline(rng, hazard)
    # sos count without materializing descriptions: replicate the count draws
    stream = _sos_stream(rng, hazard, district, timeline)
    return {
        "scenario_id": scenario_id_for(index, hazard, district["id"]),
        "index": index,
        "hazard": hazard,
        "district_id": district["id"],
        "seed": BASE_SEED + index,
        "peak_hour": peak_hour,
        "peak_severity": peak,
        "sos_count": len(stream),
    }


def write_all(sample_count: int = SAMPLE_COUNT) -> None:
    SCENARIO_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[gen] building index of {N_SCENARIOS} scenarios ...", flush=True)
    index = [scenario_index_entry(i) for i in range(N_SCENARIOS)]
    (SCENARIO_DIR / "index.json").write_text(
        json.dumps({"generated": "synthetic", "count": len(index), "scenarios": index},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"[gen] materializing {sample_count} sample scenarios ...", flush=True)
    for i in range(sample_count):
        sc = generate_scenario(i)
        (SAMPLE_DIR / f"{sc['scenario_id']}.json").write_text(
            json.dumps(sc, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    # coverage sanity
    hazards = {e["hazard"] for e in index}
    districts = {e["district_id"] for e in index}
    print(f"[gen] done. hazards={sorted(hazards)} districts={len(districts)} "
          f"total_sos={sum(e['sos_count'] for e in index)}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Sahayta scenario generator")
    ap.add_argument("--all", action="store_true", help="write index + samples")
    ap.add_argument("--count", action="store_true", help="verify index has 2000 entries")
    ap.add_argument("--scenario", help="print one scenario as JSON (by id or index)")
    args = ap.parse_args()
    if args.all:
        write_all()
        return 0
    if args.count:
        idx = json.loads((SCENARIO_DIR / "index.json").read_text(encoding="utf-8"))
        print(f"index entries: {idx['count']}")
        return 0 if idx["count"] == N_SCENARIOS else 1
    if args.scenario:
        districts = sorted(load_districts(), key=lambda d: d["id"])
        try:
            index = int(args.scenario)
        except ValueError:
            index = next(
                (e["index"] for e in
                 json.loads((SCENARIO_DIR / "index.json").read_text(encoding="utf-8"))["scenarios"]
                 if e["scenario_id"] == args.scenario),
                None,
            )
            if index is None:
                print(f"unknown scenario: {args.scenario}", file=sys.stderr)
                return 1
        print(json.dumps(generate_scenario(index), ensure_ascii=False, indent=1))
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
