"""Admin router — contracts §7 (command dashboard). All routes admin-only."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .. import schemas as S
from ..auth import Identity, require_admin
from ..database import get_session
from ..models import (
    Alert,
    AuditLog,
    District,
    DistrictRisk,
    SafetyFlag,
    Shelter,
    SOSReport,
    Task,
    Volunteer,
)
from ..services.safety import reporter_trust
from ..services.pdf_report import build_incident_pdf
from .common import (
    ACTIVE_SOS_STATUSES,
    ACTIVE_TASK_STATUSES,
    count_total,
    emit,
    log_audit,
    paginate,
    sos_to_read,
    utcnow,
    verify_reason_for,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/overview", summary="District command snapshot")
async def overview(
    district: str | None = Query(default=None),
    identity: Identity = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> S.AdminOverviewRead:
    sos_stmt = select(SOSReport)
    if district:
        sos_stmt = sos_stmt.where(SOSReport.district_id == district)
    sos_rows = (await session.execute(sos_stmt)).scalars().all()

    by_status: dict[str, int] = {}
    # sos_by_severity keeps STRING keys "1"-"5" (contract freeze, issue #6).
    by_severity: dict[str, int] = {str(i): 0 for i in range(1, 6)}
    for r in sos_rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        if r.severity:
            by_severity[str(r.severity)] = by_severity.get(str(r.severity), 0) + 1

    task_stmt = select(Task)
    if district:
        task_stmt = task_stmt.where(
            Task.sos_id.in_(
                select(SOSReport.id).where(SOSReport.district_id == district)
            )
        )
    task_rows = (await session.execute(task_stmt)).scalars().all()
    active_tasks = sum(1 for t in task_rows if t.status in ACTIVE_TASK_STATUSES)

    vol_stmt = select(Volunteer).where(Volunteer.active.is_(True))
    if district:
        vol_stmt = vol_stmt.where(Volunteer.district_id == district)
    volunteers = (await session.execute(vol_stmt)).scalars().all()
    on_task_ids = {t.volunteer_id for t in task_rows if t.status in ACTIVE_TASK_STATUSES}

    shelter_stmt = select(Shelter).where(Shelter.is_open.is_(True))
    if district:
        shelter_stmt = shelter_stmt.where(Shelter.district_id == district)
    shelters = (await session.execute(shelter_stmt)).scalars().all()
    cap = sum(s.capacity for s in shelters)
    occ = sum(min(s.occupied, s.capacity) for s in shelters)

    district_risk, risk_level = None, None
    if district:
        risk_row = (
            await session.execute(
                select(DistrictRisk)
                .where(DistrictRisk.district_id == district)
                .order_by(DistrictRisk.computed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if risk_row:
            district_risk, risk_level = risk_row.risk, risk_row.risk_level

    pending = sum(1 for r in sos_rows if r.needs_review or r.status == "reported")
    flag_stmt = select(func.count()).select_from(SafetyFlag).where(SafetyFlag.status == "open")
    if district:
        flag_stmt = flag_stmt.where(SafetyFlag.district_id == district)
    open_flags = (await session.execute(flag_stmt)).scalar_one()

    return S.AdminOverviewRead(
        district_id=district,
        sos_by_status=by_status,
        sos_by_severity=by_severity,
        active_tasks=active_tasks,
        volunteers_active=len(volunteers),
        volunteers_on_task=len(on_task_ids),
        shelters_open=len(shelters),
        shelter_occupancy_pct=round(occ / cap * 100, 1) if cap else 0.0,
        district_risk=district_risk,
        risk_level=risk_level,  # type: ignore[arg-type]
        pending_verifications=pending,
        open_safety_flags=int(open_flags),
        generated_at=utcnow(),
    )


@router.get("/verify-queue", summary="SOS reports awaiting verification")
async def verify_queue(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    identity: Identity = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> S.Paginated:
    """needs_review OR status=reported, oldest first. Each item carries a
    machine-readable ``reason`` (Wave 2 amendment, issue #9)."""
    stmt = (
        select(SOSReport)
        .options(
            selectinload(SOSReport.assessment),
            selectinload(SOSReport.tasks).selectinload(Task.volunteer),
        )
        .where(or_(SOSReport.needs_review.is_(True), SOSReport.status == "reported"))
        .order_by(SOSReport.created_at.asc())
    )
    total = await count_total(session, stmt)
    rows = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
    # Reporter weighting (Wave 4, Agent 10): one grouped query for the page's
    # devices — no N+1. Admins use the tier to prioritize the queue.
    trust_map: dict[str | None, str] = {}
    devices = {r.reporter_device_id for r in rows if r.reporter_device_id}
    if devices:
        for d in devices:
            trust_map[d] = (await reporter_trust(session, d))["tier"]  # type: ignore[assignment]
    return paginate(
        total, limit, offset,
        [sos_to_read(r, reason=verify_reason_for(r),
                     reporter_trust_tier=trust_map.get(r.reporter_device_id))
         for r in rows],
    )


@router.post("/safety/flags/{flag_id}/resolve", summary="Resolve a safety flag")
async def resolve_flag(
    flag_id: str,
    body: S.FlagResolveBody,
    identity: Identity = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> S.SafetyFlagRead:
    flag = await session.get(SafetyFlag, flag_id)
    if flag is None:
        raise HTTPException(status_code=404, detail="flag not found")
    flag.status = "resolved" if body.resolution in ("confirmed_duplicate", "confirmed") else "dismissed"
    flag.resolution = body.resolution
    flag.resolved_by = identity.actor
    if body.resolution == "confirmed_duplicate":
        # Duplicate-merge semantics (Wave 4, Agent 10): the newest report in
        # the flag becomes a labeled duplicate of the oldest; BOTH stay
        # visible and queryable — nothing is silently dropped or deleted.
        sos_ids = list(flag.sos_ids or [])
        if len(sos_ids) >= 2:
            reports = (
                await session.execute(
                    select(SOSReport).where(SOSReport.id.in_(sos_ids))
                )
            ).scalars().all()
            by_id = {r.id: r for r in reports}
            # Oldest filed = canonical. Tie-break on id for determinism
            # (created_at has second precision; rapid re-uploads can tie).
            ordered = sorted(
                (by_id[i] for i in sos_ids if i in by_id),
                key=lambda r: (r.created_at, r.id),
            )
            if len(ordered) >= 2:
                canonical, *dupes = ordered
                for dupe in dupes:
                    dupe.status = "duplicate"
                    dupe.duplicate_of = canonical.id
                    dupe.needs_review = False
                    dupe.needs_review_reason = None
                    dupe.updated_at = utcnow()
                    await log_audit(
                        session, identity.actor, "sos.merged_duplicate", "sos", dupe.id,
                        {"canonical_id": canonical.id, "flag_id": flag.id,
                         "note": body.note},
                    )
                await emit(
                    "sos.status_changed",
                    {"sos_ids": [d.id for d in dupes], "to": "duplicate",
                     "canonical_id": canonical.id, "district_id": flag.district_id},
                )
    await log_audit(
        session, identity.actor, "safety.flag_resolved", "safety_flag", flag.id,
        {"resolution": body.resolution, "note": body.note},
    )
    await session.commit()
    return S.SafetyFlagRead(
        id=flag.id, type=flag.type, sos_ids=list(flag.sos_ids or []),
        district_id=flag.district_id, evidence=flag.evidence, status=flag.status,
        created_at=flag.created_at,
    )


@router.get("/audit", summary="Audit log")
async def audit_log(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    actor: str | None = Query(default=None),
    identity: Identity = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[S.AuditEntryRead]:
    stmt = select(AuditLog).order_by(AuditLog.ts.desc())
    if actor:
        stmt = stmt.where(AuditLog.actor == actor)
    rows = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return [
        S.AuditEntryRead(
            id=r.id, ts=r.ts, actor=r.actor, action=r.action,
            target_type=r.target_type, target_id=r.target_id,
            details=dict(r.details or {}),
        )
        for r in rows
    ]


@router.get("/incidents/{district_id}/export", summary="Export incident bundle")
async def export_incident(
    district_id: str,
    format: str = Query(default="json", pattern="^(json|pdf)$"),
    identity: Identity = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """format=json always works. format=pdf returns a real server-side PDF
    (reportlab, Wave 4 Agent 11) — incident summary, SOS list, tasks, risk
    snapshot, broadcasts, timeline. Never a fake download."""
    district = await session.get(District, district_id)
    if district is None:
        raise HTTPException(status_code=404, detail="district not found")

    sos_rows = (
        await session.execute(
            select(SOSReport)
            .options(
                selectinload(SOSReport.assessment),
                selectinload(SOSReport.tasks).selectinload(Task.volunteer),
            )
            .where(SOSReport.district_id == district_id)
            .order_by(SOSReport.created_at.asc())
        )
    ).scalars().all()
    sos_ids = [r.id for r in sos_rows]
    task_rows = (
        await session.execute(
            select(Task)
            .options(selectinload(Task.volunteer))
            .where(Task.sos_id.in_(sos_ids))
        )
        if sos_ids
        else await session.execute(select(Task).where(False))
    ).scalars().all()
    alert_rows = (
        await session.execute(select(Alert).order_by(Alert.created_at.asc()))
    ).scalars().all()
    alert_rows = [a for a in alert_rows if district_id in (a.district_ids or [])]
    risk_row = (
        await session.execute(
            select(DistrictRisk)
            .where(DistrictRisk.district_id == district_id)
            .order_by(DistrictRisk.computed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    bundle = S.ExportIncidentJSON(
        district_id=district_id,
        exported_at=utcnow(),
        district={"id": district.id, "name": district.name, "state": district.state},
        risk=(
            {"risk": risk_row.risk, "risk_level": risk_row.risk_level,
             "factors": list(risk_row.factors or []),
             "computed_at": risk_row.computed_at.isoformat()}
            if risk_row
            else None
        ),
        sos_reports=[sos_to_read(r).model_dump(mode="json") for r in sos_rows],
        tasks=[
            {"id": t.id, "sos_id": t.sos_id, "volunteer_id": t.volunteer_id,
             "status": t.status}
            for t in task_rows
        ],
        alerts=[
            {"id": a.id, "type": a.type, "severity": a.severity,
             "languages": list(a.languages or []),
             "created_at": a.created_at.isoformat() if a.created_at else None}
            for a in alert_rows
        ],
    )
    if format == "pdf":
        # Real server-side PDF (Wave 4, Agent 11). The JSON bundle shape is
        # frozen, so the PDF gets its own richer bundle (audit timeline +
        # rendered broadcast messages) without touching the contract.
        alert_ids = [a.id for a in alert_rows]
        audit_rows: list[AuditLog] = []
        if sos_ids or alert_ids:
            audit_rows = (
                await session.execute(
                    select(AuditLog)
                    .where(
                        or_(
                            AuditLog.target_id.in_(sos_ids),
                            and_(
                                AuditLog.target_type == "district",
                                AuditLog.target_id == district_id,
                            ),
                            AuditLog.target_id.in_(alert_ids),
                        )
                    )
                    .order_by(AuditLog.ts.asc())
                    .limit(200)
                )
            ).scalars().all()
        pdf_bundle = {
            "district": {"id": district.id, "name": district.name,
                         "state": district.state},
            "exported_at": utcnow().isoformat(),
            "exported_by": identity.actor,
            "risk": (
                {"risk": risk_row.risk, "risk_level": risk_row.risk_level,
                 "factors": list(risk_row.factors or []),
                 "weather_source": risk_row.weather_source,
                 "computed_at": risk_row.computed_at.isoformat()}
                if risk_row else None
            ),
            "sos_reports": [sos_to_read(r).model_dump(mode="json") for r in sos_rows],
            "tasks": [
                {"id": t.id, "sos_id": t.sos_id, "volunteer_id": t.volunteer_id,
                 "volunteer_name": getattr(t.volunteer, "name", None),
                 "status": t.status}
                for t in task_rows
            ],
            "alerts": [
                {"id": a.id, "type": a.type, "severity": a.severity,
                 "languages": list(a.languages or []),
                 "messages": dict(a.messages or {}),
                 "created_at": a.created_at.isoformat() if a.created_at else None}
                for a in alert_rows
            ],
            "audit": [
                {"ts": r.ts.isoformat() if r.ts else None, "actor": r.actor,
                 "action": r.action, "target_id": r.target_id}
                for r in audit_rows
            ],
        }
        pdf_bytes = build_incident_pdf(pdf_bundle)
        await log_audit(
            session, identity.actor, "incident.exported", "district", district_id,
            {"format": "pdf", "sos_count": len(sos_ids),
             "bytes": len(pdf_bytes)},
        )
        await session.commit()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition":
                    f"attachment; filename=sahayta-incident-{district_id}.pdf"
            },
        )

    await log_audit(
        session, identity.actor, "incident.exported", "district", district_id,
        {"format": "json", "sos_count": len(sos_ids)},
    )
    await session.commit()
    return JSONResponse(
        content=bundle.model_dump(mode="json"),
        headers={
            "Content-Disposition": f"attachment; filename=sahayta-incident-{district_id}.json"
        },
    )
