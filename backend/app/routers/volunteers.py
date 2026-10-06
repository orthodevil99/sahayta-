"""Volunteers router — contracts §4."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import schemas as S
from ..auth import Identity, require_identity
from ..database import get_session
from ..models import User, Volunteer
from ..services.matching import _availability_score
from .common import count_total, emit, log_audit, paginate, volunteer_to_read

router = APIRouter(prefix="/api", tags=["volunteers"])


@router.post("/volunteers", status_code=201, summary="Register a volunteer")
async def register_volunteer(
    body: S.VolunteerCreate,
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> S.VolunteerRead:
    if body.district_id:
        from ..models import District

        if await session.get(District, body.district_id) is None:
            raise HTTPException(status_code=422, detail=f"unknown district_id: {body.district_id}")
    volunteer = Volunteer(
        user_id=identity.user.id if identity.user else None,
        name=body.name,
        phone=body.phone,
        district_id=body.district_id,
        lat=body.lat,
        lon=body.lon,
        skills=list(body.skills),
        languages=list(body.languages),
        availability=body.availability,
        active=body.active,
    )
    session.add(volunteer)
    if identity.user and identity.user.role == "citizen":
        identity.user.role = "volunteer"
    await session.flush()
    await log_audit(
        session, identity.actor, "volunteer.registered", "volunteer", volunteer.id,
        {"district_id": volunteer.district_id, "skills": volunteer.skills},
    )
    await session.commit()
    await emit(
        "volunteer.registered",
        {"id": volunteer.id, "name": volunteer.name,
         "district_id": volunteer.district_id,
         "skills": list(volunteer.skills or [])},
    )
    return volunteer_to_read(volunteer)


@router.get("/volunteers", summary="List volunteers")
async def list_volunteers(
    district: str | None = Query(default=None),
    skill: str | None = Query(default=None),
    language: str | None = Query(default=None),
    available_now: bool | None = Query(default=None),
    active: bool | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> S.Paginated:
    stmt = select(Volunteer)
    if district:
        stmt = stmt.where(Volunteer.district_id == district)
    if active is not None:
        stmt = stmt.where(Volunteer.active.is_(active))
    rows = (await session.execute(stmt)).scalars().all()

    # JSON-array membership filters in Python (SQLite portability).
    if skill:
        rows = [r for r in rows if skill in (r.skills or [])]
    if language:
        rows = [r for r in rows if language in (r.languages or [])]
    if available_now:
        rows = [r for r in rows if _availability_score(r.availability)[0] >= 1.0]

    total = len(rows)
    page = rows[offset: offset + limit]
    return paginate(total, limit, offset, [volunteer_to_read(r) for r in page])


@router.get("/volunteers/{volunteer_id}", summary="Get one volunteer")
async def get_volunteer(
    volunteer_id: str,
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> S.VolunteerRead:
    volunteer = await session.get(Volunteer, volunteer_id)
    if volunteer is None:
        raise HTTPException(status_code=404, detail="volunteer not found")
    return volunteer_to_read(volunteer)


@router.patch("/volunteers/{volunteer_id}", summary="Update own volunteer profile")
async def patch_volunteer(
    volunteer_id: str,
    body: S.VolunteerPatch,
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> S.VolunteerRead:
    """Accepted fields (Wave 2 amendment, issue #3): name, phone, district_id,
    lat, lon, skills, languages, availability, active. Owner device or admin."""
    volunteer = await session.get(Volunteer, volunteer_id)
    if volunteer is None:
        raise HTTPException(status_code=404, detail="volunteer not found")
    is_owner = (
        identity.user is not None
        and volunteer.user_id is not None
        and volunteer.user_id == identity.user.id
    )
    if not (identity.is_admin or is_owner):
        raise HTTPException(
            status_code=403, detail="only the owning device or an admin can update"
        )
    patch = body.model_dump(exclude_unset=True)
    if "district_id" in patch and patch["district_id"]:
        from ..models import District

        if await session.get(District, patch["district_id"]) is None:
            raise HTTPException(
                status_code=422, detail=f"unknown district_id: {patch['district_id']}"
            )
    for key, value in patch.items():
        setattr(volunteer, key, value)
    await log_audit(
        session, identity.actor, "volunteer.updated", "volunteer", volunteer.id,
        {"fields": sorted(patch.keys())},
    )
    await session.commit()
    return volunteer_to_read(volunteer)


@router.get("/volunteers/{volunteer_id}/reputation", summary="Reputation detail")
async def volunteer_reputation(
    volunteer_id: str,
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Wave 3 (Agent 8, additive): the full reputation read-model — score,
    completed/declined counts, avg response time, computed reliability_pct,
    and display tier. See services/reputation.py for the documented formula."""
    from ..services.reputation import reputation_detail

    volunteer = await session.get(Volunteer, volunteer_id)
    if volunteer is None:
        raise HTTPException(status_code=404, detail="volunteer not found")
    return reputation_detail(volunteer, volunteer.id)
