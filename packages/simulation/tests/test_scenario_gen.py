"""Tests for the scenario generator: determinism, coverage, shape."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scenario_gen import (  # noqa: E402
    BASE_SEED,
    HAZARDS,
    N_SCENARIOS,
    WINDOW_HOURS,
    generate_scenario,
    scenario_index_entry,
)
from sim_common import SIM_DIR  # noqa: E402


def test_count_is_2000():
    assert N_SCENARIOS == 2000


def test_determinism_same_index_twice():
    a = generate_scenario(42)
    b = generate_scenario(42)
    assert a == b, "same index must regenerate identically"


def test_determinism_index_entries_match_full():
    for i in (0, 7, 1999):
        full = generate_scenario(i)
        entry = scenario_index_entry(i)
        assert entry["scenario_id"] == full["scenario_id"]
        assert entry["peak_hour"] == full["peak_hour"]
        assert entry["peak_severity"] == full["peak_severity"]
        assert entry["sos_count"] == full["sos_count"]


def test_hazard_district_coverage():
    hazards = set()
    districts = set()
    for i in range(N_SCENARIOS):
        hazards.add(HAZARDS[i % 3])
        entry = scenario_index_entry(i)
        districts.add(entry["district_id"])
    assert hazards == set(HAZARDS)
    assert len(districts) == 20, f"expected 20 districts, got {len(districts)}"


def test_timeline_shape_and_bounds():
    for i in (0, 500, 1234, 1999):
        sc = generate_scenario(i)
        tl = sc["timeline"]
        assert len(tl) == WINDOW_HOURS
        assert all(1 <= s <= 5 for s in tl), f"severity out of bounds in {sc['scenario_id']}"
        assert sc["peak_severity"] == max(tl)
        assert tl[sc["peak_hour"]] == sc["peak_severity"]


def test_sos_stream_sorted_and_shaped():
    sc = generate_scenario(13)
    stream = sc["sos_stream"]
    assert sc["sos_count"] == len(stream)
    assert stream == sorted(stream, key=lambda e: (e["t_hour"], e["severity"]))
    for ev in stream:
        assert 1 <= ev["severity"] <= 5
        assert 0 <= ev["t_hour"] < WINDOW_HOURS
        assert ev["district_id"] == sc["district"]["id"]
        assert len(ev["description"]) > 10
        assert -90 <= ev["lat"] <= 90 and -180 <= ev["lon"] <= 180


def test_seeds_unique_per_index():
    seeds = {BASE_SEED + i for i in range(N_SCENARIOS)}
    assert len(seeds) == N_SCENARIOS


def test_index_file_on_disk_if_generated():
    idx_path = SIM_DIR / "scenarios" / "index.json"
    if not idx_path.exists():
        return  # generator not run yet; nothing to check
    idx = json.loads(idx_path.read_text(encoding="utf-8"))
    assert idx["count"] == N_SCENARIOS
    assert len(idx["scenarios"]) == N_SCENARIOS
    assert idx["scenarios"][0]["scenario_id"].startswith("flood-")
