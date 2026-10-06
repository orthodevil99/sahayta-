"""Tests: volunteers, matching, task lifecycle (the demo Acts 2-3 path)."""
from __future__ import annotations

import uuid

import pytest

from tests.conftest import DEVICE_A, DEVICE_B, _admin_headers, _guest_headers

DESC = "Waist-deep water across two lanes; residents on rooftops; urgent rescue."


async def _mk_sos(client, **kw):
    payload = {
        "description": kw.get("description", DESC),
        "lat": 25.5941, "lon": 85.1376,
        "client_report_id": str(uuid.uuid4()),
    }
    r = await client.post("/api/sos", json=payload, headers=_guest_headers(DEVICE_A))
    assert r.status_code == 201, r.text
    return r.json()


async def _mk_volunteer(client, **kw):
    payload = {
        "name": kw.get("name", "Test Volunteer"),
        "district_id": "patna", "lat": 25.60, "lon": 85.15,
        "skills": kw.get("skills", ["rescue"]),
        "languages": ["hi"], "availability": "anytime",
    }
    r = await client.post("/api/volunteers", json=payload,
                          headers=_guest_headers(kw.get("device", DEVICE_B)))
    assert r.status_code == 201, r.text
    return r.json()


async def test_register_and_get_volunteer(client):
    v = await _mk_volunteer(client, name="Asha Devi", skills=["medical", "translation"])
    assert v["reputation"] == 50
    assert v["tasks_completed"] == 0
    r = await client.get(f"/api/volunteers/{v['id']}", headers=_guest_headers())
    assert r.status_code == 200
    assert r.json()["name"] == "Asha Devi"


async def test_match_ranks_ravi_top(client):
    sos = await _mk_sos(client)
    r = await client.post(
        "/api/tasks/match",
        json={"sos_id": sos["id"], "max_results": 5, "max_distance_km": 25},
        headers=_guest_headers(),
    )
    assert r.status_code == 200, r.text
    matches = r.json()["matches"]
    assert matches, "expected volunteers in seed data"
    top = matches[0]
    assert top["volunteer"]["id"] == "vol-ravi-kumar-patna"
    assert top["score"] >= 80
    assert abs(top["distance_km"] - 2.1) < 0.5
    assert any("skill match: rescue" in reason for reason in top["reasons"])


async def test_full_task_lifecycle_demo_path(client):
    sos = await _mk_sos(client)
    sid = sos["id"]
    ravi = "vol-ravi-kumar-patna"
    owner = "seed-device-vol-ravi-kumar-patna"  # stub user device from seed

    # assign (admin)
    r = await client.post("/api/tasks",
                          json={"sos_id": sid, "volunteer_id": ravi,
                                "note": "Nearest rescue volunteer"},
                          headers=_admin_headers())
    assert r.status_code == 201, r.text
    task = r.json()
    assert task["status"] == "assigned"
    tid = task["id"]

    # duplicate active assignment -> 409
    r = await client.post("/api/tasks",
                          json={"sos_id": sid, "volunteer_id": ravi},
                          headers=_admin_headers())
    assert r.status_code == 409

    # accept as the volunteer owner device
    r = await client.post(f"/api/tasks/{tid}/accept",
                          headers=_guest_headers(owner))
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"

    # en-route flips SOS to help_on_way
    r = await client.post(f"/api/tasks/{tid}/enroute",
                          headers=_guest_headers(owner))
    assert r.status_code == 200
    assert r.json()["status"] == "en_route"
    r = await client.get(f"/api/sos/{sid}", headers=_guest_headers())
    assert r.json()["status"] == "help_on_way"

    # complete -> SOS resolved, reputation +2
    r = await client.post(f"/api/tasks/{tid}/complete",
                          json={"note": "Families moved to shelter"},
                          headers=_guest_headers(owner))
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
    r = await client.get(f"/api/sos/{sid}", headers=_guest_headers())
    assert r.json()["status"] == "resolved"
    r = await client.get(f"/api/volunteers/{ravi}", headers=_guest_headers())
    v = r.json()
    assert v["reputation"] == 52
    assert v["tasks_completed"] == 1


async def test_decline_after_accept_hurts_reputation(client):
    sos = await _mk_sos(client)
    v = await _mk_volunteer(client, name="Decliner", device="decliner-dev")
    owner = "decliner-dev"
    r = await client.post("/api/tasks",
                          json={"sos_id": sos["id"], "volunteer_id": v["id"]},
                          headers=_admin_headers())
    tid = r.json()["id"]
    await client.post(f"/api/tasks/{tid}/accept", headers=_guest_headers(owner))
    r = await client.post(f"/api/tasks/{tid}/decline",
                          json={"reason": "vehicle broke down"},
                          headers=_guest_headers(owner))
    assert r.json()["status"] == "declined"
    r = await client.get(f"/api/volunteers/{v['id']}", headers=_guest_headers())
    assert r.json()["reputation"] == 45  # 50 - 5


async def test_illegal_task_transition_400(client):
    sos = await _mk_sos(client)
    r = await client.post("/api/tasks",
                          json={"sos_id": sos["id"], "volunteer_id": "vol-ravi-kumar-patna"},
                          headers=_admin_headers())
    tid = r.json()["id"]
    owner = "seed-device-vol-ravi-kumar-patna"
    r = await client.post(f"/api/tasks/{tid}/complete", json={},
                          headers=_guest_headers(owner))
    assert r.status_code == 400  # assigned -> completed is illegal


async def test_task_auth_guards(client):
    sos = await _mk_sos(client)
    v = await _mk_volunteer(client, name="Guard", device="guard-dev")
    r = await client.post("/api/tasks",
                          json={"sos_id": sos["id"], "volunteer_id": v["id"]},
                          headers=_admin_headers())
    tid = r.json()["id"]
    # wrong device cannot accept
    r = await client.post(f"/api/tasks/{tid}/accept", headers=_guest_headers("intruder"))
    assert r.status_code == 403
    # guest cannot cancel (admin only)
    r = await client.post(f"/api/tasks/{tid}/cancel", headers=_guest_headers("guard-dev"))
    assert r.status_code == 403
    # admin can cancel
    r = await client.post(f"/api/tasks/{tid}/cancel", headers=_admin_headers())
    assert r.status_code == 200


async def test_volunteer_patch_fields_and_owner_guard(client):
    v = await _mk_volunteer(client, name="Patchy", device="patch-dev")
    # owner can patch allowed fields
    r = await client.patch(f"/api/volunteers/{v['id']}",
                           json={"active": False, "skills": ["driving"]},
                           headers=_guest_headers("patch-dev"))
    assert r.status_code == 200
    assert r.json()["active"] is False
    assert r.json()["skills"] == ["driving"]
    # stranger cannot
    r = await client.patch(f"/api/volunteers/{v['id']}", json={"active": True},
                           headers=_guest_headers("intruder"))
    assert r.status_code == 403


async def test_volunteer_filters(client):
    r = await client.get("/api/volunteers?district=patna&skill=rescue&limit=100",
                         headers=_guest_headers())
    assert r.status_code == 200
    items = r.json()["items"]
    assert items
    assert all("rescue" in v["skills"] for v in items)
