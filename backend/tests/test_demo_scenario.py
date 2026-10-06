"""End-to-end: the Patna flood demo scenario (docs/demo-scenario.md, Acts 1-5),
driven entirely through the HTTP API on a fresh seed.
"""
from __future__ import annotations

import uuid

from tests.conftest import DEMO_DESCRIPTION, _admin_headers, _guest_headers


async def test_demo_scenario_acts_1_to_5(client):
    # ---- Act 1: citizen files SOS --------------------------------------
    cid = str(uuid.uuid4())
    r = await client.post(
        "/api/sos",
        json={"description": DEMO_DESCRIPTION, "lat": 25.5941, "lon": 85.1376,
              "client_report_id": cid, "language": "hi",
              "reporter_name": "Demo Citizen"},
        headers=_guest_headers("demo-citizen"),
    )
    assert r.status_code == 201
    sos = r.json()
    assert sos["status"] == "reported" and sos["district_id"] == "patna"
    sid = sos["id"]

    # offline replay with the same client_report_id -> 200, same id, no duplicate
    r = await client.post(
        "/api/sos",
        json={"description": DEMO_DESCRIPTION, "lat": 25.5941, "lon": 85.1376,
              "client_report_id": cid, "language": "hi"},
        headers=_guest_headers("demo-citizen"),
    )
    assert r.status_code == 200 and r.json()["id"] == sid

    # ---- Act 2: AI severity (exact acceptance values) -------------------
    assert sos["severity"] == 4
    a = sos["assessment"]
    assert a["severity"] == 4
    assert a["category"] == "rescue" and a["priority"] == "critical"
    assert a["suggested_skills"] == ["rescue", "driving"]
    assert a["model"] == "rule-fallback-v1"

    r = await client.get("/api/sos?district=patna&severity_min=4",
                         headers=_guest_headers())
    assert sid in [x["id"] for x in r.json()["items"]]
    r = await client.get(f"/api/sos/{sid}", headers=_guest_headers())
    assert r.json()["assessment"]["severity"] == 4

    # ---- Act 3: match -> assign -> accept -> enroute -> complete ----------
    r = await client.post("/api/tasks/match",
                          json={"sos_id": sid, "max_results": 5},
                          headers=_guest_headers())
    top = r.json()["matches"][0]
    assert top["volunteer"]["id"] == "vol-ravi-kumar-patna"
    assert top["score"] >= 80

    r = await client.post("/api/tasks",
                          json={"sos_id": sid, "volunteer_id": "vol-ravi-kumar-patna"},
                          headers=_admin_headers())
    assert r.status_code == 201
    tid = r.json()["id"]
    owner = "seed-device-vol-ravi-kumar-patna"

    for action, want_sos in (("accept", "reported"), ("enroute", "help_on_way")):
        r = await client.post(f"/api/tasks/{tid}/{action}", headers=_guest_headers(owner))
        assert r.status_code == 200
        r = await client.get(f"/api/sos/{sid}", headers=_guest_headers())
        assert r.json()["status"] == want_sos, action

    r = await client.post(f"/api/tasks/{tid}/complete", json={"note": "done"},
                          headers=_guest_headers(owner))
    assert r.status_code == 200
    r = await client.get(f"/api/sos/{sid}", headers=_guest_headers())
    assert r.json()["status"] == "resolved"
    r = await client.get("/api/volunteers/vol-ravi-kumar-patna",
                         headers=_guest_headers())
    assert r.json()["reputation"] == 52
    assert r.json()["tasks_completed"] == 1

    # ---- Act 4: Hindi alert broadcast ------------------------------------
    r = await client.post(
        "/api/alerts/broadcast",
        json={"district_ids": ["patna"], "type": "flood",
              "title": "बाढ़ चेतावनी",
              "body": "कंकड़बाग में पानी बढ़ रहा है। ऊँची जगह जाएँ। राहत शिविर खुले हैं।",
              "severity": 4, "languages": ["hi", "hing"]},
        headers=_admin_headers(),
    )
    assert r.status_code == 202
    rendered = r.json()["rendered"]
    assert len(rendered["hi"]) <= 480
    assert any("\u0900" <= ch <= "\u097f" for ch in rendered["hi"])
    assert "hing" in rendered

    r = await client.get("/api/admin/audit?limit=100", headers=_admin_headers())
    assert any(e["action"] == "alert.broadcast" and e["actor"] == "admin:demo"
               for e in r.json())

    # ---- Act 5: command dashboard -----------------------------------------
    r = await client.get("/api/admin/overview?district=patna", headers=_admin_headers())
    ov = r.json()
    assert ov["district_risk"] >= 70
    assert ov["risk_level"] in ("high", "severe")
    total_sos = sum(ov["sos_by_status"].values())
    assert total_sos >= 1

    r = await client.get("/api/districts/patna/risk", headers=_guest_headers())
    risk = r.json()
    assert risk["risk"] >= 70 and risk["factors"]

    r = await client.get("/api/warnings/status", headers=_guest_headers())
    ws = r.json()
    assert ws["enabled"] and ws["districts_tracked"] == 20 and ws["last_ingest_ok"]
    r = await client.get("/api/districts/patna/forecast", headers=_guest_headers())
    assert len(r.json()["hours"]) == 72
