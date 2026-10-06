"""Shelters router — contracts §2. ALL rows synthetic in v1 (is_demo_data=true)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import schemas as S
from ..auth import Identity, require_identity
from ..database import get_session
from ..models import Shelter
from .common import count_total, paginate

router = APIRouter(prefix="/api", tags=["shelters"])


def _shelter_to_read(s: Shelter) -> S.ShelterRead:
    return S.ShelterRead(
        id=s.id, name=s.name, district_id=s.district_id, area=s.area,
        lat=s.lat, lon=s.lon, capacity=s.capacity, occupied=s.occupied,
        facilities=list(s.facilities or []), contact_name=s.contact_name,
        contact_phone=s.contact_phone, is_demo_data=s.is_demo_data,
        updated_at=s.updated_at,
    )


@router.get("/shelters", summary="List shelters (synthetic demo data)")
async def list_shelters(
    district: str | None = Query(default=None),
    q: str | None = Query(default=None),
    has_capacity: bool | None = Query(default=None),
    facility: list[str] | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> S.Paginated:
    stmt = select(Shelter)
    if district:
        stmt = stmt.where(Shelter.district_id == district)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            (Shelter.name.ilike(like)) | (Shelter.area.ilike(like))
        )
    if has_capacity:
        stmt = stmt.where(Shelter.occupied < Shelter.capacity)
    rows = (await session.execute(stmt)).scalars().all()

    # JSON-containment filters are applied in Python (SQLite portability).
    if facility:
        wanted = {f for f in facility}
        rows = [r for r in rows if wanted <= set(r.facilities or [])]

    total = len(rows)
    page = rows[offset: offset + limit]
    return paginate(total, limit, offset, [_shelter_to_read(r) for r in page])


@router.get("/shelters/{shelter_id}", summary="Get one shelter")
async def get_shelter(
    shelter_id: str,
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> S.ShelterRead:
    shelter = await session.get(Shelter, shelter_id)
    if shelter is None:
        raise HTTPException(status_code=404, detail="shelter not found")
    return _shelter_to_read(shelter)
