#!/usr/bin/env python3
"""Sahayta seed script — loads data/*.json into a fresh SQLite DB (default).

Usage:
    cd backend && python seed.py            # idempotent reload of demo data
    cd backend && python seed.py --fresh    # drop + recreate all tables first

Idempotency (per docs/data-models.md §3): re-running clears every row with
is_demo_data=true, then reloads. Runtime rows (is_demo_data=false) survive.

What it loads:
- data/districts.json        -> districts (20, canonical slugs)
- data/sos-reports.json      -> sos_reports (3000) + derived severity_assessments
                               (model="seed-synthetic-v1" — honest label)
- data/shelters.json         -> shelters (500, always is_demo_data=true)
- data/volunteers.json       -> volunteers (1000) + stub users rows
- data/weather-sample.json   -> district_weather_samples (600) + initial
                               district_risks. Where seed_hints exist
                               (patna: risk 82/high) the hint is honored and
                               factor contributions are normalized to sum to it.

The demo anchor volunteer keeps its FIXED id vol-ravi-kumar-patna (the
demo-scenario acceptance test matches against it).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# backend/ on sys.path so `app.*` imports resolve.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import create_engine, delete, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import Base  # noqa: E402
import app.models as M  # noqa: E402,F401
from app.services.risk import normalize_factors, score_district  # noqa: E402

log = logging.getLogger("sahayta.seed")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"


def _read_json(name: str):
    with open(DATA / name, encoding="utf-8") as f:
        return json.load(f)


def _dt(s: str | None) -> datetime | None:
    if not s:
        return None
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _day_ts(date_str: str) -> datetime:
    return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)


def clear_demo_data(session: Session) -> int:
    """Delete every is_demo_data=true row (children before parents)."""
    total = 0
    for model in (
        M.SeverityAssessment, M.Task, M.SOSReport, M.SafetyFlag, M.AuditLog,
        M.Alert, M.DistrictRisk, M.DistrictWeatherSample, M.Shelter,
        M.Volunteer, M.MediaFile, M.User, M.District,
    ):
        if hasattr(model, "is_demo_data"):
            n = session.execute(
                delete(model).where(model.is_demo_data.is_(True))
            ).rowcount
            total += n or 0
    # MediaFile has no is_demo_data — clear only obvious seed leftovers? No:
    # MediaFile rows are runtime uploads; leave them. (Seed never creates them.)
    session.commit()
    return total


def seed_districts(session: Session) -> int:
    bundle = _read_json("districts.json")
    districts = bundle["districts"] if isinstance(bundle, dict) else bundle
    for d in districts:
        session.add(M.District(
            id=d["id"], name=d["name"], state=d["state"],
            lat=d["lat"], lon=d["lon"], population=d.get("population"),
            is_demo_data=True,
        ))
    session.commit()
    return len(districts)


_SEV_RATIONALE = {
    1: "minor disruption, no one at immediate risk",
    2: "localized impact, monitoring advised",
    3: "significant impact, assistance likely needed",
    4: "severe impact, urgent assistance required",
    5: "catastrophic impact, immediate large-scale response required",
}


def seed_sos(session: Session) -> tuple[int, int]:
    bundle = _read_json("sos-reports.json")
    reports = bundle["reports"] if isinstance(bundle, dict) else bundle
    n_assess = 0
    for r in reports:
        sos = M.SOSReport(
            id=r["id"], client_report_id=r["client_report_id"],
            description=r["description"], language=r.get("language", "hi"),
            category=r.get("category", "other"), severity=r.get("severity"),
            priority=r.get("priority", "medium"), status=r.get("status", "reported"),
            lat=r.get("lat"), lon=r.get("lon"), district_id=r.get("district_id"),
            photo_url=r.get("photo_url"), photo_hash=r.get("photo_hash"),
            photo_description=r.get("photo_description"),
            reporter_name=r.get("reporter_name"), reporter_phone=r.get("reporter_phone"),
            reporter_device_id=f"seed-device-{r['id'][:8]}",
            needed_skills=r.get("needed_skills") or [],
            needs_review=bool(r.get("needs_review", False)),
            needs_review_reason="seed_flagged" if r.get("needs_review") else None,
            is_demo_data=True,
            created_at=_dt(r.get("created_at")), updated_at=_dt(r.get("updated_at")),
        )
        session.add(sos)
        if r.get("severity"):
            sev = int(r["severity"])
            session.add(M.SeverityAssessment(
                sos_report_id=r["id"], severity=sev,
                rationale=f"[synthetic seed] {_SEV_RATIONALE.get(sev, '')}: "
                          f"{(r.get('photo_description') or r['description'])[:160]}",
                rationale_en=f"[synthetic seed] severity {sev}/5.",
                area_tags=[], category=r.get("category", "other"),
                priority=r.get("priority", "medium"),
                suggested_skills=r.get("needed_skills") or [],
                model="seed-synthetic-v1",  # honest: never presented as an LLM call
                assessed_at=_dt(r.get("created_at")),
            ))
            n_assess += 1
    session.commit()
    return len(reports), n_assess


def seed_shelters(session: Session) -> int:
    bundle = _read_json("shelters.json")
    shelters = bundle["shelters"] if isinstance(bundle, dict) else bundle
    for s in shelters:
        session.add(M.Shelter(
            id=s["id"], name=s["name"], district_id=s["district_id"],
            area=s.get("area"), lat=s.get("lat"), lon=s.get("lon"),
            capacity=s["capacity"], occupied=s.get("occupied", 0),
            facilities=s.get("facilities") or [],
            contact_name=s.get("contact_name"), contact_phone=s.get("contact_phone"),
            is_open=s.get("is_open", True), is_demo_data=True,
        ))
    session.commit()
    return len(shelters)


def seed_volunteers(session: Session) -> int:
    bundle = _read_json("volunteers.json")
    volunteers = bundle["volunteers"] if isinstance(bundle, dict) else bundle
    for v in volunteers:
        session.add(M.Volunteer(
            id=v["id"], name=v["name"], phone=v.get("phone"),
            district_id=v.get("district_id"), lat=v.get("lat"), lon=v.get("lon"),
            skills=v.get("skills") or [], languages=v.get("languages") or ["hi"],
            availability=v.get("availability", "anytime"),
            active=v.get("active", True), reputation=v.get("reputation", 50),
            tasks_completed=v.get("tasks_completed", 0),
            tasks_declined=v.get("tasks_declined", 0),
            avg_response_min=v.get("avg_response_min"),
            is_demo_data=True,
        ))
        # Stub user row so volunteer device-ownership works in tests/demo.
        session.add(M.User(
            device_id=f"seed-device-{v['id']}", role="volunteer",
            display_name=v["name"], phone=v.get("phone"),
            preferred_lang=(v.get("languages") or ["hi"])[0],
            is_demo_data=True,
        ))
    # Link volunteers to their stub users.
    session.flush()
    for v in volunteers:
        user = session.execute(
            select(M.User).where(M.User.device_id == f"seed-device-{v['id']}")
        ).scalar_one()
        vol = session.get(M.Volunteer, v["id"])
        assert vol is not None
        vol.user_id = user.id
    session.commit()
    return len(volunteers)


def seed_weather(session: Session) -> tuple[int, int]:
    bundle = _read_json("weather-sample.json")
    districts_data: dict = bundle["districts"]
    hints: dict = bundle.get("seed_hints", {})
    n_samples = 0
    now = datetime.now(timezone.utc)
    for district_id, days in districts_data.items():
        for day in days:
            session.add(M.DistrictWeatherSample(
                district_id=district_id, ts=_day_ts(day["date"]),
                rain_mm=day.get("rain_mm"), temp_c=day.get("temp_c"),
                humidity_pct=day.get("humidity_pct"), wind_kph=day.get("wind_kph"),
                river_level_m=day.get("river_level_m"),
                river_trend=day.get("river_trend"),
                source=day.get("source", "simulated"), ingested_at=now,
            ))
            n_samples += 1
    session.commit()

    # Initial risk snapshots from the latest sample per district.
    n_risks = 0
    for district_id, days in districts_data.items():
        last = days[-1]
        risk, level, factors, advisory = score_district(last)
        hint = hints.get(district_id)
        if hint and "risk" in hint:
            log.info("seed_hints override: %s risk %s -> %s (%s)",
                     district_id, risk, hint["risk"], hint.get("note", ""))
            factors = normalize_factors(factors, int(hint["risk"]))
            risk, level = int(hint["risk"]), hint.get("risk_level", level)
        session.add(M.DistrictRisk(
            district_id=district_id, risk=risk, risk_level=level,
            factors=factors, advisory=advisory,
            weather_source=last.get("source", "simulated"), computed_at=now,
        ))
        n_risks += 1
    session.commit()
    return n_samples, n_risks


def _sync_url() -> str:
    url = get_settings().database_url
    return url.replace("sqlite+aiosqlite://", "sqlite://").replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Sahayta database.")
    parser.add_argument("--fresh", action="store_true",
                        help="drop + recreate all tables before seeding")
    args = parser.parse_args()

    engine = create_engine(_sync_url())
    if args.fresh:
        log.info("dropping + recreating all tables")
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
    else:
        Base.metadata.create_all(engine)  # no-op if tables exist

    with Session(engine) as session:
        cleared = clear_demo_data(session)
        log.info("cleared %d demo rows", cleared)
        n_d = seed_districts(session)
        log.info("districts: %d", n_d)
        n_sos, n_ass = seed_sos(session)
        log.info("sos_reports: %d (+%d synthetic assessments)", n_sos, n_ass)
        n_sh = seed_shelters(session)
        log.info("shelters: %d", n_sh)
        n_v = seed_volunteers(session)
        log.info("volunteers: %d (+ stub users)", n_v)
        n_w, n_r = seed_weather(session)
        log.info("weather samples: %d, initial district risks: %d", n_w, n_r)

    # Anchor check — the demo-scenario acceptance test depends on these.
    with Session(engine) as session:
        ravi = session.get(M.Volunteer, "vol-ravi-kumar-patna")
        assert ravi is not None and ravi.name == "Ravi Kumar", "demo anchor volunteer missing!"
        patna_risk = session.execute(
            select(M.DistrictRisk)
            .where(M.DistrictRisk.district_id == "patna")
            .order_by(M.DistrictRisk.computed_at.desc())
        ).scalar_one()
        assert patna_risk.risk >= 70, f"patna seed risk {patna_risk.risk} < 70!"
        log.info("ANCHORS OK: ravi=%s (%.2f, %.2f), patna risk=%d/%s",
                 ravi.id, ravi.lat, ravi.lon, patna_risk.risk, patna_risk.risk_level)
    log.info("seed complete")


if __name__ == "__main__":
    main()
