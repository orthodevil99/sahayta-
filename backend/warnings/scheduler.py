"""Scheduler — the early-warning background loop.

Runs inside the FastAPI lifespan (wired in ``app/main.py``): a single asyncio
task that sleeps ``SAHAYTA_WEATHER_INGEST_MINUTES`` (default 15) between
cycles. The FIRST cycle is delayed by one full interval so app startup stays
fast and tests (which boot the app via ASGITransport) are never disturbed by
a surprise ingest.

Each cycle:
    ingest_all()      → trailing-24h weather per district (live or simulated)
    recompute_all()   → DistrictRisk rows via the shared v1 formula
    process_crossings() → automatic broadcasts on threshold crossings

Single-worker assumption: with multiple uvicorn workers each would run the
loop — deploy v1 with ``--workers 1`` (documented in README.md).

``run_cycle()`` is also importable for manual/ops triggering::

    cd backend && python -c "import asyncio; from warnings.scheduler import run_cycle; print(asyncio.run(run_cycle()))"
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import FastAPI

from app.config import get_settings
from app.database import get_session_factory
from .ingest import ingest_all
from .recompute import recompute_all
from .thresholds import process_crossings

log = logging.getLogger("sahayta.warnings.scheduler")


async def run_cycle(district_ids: list[str] | None = None) -> dict[str, Any]:
    """One full early-warning pass. Opens its own DB session (background task)."""
    settings = get_settings()
    if settings.districts.strip().lower() not in ("", "all") and district_ids is None:
        district_ids = [s.strip() for s in settings.districts.split(",") if s.strip()]
    summary: dict[str, Any] = {
        "districts": 0, "live": 0, "simulated": 0,
        "risks_recomputed": 0, "broadcasts_sent": 0, "errors": [],
    }
    factory = get_session_factory()
    async with factory() as session:
        try:
            results = await ingest_all(session, settings, district_ids)
        except Exception as exc:  # noqa: BLE001 — a cycle must never die loudly
            log.exception("ingest cycle failed")
            summary["errors"].append(f"ingest: {exc}")
            return summary
        summary["districts"] = len(results)
        summary["live"] = sum(1 for r in results if r.source == "live")
        summary["simulated"] = sum(1 for r in results if r.source == "simulated")
        try:
            recomputed = await recompute_all(session, district_ids)
            summary["risks_recomputed"] = sum(1 for new, _ in recomputed if new)
            sent = await process_crossings(session, recomputed)
            summary["broadcasts_sent"] = len(sent)
        except Exception as exc:  # noqa: BLE001
            log.exception("recompute/threshold cycle failed")
            summary["errors"].append(f"recompute: {exc}")
    log.info("warning cycle complete: %s", summary)
    return summary


async def _loop(stop: asyncio.Event) -> None:
    settings = get_settings()
    interval = max(1, settings.weather_ingest_minutes) * 60
    log.info("early-warning scheduler started (interval=%ds, mode=%s)",
             interval, settings.weather_mode)
    try:
        # Delayed first cycle: keep startup fast, never surprise tests.
        await asyncio.wait_for(stop.wait(), timeout=interval)
        while not stop.is_set():
            try:
                await run_cycle()
            except Exception:  # noqa: BLE001 — the loop itself must not die
                log.exception("warning cycle crashed; continuing")
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
    except asyncio.CancelledError:
        pass
    log.info("early-warning scheduler stopped")


async def start_scheduler(app: FastAPI) -> asyncio.Task | None:
    """Start the background loop; returns the task (stored on app.state)."""
    stop = asyncio.Event()
    task = asyncio.create_task(_loop(stop), name="sahayta-warning-loop")
    app.state.warning_stop = stop
    app.state.warning_task = task
    return task


async def stop_scheduler(app: FastAPI) -> None:
    stop: asyncio.Event | None = getattr(app.state, "warning_stop", None)
    task: asyncio.Task | None = getattr(app.state, "warning_task", None)
    if stop is not None:
        stop.set()
    if task is not None:
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=10)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            task.cancel()
