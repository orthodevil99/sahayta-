"""Fixture accuracy test: rule path vs data/severity-labels.csv.

Honest, deterministic (seeded sample). Thresholds sit below the measured
values (exact 0.602, within-one 1.000 on seed 20261006, n=600) so the test
is a regression guard, not a tautology. If rules are retuned, update the
measured numbers in this docstring and in severity.py together.
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

from severity import rule_assess

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
LABELS_CSV = REPO_ROOT / "data" / "severity-labels.csv"
SAMPLE_N = 600
SAMPLE_SEED = 20261006


def _sample():
    rows = list(csv.DictReader(LABELS_CSV.open(encoding="utf-8")))
    rng = random.Random(SAMPLE_SEED)
    return rng.sample(rows, SAMPLE_N)


def test_label_accuracy_regression():
    exact = within1 = 0
    for row in _sample():
        pred = rule_assess("", "en", row["photo_description"]).severity
        true = int(row["severity"])
        exact += pred == true
        within1 += abs(pred - true) <= 1
    exact_rate, within1_rate = exact / SAMPLE_N, within1 / SAMPLE_N
    print(f"\nseverity-labels accuracy: exact={exact_rate:.3f} "
          f"within-one={within1_rate:.3f} (n={SAMPLE_N})")
    assert exact_rate >= 0.55, f"exact-match regressed: {exact_rate:.3f}"
    assert within1_rate >= 0.95, f"within-one regressed: {within1_rate:.3f}"


def test_demo_fixture_semantic_anchors():
    """Rows mirroring the demo fixture semantics
    (knee-deep + elderly + rooftops) must all score 4."""
    hits = 0
    for row in csv.DictReader(LABELS_CSV.open(encoding="utf-8")):
        desc = row["photo_description"].lower()
        if "knee" in desc and "rooftop" in desc and "elderly" in desc:
            hits += 1
            pred = rule_assess("", "en", row["photo_description"]).severity
            assert pred == 4, f"anchor mis-scored: {row['photo_description'][:80]}"
    assert hits >= 5, f"expected several fixture anchors, found {hits}"
