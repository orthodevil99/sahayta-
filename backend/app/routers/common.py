"""Shared router helpers — serialization, audit, pagination, transitions."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .. import schemas as S
from ..models import AuditLog, SOSReport, Task, Volunteer
from ..ws import get_hub

log = logging.getLogger("sahayta.routers")

# --- status transition matrices (docs/api-contracts.md, frozen) ---

SOS_TRANSITIONS: dict[str, set[str]] = {
    "reported": {"verified", "duplicate", "rejected"},
    "verified": {"help_on_way", "resolved", "rejected"},
    "help_on_way": {"resolved"},
    "resolved": set(),
    "duplicate": set(),
    "rejected": set(),
}

TASK_TRANSITIONS: dict[str, set[str]] = {
    "assigned": {"accepted", "declined", "cancelled"},
    "accepted": {"en_route", "declined", "cancelled"},
    "en_route": {"completed", "cancelled"},
    "completed": set(),
    "declined": set(),
    "cancelled": set(),
}

ACTIVE_TASK_STATUSES = {"assigned", "accepted", "en_route"}
ACTIVE_SOS_STATUSES = {"reported", "verified", "help_on_way"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def verify_reason_for(sos: SOSReport) -> str:
    """Machine-readable reason for the verify queue (Wave 2 amendment #9)."""
    if sos.needs_review_reason:
        return sos.needs_review_reason
    if sos.needs_review:
        return "flagged_for_review"
    return "awaiting_verification"


async def log_audit(
    session: AsyncSession,
    actor: str,
    action: str,
    target_type: str,
    target_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditLog(
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
        )
    )


async def emit(event_type: str, data: dict[str, Any]) -> None:
    """Fire-and-forget WS broadcast — never breaks the request on failure."""
    try:
        await get_hub().emit(event_type, data)
    except Exception as exc:  # noqa: BLE001 — realtime must not break REST
        log.warning("WS emit %s failed: %s", event_type, exc)


def sos_compact(sos: SOSReport) -> dict[str, Any]:
    """Compact SOS payload for WS sos.created (no nested assessment)."""
    return {
        "id": sos.id,
        "client_report_id": sos.client_report_id,
        "description": sos.description,
        "language": sos.language,
        "category": sos.category,
        "severity": sos.severity,
        "priority": sos.priority,
        "status": sos.status,
        "lat": sos.lat,
        "lon": sos.lon,
        "district_id": sos.district_id,
        "photo_url": sos.photo_url,
        "created_at": (sos.created_at or utcnow()).isoformat(),
    }


async def load_sos_full(session: AsyncSession, sos_id: str) -> SOSReport | None:
    result = await session.execute(
        select(SOSReport)
        .options(
            selectinload(SOSReport.assessment),
            selectinload(SOSReport.tasks).selectinload(Task.volunteer),
        )
        .where(SOSReport.id == sos_id)
    )
    return result.scalar_one_or_none()


def sos_to_read(sos: SOSReport, reason: str | None = None,
                reporter_trust_tier: str | None = None) -> S.SOSRead:
    assessment = None
    if sos.assessment is not None:
        a = sos.assessment
        assessment = S.AssessmentRead(
            id=a.id,
            severity=a.severity,
            rationale=a.rationale,
            rationale_en=a.rationale_en,
            area_tags=list(a.area_tags or []),
            category=a.category,  # type: ignore[arg-type]
            priority=a.priority,  # type: ignore[arg-type]
            suggested_skills=list(a.suggested_skills or []),
            model=a.model,
            assessed_at=a.assessed_at,
        )
    tasks = [
        S.TaskSummary(
            id=t.id,
            volunteer_id=t.volunteer_id,
            volunteer_name=getattr(t.volunteer, "name", None),
            status=t.status,  # type: ignore[arg-type]
        )
        for t in (sos.tasks or [])
    ]
    return S.SOSRead(
        id=sos.id,
        client_report_id=sos.client_report_id,
        description=sos.description,
        language=sos.language,
        category=sos.category,  # type: ignore[arg-type]
        severity=sos.severity,
        severity_rationale=assessment.rationale if assessment else None,
        priority=sos.priority,  # type: ignore[arg-type]
        status=sos.status,  # type: ignore[arg-type]
        lat=sos.lat,
        lon=sos.lon,
        district_id=sos.district_id,
        photo_url=sos.photo_url,
        photo_hash=sos.photo_hash,
        photo_description=sos.photo_description,
        reporter_name=sos.reporter_name,
        reporter_phone=sos.reporter_phone,
        needed_skills=list(sos.needed_skills or []),
        needs_review=sos.needs_review,
        reason=reason,
        duplicate_of=sos.duplicate_of,
        reporter_trust_tier=reporter_trust_tier,
        is_demo_data=sos.is_demo_data,
        created_at=sos.created_at,
        updated_at=sos.updated_at,
        assessment=assessment,
        tasks=tasks,
    )


def volunteer_to_read(v: Volunteer) -> S.VolunteerRead:
    return S.VolunteerRead(
        id=v.id,
        name=v.name,
        phone=v.phone,
        district_id=v.district_id,
        lat=v.lat,
        lon=v.lon,
        skills=list(v.skills or []),
        languages=list(v.languages or []),
        availability=v.availability if v.availability is not None else "anytime",
        active=v.active,
        reputation=v.reputation,
        tasks_completed=v.tasks_completed,
        avg_response_min=v.avg_response_min,
        created_at=v.created_at,
    )


def task_to_read(t: Task) -> S.TaskRead:
    sos_summary = None
    if t.sos is not None:
        s = t.sos
        sos_summary = {
            "id": s.id,
            "description": s.description,
            "severity": s.severity,
            "category": s.category,
            "priority": s.priority,
            "lat": s.lat,
            "lon": s.lon,
            "district_id": s.district_id,
            "status": s.status,
        }
    return S.TaskRead(
        id=t.id,
        sos_id=t.sos_id,
        volunteer_id=t.volunteer_id,
        status=t.status,  # type: ignore[arg-type]
        note=t.note,
        assigned_at=t.assigned_at,
        accepted_at=t.accepted_at,
        completed_at=t.completed_at,
        proof_photo_url=t.proof_photo_url,
        created_at=t.created_at,
        updated_at=t.updated_at,
        volunteer=volunteer_to_read(t.volunteer) if t.volunteer is not None else None,
        sos=sos_summary,
    )


def paginate(total: int, limit: int, offset: int, items: list[Any]) -> S.Paginated:
    return S.Paginated(items=items, total=total, limit=limit, offset=offset)


async def count_total(session: AsyncSession, stmt) -> int:
    """Count rows for a filtered select (wraps as subquery)."""
    sub = stmt.order_by(None).subquery()
    result = await session.execute(select(func.count()).select_from(sub))
    return int(result.scalar_one())
