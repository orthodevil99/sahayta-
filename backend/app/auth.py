"""Auth + rate limiting.

Auth modes (docs/api-contracts.md §0.2):
- Guest (citizen/volunteer): ``X-Device-Id: <uuid>`` — client-generated,
  persisted. Auto-provisions a ``users`` row on first sight.
- Service key (optional): ``X-API-Key`` — same as guest, higher rate limits.
- Admin (district official): ``X-Admin-Key`` — checked against env, never stored.

Rate limits (in-memory sliding window, per key, rolling hour):
- Guest: 20 POST /api/sos/hr, 200 other requests/hr.
- Service/admin: 1000 requests/hr.
Exceeded -> 429 ``{"detail": "rate limit exceeded", "retry_after": <s>}``.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings, get_settings
from .database import get_session
from .models import User

log = logging.getLogger("sahayta.auth")

# key -> deque[timestamps]; module-level = per-process (fine for v1 monolith).
_hits: dict[str, deque[float]] = defaultdict(deque)
_WINDOW_S = 3600.0


@dataclass
class Identity:
    """Resolved caller identity for a request."""

    device_id: str | None
    is_admin: bool
    is_service: bool
    actor: str  # for the audit log: "admin:demo" | "device:<uuid>" | "system"
    user: User | None = None

    @property
    def rate_key(self) -> str:
        if self.is_admin:
            return f"admin:{self.actor}"
        if self.is_service:
            return f"service:{self.device_id}"
        return f"guest:{self.device_id}"


def _check_rate_limit(identity: Identity, settings: Settings, *, is_sos_post: bool) -> None:
    if identity.is_admin or identity.is_service:
        limit = settings.rl_privileged_per_hour
    elif is_sos_post:
        limit = settings.rl_guest_sos_per_hour
    else:
        limit = settings.rl_guest_other_per_hour

    now = time.monotonic()
    dq = _hits[identity.rate_key]
    while dq and dq[0] <= now - _WINDOW_S:
        dq.popleft()
    if len(dq) >= limit:
        retry_after = int(_WINDOW_S - (now - dq[0])) + 1
        raise HTTPException(
            status_code=429,
            detail="rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
    dq.append(now)


def reset_rate_limits() -> None:
    """Test hook."""
    _hits.clear()


async def _get_or_create_user(session: AsyncSession, device_id: str) -> User:
    user = (
        await session.execute(select(User).where(User.device_id == device_id))
    ).scalar_one_or_none()
    if user is None:
        user = User(device_id=device_id, role="citizen")
        session.add(user)
        await session.flush()
    return user


async def get_identity(
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
) -> Identity:
    """Resolve identity for guest+ routes (device id required)."""
    is_service = bool(settings.api_key and x_api_key == settings.api_key)
    is_admin = bool(x_admin_key and x_admin_key == settings.admin_key)
    if not x_device_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing X-Device-Id header",
        )
    user = await _get_or_create_user(session, x_device_id) if x_device_id else None
    if is_admin:
        actor = "admin:demo" if settings.using_default_admin_key else "admin:env"
    elif x_device_id:
        actor = f"device:{x_device_id}"
    else:
        actor = "system"
    return Identity(
        device_id=x_device_id, is_admin=is_admin, is_service=is_service,
        actor=actor, user=user,
    )


async def require_identity(
    identity: Identity = Depends(get_identity),
) -> Identity:
    """Guest+ dependency — exactly one rate-limit check per request."""
    _check_rate_limit(identity, get_settings(), is_sos_post=False)
    return identity


async def require_sos_identity(
    identity: Identity = Depends(get_identity),
) -> Identity:
    """Stricter quota for POST /api/sos (20/hr per guest device)."""
    _check_rate_limit(identity, get_settings(), is_sos_post=True)
    return identity


async def require_admin(
    identity: Identity = Depends(get_identity),
) -> Identity:
    """Admin-only dependency. Valid credentials but not admin -> 403."""
    if not identity.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin key required",
        )
    _check_rate_limit(identity, get_settings(), is_sos_post=False)
    return identity

