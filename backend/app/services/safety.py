"""Safety guardrails service — dedup, misinformation heuristics, spam bursts.

All functions here are *triage aids*: they raise ``SafetyFlag`` rows for human
review. Nothing in this module silently drops, hides, or auto-rejects a report.
See ``docs/safety.md`` for the honest capability model.

Flag types (``SafetyFlag.type``):
- ``possible_duplicate`` — same photo re-uploaded (hash + time + geo window).
- ``conflicting_reports`` — a severe report contradicted by several mild ones
  nearby (or vice versa). Heuristic, not truth detection.
- ``spam_burst`` — one device filing many reports in a short window.
- ``reporter_flag`` — reserved for manual admin flags (Wave 4+: unused by
  automation; admins create these via the verify queue notes).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..geo import haversine_km
from ..models import SafetyFlag, SOSReport

log = logging.getLogger("sahayta.services.safety")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def raise_flag(
    session: AsyncSession,
    *,
    type: str,
    sos_ids: list[str],
    district_id: str | None,
    evidence: str,
) -> SafetyFlag:
    """Create an open flag, unless an identical open one already exists.

    "Identical" = same type and same set of sos_ids. This keeps repeated
    triggers (e.g. every request in a spam burst) from flooding the flag table.
    """
    wanted = sorted(set(sos_ids))
    existing = (
        await session.execute(
            select(SafetyFlag).where(
                SafetyFlag.type == type,
                SafetyFlag.status == "open",
            )
        )
    ).scalars().all()
    for flag in existing:
        if sorted(flag.sos_ids or []) == wanted:
            return flag
    flag = SafetyFlag(
        type=type,
        sos_ids=wanted,
        district_id=district_id,
        evidence=evidence,
        status="open",
    )
    session.add(flag)
    await session.flush()
    log.info("safety flag raised: %s on %s", type, wanted)
    return flag


async def check_duplicate_photo(
    session: AsyncSession,
    settings: Settings,
    *,
    photo_hash: str | None,
    new_id: str,
    district_id: str | None,
    lat: float | None,
    lon: float | None,
) -> str | None:
    """Failure-injection #4: same photo re-uploaded -> ``possible_duplicate``.

    Match rule: identical ``photo_hash`` AND the earlier report is within
    ``safety_dup_window_hours`` AND (when both have coordinates) within
    ``safety_dup_radius_km``. The hash alone is not enough — the same stock
    photo of "flooded street" reused a month later in another district is a
    different (though still review-worthy) situation; the window keeps the
    flag precise for true re-uploads.

    Returns an evidence string when a duplicate is found, else None.
    The new report is NEVER dropped — the caller marks it for review.
    """
    if not photo_hash:
        return None
    cutoff = _utcnow() - timedelta(hours=settings.safety_dup_window_hours)
    candidates = (
        await session.execute(
            select(SOSReport).where(
                SOSReport.photo_hash == photo_hash,
                SOSReport.id != new_id,
                SOSReport.created_at >= cutoff,
            )
        )
    ).scalars().all()
    for existing in candidates:
        if (
            lat is not None and lon is not None
            and existing.lat is not None and existing.lon is not None
        ):
            dist = haversine_km(lat, lon, existing.lat, existing.lon)
            if dist > settings.safety_dup_radius_km:
                continue
        evidence = (
            f"photo_hash match {photo_hash[:16]} with report {existing.id} "
            f"(district {existing.district_id}, filed {existing.created_at})"
        )
        await raise_flag(
            session,
            type="possible_duplicate",
            sos_ids=[new_id, existing.id],
            district_id=district_id,
            evidence=evidence,
        )
        return evidence
    return None


async def check_conflicting_reports(
    session: AsyncSession,
    settings: Settings,
    *,
    sos: SOSReport,
) -> str | None:
    """Misinformation triage heuristic — ``conflicting_reports``.

    Rule (documented honestly in docs/safety.md; this is NOT truth detection):
    - a new report with severity >= 4 is contradicted by >=
      ``safety_conflict_min_cluster`` reports with severity <= 2 filed within
      ``safety_conflict_hours`` and ``safety_conflict_radius_km`` of it, or
    - a new report with severity <= 2 lands amid >= ``safety_conflict_min_cluster``
      reports with severity >= 4 in the same window.

    Either direction raises one flag for human review. Returns evidence or None.
    """
    if sos.severity is None or sos.lat is None or sos.lon is None:
        return None
    if sos.severity >= 4:
        want_low, direction = True, "severe report amid mild ones"
    elif sos.severity <= 2:
        want_low, direction = False, "mild report amid severe ones"
    else:
        return None  # severity 3 is the murky middle — no heuristic fires.

    cutoff = _utcnow() - timedelta(hours=settings.safety_conflict_hours)
    # Bounding-box prefilter in SQL (SQLite has no PostGIS), exact check in Python.
    import math

    lat_window = settings.safety_conflict_radius_km / 111.0
    lon_window = settings.safety_conflict_radius_km / (
        111.0 * max(0.2, abs(math.cos(math.radians(sos.lat))))
    )
    rows = (
        await session.execute(
            select(SOSReport).where(
                SOSReport.id != sos.id,
                SOSReport.created_at >= cutoff,
                SOSReport.lat.isnot(None),
                SOSReport.lon.isnot(None),
                SOSReport.lat.between(sos.lat - lat_window, sos.lat + lat_window),
                SOSReport.lon.between(sos.lon - lon_window, sos.lon + lon_window),
                SOSReport.severity.isnot(None),
            )
        )
    ).scalars().all()
    near = [
        r for r in rows
        if haversine_km(sos.lat, sos.lon, r.lat, r.lon) <= settings.safety_conflict_radius_km
    ]
    lows = [r.id for r in near if (r.severity or 0) <= 2]
    highs = [r.id for r in near if (r.severity or 0) >= 4]
    cluster = lows if want_low else highs
    if len(cluster) >= settings.safety_conflict_min_cluster:
        evidence = (
            f"{direction}: report {sos.id} (severity {sos.severity}) vs "
            f"{len(cluster)} contradicting reports within "
            f"{settings.safety_conflict_radius_km} km / {settings.safety_conflict_hours} h: "
            f"{', '.join(cluster[:5])}{'...' if len(cluster) > 5 else ''}"
        )
        await raise_flag(
            session,
            type="conflicting_reports",
            sos_ids=[sos.id, *cluster],
            district_id=sos.district_id,
            evidence=evidence,
        )
        return evidence
    return None


async def check_spam_burst(
    session: AsyncSession,
    settings: Settings,
    *,
    device_id: str | None,
    district_id: str | None,
) -> str | None:
    """Abuse prevention: N reports from one device in M minutes.

    When the count (including the report about to be filed) reaches
    ``safety_spam_threshold`` within ``safety_spam_window_minutes``, raise a
    single ``spam_burst`` flag and return evidence so the caller can throttle
    (429) the request. The already-filed reports stay visible; nothing is
    deleted.
    """
    if not device_id:
        return None
    cutoff = _utcnow() - timedelta(minutes=settings.safety_spam_window_minutes)
    count = (
        await session.execute(
            select(func.count())
            .select_from(SOSReport)
            .where(
                SOSReport.reporter_device_id == device_id,
                SOSReport.created_at >= cutoff,
            )
        )
    ).scalar_one()
    # +1 for the report currently being filed.
    if count + 1 >= settings.safety_spam_threshold:
        evidence = (
            f"device {device_id} filed {count + 1} reports in "
            f"{settings.safety_spam_window_minutes} min "
            f"(threshold {settings.safety_spam_threshold})"
        )
        await raise_flag(
            session,
            type="spam_burst",
            sos_ids=[],
            district_id=district_id,
            evidence=evidence,
        )
        return evidence
    return None


async def reporter_trust(
    session: AsyncSession, device_id: str | None
) -> dict[str, int | float | str]:
    """Device-level trust summary for the verify queue (reporter weighting).

    Counts lifetime reports by verification outcome. Tiers:
    - ``trusted``: >= 5 verified and zero rejected/duplicates
    - ``flagged``: >= 2 rejected or any spam_burst flag on file
    - ``new``: < 3 reports filed
    - ``standard``: everything else
    """
    if not device_id:
        return {"reports": 0, "verified": 0, "rejected": 0, "tier": "new"}
    rows = (
        await session.execute(
            select(SOSReport.status, func.count())
            .where(SOSReport.reporter_device_id == device_id)
            .group_by(SOSReport.status)
        )
    ).all()
    by_status = {s: n for s, n in rows}
    total = sum(by_status.values())
    verified = by_status.get("verified", 0)
    rejected = by_status.get("rejected", 0)
    spam_flags = (
        await session.execute(
            select(func.count())
            .select_from(SafetyFlag)
            .where(
                SafetyFlag.type == "spam_burst",
                SafetyFlag.evidence.like(f"%{device_id}%"),
            )
        )
    ).scalar_one()
    if verified >= 5 and rejected == 0 and by_status.get("duplicate", 0) == 0:
        tier = "trusted"
    elif rejected >= 2 or spam_flags > 0:
        tier = "flagged"
    elif total < 3:
        tier = "new"
    else:
        tier = "standard"
    return {
        "reports": total,
        "verified": verified,
        "rejected": rejected,
        "tier": tier,
    }
