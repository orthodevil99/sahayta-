"""Tests for the demo director: structure + graceful failure (no live server)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from demo_director import STEPS, run_director  # noqa: E402
from sim_common import (  # noqa: E402
    devanagari_present,
    encode_multipart,
    latin_present,
)


def test_fourteen_steps_defined():
    assert len(STEPS) == 14, f"expected 14 steps, got {len(STEPS)}"
    names = [n for n, _ in STEPS]
    assert len(set(names)) == 14, "step names must be unique"


def test_expected_step_names_present():
    names = {n for n, _ in STEPS}
    for expected in ("sos_filed", "severity_assessed", "volunteer_matched",
                     "task_dispatched", "task_completed", "broadcast_sent",
                     "district_risk", "forecast_72h"):
        assert expected in names


def test_script_helpers():
    assert devanagari_present("बाढ़ चेतावनी")
    assert not devanagari_present("flood warning")
    assert latin_present("Flood warning")
    assert not latin_present("बाढ़")
    body, ctype = encode_multipart({"a": "1"}, {"f": ("x.jpg", "image/jpeg", b"data")})
    assert b'name="a"' in body and b'filename="x.jpg"' in body
    assert "multipart/form-data" in ctype


def test_director_fails_gracefully_without_server():
    # Nothing listens on port 9; every step must FAIL (not raise), quickly.
    results = run_director("http://127.0.0.1:9")
    assert len(results) == 14
    assert all(not r.passed for r in results), "all steps should fail with no server"
    assert all(r.detail for r in results), "each failure should carry a reason"
