"""Sahayta backend — FastAPI application entrypoint (Wave 2, Agent 5).

Run:  uvicorn app.main:app --host 127.0.0.1 --port 8000   (from backend/)
Docs: http://127.0.0.1:8000/docs  (auto-generated OpenAPI; must stay
      consistent with docs/api-contracts.md — Wave 5 verifies)
"""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .routers import admin, alerts, districts, meta, safety, shelters, sos, tasks, uploads, users, volunteers
from .ws import _ClientState, get_hub, handle_client_message

# NOTE (Wave 3, Agent 8 fix): backend/warnings/ is a top-level package named
# `warnings` per the Wave 3 brief, but the stdlib `warnings` module is always
# pre-cached in sys.modules, so `from warnings import scheduler` can never
# resolve to it (it ImportErrors in every interpreter — uvicorn, pytest,
# scripts). Load the package by file location under an unambiguous name
# (`sahayta_warnings`) so its relative imports keep working; the submodules
# only use `app.*` + relative imports, so this is deterministic everywhere.
import importlib.util as _ilu
import sys as _sys
from pathlib import Path as _Path


def _load_warnings_scheduler():  # noqa: D103 - internal loader
    pkg_path = _Path(__file__).resolve().parent.parent / "warnings"
    pkg_spec = _ilu.spec_from_file_location(
        "sahayta_warnings",
        pkg_path / "__init__.py",
        submodule_search_locations=[str(pkg_path)],
    )
    if pkg_spec is None or pkg_spec.loader is None:
        raise ImportError(f"cannot load warnings package from {pkg_path}")
    pkg = _ilu.module_from_spec(pkg_spec)
    _sys.modules["sahayta_warnings"] = pkg
    pkg_spec.loader.exec_module(pkg)
    import importlib as _importlib

    return _importlib.import_module("sahayta_warnings.scheduler")


warnings_scheduler = _load_warnings_scheduler()
del _load_warnings_scheduler, _ilu, _sys, _Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger("sahayta.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.using_default_admin_key:
        log.warning(
            "SAHAYTA_ADMIN_KEY is the demo default — change it in any real deployment."
        )
    # Ensure the media dir exists so /media never 404s on a fresh checkout.
    settings.media_path.mkdir(parents=True, exist_ok=True)
    log.info("Sahayta backend starting (db=%s)", settings.database_url)
    # Early-warning background loop (Wave 3, Agent 7): first cycle is delayed
    # one full ingest interval so startup stays fast; never raises.
    try:
        await warnings_scheduler.start_scheduler(app)
    except Exception:  # noqa: BLE001 — the API must boot even if the loop can't
        log.exception("could not start early-warning scheduler")
    yield
    try:
        await warnings_scheduler.stop_scheduler(app)
    except Exception:  # noqa: BLE001
        log.exception("error stopping early-warning scheduler")
    log.info("Sahayta backend stopping")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Sahayta — Disaster Response OS",
        version="1.0.0-wave2",
        description=(
            "Citizen SOS intake with AI severity estimation, volunteer "
            "coordination, multilingual alerts, and district command view. "
            "Implements docs/api-contracts.md."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for router in (
        sos.router,
        uploads.router,
        shelters.router,
        districts.router,
        volunteers.router,
        tasks.router,
        alerts.router,
        admin.router,
        safety.router,
        users.router,
        meta.router,
    ):
        app.include_router(router)

    # Ensure the media dir exists before mounting (lifespan runs too late for this).
    settings.media_path.mkdir(parents=True, exist_ok=True)
    # Serve uploaded photos at /media/... (photo_url values point here).
    app.mount("/media", StaticFiles(directory=str(settings.media_path)), name="media")

    @app.websocket("/api/stream")
    async def stream(
        ws: WebSocket,
        device_id: str = "",
        last_event_id: int = 0,
        admin_key: str = "",
    ):
        """WS /api/stream — contracts §10.

        Auth: guest+ via ?device_id=. The ?admin_key= query param is a
        DEMO-ONLY convenience (documented in contracts §10); a real deployment
        should use a proper auth ticket (Wave 4 owns that).
        """
        settings = get_settings()
        if not device_id:
            await ws.close(code=4401)
            return
        if admin_key and admin_key != settings.admin_key:
            await ws.close(code=4403)
            return
        await ws.accept()
        hub = get_hub()
        client = _ClientState()
        hub.register(client)
        log.info("WS client connected (device=%s…)", device_id[:8])
        try:
            # Replay missed events from the connect-time cursor.
            if last_event_id:
                for env in await hub.missed_since(last_event_id):
                    if client.accepts(env):
                        await ws.send_json(env)
            sender = _pump(client, ws)
            receiver = _receive(hub, client, ws)
            await _first_done(sender, receiver)
        except WebSocketDisconnect:
            pass
        finally:
            hub.unregister(client)
            log.info("WS client disconnected")

    return app


async def _pump(client: _ClientState, ws: WebSocket):
    import asyncio

    while True:
        env = await client.queue.get()
        await ws.send_json(env)


async def _receive(hub, client: _ClientState, ws: WebSocket):
    while True:
        raw = await ws.receive_text()
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(msg, dict):
            await handle_client_message(hub, client, ws, msg)


async def _first_done(*coros):
    import asyncio

    done, pending = await asyncio.wait(
        [asyncio.create_task(c) for c in coros],
        return_when=asyncio.FIRST_COMPLETED,
    )
    for t in pending:
        t.cancel()
    for t in done:
        t.result()  # re-raise real errors (except CancelledError paths)


app = create_app()
