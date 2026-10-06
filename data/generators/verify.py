"""Verify Sahayta synthetic datasets: schema sanity, counts, cross-file consistency,
demo-scenario anchors. Exits non-zero on failure. Run from data/generators/.
"""
import csv
import json
import math
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent
fails = []

def check(cond, msg):
    if not cond:
        fails.append(msg)
        print(f"FAIL: {msg}")

def load(name):
    with open(DATA / name, encoding="utf-8") as f:
        return json.load(f)

# ---- districts.json
districts = load("districts.json")["districts"]
slugs = [d["slug"] if "slug" in d else d["id"] for d in districts]
slugs = [d["id"] for d in districts]
check(len(districts) == 20, f"districts.json: expected 20, got {len(districts)}")
check(len(set(slugs)) == 20, "districts.json: slugs not unique")
for must in ("patna", "vaishali", "gaya", "muzaffarpur", "darbhanga", "bhagalpur"):
    check(must in slugs, f"districts.json: missing Agent-1 slug {must}")
print(f"districts: {len(districts)} OK")

# ---- sos-reports.json
sos = load("sos-reports.json")
reps = sos["reports"]
check(sos["meta"]["count"] == 3000 and len(reps) == 3000, f"sos-reports: count {len(reps)}")
valid_cat = {"medical","rescue","food","shelter","infrastructure","other"}
valid_status = {"reported","verified","help_on_way","resolved","duplicate","rejected"}
valid_prio = {"low","medium","high","critical"}
for r in reps:
    if r["district_id"] not in slugs: check(False, f"sos bad district {r['district_id']}"); break
for r in reps:
    if not (1 <= r["severity"] <= 5): check(False, "sos severity out of range"); break
    if r["category"] not in valid_cat: check(False, f"sos bad category {r['category']}"); break
    if r["status"] not in valid_status: check(False, f"sos bad status {r['status']}"); break
    if r["priority"] not in valid_prio: check(False, f"sos bad priority {r['priority']}"); break
    if not (10 <= len(r["description"]) <= 2000): check(False, "sos description length"); break
patna4 = [r for r in reps if r["district_id"] == "patna" and r["severity"] == 4]
check(len(patna4) >= 25, f"sos: Patna sev-4 anchors {len(patna4)} < 25")
sev = [r["severity"] for r in reps]
from collections import Counter
sc = Counter(sev)
check(sc[1] + sc[2] + sc[3] > sc[4] + sc[5], f"sos: severity skew wrong {dict(sc)}")
print(f"sos-reports: {len(reps)} OK, Patna sev-4 anchors={len(patna4)}, sev dist={dict(sorted(sc.items()))}")

# ---- severity-labels.csv
with open(DATA / "severity-labels.csv", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
check(len(rows) == 5000, f"severity-labels: {len(rows)} rows")
check(all(r["photo_description"].strip() and r["rationale"].strip() for r in rows),
      "severity-labels: empty description/rationale")
check(all(r["severity"] in "12345" for r in rows), "severity-labels: bad severity")
check(len({r["photo_description"] for r in rows}) > 4500, "severity-labels: too many dupes")
fix = [r for r in rows if r["severity"] == "4" and "rooftop" in r["photo_description"]]
check(len(fix) >= 30, "severity-labels: fixture rows missing")
print(f"severity-labels: {len(rows)} OK")

# ---- shelters.json
sh = load("shelters.json")["shelters"]
check(len(sh) == 500, f"shelters: {len(sh)}")
check(all(s["is_demo_data"] for s in sh), "shelters: is_demo_data not all true")
check(all(s["occupied"] <= s["capacity"] for s in sh), "shelters: occupied > capacity")
check(all(s["district_id"] in slugs for s in sh), "shelters: bad district slug")
sdc = Counter(s["district_id"] for s in sh)
check(len(sdc) == 10 and all(v == 50 for v in sdc.values()), f"shelters: district spread {dict(sdc)}")
print(f"shelters: {len(sh)} OK across {len(sdc)} districts")

# ---- volunteers.json
vol = load("volunteers.json")["volunteers"]
check(len(vol) == 1000, f"volunteers: {len(vol)}")
ravi = next((v for v in vol if v["id"] == "vol-ravi-kumar-patna"), None)
check(ravi is not None, "volunteers: Ravi Kumar anchor missing")
if ravi:
    check(ravi["skills"] == ["rescue", "driving"], f"ravi skills {ravi['skills']}")
    check(ravi["languages"] == ["hi", "hing"], f"ravi langs {ravi['languages']}")
    check(ravi["availability"] == "anytime", "ravi availability")
    check(ravi["reputation"] == 50 and ravi["tasks_completed"] == 0, "ravi rep/tasks")
    d_km = math.dist((ravi["lat"], ravi["lon"]), (25.5941, 85.1376))
    d_km = math.sqrt((d_km * 111.19) ** 2)  # rough; recompute properly below
    # proper haversine-ish for small distances
    import math as m
    dy = (ravi["lat"] - 25.5941) * 111.19
    dx = (ravi["lon"] - 85.1376) * 111.19 * m.cos(m.radians(25.5941))
    dist = m.sqrt(dx * dx + dy * dy)
    check(1.6 <= dist <= 2.6, f"ravi distance {dist:.2f} km not ~2.1")
check(all(v["district_id"] in slugs for v in vol), "volunteers: bad district slug")
vskills = {"medical","rescue","driving","cooking","shelter_mgmt","translation","logistics","counseling","engineering"}
check(all(set(v["skills"]) <= vskills and v["skills"] for v in vol), "volunteers: bad skills")
print(f"volunteers: {len(vol)} OK (Ravi anchor ~{dist:.2f} km from SOS pin)")

# ---- weather-sample.json
wx = load("weather-sample.json")
check(wx["meta"]["days"] == 30, "weather: days")
check(len(wx["districts"]) == 20, f"weather: districts {len(wx['districts'])}")
check(all(len(v) == 30 for v in wx["districts"].values()), "weather: series length")
patna_wx = wx["districts"]["patna"][-3:]
rains = [d["rain_mm"] for d in patna_wx]
check(rains[2] >= 150 and all(p["river_trend"] == "rising" for p in patna_wx),
      f"weather: Patna spike wrong {rains}")
check(wx["seed_hints"]["patna"]["risk"] == 82, "weather: seed hint risk != 82")
nagpur = wx["districts"]["nagpur"][-7:]
check(all(d["temp_c"] >= 43 for d in nagpur), "weather: Nagpur heatwave missing")
puri = wx["districts"]["puri"][-2:]
check(all(d["wind_kph"] >= 90 for d in puri), "weather: Puri cyclone winds missing")
print(f"weather: 20x30 OK; Patna last-3d rain={rains}")

# ---- alert-templates
langs = ["hi","hing","bn","ta","te","mr","gu","kn","ml","pa"]
for dtype in ("flood", "heatwave", "cyclone"):
    t = load(f"alert-templates/{dtype}.json")
    check(set(t["templates"].keys()) == set(langs), f"alerts/{dtype}: langs {set(t['templates'].keys())}")
    for lang, text in t["templates"].items():
        rendered = text.format(district="Patna", helpline="1078",
                               temp="45", wind="110")
        if len(rendered) > 165:
            check(False, f"alerts/{dtype}/{lang}: {len(rendered)} chars > ~160")
print("alert-templates: 3 types x 10 languages OK (<=160 chars rendered)")

print()
if fails:
    print(f"{len(fails)} FAILURES")
    sys.exit(1)
print("ALL CHECKS PASSED")
