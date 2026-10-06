"""Generate data/volunteers.json — 1,000 synthetic volunteer profiles.

Includes the FIXED demo-scenario anchor:
  id "vol-ravi-kumar-patna" — Ravi Kumar, Patna, skills ["rescue","driving"],
  2.1 km from the demo SOS pin (25.5941, 85.1376), languages ["hi","hing"],
  availability "anytime", reputation 50, tasks_completed 0.
(per docs/demo-scenario.md — this is the acceptance-test match.)

ALL OUTPUT IS SYNTHETIC DEMO DATA.
"""
import json

from common import (
    DATA_DIR, FIRST_NAMES, LAST_NAMES, VOLUNTEER_SKILLS, LANG_CODES,
    load_districts, make_rng, new_uuid, indian_phone, jitter,
)

N_VOLUNTEERS = 1000
# demo SOS pin (Kankarbagh, Patna) — Ravi sits ~2.1 km away
RAVI_LAT, RAVI_LON = 25.6071, 85.1526

def main():
    rng = make_rng("volunteers")
    districts = load_districts()
    total_pop = sum(d["population"] for d in districts)
    weights = [(d, d["population"] / total_pop) for d in districts]

    def pick_district():
        r = rng.random()
        upto = 0.0
        for d, w in weights:
            upto += w
            if r <= upto:
                return d
        return districts[-1]

    volunteers = []
    # ---- fixed anchor FIRST (demo scenario)
    volunteers.append({
        "id": "vol-ravi-kumar-patna",
        "name": "Ravi Kumar",
        "phone": "+91-9812345678",  # FAKE (synthetic data)
        "district_id": "patna",
        "lat": RAVI_LAT, "lon": RAVI_LON,
        "skills": ["rescue", "driving"],
        "languages": ["hi", "hing"],
        "availability": "anytime",
        "active": True,
        "reputation": 50,
        "tasks_completed": 0,
        "tasks_declined": 0,
        "avg_response_min": None,
        "is_demo_data": True,
    })
    # ---- bulk
    for _ in range(N_VOLUNTEERS - 1):
        d = pick_district()
        n_skills = rng.choices([1, 2, 3], weights=[0.45, 0.40, 0.15])[0]
        skills = rng.sample(VOLUNTEER_SKILLS, n_skills)
        n_langs = rng.choices([1, 2, 3], weights=[0.55, 0.35, 0.10])[0]
        # bias languages toward the district's region: hi/hing common everywhere
        lang_pool = ["hi", "hing"] + [c for c in LANG_CODES if c not in ("hi", "hing", "en")]
        languages = rng.sample(lang_pool, min(n_langs, len(lang_pool)))
        if rng.random() < 0.70:
            availability = "anytime"
        else:
            days = rng.sample(["mon","tue","wed","thu","fri","sat","sun"], rng.randint(2, 5))
            availability = [{"day": day, "start": "09:00", "end": "18:00"} for day in days]
        lat, lon = jitter(rng, d["lat"], d["lon"], spread=0.40)
        tasks_completed = int(rng.expovariate(1 / 6))  # mean ~6
        volunteers.append({
            "id": new_uuid(rng),
            "name": f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
            "phone": indian_phone(rng),  # FAKE (synthetic data)
            "district_id": d["id"],
            "lat": lat, "lon": lon,
            "skills": sorted(skills),
            "languages": languages,
            "availability": availability,
            "active": rng.random() < 0.90,
            "reputation": max(0, min(100, int(rng.gauss(55, 15)))),
            "tasks_completed": tasks_completed,
            "tasks_declined": int(rng.expovariate(1 / 1.5)),
            "avg_response_min": round(rng.uniform(8, 90), 1) if tasks_completed else None,
            "is_demo_data": True,
        })
    out = {"meta": {"count": len(volunteers), "synthetic": True,
                    "note": "ALL ROWS SYNTHETIC. Names and phone numbers are fictional. "
                            "Includes fixed anchor vol-ravi-kumar-patna for the demo scenario."},
           "volunteers": volunteers}
    path = DATA_DIR / "volunteers.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"wrote {path} ({len(volunteers)} volunteers)")

if __name__ == "__main__":
    main()
