"""Realtime event hub — WS /api/stream (docs/api-contracts.md §10).

In-process pub/sub (fits the modular-monolith decision from Agent 1):
- Every emitted event gets a monotonically increasing ``event_id`` and is
  appended to a bounded replay log (last 500).
- Each connection may ``subscribe`` to a district filter; unsubscribed
  connections receive everything (except admin-only scoping, which v1 does
  not need — all events are district-scoped or public).
- Reconnect: client sends ``last_event_id`` as a query param on connect OR a
  ``{"type": "resync", "last_event_id": n}`` message (the frontend uses the
  message form); missed events are replayed in order.

Auth: guest+ via ``?device_id=``; admin events note the demo-only
``?admin_key=`` query param (see contracts §10 — a real deployment should use
a proper auth ticket; Wave 4 owns that).
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

log = logging.getLogger("sahayta.ws")

REPLAY_BUFFER = 500


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventHub:
    """Process-wide hub. One instance is created at app startup."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._next_id = 0
        self._log: deque[dict[str, Any]] = deque(maxlen=REPLAY_BUFFER)
        self._clients: set["_ClientState"] = set()

    async def emit(self, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        """Broadcast an event to all connected clients. Returns the envelope."""
        async with self._lock:
            self._next_id += 1
            envelope = {
                "event_id": self._next_id,
                "type": event_type,
                "ts": _now_iso(),
                "data": data,
            }
            self._log.append(envelope)
            clients = list(self._clients)
        for client in clients:
            if client.accepts(envelope):
                client.queue.put_nowait(envelope)
        return envelope

    async def missed_since(self, last_event_id: int) -> list[dict[str, Any]]:
        async with self._lock:
            return [e for e in self._log if e["event_id"] > last_event_id]

    def register(self, client: "_ClientState") -> None:
        self._clients.add(client)

    def unregister(self, client: "_ClientState") -> None:
        self._clients.discard(client)


class _ClientState:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.districts: set[str] | None = None  # None = all

    def accepts(self, envelope: dict[str, Any]) -> bool:
        if not self.districts:
            return True
        data = envelope.get("data") or {}
        ids: list[str] = []
        if isinstance(data.get("district_ids"), list):
            ids = [str(x) for x in data["district_ids"]]
        elif data.get("district_id"):
            ids = [str(data["district_id"])]
        if not ids:
            return True  # event carries no district scope -> deliver
        return any(i in self.districts for i in ids)


_hub: EventHub | None = None


def get_hub() -> EventHub:
    global _hub
    if _hub is None:
        _hub = EventHub()
    return _hub


def reset_hub() -> None:
    """Test hook."""
    global _hub
    _hub = None


async def handle_client_message(
    hub: EventHub, client: _ClientState, ws: WebSocket, raw: dict[str, Any]
) -> None:
    """Handle one client->server message. Never raises to the socket loop."""
    try:
        mtype = raw.get("type")
        if mtype == "ping":
            await ws.send_json({"event_id": 0, "type": "pong", "ts": _now_iso(), "data": {}})
        elif mtype == "subscribe":
            districts = raw.get("districts") or []
            client.districts = {str(d) for d in districts}
            await ws.send_json(
                {
                    "event_id": 0,
                    "type": "subscribed",
                    "ts": _now_iso(),
                    "data": {"districts": sorted(client.districts)},
                }
            )
        elif mtype == "resync":
            last_id = int(raw.get("last_event_id") or 0)
            for env in await hub.missed_since(last_id):
                if client.accepts(env):
                    await ws.send_json(env)
        else:
            log.debug("unknown WS client message type: %r", mtype)
    except Exception as exc:  # noqa: BLE001 — a bad client message must not kill the socket
        log.warning("WS message handling failed: %s", exc)
