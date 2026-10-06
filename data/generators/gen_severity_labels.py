"""Generate data/severity-labels.csv — 5,000 photo-description -> severity + rationale
pairs for training/evaluating the severity estimator.

ALL OUTPUT IS SYNTHETIC DEMO DATA.
"""
import csv

from common import (
    DATA_DIR, LOCALITIES, PHOTO_TEMPLATES, PLACES, PHOTO_DETAILS,
    SEVERITY_RATIONALES, load_districts, make_rng,
)

N_ROWS = 5000
SEVERITY_WEIGHTS = {1: 0.28, 2: 0.30, 3: 0.22, 4: 0.13, 5: 0.07}
DTYPES = ["flood", "flood", "flood", "heatwave", "cyclone"]  # flood-heavy, like the event

def weighted(rng, weights):
    total = sum(weights.values())
    r = rng.random() * total
    upto = 0.0
    for k, w in weights.items():
        upto += w
        if r <= upto:
            return k
    return list(weights)[-1]

def render(rng, dtype, severity):
    pool = PHOTO_TEMPLATES[dtype][severity]
    district = rng.choice(load_districts())
    locality = rng.choice(LOCALITIES[district["id"]])
    return rng.choice(pool).format(place=rng.choice(PLACES),
                                   locality=locality,
                                   detail=rng.choice(PHOTO_DETAILS))

def main():
    rng = make_rng("severity-labels")
    districts = load_districts()
    rows = []
    seen = set()
    i = 0
    # fixture-support rows: knee/waist-deep residential water -> severity 4
    fixture_templates = [
        "Waist-deep water across a residential lane in {locality}; residents on rooftops; water entering homes.",
        "Knee-to-waist deep floodwater in {locality}; elderly residents waiting on rooftops for rescue.",
        "Waist-deep brown water submerging homes in {locality}; families stranded on rooftops.",
    ]
    for t in range(40):
        desc = fixture_templates[t % len(fixture_templates)].format(
            locality=rng.choice(LOCALITIES[rng.choice(districts)["id"]]))
        rows.append({"id": f"sevlab-{i:05d}", "photo_description": desc,
                     "severity": 4,
                     "rationale": rng.choice(SEVERITY_RATIONALES[4]),
                     "disaster_type": "flood"})
        seen.add(desc)
        i += 1
    while len(rows) < N_ROWS:
        severity = weighted(rng, SEVERITY_WEIGHTS)
        dtype = rng.choice(DTYPES)
        desc = render(rng, dtype, severity)
        if desc in seen:  # keep the set diverse
            continue
        seen.add(desc)
        rows.append({"id": f"sevlab-{i:05d}", "photo_description": desc,
                     "severity": severity,
                     "rationale": rng.choice(SEVERITY_RATIONALES[severity]),
                     "disaster_type": dtype})
        i += 1
    path = DATA_DIR / "severity-labels.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "photo_description", "severity",
                                          "rationale", "disaster_type"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {path} ({len(rows)} rows)")

if __name__ == "__main__":
    main()
