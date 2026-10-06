"""Alerts router — contracts §6 (multilingual broadcast)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import schemas as S
from ..auth import Identity, require_admin, require_identity
from ..database import get_session
from ..models import Alert, District
from ..services.alerts_render import TEN_LANGS, estimate_recipients, render_multilingual
from .common import count_total, emit, log_audit, paginate, utcnow

log = logging.getLogger("sahayta.routers.alerts")

router = APIRouter(prefix="/api", tags=["alerts"])


def _alert_item(alert: Alert, lang: str | None, include_map: bool) -> S.AlertItemRead:
    messages = dict(alert.messages or {})
    if lang == "all":
        include_map = True
        message = messages.get("hi", "")
    else:
        message = messages.get(lang or "hi", messages.get("hi", ""))
    return S.AlertItemRead(
        id=alert.id,
        district_ids=list(alert.district_ids or []),
        type=alert.type,  # type: ignore[arg-type]
        severity=alert.severity,
        languages=list(alert.languages or []),
        message=message,
        messages=messages if include_map else None,
        created_at=alert.created_at,
    )


@router.post("/alerts/broadcast", status_code=202, summary="Compose & send a broadcast")
async def broadcast(
    body: S.BroadcastCreate,
    identity: Identity = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> S.BroadcastResponse:
    districts = (
        await session.execute(select(District).where(District.id.in_(body.district_ids)))
    ).scalars().all()
    found = {d.id for d in districts}
    missing = [d for d in body.district_ids if d not in found]
    if missing:
        raise HTTPException(status_code=422, detail=f"unknown district_ids: {missing}")

    languages = body.languages or TEN_LANGS
    district_names = [d.name for d in districts]
    rendered, renderer = render_multilingual(
        alert_type=body.type,
        languages=languages,
        district_names=district_names,
        body=body.body,
        title=body.title,
    )
    now = utcnow()
    alert = Alert(
        district_ids=list(body.district_ids),
        type=body.type,
        severity=body.severity,
        title=body.title,
        body=body.body,
        source_lang="hi",
        messages=rendered,
        languages=languages,
        scheduled_at=body.scheduled_at,
        sent_at=None if body.scheduled_at else now,
        recipient_estimate=estimate_recipients([d.population for d in districts]),
        created_by=identity.actor,
    )
    session.add(alert)
    await session.flush()
    await log_audit(
        session, identity.actor, "alert.broadcast", "alert", alert.id,
        {"district_ids": body.district_ids, "type": body.type,
         "languages": languages, "renderer": renderer},
    )
    await session.commit()
    await emit(
        "alert.broadcast",
        {"broadcast_id": alert.id, "district_ids": body.district_ids,
         "type": body.type, "severity": body.severity, "languages": languages},
    )
    return S.BroadcastResponse(
        broadcast_id=alert.id,
        status="scheduled" if body.scheduled_at else "sent",
        rendered=rendered,
        recipient_estimate=alert.recipient_estimate or 0,
        created_at=alert.created_at,
    )


@router.get("/alerts", summary="Alert feed")
async def list_alerts(
    district: str | None = Query(default=None),
    type: str | None = Query(default=None),
    lang: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> S.Paginated:
    stmt = select(Alert).order_by(Alert.created_at.desc())
    if type:
        stmt = stmt.where(Alert.type == type)
    rows = (await session.execute(stmt)).scalars().all()
    if district:
        rows = [r for r in rows if district in (r.district_ids or [])]
    total = len(rows)
    page = rows[offset: offset + limit]
    # ?lang=all includes the full messages map (Wave 2 amendment, issue #1).
    include_map = lang == "all"
    return paginate(
        total, limit, offset,
        [_alert_item(r, lang, include_map) for r in page],
    )


@router.get("/alerts/{alert_id}", summary="Get one alert (full language map)")
async def get_alert(
    alert_id: str,
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> S.AlertItemRead:
    alert = await session.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="alert not found")
    return _alert_item(alert, None, include_map=True)
