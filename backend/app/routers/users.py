"""Users router — PATCH /api/users/me (Wave 2 amendment, issue #4).

The i18n plan referenced a user-preference endpoint; the contracts had none.
This closes the loop: device-anchored users can store preferred_lang (and an
optional display name / phone) server-side.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .. import schemas as S
from ..auth import Identity, require_identity
from ..database import get_session
from .common import log_audit

router = APIRouter(prefix="/api", tags=["users"])


@router.patch("/users/me", summary="Update own user preferences")
async def patch_me(
    body: S.UserPatch,
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> S.UserRead:
    user = identity.user
    assert user is not None  # require_identity guarantees a device user
    if body.preferred_lang is not None:
        user.preferred_lang = body.preferred_lang
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.phone is not None:
        user.phone = body.phone
    await log_audit(
        session, identity.actor, "user.updated", "user", user.id,
        {"fields": sorted(body.model_dump(exclude_unset=True).keys())},
    )
    await session.commit()
    return S.UserRead(
        id=user.id, device_id=user.device_id, role=user.role,
        display_name=user.display_name, phone=user.phone,
        preferred_lang=user.preferred_lang, created_at=user.created_at,
    )
