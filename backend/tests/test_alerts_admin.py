"""Tests: alerts broadcast + feed, admin dashboard, safety, media, users, districts."""
from __future__ import annotations

import uuid

from tests.conftest import DEVICE_A, _admin_headers, _guest_headers


async def _broadcast(client, **kw):
    payload = {
        "district_ids": kw.get("district_ids", ["patna"]),
        "type": kw.get("type", "flood"),
        "title": kw.get("title", "बाढ़ चेतावनी"),
        "body": kw.get("body", "कंकड़बाग में पानी बढ़ रहा है। ऊँची जगह जाएँ। राहत शिविर खुले हैं।"),
        "severity": 4,
        "languages": kw.get("languages", ["hi", "hing"]),
    }
    return await client.post("/api/alerts/broadcast", json=payload,
                             headers=_admin_headers())


async def test_broadcast_admin_only_and_shape(client):
    r = await client.post("/api/alerts/broadcast",
                          json={"district_ids": ["patna"], "type": "flood",
                                "title": "t", "body": "0123456789abcdef"},
                          headers=_guest_headers())
    assert r.status_code == 403

    r = await _broadcast(client)
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "sent"
    hi = body["rendered"]["hi"]
    assert len(hi) <= 480
    assert any("\u0900" <= ch <= "\u097f" for ch in hi), "hi message must be Devanagari"
    assert "Patna" in hi or "पटना" in hi
    assert body["recipient_estimate"] > 0


async def test_alert_feed_and_lang_all(client):
    await _broadcast(client, languages=["hi", "hing", "bn"])
    r = await client.get("/api/alerts?lang=hi&limit=5", headers=_guest_headers())
    assert r.status_code == 200
    items = r.json()["items"]
    assert items
    assert items[0]["messages"] is None  # map only with lang=all or detail
    assert items[0]["message"]

    r = await client.get("/api/alerts?lang=all&limit=5", headers=_guest_headers())
    item = r.json()["items"][0]
    assert item["messages"] is not None
    assert set(["hi", "hing", "bn"]) <= set(item["messages"].keys())

    r = await client.get(f"/api/alerts/{item['id']}", headers=_guest_headers())
    assert r.status_code == 200
    assert len(r.json()["messages"]) >= 3


async def test_admin_overview_shape(client):
    r = await client.get("/api/admin/overview?district=patna", headers=_admin_headers())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["district_id"] == "patna"
    # sos_by_severity keeps STRING keys "1"-"5" (frozen)
    assert set(body["sos_by_severity"].keys()) == {"1", "2", "3", "4", "5"}
    assert body["district_risk"] == 82
    assert body["risk_level"] == "high"
    assert body["volunteers_active"] > 0
    # guest cannot access
    r = await client.get("/api/admin/overview", headers=_guest_headers())
    assert r.status_code == 403


async def test_verify_queue_has_reason(client):
    payload = {"description": "Need drinking water for 20 families in Rajendra Nagar.",
               "district_id": "patna", "client_report_id": str(uuid.uuid4())}
    r = await client.post("/api/sos", json=payload, headers=_guest_headers())
    assert r.status_code == 201
    sid = r.json()["id"]
    r = await client.get("/api/admin/verify-queue?limit=1", headers=_admin_headers())
    total = r.json()["total"]
    r = await client.get(
        f"/api/admin/verify-queue?limit=100&offset={max(0, total - 100)}",
        headers=_admin_headers(),
    )
    mine = [x for x in r.json()["items"] if x["id"] == sid]
    assert mine and mine[0]["reason"] in ("awaiting_verification", "flagged_for_review",
                                          "assessment_failed", "possible_duplicate",
                                          "reporter_flagged", "seed_flagged")


async def test_audit_log_records_actions(client):
    payload = {"description": "Urgent: medicine needed at the relief camp urgently.",
               "district_id": "patna", "client_report_id": str(uuid.uuid4())}
    r = await client.post("/api/sos", json=payload, headers=_guest_headers())
    sid = r.json()["id"]
    r = await client.get("/api/admin/audit?limit=50", headers=_admin_headers())
    assert r.status_code == 200
    entries = r.json()
    assert isinstance(entries, list)
    mine = [e for e in entries if e["target_id"] == sid and e["action"] == "sos.created"]
    assert mine and mine[0]["actor"].startswith("device:")


async def test_safety_flags_admin_and_guest_views(client):
    # admin full list
    r = await client.get("/api/safety/flags", headers=_admin_headers())
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    # guest anonymized counts need ?district=
    r = await client.get("/api/safety/flags", headers=_guest_headers())
    assert r.status_code == 422
    r = await client.get("/api/safety/flags?district=patna", headers=_guest_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["district"] == "patna" and "open_flags" in body


async def test_incident_export_json_and_pdf(client):
    r = await client.get("/api/admin/incidents/patna/export?format=json",
                         headers=_admin_headers())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["district_id"] == "patna"
    assert "sos_reports" in body and "risk" in body
    # Wave 4 (Agent 11): PDF is real now — never a fake download.
    r = await client.get("/api/admin/incidents/patna/export?format=pdf",
                         headers=_admin_headers())
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
    assert "sahayta-incident-patna.pdf" in r.headers["content-disposition"]
    assert len(r.content) > 5000  # real report, not an empty shell


async def test_incident_export_pdf_guards(client):
    # Unknown district -> 404.
    r = await client.get("/api/admin/incidents/nocity/export?format=pdf",
                         headers=_admin_headers())
    assert r.status_code == 404
    # No admin key -> 403.
    r = await client.get("/api/admin/incidents/patna/export?format=pdf",
                         headers=_guest_headers())
    assert r.status_code in (401, 403)


async def test_duplicate_photo_raises_flag_not_drop(client):
    from PIL import Image
    import io

    img = Image.new("RGB", (64, 64), (90, 120, 140))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png = buf.getvalue()

    async def _sos_with_photo(desc):
        files = {"photo": ("a.png", png, "image/png")}
        data = {"description": desc, "district_id": "patna",
                "client_report_id": str(uuid.uuid4())}
        r = await client.post("/api/sos", data=data, files=files,
                              headers=_guest_headers())
        assert r.status_code == 201, r.text
        return r.json()

    first = await _sos_with_photo("Flood water rising near the school gate, children waiting.")
    second = await _sos_with_photo("Flood water rising near the school gate, more families arriving.")
    assert second["needs_review"] is True
    # safety flag exists linking both
    r = await client.get("/api/safety/flags", headers=_admin_headers())
    dups = [f for f in r.json()
            if f["type"] == "possible_duplicate" and second["id"] in f["sos_ids"]]
    assert dups, "expected a possible_duplicate flag for the re-uploaded photo"


async def test_media_upload_and_photo_id_link(client):
    from PIL import Image
    import io

    img = Image.new("RGB", (32, 32), (10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    files = {"photo": ("x.jpg", buf.getvalue(), "image/jpeg")}
    r = await client.post("/api/media", files=files, headers=_guest_headers())
    assert r.status_code == 201, r.text
    pid = r.json()["photo_id"]
    assert r.json()["url"].startswith("/media/sos/")

    # photo_id links into an SOS JSON report
    r = await client.post(
        "/api/sos",
        json={"description": "Waterlogging near the market, knee-deep water rising.",
              "district_id": "patna", "client_report_id": str(uuid.uuid4()),
              "photo_id": pid},
        headers=_guest_headers(),
    )
    assert r.status_code == 201
    assert r.json()["photo_url"] == f"/media/sos/{pid}.jpg"


async def test_users_me_patch(client):
    r = await client.patch("/api/users/me", json={"preferred_lang": "bn"},
                           headers=_guest_headers())
    assert r.status_code == 200, r.text
    assert r.json()["preferred_lang"] == "bn"


async def test_districts_risk_and_forecast(client):
    r = await client.get("/api/districts", headers=_guest_headers())
    assert r.status_code == 200
    assert len(r.json()) == 20

    r = await client.get("/api/districts/patna/risk", headers=_guest_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["risk"] == 82 and body["risk_level"] == "high"
    assert any(f["name"] == "rainfall_24h_mm" for f in body["factors"])
    assert body["weather_source"] == "simulated"
    assert body["advisory"]

    r = await client.get("/api/districts/patna/forecast", headers=_guest_headers())
    assert r.status_code == 200
    hours = r.json()["hours"]
    assert len(hours) == 72
    assert all("risk" in h and "risk_level" in h for h in hours)


async def test_shelters_and_meta(client):
    r = await client.get("/api/shelters?district=patna&has_capacity=true&limit=5",
                         headers=_guest_headers())
    assert r.status_code == 200
    items = r.json()["items"]
    assert items and all(i["is_demo_data"] for i in items)
    assert all(i["occupied"] < i["capacity"] for i in items)

    r = await client.get("/api/health")
    assert r.status_code == 200
    h = r.json()
    assert h["status"] == "ok" and h["llm"] == "fallback" and h["weather"] == "simulated"

    r = await client.get("/api/meta/languages")
    assert len(r.json()["languages"]) == 10

    r = await client.get("/api/warnings/status", headers=_guest_headers())
    ws = r.json()
    assert ws["enabled"] and ws["districts_tracked"] == 20 and ws["last_ingest_ok"]
