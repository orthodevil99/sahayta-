"""Tests: Wave 3 Agent 8 — volunteer coordination extensions.

Covers: registration validation, matching explainability + tie-breakers,
decline re-offer, reputation math/endpoint, SMS notification templates.
The demo Act 3 path (Ravi top match ≥ 80, lifecycle, +2 reputation) is
covered in test_tasks.py; these tests cover the Wave 3 additions.
"""
from __future__ import annotations

import uuid

import pytest

from app.models import SOSReport, Volunteer
from app.services import reputation as rep
from app.services.matching import rank_volunteers, score_breakdown, score_volunteer
from app.services.notify_templates import (
    LANGS,
    NOTIFY_EVENTS,
    TEMPLATES,
    notification_preview,
    render_notification,
)
from tests.conftest import _admin_headers, _guest_headers

DEVICE_C = "test-device-cccc"


async def _mk_sos(client, **kw):
    payload = {
        "description": kw.get("description", "Waist-deep water; residents on rooftops; urgent rescue."),
        "lat": kw.get("lat", 25.5941),
        "lon": kw.get("lon", 85.1376),
        "client_report_id": str(uuid.uuid4()),
    }
    r = await client.post("/api/sos", json=payload, headers=_guest_headers(DEVICE_C))
    assert r.status_code == 201, r.text
    return r.json()


async def _mk_volunteer(client, **kw):
    payload = {
        "name": kw.get("name", "Test Volunteer"),
        "district_id": "patna",
        "lat": kw.get("lat", 25.60),
        "lon": kw.get("lon", 85.15),
        "skills": kw.get("skills", ["rescue"]),
        "languages": kw.get("languages", ["hi"]),
        "availability": kw.get("availability", "anytime"),
    }
    r = await client.post("/api/volunteers", json=payload,
                          headers=_guest_headers(kw.get("device", DEVICE_C)))
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------- registration validation


async def test_register_rejects_bad_language(client):
    r = await client.post("/api/volunteers",
                          json={"name": "Bad Lang", "skills": ["rescue"],
                                "languages": ["xx"]},
                          headers=_guest_headers(DEVICE_C))
    assert r.status_code == 422


async def test_register_rejects_bad_availability_windows(client):
    bad_windows = [
        [{"day": "funday", "start": "09:00", "end": "18:00"}],   # bad day
        [{"day": "mon", "start": "9am", "end": "18:00"}],        # bad time
        [{"day": "mon", "start": "18:00", "end": "09:00"}],       # start >= end
        ["anytime"],                                             # not an object
    ]
    for windows in bad_windows:
        r = await client.post("/api/volunteers",
                              json={"name": "Bad Avail", "skills": ["rescue"],
                                    "availability": windows},
                              headers=_guest_headers(DEVICE_C))
        assert r.status_code == 422, f"expected 422 for {windows}: {r.text}"


async def test_register_accepts_valid_windows_and_lat_lon_together(client):
    r = await client.post(
        "/api/volunteers",
        json={"name": "Windowed", "skills": ["medical"],
              "availability": [{"day": "mon", "start": "09:00", "end": "18:00"}]},
        headers=_guest_headers(DEVICE_C),
    )
    assert r.status_code == 201, r.text
    # lat without lon -> 422
    r = await client.post("/api/volunteers",
                          json={"name": "Half Geo", "skills": ["rescue"], "lat": 25.6},
                          headers=_guest_headers(DEVICE_C))
    assert r.status_code == 422


async def test_register_rejects_empty_skills(client):
    r = await client.post("/api/volunteers",
                          json={"name": "Skilless", "skills": []},
                          headers=_guest_headers(DEVICE_C))
    assert r.status_code == 422


# ---------------------------------------------------------------- matching: breakdown + tie-breakers


def _mem_sos(**kw):
    return SOSReport(
        id=kw.get("id", "sos-x"),
        description="test",
        lat=kw.get("lat", 25.5941),
        lon=kw.get("lon", 85.1376),
        needed_skills=kw.get("needed_skills", ["rescue"]),
    )


def _mem_vol(**kw):
    return Volunteer(
        id=kw.get("id", "vol-x"),
        name=kw.get("name", "V"),
        district_id="patna",
        lat=kw.get("lat", 25.60),
        lon=kw.get("lon", 85.15),
        skills=kw.get("skills", ["rescue"]),
        languages=["hi"],
        availability=kw.get("availability", "anytime"),
        active=kw.get("active", True),
        reputation=kw.get("reputation", 50),
    )


def test_match_tiebreaker_is_deterministic():
    sos = _mem_sos()
    a = _mem_vol(id="vol-a")
    b = _mem_vol(id="vol-b")
    ranked = rank_volunteers(sos, [b, a], max_results=5, max_distance_km=25)
    assert [v.id for v, _, _, _ in ranked] == ["vol-a", "vol-b"]
    # higher reputation wins ties
    c = _mem_vol(id="vol-c", reputation=80)
    ranked = rank_volunteers(sos, [a, c], max_results=5, max_distance_km=25)
    s_a = score_volunteer(sos, a, 25)[0]
    s_c = score_volunteer(sos, c, 25)[0]
    assert s_c > s_a  # reputation component differs -> not a tie
    assert ranked[0][0].id == "vol-c"


def test_match_inactive_volunteers_excluded():
    sos = _mem_sos()
    off = _mem_vol(id="vol-off", active=False)
    ranked = rank_volunteers(sos, [off], max_results=5, max_distance_km=25)
    assert ranked == []


async def test_match_response_carries_score_breakdown(client):
    sos = await _mk_sos(client)
    r = await client.post("/api/tasks/match",
                          json={"sos_id": sos["id"], "max_results": 3,
                                "max_distance_km": 25},
                          headers=_guest_headers())
    assert r.status_code == 200, r.text
    matches = r.json()["matches"]
    assert matches
    bd = matches[0]["score_breakdown"]
    assert set(bd) == {"skill", "distance", "availability", "reputation"}
    rebuilt = (0.45 * bd["skill"] + 0.30 * bd["distance"]
               + 0.15 * bd["availability"] + 0.10 * bd["reputation"])
    assert abs(rebuilt * 100 - matches[0]["score"]) < 0.2


# ---------------------------------------------------------------- decline re-offer


async def test_decline_reoffers_next_ranked_volunteer(client):
    sos = await _mk_sos(client)
    x = await _mk_volunteer(client, name="Reoffered Away", device="reoffer-dev")
    r = await client.post("/api/tasks",
                          json={"sos_id": sos["id"], "volunteer_id": x["id"]},
                          headers=_admin_headers())
    tid = r.json()["id"]
    r = await client.post(f"/api/tasks/{tid}/decline",
                          json={"reason": "too far"},
                          headers=_guest_headers("reoffer-dev"))
    assert r.status_code == 200
    assert r.json()["status"] == "declined"
    # a fresh assigned task exists for the next-ranked volunteer (Ravi)
    r = await client.get(f"/api/tasks?sos_id={sos['id']}",
                         headers=_guest_headers())
    tasks = r.json()["items"]
    assert len(tasks) == 2
    reoffered = next(t for t in tasks if t["id"] != tid)
    assert reoffered["status"] == "assigned"
    assert reoffered["volunteer_id"] == "vol-ravi-kumar-patna"
    assert "Re-offered" in (reoffered["note"] or "")
    # the original SOS is untouched by the decline
    r = await client.get(f"/api/sos/{sos['id']}", headers=_guest_headers())
    assert r.json()["status"] == "reported"


async def test_decline_with_no_candidates_creates_nothing(client):
    sos = await _mk_sos(client, lat=0.0, lon=0.0)  # mid-ocean: nobody in range
    x = await _mk_volunteer(client, name="Lonely", device="lonely-dev")
    r = await client.post("/api/tasks",
                          json={"sos_id": sos["id"], "volunteer_id": x["id"]},
                          headers=_admin_headers())
    tid = r.json()["id"]
    r = await client.post(f"/api/tasks/{tid}/decline",
                          json={"reason": "too far"},
                          headers=_guest_headers("lonely-dev"))
    assert r.status_code == 200
    r = await client.get(f"/api/tasks?sos_id={sos['id']}",
                         headers=_guest_headers())
    assert len(r.json()["items"]) == 1  # no re-offer possible


async def test_decline_after_accept_still_reoffers_and_penalizes(client):
    sos = await _mk_sos(client)
    x = await _mk_volunteer(client, name="Flaky", device="flaky-dev")
    r = await client.post("/api/tasks",
                          json={"sos_id": sos["id"], "volunteer_id": x["id"]},
                          headers=_admin_headers())
    tid = r.json()["id"]
    await client.post(f"/api/tasks/{tid}/accept", headers=_guest_headers("flaky-dev"))
    r = await client.post(f"/api/tasks/{tid}/decline",
                          json={"reason": "vehicle broke"},
                          headers=_guest_headers("flaky-dev"))
    assert r.json()["status"] == "declined"
    r = await client.get(f"/api/volunteers/{x['id']}", headers=_guest_headers())
    assert r.json()["reputation"] == 45  # broken commitment: -5
    r = await client.get(f"/api/tasks?sos_id={sos['id']}",
                         headers=_guest_headers())
    assert len(r.json()["items"]) == 2  # re-offer went out anyway


# ---------------------------------------------------------------- reputation service + endpoint


def test_reputation_math_caps_and_floors():
    v = Volunteer(name="T", reputation=99, tasks_completed=10, tasks_declined=0,
                  avg_response_min=None)
    assert rep.on_task_completed(v) == 100  # cap
    assert v.tasks_completed == 11
    v2 = Volunteer(name="T", reputation=3, tasks_completed=1, tasks_declined=0,
                   avg_response_min=None)
    assert rep.on_decline_after_commit(v2) == 0  # floor
    assert v2.tasks_declined == 1


def test_reputation_response_time_running_average():
    v = Volunteer(name="T", reputation=50, tasks_completed=0, tasks_declined=0,
                  avg_response_min=None)
    assert rep.record_response_time(v, 10.0) == 10.0
    assert rep.record_response_time(v, 20.0) == 15.0


def test_reputation_reliability_and_tiers():
    v = Volunteer(name="T", reputation=95, tasks_completed=9, tasks_declined=1,
                  avg_response_min=12.5)
    assert rep.reliability_pct(v) == 90.0
    assert rep.reputation_tier(95) == "guardian"
    assert rep.reputation_tier(70) == "responder"
    assert rep.reputation_tier(40) == "helper"
    assert rep.reputation_tier(39) == "newcomer"
    fresh = Volunteer(name="N", reputation=50, tasks_completed=0,
                      tasks_declined=0, avg_response_min=None)
    assert rep.reliability_pct(fresh) == 100.0  # no history: not penalized


async def test_reputation_endpoint_shape(client):
    v = await _mk_volunteer(client, name="Rep Check", device="rep-dev")
    r = await client.get(f"/api/volunteers/{v['id']}/reputation",
                         headers=_guest_headers())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {
        "volunteer_id": v["id"],
        "reputation": 50,
        "tasks_completed": 0,
        "tasks_declined": 0,
        "avg_response_min": None,
        "reliability_pct": 100.0,
        "tier": "helper",
    }
    r = await client.get("/api/volunteers/does-not-exist/reputation",
                         headers=_guest_headers())
    assert r.status_code == 404


async def test_reputation_endpoint_reflects_history(client):
    sos = await _mk_sos(client)
    v = await _mk_volunteer(client, name="Hist", device="hist-dev")
    r = await client.post("/api/tasks",
                          json={"sos_id": sos["id"], "volunteer_id": v["id"]},
                          headers=_admin_headers())
    tid = r.json()["id"]
    await client.post(f"/api/tasks/{tid}/accept", headers=_guest_headers("hist-dev"))
    await client.post(f"/api/tasks/{tid}/enroute", headers=_guest_headers("hist-dev"))
    await client.post(f"/api/tasks/{tid}/complete", json={"note": "done"},
                      headers=_guest_headers("hist-dev"))
    r = await client.get(f"/api/volunteers/{v['id']}/reputation",
                         headers=_guest_headers())
    body = r.json()
    assert body["reputation"] == 52
    assert body["tasks_completed"] == 1
    assert body["avg_response_min"] is not None


# ---------------------------------------------------------------- notification templates


def test_notify_templates_all_languages_all_events_short():
    assert set(TEMPLATES) == set(NOTIFY_EVENTS)
    for event in NOTIFY_EVENTS:
        assert set(TEMPLATES[event]) == set(LANGS), f"{event} missing languages"
    long_vals = {"name": "A" * 30, "district": "B" * 30, "km": "123.4", "sos": "c" * 8}
    for event in NOTIFY_EVENTS:
        for lang in LANGS:
            text = render_notification(event, lang, **long_vals)
            assert len(text) <= 160, f"{event}/{lang} is {len(text)} chars"


def test_notify_fallback_chain():
    hi = render_notification("assigned", "hi", name="Ravi")
    assert render_notification("assigned", "xx", name="Ravi") == hi  # unknown -> hi
    assert "सहायता" in hi
    bn = render_notification("assigned", "bn", name="Ravi")
    assert "সহায়তা" in bn
    with pytest.raises(ValueError):
        render_notification("nope", "hi")


def test_notify_preview_renders_all_events():
    msgs = notification_preview("hi", name="Ravi", district="Patna",
                                km="2.1", sos="abc123")
    assert set(msgs) == set(NOTIFY_EVENTS)
    assert all(len(m) <= 160 for m in msgs.values())
    assert "2.1" in msgs["assigned"] and "Patna" in msgs["assigned"]


async def test_task_notifications_endpoint(client):
    sos = await _mk_sos(client)
    v = await _mk_volunteer(client, name="Ravi Test", device="notif-dev")
    r = await client.post("/api/tasks",
                          json={"sos_id": sos["id"], "volunteer_id": v["id"]},
                          headers=_admin_headers())
    tid = r.json()["id"]
    r = await client.get(f"/api/tasks/{tid}/notifications?lang=hi",
                         headers=_guest_headers())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["task_id"] == tid and body["lang"] == "hi"
    assert set(body["messages"]) == set(NOTIFY_EVENTS)
    assert all(len(m) <= 160 for m in body["messages"].values())
    assert "सहायता" in body["messages"]["assigned"]
    # unknown language falls back to Hindi
    r = await client.get(f"/api/tasks/{tid}/notifications?lang=xx",
                         headers=_guest_headers())
    assert "सहायता" in r.json()["messages"]["assigned"]
    r = await client.get("/api/tasks/does-not-exist/notifications",
                         headers=_guest_headers())
    assert r.status_code == 404
