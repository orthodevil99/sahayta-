"""Tests: SOS intake, filters, transitions, verify, flag, assess."""
from __future__ import annotations

import uuid

import pytest

from tests.conftest import (
    ADMIN_KEY,
    DEMO_DESCRIPTION,
    DEVICE_A,
    DEVICE_B,
    _admin_headers,
    _guest_headers,
)

DESC = "Water entered homes in two lanes of Kankarbagh, knee-deep on the road."


async def _post_sos(client, **kw):
    payload = {
        "description": kw.get("description", DESC),
        "lat": 25.5941,
        "lon": 85.1376,
        "client_report_id": kw.get("client_report_id", str(uuid.uuid4())),
    }
    for k in ("district_id", "language", "reporter_name", "photo_description"):
        if k in kw:
            payload[k] = kw[k]
    return await client.post("/api/sos", json=payload, headers=_guest_headers(kw.get("device", DEVICE_A)))


async def test_create_sos_json_201(client):
    r = await _post_sos(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "reported"
    assert body["district_id"] == "patna"  # nearest-district resolution
    assert body["severity"] in (1, 2, 3, 4, 5)
    assert body["assessment"]["model"] == "rule-fallback-v1"
    assert body["client_report_id"]


async def test_create_sos_multipart(client):
    data = {
        "description": DESC,
        "lat": "25.5941",
        "lon": "85.1376",
        "client_report_id": str(uuid.uuid4()),
    }
    files = {"photo": ("flood.jpg", b"\xff\xd8\xff" + b"\x00" * 100, "image/jpeg")}
    r = await client.post("/api/sos", data=data, files=files, headers=_guest_headers())
    # bytes are not a decodable image -> dhash falls back to sha256: prefix (honest)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["photo_url"].startswith("/media/sos/")
    assert body["photo_hash"].startswith("sha256:")


async def test_idempotent_replay_returns_200_same_id(client):
    cid = str(uuid.uuid4())
    r1 = await _post_sos(client, client_report_id=cid)
    r2 = await _post_sos(client, client_report_id=cid)
    assert r1.status_code == 201
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]


async def test_sos_validation_errors(client):
    # no geo at all
    r = await client.post(
        "/api/sos",
        json={"description": DESC, "client_report_id": str(uuid.uuid4())},
        headers=_guest_headers(),
    )
    assert r.status_code == 422
    # description too short
    r = await client.post(
        "/api/sos",
        json={"description": "help", "lat": 25.5, "lon": 85.1,
              "client_report_id": str(uuid.uuid4())},
        headers=_guest_headers(),
    )
    assert r.status_code == 422
    # missing device id
    r = await client.post(
        "/api/sos",
        json={"description": DESC, "lat": 25.5, "lon": 85.1,
              "client_report_id": str(uuid.uuid4())},
    )
    assert r.status_code == 401


async def test_intake_never_fails_when_ai_breaks(client, monkeypatch):
    import app.ai_client as ai

    def _boom(*a, **k):
        raise RuntimeError("llm exploded")

    monkeypatch.setattr(ai, "assess_and_route", _boom)
    r = await _post_sos(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["severity"] is None
    assert body["needs_review"] is True
    assert body["assessment"] is None


async def test_list_filters_and_sort(client):
    await _post_sos(client, district_id="patna",
                    description="Waist-deep water, residents on rooftops, urgent rescue needed now.")
    r = await client.get("/api/sos?district=patna&sort=severity&limit=5",
                         headers=_guest_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    sevs = [x["severity"] for x in body["items"] if x["severity"]]
    assert sevs == sorted(sevs, reverse=True), "sort=severity must be descending"

    r = await client.get("/api/sos?district=patna&severity_min=4",
                         headers=_guest_headers())
    assert all((x["severity"] or 0) >= 4 for x in r.json()["items"])


async def test_status_transitions_and_guards(client):
    r = await _post_sos(client, device=DEVICE_B)
    sid = r.json()["id"]
    hdr_b = _guest_headers(DEVICE_B)

    # reporter device can transition reported -> verified
    r = await client.patch(f"/api/sos/{sid}", json={"status": "verified"}, headers=hdr_b)
    assert r.status_code == 200
    assert r.json()["status"] == "verified"

    # illegal: verified -> reported
    r = await client.patch(f"/api/sos/{sid}", json={"status": "reported"}, headers=hdr_b)
    assert r.status_code == 400

    # another device cannot transition (403)
    r = await client.patch(f"/api/sos/{sid}", json={"status": "help_on_way"},
                           headers=_guest_headers(DEVICE_A))
    assert r.status_code == 403

    # admin can
    r = await client.patch(f"/api/sos/{sid}", json={"status": "help_on_way"},
                           headers=_admin_headers())
    assert r.status_code == 200


async def test_verify_endpoint(client):
    r = await _post_sos(client)
    sid = r.json()["id"]
    # guest cannot verify
    r = await client.post(f"/api/sos/{sid}/verify",
                          json={"verdict": "verified"}, headers=_guest_headers())
    assert r.status_code == 403
    # admin verifies
    r = await client.post(f"/api/sos/{sid}/verify",
                          json={"verdict": "verified", "note": "field team confirmed"},
                          headers=_admin_headers())
    assert r.status_code == 200
    assert r.json()["status"] == "verified"
    # duplicate verdict requires duplicate_of
    r = await client.post(f"/api/sos/{sid}/verify",
                          json={"verdict": "duplicate"}, headers=_admin_headers())
    assert r.status_code == 422


async def test_flag_sos(client):
    r = await _post_sos(client)
    sid = r.json()["id"]
    r = await client.post(f"/api/sos/{sid}/flag",
                          json={"reason": "spam", "note": "looks fake"},
                          headers=_guest_headers())
    assert r.status_code == 201
    assert r.json()["status"] == "received"
    # flagged report lands in the verify queue with a reason
    # (queue is oldest-first; the new item is on the last page)
    r = await client.get("/api/admin/verify-queue?limit=1", headers=_admin_headers())
    total = r.json()["total"]
    r = await client.get(
        f"/api/admin/verify-queue?limit=100&offset={max(0, total - 100)}",
        headers=_admin_headers(),
    )
    mine = [x for x in r.json()["items"] if x["id"] == sid]
    assert mine and mine[0]["reason"] == "reporter_flagged"


async def test_assess_endpoint_demo_fixture_scores_4(client):
    r = await client.post(
        "/api/assess",
        json={"description": DEMO_DESCRIPTION, "language": "hi",
              "lat": 25.5941, "lon": 85.1376},
        headers=_guest_headers(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["severity"] == 4
    assert body["category"] == "rescue"
    assert body["priority"] == "critical"
    assert body["suggested_skills"] == ["rescue", "driving"]
    assert set(["road_submerged", "residential"]) <= set(body["area_tags"])
    assert body["model"] == "rule-fallback-v1"
    assert "घुटनों तक पानी" in body["rationale"]
    assert body["latency_ms"] < 300


async def test_post_sos_demo_fixture_scores_4(client):
    r = await _post_sos(client, description=DEMO_DESCRIPTION, district_id="patna")
    assert r.status_code == 201
    body = r.json()
    assert body["severity"] == 4
    assert body["assessment"]["severity"] == 4
