"""Safety router — contracts §8.

Visibility policy (finalized Wave 4, Agent 10 — see docs/safety.md):

- **Admin** (X-Admin-Key): full flag records — every field, every status.
- **Reporter** (guest with ``?mine=true``): flags that touch their OWN
  reports (matched by reporter_device_id) — type, status, resolution note,
  timestamps. Reporters deserve to know why their report is under review.
- **Public / guest**: anonymized counts only — ``?district=`` is required,
  response is open-flag counts by type for that district. No report IDs,
  no evidence text, no reporter linkage.

Rationale: full public evidence would let bad actors probe exactly which
reports got flagged (and why), then tune around the guardrails. District-
level counts keep community transparency without leaking the detection
surface. Nothing here hides a report's *existence* — duplicates and flagged
reports stay visible on the board with their status.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import schemas as S
from ..auth import Identity, require_identity
from ..database import get_session
from ..models import SafetyFlag, SOSReport

router = APIRouter(prefix="/api", tags=["safety"])


@router.get("/safety/flags", summary="Safety flags (role-scoped visibility)")
async def safety_flags(
    district: str | None = Query(default=None),
    status: str | None = Query(default=None),
    mine: bool = Query(default=False, description="own reports' flags (reporters)"),
    limit: int = Query(default=50, ge=1, le=200),
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
):
    if identity.is_admin:
        stmt = select(SafetyFlag).order_by(SafetyFlag.created_at.desc())
        if district:
            stmt = stmt.where(SafetyFlag.district_id == district)
        if status:
            stmt = stmt.where(SafetyFlag.status == status)
        rows = (await session.execute(stmt.limit(limit))).scalars().all()
        return [
            S.SafetyFlagRead(
                id=f.id, type=f.type, sos_ids=list(f.sos_ids or []),
                district_id=f.district_id, evidence=f.evidence, status=f.status,
                created_at=f.created_at,
            )
            for f in rows
        ]
    if mine:
        # Reporter's own view: flags touching reports filed by this device.
        if not identity.device_id:
            raise HTTPException(status_code=401, detail="device identity required")
        own_ids = (
            await session.execute(
                select(SOSReport.id).where(
                    SOSReport.reporter_device_id == identity.device_id
                )
            )
        ).scalars().all()
        own_set = set(own_ids)
        stmt = select(SafetyFlag).order_by(SafetyFlag.created_at.desc())
        if status:
            stmt = stmt.where(SafetyFlag.status == status)
        rows = (await session.execute(stmt.limit(limit))).scalars().all()
        mine_rows = [
            f for f in rows if own_set.intersection(f.sos_ids or [])
        ]
        return [
            {
                "id": f.id,
                "type": f.type,
                "status": f.status,
                "resolution": f.resolution,
                "created_at": f.created_at,
                # Only the reporter's own report IDs — never anyone else's.
                "sos_ids": [i for i in (f.sos_ids or []) if i in own_set],
                "district_id": f.district_id,
            }
            for f in mine_rows
        ]
    # Guest: anonymized counts for one district only.
    if not district:
        raise HTTPException(status_code=422, detail="?district= is required for guests")
    by_type = (
        await session.execute(
            select(SafetyFlag.type, func.count())
            .where(SafetyFlag.district_id == district, SafetyFlag.status == "open")
            .group_by(SafetyFlag.type)
        )
    ).all()
    return {
        "district": district,
        "open_flags": sum(n for _, n in by_type),
        "by_type": {t: n for t, n in by_type},
    }
