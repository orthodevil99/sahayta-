"""Generate data/sos-reports.json — 3,000 synthetic SOS reports over a simulated
72-hour flood event (2026-10-03T00:00Z -> 2026-10-06T00:00Z).

ALL OUTPUT IS SYNTHETIC DEMO DATA.
"""
import json
from datetime import datetime, timedelta, timezone

from common import (
    DATA_DIR, FIRST_NAMES, LAST_NAMES, LOCALITIES, SOS_TEMPLATES,
    OTHER_LANG_TEMPLATES, PHOTO_TEMPLATES, PLACES, PHOTO_DETAILS,
    CATEGORIES, CATEGORY_SKILLS, SEVERITY_PRIORITY,
    load_districts, make_rng, new_uuid, indian_phone, jitter,
)

EVENT_START = datetime(2026, 10, 3, 0, 0, 0, tzinfo=timezone.utc)
EVENT_END = datetime(2026, 10, 6, 0, 0, 0, tzinfo=timezone.utc)
N_REPORTS = 3000
N_ANCHORS = 25  # Patna severity-4 flood anchors (demo scenario)

DISTRICT_WEIGHTS = {
    "patna": 0.26, "vaishali": 0.06, "muzaffarpur": 0.06, "darbhanga": 0.06,
    "bhagalpur": 0.06, "purnia": 0.06, "katihar": 0.06, "samastipur": 0.06,
    "sitamarhi": 0.06, "gaya": 0.03, "lucknow": 0.03, "gorakhpur": 0.03,
    "varanasi": 0.03, "guwahati": 0.02, "dibrugarh": 0.02, "kolkata": 0.02,
    "howrah": 0.02, "puri": 0.02, "nagpur": 0.02, "chennai": 0.02,
}
CATEGORY_WEIGHTS = {"medical": 0.15, "rescue": 0.30, "food": 0.18,
                    "shelter": 0.15, "infrastructure": 0.15, "other": 0.07}
SEVERITY_WEIGHTS = {1: 0.30, 2: 0.32, 3: 0.22, 4: 0.11, 5: 0.05}
LANG_WEIGHTS = [("hi", 0.40), ("hing", 0.25), ("en", 0.20), ("bn", 0.05),
                ("ta", 0.0143), ("te", 0.0143), ("mr", 0.0143), ("gu", 0.0143),
                ("kn", 0.0143), ("ml", 0.0143), ("pa", 0.0144)]

# near-fixture Hindi anchor texts (mirror docs/demo-scenario.md fixture, varied)
ANCHOR_TEXTS = [
    "पटना के कंकड़बाग इलाके में घुटनों तक पानी भर गया है। दो गलियों में घरों में पानी घुस गया है, बुजुर्ग छत पर हैं। तुरंत मदद चाहिए।",
    "कंकड़बाग, पटना में कमर तक पानी पहुँच गया है। घरों में पानी घुस रहा है, बच्चे और बुजुर्ग फँसे हैं। नाव भेजें।",
    "पटना के कंकड़बाग में घुटने से ऊपर पानी है। बिजली गुल है, छतों पर लोग हैं। तुरंत बचाव दल चाहिए।",
]

def weighted_choice(rng, weights):
    items = list(weights.items()) if isinstance(weights, dict) else weights
    total = sum(w for _, w in items)
    r = rng.random() * total
    upto = 0.0
    for k, w in items:
        upto += w
        if r <= upto:
            return k
    return items[-1][0]

def render_description(rng, category, language, district):
    name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
    locality = rng.choice(LOCALITIES[district["id"]])
    dname = district["name"]
    if language in OTHER_LANG_TEMPLATES:
        return OTHER_LANG_TEMPLATES[language].format(locality=locality, district=dname)
    pool = SOS_TEMPLATES[category].get(language) or SOS_TEMPLATES[category]["en"]
    return rng.choice(pool).format(name=name, locality=locality, district=dname)

def render_photo_desc(rng, severity, district):
    dtype = district["hazards"][0]
    pool = PHOTO_TEMPLATES[dtype][severity]
    return rng.choice(pool).format(place=rng.choice(PLACES),
                                   locality=rng.choice(LOCALITIES[district["id"]]),
                                   detail=rng.choice(PHOTO_DETAILS))

def sample_hour(rng):
    # ramp: reports intensify as the flood peaks
    weights = [1 + 4 * (h / 71) ** 2 for h in range(72)]
    return weighted_choice(rng, {h: w for h, w in enumerate(weights)})

def sample_severity(rng, district_id, hour):
    sev = weighted_choice(rng, SEVERITY_WEIGHTS)
    bump_p = 0.0
    if district_id == "patna" and hour >= 48:
        bump_p = 0.40
    elif hour >= 60:
        bump_p = 0.20
    if rng.random() < bump_p:
        sev = min(5, sev + 1)
    return sev

def sample_status(rng, age_hours):
    if age_hours > 48:
        w = {"reported": 0.15, "verified": 0.20, "help_on_way": 0.10,
             "resolved": 0.50, "duplicate": 0.03, "rejected": 0.02}
    elif age_hours > 24:
        w = {"reported": 0.35, "verified": 0.30, "help_on_way": 0.12,
             "resolved": 0.18, "duplicate": 0.03, "rejected": 0.02}
    else:
        w = {"reported": 0.55, "verified": 0.25, "help_on_way": 0.10,
             "resolved": 0.05, "duplicate": 0.03, "rejected": 0.02}
    return weighted_choice(rng, w)

def build_report(rng, districts_by_id, district_id, severity, category, language,
                 created_at, description=None, photo_desc=None, status=None,
                 lat=None, lon=None, anchor=False):
    d = districts_by_id[district_id]
    age_h = (EVENT_END - created_at).total_seconds() / 3600
    if description is None:
        description = render_description(rng, category, language, d)
    if photo_desc is None and rng.random() < 0.60:
        photo_desc = render_photo_desc(rng, severity, d)
    if lat is None or lon is None:
        lat, lon = jitter(rng, d["lat"], d["lon"], spread=0.30)
    if status is None:
        status = sample_status(rng, age_h)
    priority = SEVERITY_PRIORITY[severity]
    if severity == 2 and rng.random() < 0.4:
        priority = "low"
    if severity == 3 and rng.random() < 0.4:
        priority = "high"
    needs_review = (severity >= 4 and status == "reported" and rng.random() < 0.5) \
        or rng.random() < 0.05
    updated_at = created_at + timedelta(minutes=rng.randint(5, 300))
    return {
        "id": new_uuid(rng),
        "client_report_id": new_uuid(rng),
        "description": description,
        "language": language,
        "category": category,
        "severity": severity,
        "priority": priority,
        "status": status,
        "lat": lat, "lon": lon,
        "district_id": district_id,
        "photo_url": None,
        "photo_hash": None,
        "photo_description": photo_desc,
        "reporter_name": f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
        "reporter_phone": indian_phone(rng),
        "needed_skills": CATEGORY_SKILLS[category],
        "needs_review": needs_review,
        "is_demo_data": True,
        "created_at": created_at.isoformat().replace("+00:00", "Z"),
        "updated_at": updated_at.isoformat().replace("+00:00", "Z"),
    }

def main():
    rng = make_rng("sos-reports")
    districts = load_districts()
    by_id = {d["id"]: d for d in districts}
    reports = []

    # ---- anchors: Patna severity-4 flood reports in the final 12h (demo scenario)
    patna = by_id["patna"]
    for i in range(N_ANCHORS):
        created = EVENT_END - timedelta(hours=rng.uniform(0.5, 12))
        if i < len(ANCHOR_TEXTS):
            desc, lang = ANCHOR_TEXTS[i], "hi"
        else:
            desc, lang = None, weighted_choice(rng, [("hi", 0.6), ("hing", 0.25), ("en", 0.15)])
        lat = round(25.5941 + rng.uniform(-0.05, 0.05), 6)
        lon = round(85.1376 + rng.uniform(-0.05, 0.05), 6)
        reports.append(build_report(rng, by_id, "patna", 4, "rescue", lang, created,
                                    description=desc, status="reported",
                                    lat=lat, lon=lon, anchor=True))

    # ---- bulk random reports
    for _ in range(N_REPORTS - N_ANCHORS):
        district_id = weighted_choice(rng, DISTRICT_WEIGHTS)
        hour = sample_hour(rng)
        created = EVENT_START + timedelta(hours=hour, minutes=rng.randint(0, 59),
                                          seconds=rng.randint(0, 59))
        severity = sample_severity(rng, district_id, hour)
        category = weighted_choice(rng, CATEGORY_WEIGHTS)
        language = weighted_choice(rng, LANG_WEIGHTS)
        reports.append(build_report(rng, by_id, district_id, severity, category,
                                    language, created))

    reports.sort(key=lambda r: r["created_at"])
    out = {
        "meta": {
            "count": len(reports),
            "event": "simulated 72-hour flood",
            "window_start": EVENT_START.isoformat().replace("+00:00", "Z"),
            "window_end": EVENT_END.isoformat().replace("+00:00", "Z"),
            "synthetic": True,
            "note": "ALL ROWS SYNTHETIC DEMO DATA. Includes 25 Patna severity-4 anchors for the demo scenario.",
        },
        "reports": reports,
    }
    path = DATA_DIR / "sos-reports.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"wrote {path} ({len(reports)} reports)")

if __name__ == "__main__":
    main()
