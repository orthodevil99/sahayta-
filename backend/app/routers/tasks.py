"""Tasks router — contracts §5 (volunteer coordination).

Lifecycle (frozen): assigned → accepted|declined|cancelled;
accepted → en_route|declined|cancelled; en_route → completed|cancelled.
Side effects: en_route flips the parent SOS to help_on_way (first task wins);
complete flips SOS to resolved when no other active tasks remain.
Reputation: +2 per completed task (cap 100), −5 per declined-after-accept
(floor 0) — server-managed, never client-set.
"""
from __future__ import annotations

import logging
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .. import schemas as S
from ..auth import Identity, require_admin, require_identity
from ..config import Settings, get_settings
from ..database import get_session
from ..models import MediaFile, SOSReport, Task, Volunteer
from ..services.matching import rank_volunteers, score_breakdown
from ..services.notify_templates import notification_preview
from ..services.reputation import (
    on_decline_after_commit,
    on_task_completed,
    record_response_time,
)
from .common import (
    ACTIVE_TASK_STATUSES,
    TASK_TRANSITIONS,
    count_total,
    emit,
    log_audit,
    paginate,
    task_to_read,
    utcnow,
    volunteer_to_read,
)

log = logging.getLogger("sahayta.routers.tasks")

router = APIRouter(prefix="/api", tags=["tasks"])


async def _load_task_full(session: AsyncSession, task_id: str) -> Task | None:
    result = await session.execute(
        select(Task)
        .options(selectinload(Task.volunteer), selectinload(Task.sos))
        .where(Task.id == task_id)
    )
    return result.scalar_one_or_none()


def _guard_transition(task: Task, to: str) -> None:
    allowed = TASK_TRANSITIONS.get(task.status, set())
    if to not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"illegal task transition {task.status} → {to}",
        )


async def _assert_actor(
    identity: Identity, task: Task, *, admin_only: bool = False
) -> None:
    if identity.is_admin:
        return
    if admin_only:
        raise HTTPException(status_code=403, detail="admin only")
    volunteer = task.volunteer
    is_owner = (
        identity.user is not None
        and volunteer is not None
        and volunteer.user_id is not None
        and volunteer.user_id == identity.user.id
    )
    if not is_owner:
        raise HTTPException(
            status_code=403, detail="only the assigned volunteer or an admin"
        )


async def _maybe_resolve_sos(session: AsyncSession, sos: SOSReport) -> bool:
    """Flip SOS to resolved when no active tasks remain. Returns True if flipped."""
    active = (
        await session.execute(
            select(Task).where(
                Task.sos_id == sos.id, Task.status.in_(ACTIVE_TASK_STATUSES)
            )
        )
    ).scalars().all()
    if not active and sos.status != "resolved":
        sos.status = "resolved"
        sos.updated_at = utcnow()
        return True
    return False


@router.post("/tasks/match", summary="Preview ranked volunteers for an SOS")
async def match_tasks(
    body: S.MatchRequest,
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> S.MatchResponse:
    sos = await session.get(SOSReport, body.sos_id)
    if sos is None:
        raise HTTPException(status_code=404, detail="sos not found")
    max_results = body.max_results or settings.match_default_max_results
    max_distance = body.max_distance_km or settings.match_default_max_distance_km
    volunteers = (
        await session.execute(select(Volunteer).where(Volunteer.active.is_(True)))
    ).scalars().all()
    ranked = rank_volunteers(sos, list(volunteers), max_results, max_distance)
    return S.MatchResponse(
        sos_id=sos.id,
        matches=[
            S.VolunteerMatchRead(
                volunteer=volunteer_to_read(v),
                score=score,
                distance_km=dist,
                reasons=reasons,
                score_breakdown=score_breakdown(sos, v, max_distance),
            )
            for v, score, dist, reasons in ranked
        ],
    )


async def _plan_reoffer(
    session: AsyncSession,
    task: Task,
    sos: SOSReport | None,
    settings: Settings,
) -> dict | None:
    """Plan the auto re-offer of a declined task to the next-ranked volunteer
    (Wave 3, Agent 8). The decliner and anyone already holding an active task
    on this SOS are excluded. Adds the new Task + audit entry to the session
    (no commit — the caller commits) and returns the WS event payload.
    Returns None when there is no eligible candidate or the SOS is terminal.
    At most one new task per decline — no recursion."""
    if sos is None or sos.status in ("resolved", "duplicate", "rejected"):
        return None
    busy = (
        await session.execute(
            select(Task.volunteer_id).where(
                Task.sos_id == sos.id,
                Task.status.in_(ACTIVE_TASK_STATUSES),
            )
        )
    ).scalars().all()
    excluded = set(busy) | {task.volunteer_id}
    volunteers = (
        await session.execute(
            select(Volunteer).where(Volunteer.active.is_(True))
        )
    ).scalars().all()
    candidates = [v for v in volunteers if v.id not in excluded]
    ranked = rank_volunteers(
        sos, candidates, max_results=5,
        max_distance_km=settings.match_default_max_distance_km,
    )
    if not ranked:
        log.info("reoffer: no eligible volunteer for sos %s after decline of task %s",
                 sos.id, task.id)
        return None
    nxt, score, _dist, _reasons = ranked[0]
    decliner_name = task.volunteer.name if task.volunteer else task.volunteer_id
    new_task = Task(
        sos_id=sos.id,
        volunteer_id=nxt.id,
        status="assigned",
        note=f"Re-offered after {decliner_name} declined (match score {score})",
    )
    session.add(new_task)
    await session.flush()
    await log_audit(
        session, "system", "task.reoffered", "task", new_task.id,
        {"sos_id": sos.id, "volunteer_id": nxt.id,
         "after_decline_of": task.id, "match_score": score},
    )
    return {
        "task_id": new_task.id, "sos_id": sos.id,
        "volunteer": {"id": nxt.id, "name": nxt.name},
        "district_id": sos.district_id, "reoffer": True,
    }


@router.post("/tasks", status_code=201, summary="Assign a task")
async def create_task(
    body: S.TaskCreate,
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> S.TaskRead:
    """Auth: admin, or the SOS reporter's device (auto-system path)."""
    sos = await session.get(SOSReport, body.sos_id)
    if sos is None:
        raise HTTPException(status_code=404, detail="sos not found")
    volunteer = await session.get(Volunteer, body.volunteer_id)
    if volunteer is None:
        raise HTTPException(status_code=404, detail="volunteer not found")
    if not identity.is_admin and sos.reporter_device_id != identity.device_id:
        raise HTTPException(
            status_code=403,
            detail="only an admin or the SOS reporter can assign tasks",
        )
    dup = (
        await session.execute(
            select(Task).where(
                Task.sos_id == sos.id,
                Task.volunteer_id == volunteer.id,
                Task.status.in_(ACTIVE_TASK_STATUSES),
            )
        )
    ).scalar_one_or_none()
    if dup is not None:
        raise HTTPException(
            status_code=409, detail="an active task already exists for this sos+volunteer"
        )
    task = Task(sos_id=sos.id, volunteer_id=volunteer.id, note=body.note, status="assigned")
    session.add(task)
    await session.flush()
    await log_audit(
        session, identity.actor, "task.assigned", "task", task.id,
        {"sos_id": sos.id, "volunteer_id": volunteer.id},
    )
    await session.commit()
    await emit(
        "task.assigned",
        {"task_id": task.id, "sos_id": sos.id,
         "volunteer": {"id": volunteer.id, "name": volunteer.name},
         "district_id": sos.district_id},
    )
    return task_to_read((await _load_task_full(session, task.id)) or task)


@router.get("/tasks", summary="List tasks")
async def list_tasks(
    volunteer_id: str | None = Query(default=None),
    sos_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    district: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> S.Paginated:
    stmt = select(Task)
    if volunteer_id:
        stmt = stmt.where(Task.volunteer_id == volunteer_id)
    if sos_id:
        stmt = stmt.where(Task.sos_id == sos_id)
    if status:
        stmt = stmt.where(Task.status == status)
    if district:
        stmt = stmt.where(
            Task.sos_id.in_(
                select(SOSReport.id).where(SOSReport.district_id == district)
            )
        )
    total = await count_total(session, stmt)
    rows = (
        await session.execute(
            stmt.options(selectinload(Task.volunteer), selectinload(Task.sos))
            .order_by(Task.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return paginate(total, limit, offset, [task_to_read(t) for t in rows])


@router.get("/tasks/{task_id}", summary="Get one task")
async def get_task(
    task_id: str,
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> S.TaskRead:
    task = await _load_task_full(session, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task_to_read(task)


async def _transition(
    session: AsyncSession,
    identity: Identity,
    task_id: str,
    to: str,
    *,
    admin_only: bool = False,
    note: str | None = None,
    decline_reason: str | None = None,
    proof_photo_id: str | None = None,
) -> S.TaskRead:
    task = await _load_task_full(session, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    await _assert_actor(identity, task, admin_only=admin_only)
    _guard_transition(task, to)

    from_status = task.status
    now = utcnow()
    task.status = to

    if to == "accepted":
        task.accepted_at = now
        if task.volunteer and task.assigned_at:
            accepted = task.assigned_at
            if accepted.tzinfo is None:
                accepted = accepted.replace(tzinfo=timezone.utc)
            mins = (now - accepted).total_seconds() / 60
            record_response_time(task.volunteer, mins)
    elif to == "declined":
        task.decline_reason = decline_reason
        # Declined AFTER accept/en-route hurts reputation; instant decline is
        # free — the pipeline re-offers to the next-ranked volunteer instead.
        if from_status in ("accepted", "en_route") and task.volunteer:
            on_decline_after_commit(task.volunteer)
    elif to == "en_route":
        task.en_route_at = now
    elif to == "completed":
        task.completed_at = now
        if note:
            task.note = note
        if proof_photo_id:
            media = await session.get(MediaFile, proof_photo_id)
            if media is None:
                raise HTTPException(status_code=422, detail="unknown proof_photo_id")
            task.proof_photo_url = media.url
        if task.volunteer:
            on_task_completed(task.volunteer)
            task.volunteer.last_active_at = now

    await log_audit(
        session, identity.actor, f"task.{to}", "task", task.id,
        {"from": from_status, "sos_id": task.sos_id, "volunteer_id": task.volunteer_id},
    )
    await session.flush()

    sos = task.sos
    sos_events: list[tuple[str, dict]] = [
        ("task.updated", {"task_id": task.id, "sos_id": task.sos_id,
                          "from": from_status, "to": to,
                          "district_id": sos.district_id if sos else None})
    ]
    if to == "en_route" and sos is not None and sos.status in ("reported", "verified"):
        # First task to go en-route wins.
        prev_sos = sos.status
        sos.status = "help_on_way"
        sos.updated_at = now
        await log_audit(
            session, "system", "sos.status_changed", "sos", sos.id,
            {"from": prev_sos, "to": "help_on_way", "via": f"task:{task.id}"},
        )
        sos_events.append(
            ("sos.status_changed",
             {"sos_id": sos.id, "from": prev_sos, "to": "help_on_way",
              "note": "volunteer en route", "district_id": sos.district_id})
        )
    if to == "completed" and sos is not None:
        if await _maybe_resolve_sos(session, sos):
            await log_audit(
                session, "system", "sos.status_changed", "sos", sos.id,
                {"from": "help_on_way", "to": "resolved", "via": f"task:{task.id}"},
            )
            sos_events.append(
                ("sos.status_changed",
                 {"sos_id": sos.id, "from": "help_on_way", "to": "resolved",
                  "note": "all tasks complete", "district_id": sos.district_id})
            )

    reoffer_event: dict | None = None
    if to == "declined":
        # Auto re-offer to the next-ranked volunteer (Wave 3, Agent 8).
        # Planned pre-commit so no expired ORM attributes are touched;
        # the new task commits together with the decline, event emits after.
        reoffer_event = await _plan_reoffer(session, task, sos, get_settings())

    await session.commit()
    for etype, data in sos_events:
        await emit(etype, data)
    if reoffer_event is not None:
        await emit("task.assigned", reoffer_event)
    return task_to_read((await _load_task_full(session, task.id)) or task)


@router.post("/tasks/{task_id}/accept", summary="Accept a task")
async def accept_task(
    task_id: str,
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> S.TaskRead:
    return await _transition(session, identity, task_id, "accepted")


@router.post("/tasks/{task_id}/decline", summary="Decline a task")
async def decline_task(
    task_id: str,
    body: S.TaskDecline,
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> S.TaskRead:
    return await _transition(
        session, identity, task_id, "declined", decline_reason=body.reason
    )


@router.post("/tasks/{task_id}/enroute", summary="Mark task en-route")
async def enroute_task(
    task_id: str,
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> S.TaskRead:
    return await _transition(session, identity, task_id, "en_route")


@router.post("/tasks/{task_id}/complete", summary="Complete a task")
async def complete_task(
    task_id: str,
    body: S.TaskComplete,
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> S.TaskRead:
    return await _transition(
        session, identity, task_id, "completed",
        note=body.note, proof_photo_id=body.proof_photo_id,
    )


@router.post("/tasks/{task_id}/cancel", summary="Cancel a task (admin)")
async def cancel_task(
    task_id: str,
    identity: Identity = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> S.TaskRead:
    return await _transition(session, identity, task_id, "cancelled", admin_only=True)


@router.get("/tasks/{task_id}/notifications", summary="SMS preview for task events")
async def task_notifications(
    task_id: str,
    lang: str = Query(default="hi"),
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Wave 3 (Agent 8, additive): render the SMS-style notification templates
    for every lifecycle event of this task. Demo/preview only — v1 sends no
    real SMS (see services/notify_templates.py)."""
    from ..geo import haversine_km
    from ..models import District

    task = await _load_task_full(session, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    sos = task.sos
    volunteer = task.volunteer
    district_name = (sos.district_id if sos else None) or "—"
    if sos and sos.district_id:
        district = await session.get(District, sos.district_id)
        if district is not None and district.name:
            district_name = district.name
    km = "—"
    if (
        sos and volunteer
        and sos.lat is not None and sos.lon is not None
        and volunteer.lat is not None and volunteer.lon is not None
    ):
        km = f"{haversine_km(sos.lat, sos.lon, volunteer.lat, volunteer.lon):.1f}"
    name = (volunteer.name.split()[0] if volunteer and volunteer.name else "—")
    return {
        "task_id": task.id,
        "lang": lang,
        "messages": notification_preview(
            lang,
            name=name,
            district=district_name,
            km=km,
            sos=(task.sos_id or "")[:8],
        ),
    }
