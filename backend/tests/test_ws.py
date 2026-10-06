"""Tests: WS event hub — emit, district filtering, replay, client messages.

The hub is exercised directly (no real socket): the HTTP integration path is
covered by asserting that POST /api/sos appends sos.created + sos.assessed to
the hub log, which is exactly what connected sockets get pumped.
"""
from __future__ import annotations

import uuid

import pytest

from app.ws import _ClientState, get_hub, handle_client_message, reset_hub
from tests.conftest import DEMO_DESCRIPTION, _guest_headers


class _FakeWS:
    def __init__(self):
        self.sent = []

    async def send_json(self, obj):
        self.sent.append(obj)


async def test_emit_and_replay():
    reset_hub()
    hub = get_hub()
    await hub.emit("sos.created", {"sos_id": "a", "district_id": "patna"})
    await hub.emit("sos.created", {"sos_id": "b", "district_id": "gaya"})
    missed = await hub.missed_since(1)
    assert [e["event_id"] for e in missed] == [2]
    assert await hub.missed_since(2) == []


async def test_district_filtering():
    reset_hub()
    hub = get_hub()
    client = _ClientState()
    client.districts = {"patna"}
    hub.register(client)
    await hub.emit("sos.created", {"sos_id": "a", "district_id": "patna"})
    await hub.emit("sos.created", {"sos_id": "b", "district_id": "gaya"})
    got = [hub._log[i]["data"]["sos_id"] for i in range(len(hub._log))]
    assert got == ["a", "b"]
    queued = []
    while not client.queue.empty():
        queued.append(client.queue.get_nowait()["data"]["sos_id"])
    assert queued == ["a"]  # gaya filtered out
    hub.unregister(client)


async def test_client_messages():
    reset_hub()
    hub = get_hub()
    client = _ClientState()
    ws = _FakeWS()
    await handle_client_message(hub, client, ws, {"type": "ping"})
    assert ws.sent[-1]["type"] == "pong"
    await handle_client_message(hub, client, ws, {"type": "subscribe", "districts": ["patna"]})
    assert client.districts == {"patna"}
    assert ws.sent[-1]["type"] == "subscribed"
    await hub.emit("risk.updated", {"district_id": "patna", "risk": 82})
    await handle_client_message(hub, client, ws, {"type": "resync", "last_event_id": 0})
    assert any(m.get("type") == "risk.updated" for m in ws.sent)


async def test_post_sos_emits_to_hub_log(client):
    reset_hub()
    from app.ws import get_hub

    hub = get_hub()
    r = await client.post(
        "/api/sos",
        json={"description": DEMO_DESCRIPTION,
              "district_id": "patna", "client_report_id": str(uuid.uuid4())},
        headers=_guest_headers(),
    )
    assert r.status_code == 201
    types = [e["type"] for e in hub._log]
    assert "sos.created" in types
    assert "sos.assessed" in types
    assessed = next(e for e in hub._log if e["type"] == "sos.assessed")
    assert assessed["data"]["severity"] == 4
    assert all("event_id" in e and "ts" in e and "data" in e for e in hub._log)
