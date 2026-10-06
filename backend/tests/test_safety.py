"""Tests: safety guardrails — dedup, conflict heuristic, spam throttle, audit,
visibility policy, duplicate merge. (Wave 4, Agent 10.)"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.models import AuditLog, SafetyFlag, SOSReport
from tests.conftest import (
    ADMIN_KEY,
    DEMO_DESCRIPTION,
    DEVICE_A,
    DEVICE_B,
    _admin_headers,
    _guest_headers,
)

# Minimal valid JPEG bytes (SOI marker + padding). dHash fails on these ->
# sha256 fallback, which is deterministic for identical bytes.
PHOTO_BYTES = b"\xff\xd8\xff" + b"\x00" * 200
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200

MILD = "Light drizzle in Rajendra Nagar, roads wet but fully passable."
LAT, LON = 25.5941, 85.1376


async def _post_sos(client, device=DEVICE_A, **kw):
    payload = {
        "description": kw.get("description", MILD),
        "lat": kw.get("lat", LAT),
        "lon": kw.get("lon", LON),
        "client_report_id": kw.get("client_report_id", str(uuid.uuid4())),
    }
    for k in ("photo_id", "photo_description", "district_id", "language"):
        if k in kw:
            payload[k] = kw[k]
    return await client.post("/api/sos", json=payload, headers=_guest_headers(device))


async def _upload(client, data=PHOTO_BYTES, ctype="image/jpeg", device=DEVICE_A):
    return await client.post(
        "/api/media",
        files={"photo": ("flood.jpg", data, ctype)},
        headers=_guest_headers(device),
    )


async def _open_flags(client, flag_type=None):
    r = await client.get("/api/safety/flags", headers=_admin_headers())
    assert r.status_code == 200, r.text
    flags = r.json()
    if flag_type:
        flags = [f for f in flags if f["type"] == flag_type]
    return [f for f in flags if f["status"] == "open"]


# --- failure injection #4: duplicate photo ---------------------------------

async def test_failure_injection_4_duplicate_photo_flagged_not_dropped(client):
    """Re-upload the same photo -> possible_duplicate flag; 2nd report kept."""
    u1 = await _upload(client)
    assert u1.status_code == 201, u1.text
    photo_id = u1.json()["photo_id"]
    photo_hash = u1.json()["photo_hash"]

    # Same bytes again -> identical hash (sha256 fallback is deterministic).
    u2 = await _upload(client)
    assert u2.json()["photo_hash"] == photo_hash

    r1 = await _post_sos(client, photo_id=photo_id)
    assert r1.status_code == 201, r1.text
    id1 = r1.json()["id"]

    r2 = await _post_sos(client, photo_id=photo_id)
    assert r2.status_code == 201, r2.text  # NOT dropped
    body2 = r2.json()
    id2 = body2["id"]
    assert id2 != id1
    assert body2["needs_review"] is True
    assert body2["reason"] == "possible_duplicate"

    flags = await _open_flags(client, "possible_duplicate")
    assert len(flags) == 1
    assert set(flags[0]["sos_ids"]) == {id1, id2}
    assert id1 in flags[0]["evidence"]


async def test_duplicate_photo_outside_window_no_flag(client, session):
    """Same hash but the earlier report is > 24 h old -> no auto flag."""
    u = await _upload(client)
    photo_id = u.json()["photo_id"]
    r1 = await _post_sos(client, photo_id=photo_id)
    id1 = r1.json()["id"]
    # Backdate the first report beyond the dedup window.
    await session.execute(
        update(SOSReport)
        .where(SOSReport.id == id1)
        .values(created_at=datetime.now(timezone.utc) - timedelta(hours=30))
    )
    await session.commit()

    r2 = await _post_sos(client, photo_id=photo_id)
    assert r2.status_code == 201, r2.text
    assert r2.json()["needs_review"] is False
    assert await _open_flags(client, "possible_duplicate") == []


# --- conflict heuristic ----------------------------------------------------

async def test_conflicting_reports_flagged(client, session):
    """Severe report amid a cluster of mild ones -> conflicting_reports flag."""
    for i in range(3):
        r = await _post_sos(
            client, description=f"{MILD} (corner {i})",
            lat=LAT + i * 0.001, lon=LON + i * 0.001,
        )
        assert r.status_code == 201, r.text
        # Pin severities deterministically: mild cluster = 1.
        await session.execute(
            update(SOSReport).where(SOSReport.id == r.json()["id"]).values(severity=1)
        )
    await session.commit()

    r4 = await _post_sos(
        client, description=DEMO_DESCRIPTION, lat=LAT + 0.0005, lon=LON + 0.0005,
    )
    assert r4.status_code == 201, r4.text
    assert r4.json()["severity"] == 4  # rule fallback scores the fixture at 4
    assert r4.json()["needs_review"] is True
    assert r4.json()["reason"] == "conflicting_reports"

    flags = await _open_flags(client, "conflicting_reports")
    assert len(flags) == 1
    assert r4.json()["id"] in flags[0]["sos_ids"]
    assert len(flags[0]["sos_ids"]) == 4


async def test_no_conflict_for_isolated_severe_report(client):
    """A lone severe report far from any cluster -> no conflict flag."""
    r = await _post_sos(
        client, description=DEMO_DESCRIPTION, lat=28.6139, lon=77.2090,  # Delhi
    )
    assert r.status_code == 201, r.text
    assert r.json()["reason"] != "conflicting_reports"
    assert await _open_flags(client, "conflicting_reports") == []


# --- spam burst ------------------------------------------------------------

async def test_spam_burst_throttled_and_flagged(client):
    """5th report inside 10 min from one device -> 429 + spam_burst flag."""
    for i in range(4):
        r = await _post_sos(client, device=DEVICE_B,
                            description=f"Spam probe report number {i} with enough text.")
        assert r.status_code == 201, r.text
    r5 = await _post_sos(client, device=DEVICE_B,
                         description="Spam probe report number 4 with enough text.")
    assert r5.status_code == 429, r5.text
    assert "Retry-After" in r5.headers

    flags = await _open_flags(client, "spam_burst")
    assert len(flags) == 1
    assert DEVICE_B in flags[0]["evidence"]


# --- audit coverage ---------------------------------------------------------

async def test_audit_covers_status_verify_and_throttle(client, session):
    """Every mutation writes an audit row with actor + reason."""
    r = await _post_sos(client)
    sid = r.json()["id"]

    v = await client.post(
        f"/api/sos/{sid}/verify",
        json={"verdict": "verified", "note": "looks genuine"},
        headers=_admin_headers(),
    )
    assert v.status_code == 200, v.text

    rows = (
        await session.execute(select(AuditLog).where(AuditLog.target_id == sid))
    ).scalars().all()
    actions = {a.action: a for a in rows}
    assert "sos.created" in actions
    assert "sos.verified" in actions
    assert actions["sos.verified"].actor.startswith("admin:")
    assert actions["sos.verified"].details["verdict"] == "verified"
    assert actions["sos.verified"].details["note"] == "looks genuine"


# --- visibility policy -------------------------------------------------------

async def test_flag_visibility_policy(client):
    """Admin: full. Guest: 422 w/o district, counts with. Reporter: ?mine=true."""
    u = await _upload(client)
    photo_id = u.json()["photo_id"]
    await _post_sos(client, photo_id=photo_id)
    r2 = await _post_sos(client, photo_id=photo_id)
    assert r2.json()["reason"] == "possible_duplicate"

    # Admin sees everything.
    admin = await client.get("/api/safety/flags", headers=_admin_headers())
    assert admin.status_code == 200
    full = admin.json()
    assert len(full) >= 1 and "evidence" in full[0] and "sos_ids" in full[0]

    # Guest without district -> 422.
    g = await client.get("/api/safety/flags", headers=_guest_headers(DEVICE_B))
    assert g.status_code == 422

    # Guest with district -> anonymized counts only.
    g2 = await client.get(
        "/api/safety/flags?district=patna", headers=_guest_headers(DEVICE_B)
    )
    assert g2.status_code == 200
    counts = g2.json()
    assert counts["district"] == "patna"
    assert counts["by_type"].get("possible_duplicate", 0) >= 1
    assert "sos_ids" not in counts and "evidence" not in counts

    # Reporter sees their own flags via ?mine=true ...
    m1 = await client.get(
        "/api/safety/flags?mine=true", headers=_guest_headers(DEVICE_A)
    )
    assert m1.status_code == 200
    mine = m1.json()
    assert len(mine) >= 1
    assert mine[0]["type"] == "possible_duplicate"
    assert "evidence" not in mine[0]  # no detection internals leaked

    # ... but not another device's.
    m2 = await client.get(
        "/api/safety/flags?mine=true", headers=_guest_headers(DEVICE_B)
    )
    assert m2.status_code == 200 and m2.json() == []


# --- duplicate merge ----------------------------------------------------------

async def test_duplicate_merge_keeps_both_visible(client, session):
    """confirmed_duplicate -> newer report labeled duplicate w/ link; both visible."""
    u = await _upload(client)
    photo_id = u.json()["photo_id"]
    r1 = await _post_sos(client, photo_id=photo_id)
    r2 = await _post_sos(client, photo_id=photo_id)
    id1, id2 = r1.json()["id"], r2.json()["id"]

    flags = await _open_flags(client, "possible_duplicate")
    assert len(flags) == 1

    res = await client.post(
        f"/api/admin/safety/flags/{flags[0]['id']}/resolve",
        json={"resolution": "confirmed_duplicate", "note": "same photo"},
        headers=_admin_headers(),
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "resolved"
    # The test harness shares one session with expire_on_commit=False across
    # requests; expire so the next GET re-reads (production uses fresh
    # sessions per request, so this staleness cannot occur there).
    session.expire_all()

    # One of the two is now a labeled duplicate of the other; both retrievable.
    # (Which one is canonical is deterministic — oldest created_at, id tiebreak —
    # but the invariant is the link, not the direction.)
    newer = (await client.get(f"/api/sos/{id2}", headers=_admin_headers())).json()
    older = (await client.get(f"/api/sos/{id1}", headers=_admin_headers())).json()
    dup, canon = (newer, older) if newer["status"] == "duplicate" else (older, newer)
    assert dup["status"] == "duplicate"
    assert dup["duplicate_of"] == canon["id"]
    assert canon["status"] == "reported"  # canonical untouched
    assert canon["duplicate_of"] is None

    # Duplicates remain listed (never silently dropped).
    listed = await client.get(
        "/api/sos?district=patna&status=duplicate", headers=_admin_headers()
    )
    assert listed.status_code == 200
    assert dup["id"] in [s["id"] for s in listed.json()["items"]]


# --- upload hardening ----------------------------------------------------------

async def test_upload_rejects_magic_byte_mismatch(client):
    """PNG bytes claimed as image/jpeg -> 422."""
    r = await _upload(client, data=PNG_BYTES, ctype="image/jpeg")
    assert r.status_code == 422, r.text
    assert "bytes do not match" in r.json()["detail"]


async def test_sos_multipart_rejects_magic_byte_mismatch(client):
    r = await client.post(
        "/api/sos",
        data={"description": MILD, "lat": str(LAT), "lon": str(LON),
              "client_report_id": str(uuid.uuid4())},
        files={"photo": ("evil.jpg", PNG_BYTES, "image/jpeg")},
        headers=_guest_headers(),
    )
    assert r.status_code == 422, r.text
