"""Generate data/shelters.json — 500 synthetic shelters across 10 districts
(50 per district). ALL OUTPUT IS SYNTHETIC DEMO DATA (is_demo_data=true always).
"""
import json

from common import (
    DATA_DIR, FIRST_NAMES, LAST_NAMES, LOCALITIES,
    load_districts, make_rng, new_uuid, indian_phone, jitter,
)

SHELTER_DISTRICTS = ["patna", "vaishali", "gaya", "muzaffarpur", "darbhanga",
                     "bhagalpur", "purnia", "lucknow", "guwahati", "kolkata"]
PER_DISTRICT = 50
FACILITIES = ["drinking_water", "medical", "food", "pet_friendly",
              "wheelchair_access", "power_backup"]
SHELTER_TYPES = ["High School Relief Camp", "Community Hall Shelter",
                 "Primary School Camp", "Panchayat Bhawan Shelter",
                 "College Relief Center", "Stadium Relief Camp",
                 "Railway Station Shelter", "Government Building Camp"]

def main():
    rng = make_rng("shelters")
    by_id = {d["id"]: d for d in load_districts()}
    shelters = []
    for did in SHELTER_DISTRICTS:
        d = by_id[did]
        for _ in range(PER_DISTRICT):
            locality = rng.choice(LOCALITIES[did])
            stype = rng.choice(SHELTER_TYPES)
            capacity = rng.choice([100, 150, 200, 250, 300, 400, 500, 750, 1000])
            occupied = min(capacity, int(capacity * rng.uniform(0.05, 0.75)))
            nfac = rng.randint(2, 5)
            facilities = rng.sample(FACILITIES, nfac)
            if rng.random() < 0.7 and "drinking_water" not in facilities:
                facilities.append("drinking_water")
            lat, lon = jitter(rng, d["lat"], d["lon"], spread=0.35)
            shelters.append({
                "id": new_uuid(rng),
                "name": f"{locality} {stype}",
                "district_id": did,
                "area": locality,
                "lat": lat, "lon": lon,
                "capacity": capacity,
                "occupied": occupied,
                "facilities": sorted(facilities),
                "contact_name": f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                "contact_phone": indian_phone(rng),  # FAKE number (synthetic data)
                "is_open": rng.random() < 0.92,
                "is_demo_data": True,
            })
    out = {"meta": {"count": len(shelters), "synthetic": True,
                    "note": "ALL ROWS SYNTHETIC. Names, phones and locations are fictional."},
           "shelters": shelters}
    path = DATA_DIR / "shelters.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"wrote {path} ({len(shelters)} shelters)")

if __name__ == "__main__":
    main()
