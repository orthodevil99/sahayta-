"""SOS intake & triage router — contracts §1.

POST /api/sos accepts BOTH ``multipart/form-data`` (photo upload) and
``application/json`` (text/demo mode, optional ``photo_description`` /
``photo_id``) on the same path — content type is negotiated per request.

The AI pipeline runs synchronously inside POST /api/sos but intake NEVER
fails: on pipeline error the report persists with severity=None +
needs_review=True.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import case, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .. import ai_client, schemas as S
from ..auth import Identity, require_admin, require_identity, require_sos_identity
from ..config import Settings, get_settings
from ..database import get_session
from ..geo import haversine_km
from ..media import ALLOWED_CONTENT_TYPES, sniff_ok, store_photo
from ..models import District, MediaFile, SafetyFlag, SOSReport, SeverityAssessment, Task
from ..services.safety import (
    check_conflicting_reports,
    check_duplicate_photo,
    check_spam_burst,
)
from .common import (
    SOS_TRANSITIONS,
    count_total,
    emit,
    load_sos_full,
    log_audit,
    paginate,
    sos_compact,
    sos_to_read,
    utcnow,
    verify_reason_for,
)

log = logging.getLogger("sahayta.routers.sos")

router = APIRouter(prefix="/api", tags=["sos"])

PRIORITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def _json(model: S.BaseModel, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=model.model_dump(mode="json"))


async def _resolve_district(
    session: AsyncSession, district_id: str | None, lat: float | None, lon: float | None
) -> str | None:
    if district_id:
        district = await session.get(District, district_id)
        if district is None:
            raise HTTPException(status_code=422, detail=f"unknown district_id: {district_id}")
        return district.id
    if lat is not None and lon is not None:
        districts = (await session.execute(select(District))).scalars().all()
        if not districts:
            return None
        return min(districts, key=lambda d: haversine_km(lat, lon, d.lat, d.lon)).id
    return None


async def _run_pipeline_and_persist(
    session: AsyncSession,
    sos: SOSReport,
    photo_description: str | None,
) -> None:
    """Run assess_and_route synchronously; never let AI failure break intake."""
    try:
        result = ai_client.assess_and_route(
            description=sos.description,
            language=sos.language,
            lat=sos.lat,
            lon=sos.lon,
            photo_description=photo_description,
            photo_path=None,
        )
    except Exception as exc:  # noqa: BLE001 — intake must never fail
        log.exception("AI pipeline hard failure on SOS %s", sos.id)
        sos.severity = None
        sos.category = "other"
        sos.priority = "medium"
        sos.needs_review = True
        sos.needs_review_reason = "assessment_failed"
        await session.flush()
        await emit(
            "sos.assessed",
            {"sos_id": sos.id, "severity": None, "model": "failed",
             "needs_review": True, "error": str(exc)[:200]},
        )
        return

    session.add(
        SeverityAssessment(
            sos_report_id=sos.id,
            severity=result.severity,
            rationale=result.rationale,
            rationale_en=result.rationale_en,
            area_tags=result.area_tags,
            category=result.category,
            priority=result.priority,
            suggested_skills=result.suggested_skills,
            model=result.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            latency_ms=result.latency_ms,
        )
    )
    sos.severity = result.severity
    sos.category = result.category
    sos.priority = result.priority
    sos.needed_skills = result.suggested_skills
    await session.flush()
    await emit(
        "sos.assessed",
        {
            "sos_id": sos.id,
            "severity": result.severity,
            "category": result.category,
            "priority": result.priority,
            "rationale": result.rationale,
            "model": result.model,
        },
    )


async def _create_sos_core(
    session: AsyncSession,
    identity: Identity,
    settings: Settings,
    *,
    description: str,
    lat: float | None,
    lon: float | None,
    district_id: str | None,
    language: str | None,
    reporter_name: str | None,
    reporter_phone: str | None,
    client_report_id: str,
    photo_description: str | None,
    photo_bytes: bytes | None,
    photo_content_type: str | None,
    photo_id: str | None,
) -> tuple[SOSReport, int]:
    # ---- validation ------------------------------------------------------
    if not (10 <= len(description) <= 2000):
        raise HTTPException(status_code=422, detail="description must be 10-2000 chars")
    if not ((lat is not None and lon is not None) or district_id):
        raise HTTPException(status_code=422, detail="lat+lon or district_id is required")
    if lat is not None and not (-90 <= lat <= 90):
        raise HTTPException(status_code=422, detail="lat out of range")
    if lon is not None and not (-180 <= lon <= 180):
        raise HTTPException(status_code=422, detail="lon out of range")

    # ---- idempotent replay (offline outbox) -------------------------------
    existing = (
        await session.execute(
            select(SOSReport).where(SOSReport.client_report_id == client_report_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return (await load_sos_full(session, existing.id)) or existing, 200

    # ---- spam burst throttle (Wave 4, Agent 10) ---------------------------
    # N reports from one device in M minutes -> flag + 429. Already-filed
    # reports stay visible; nothing is deleted.
    spam_evidence = await check_spam_burst(
        session, settings,
        device_id=identity.device_id,
        district_id=district_id,
    )
    if spam_evidence:
        await log_audit(
            session, identity.actor, "sos.spam_throttled", "sos", "pending",
            {"device_id": identity.device_id, "evidence": spam_evidence},
        )
        await session.commit()
        raise HTTPException(
            status_code=429,
            detail="too many reports from this device; please wait a few minutes",
            headers={"Retry-After": str(settings.safety_spam_window_minutes * 60)},
        )

    # ---- photo ------------------------------------------------------------
    photo_url, photo_hash = None, None
    if photo_bytes is not None:
        if photo_content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(status_code=422, detail="photo must be jpeg/png/webp")
        if len(photo_bytes) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(status_code=413, detail="photo too large")
        if not sniff_ok(photo_bytes, photo_content_type):
            log.warning("sos intake magic-byte mismatch: claimed %s", photo_content_type)
            raise HTTPException(
                status_code=422,
                detail="file bytes do not match the claimed image type",
            )
        new_id, photo_url, photo_hash = store_photo(
            photo_bytes, photo_content_type, settings.media_path, "sos"
        )
        session.add(
            MediaFile(
                id=new_id, url=photo_url, photo_hash=photo_hash,
                content_type=photo_content_type, size_bytes=len(photo_bytes),
                uploaded_by=identity.device_id,
            )
        )
    elif photo_id:
        media_row = await session.get(MediaFile, photo_id)
        if media_row is None:
            raise HTTPException(status_code=422, detail=f"unknown photo_id: {photo_id}")
        photo_url, photo_hash = media_row.url, media_row.photo_hash

    resolved_district = await _resolve_district(session, district_id, lat, lon)

    sos = SOSReport(
        client_report_id=client_report_id,
        description=description,
        language=language or settings.default_lang,
        lat=lat,
        lon=lon,
        district_id=resolved_district,
        photo_url=photo_url,
        photo_hash=photo_hash,
        photo_description=photo_description,
        reporter_name=reporter_name,
        reporter_phone=reporter_phone,
        reporter_device_id=identity.device_id,
        status="reported",
    )
    session.add(sos)
    try:
        await session.flush()
    except IntegrityError:
        # Lost a race with an identical client_report_id -> return the winner.
        await session.rollback()
        winner = (
            await session.execute(
                select(SOSReport).where(SOSReport.client_report_id == client_report_id)
            )
        ).scalar_one()
        return (await load_sos_full(session, winner.id)) or winner, 200

    await emit("sos.created", sos_compact(sos))
    await _run_pipeline_and_persist(session, sos, photo_description)

    # ---- safety triage (Wave 4, Agent 10) ---------------------------------
    # Nothing here drops the report — flags mark it for human review.
    dup_evidence = await check_duplicate_photo(
        session, settings,
        photo_hash=photo_hash, new_id=sos.id, district_id=sos.district_id,
        lat=sos.lat, lon=sos.lon,
    )
    if dup_evidence:
        sos.needs_review = True
        sos.needs_review_reason = "possible_duplicate"
        await session.flush()
    conflict_evidence = await check_conflicting_reports(
        session, settings, sos=sos,
    )
    if conflict_evidence and not sos.needs_review:
        sos.needs_review = True
        sos.needs_review_reason = "conflicting_reports"
        await session.flush()
    if conflict_evidence:
        await emit(
            "safety.flag_raised",
            {"type": "conflicting_reports", "sos_id": sos.id,
             "district_id": sos.district_id},
        )

    await log_audit(
        session, identity.actor, "sos.created", "sos", sos.id,
        {"district_id": sos.district_id, "severity": sos.severity},
    )
    await session.commit()
    return (await load_sos_full(session, sos.id)) or sos, 201


@router.post("/sos", status_code=201, summary="File an SOS report")
async def create_sos(
    request: Request,
    identity: Identity = Depends(require_sos_identity),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Accepts multipart/form-data (photo upload) OR application/json
    (text/demo mode). Idempotent on client_report_id: replays return 200."""
    ctype = request.headers.get("content-type", "")
    if "multipart/form-data" in ctype:
        form = await request.form()
        photo_bytes, photo_ct = None, None
        upload = form.get("photo")
        if upload is not None and hasattr(upload, "read"):
            photo_bytes = await upload.read()  # type: ignore[union-attr]
            photo_ct = upload.content_type  # type: ignore[union-attr]

        def _f(name: str):
            v = form.get(name)
            return None if v in (None, "") else v

        def _f_float(name: str):
            v = _f(name)
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail=f"invalid {name}")

        kwargs = dict(
            description=_f("description") or "",
            lat=_f_float("lat"),
            lon=_f_float("lon"),
            district_id=_f("district_id"),
            language=_f("language"),
            reporter_name=_f("reporter_name"),
            reporter_phone=_f("reporter_phone"),
            client_report_id=_f("client_report_id") or "",
            photo_description=_f("photo_description"),
            photo_bytes=photo_bytes,
            photo_content_type=photo_ct,
            photo_id=_f("photo_id"),
        )
    else:
        try:
            payload = S.SOSCreate.model_validate(await request.json())
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        kwargs = dict(
            description=payload.description,
            lat=payload.lat,
            lon=payload.lon,
            district_id=payload.district_id,
            language=payload.language,
            reporter_name=payload.reporter_name,
            reporter_phone=payload.reporter_phone,
            client_report_id=payload.client_report_id,
            photo_description=payload.photo_description,
            photo_bytes=None,
            photo_content_type=None,
            photo_id=payload.photo_id,
        )

    sos, code = await _create_sos_core(session, identity, settings, **kwargs)
    return _json(sos_to_read(sos, reason=verify_reason_for(sos)), code)


@router.get("/sos", summary="List / filter SOS reports")
async def list_sos(
    district: str | None = Query(default=None),
    severity_min: int | None = Query(default=None, ge=1, le=5),
    severity_max: int | None = Query(default=None, ge=1, le=5),
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    q: str | None = Query(default=None),
    verified_only: bool = Query(default=False),
    since: str | None = Query(default=None),
    sort: str = Query(default="-created_at"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> S.Paginated:
    stmt = select(SOSReport).options(
        selectinload(SOSReport.assessment),
        selectinload(SOSReport.tasks).selectinload(Task.volunteer),
    )
    if district:
        stmt = stmt.where(SOSReport.district_id == district)
    if severity_min is not None:
        stmt = stmt.where(SOSReport.severity >= severity_min)
    if severity_max is not None:
        stmt = stmt.where(SOSReport.severity <= severity_max)
    if status:
        stmt = stmt.where(SOSReport.status == status)
    if category:
        stmt = stmt.where(SOSReport.category == category)
    if priority:
        stmt = stmt.where(SOSReport.priority == priority)
    if q:
        stmt = stmt.where(SOSReport.description.ilike(f"%{q}%"))
    if verified_only:
        stmt = stmt.where(SOSReport.status == "verified")
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=422, detail="invalid since timestamp")
        stmt = stmt.where(SOSReport.created_at >= since_dt)

    # sort=severity is DESCENDING (most severe first) — contract amendment #5.
    if sort == "severity":
        stmt = stmt.order_by(SOSReport.severity.desc().nulls_last(),
                             SOSReport.created_at.desc())
    elif sort == "priority":
        stmt = stmt.order_by(
            case(PRIORITY_ORDER, value=SOSReport.priority, else_=0).desc(),
            SOSReport.created_at.desc(),
        )
    else:  # "-created_at" default
        stmt = stmt.order_by(SOSReport.created_at.desc())

    total = await count_total(session, stmt)
    rows = (
        await session.execute(stmt.limit(limit).offset(offset))
    ).scalars().all()
    return paginate(total, limit, offset, [sos_to_read(r) for r in rows])


@router.get("/sos/{sos_id}", summary="Get one SOS report (full, with assessment)")
async def get_sos(
    sos_id: str,
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> S.SOSRead:
    sos = await load_sos_full(session, sos_id)
    if sos is None:
        raise HTTPException(status_code=404, detail="sos not found")
    return sos_to_read(sos)


@router.patch("/sos/{sos_id}", summary="Status transition")
async def patch_sos(
    sos_id: str,
    body: S.StatusPatch,
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> S.SOSRead:
    sos = await load_sos_full(session, sos_id)
    if sos is None:
        raise HTTPException(status_code=404, detail="sos not found")
    if not identity.is_admin and sos.reporter_device_id != identity.device_id:
        raise HTTPException(
            status_code=403, detail="only the reporter device or an admin can transition"
        )
    allowed = SOS_TRANSITIONS.get(sos.status, set())
    if body.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"illegal transition {sos.status} → {body.status}",
        )
    from_status = sos.status
    sos.status = body.status
    sos.updated_at = utcnow()
    await log_audit(
        session, identity.actor, "sos.status_changed", "sos", sos.id,
        {"from": from_status, "to": body.status, "note": body.note},
    )
    await session.commit()
    await emit(
        "sos.status_changed",
        {"sos_id": sos.id, "from": from_status, "to": body.status,
         "note": body.note, "district_id": sos.district_id},
    )
    return sos_to_read((await load_sos_full(session, sos.id)) or sos)


@router.post("/sos/{sos_id}/verify", summary="Admin verification")
async def verify_sos(
    sos_id: str,
    body: S.VerifyBody,
    identity: Identity = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> S.SOSRead:
    sos = await load_sos_full(session, sos_id)
    if sos is None:
        raise HTTPException(status_code=404, detail="sos not found")
    if body.verdict == "duplicate" and not body.duplicate_of:
        raise HTTPException(status_code=422, detail="duplicate_of is required for duplicate verdict")
    if body.duplicate_of:
        target = await session.get(SOSReport, body.duplicate_of)
        if target is None:
            raise HTTPException(status_code=422, detail="duplicate_of target not found")

    mapping = {"verified": "verified", "rejected": "rejected", "duplicate": "duplicate"}
    from_status = sos.status
    sos.status = mapping[body.verdict]
    if body.verdict == "duplicate":
        # Persist the merge link (Wave 4, Agent 10): the duplicate stays
        # visible and queryable, linked to the canonical report.
        sos.duplicate_of = body.duplicate_of
    sos.needs_review = False
    sos.needs_review_reason = None
    sos.updated_at = utcnow()
    await log_audit(
        session, identity.actor, "sos.verified", "sos", sos.id,
        {"verdict": body.verdict, "from": from_status,
         "duplicate_of": body.duplicate_of, "note": body.note},
    )
    await session.commit()
    await emit(
        "sos.status_changed",
        {"sos_id": sos.id, "from": from_status, "to": sos.status,
         "note": body.note, "district_id": sos.district_id},
    )
    return sos_to_read((await load_sos_full(session, sos.id)) or sos)


@router.post("/sos/{sos_id}/flag", status_code=201, summary="Flag a report")
async def flag_sos(
    sos_id: str,
    body: S.FlagBody,
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
):
    sos = await session.get(SOSReport, sos_id)
    if sos is None:
        raise HTTPException(status_code=404, detail="sos not found")
    flag = SafetyFlag(
        type="reporter_flag",
        sos_ids=[sos_id],
        district_id=sos.district_id,
        evidence=f"reporter_flag: {body.reason}" + (f" — {body.note}" if body.note else ""),
        status="open",
    )
    session.add(flag)
    sos.needs_review = True
    sos.needs_review_reason = "reporter_flagged"
    await log_audit(
        session, identity.actor, "sos.flagged", "sos", sos_id,
        {"reason": body.reason, "note": body.note},
    )
    await session.commit()
    return {"id": flag.id, "status": "received"}


@router.post("/assess", summary="Standalone severity estimation")
async def assess(
    body: S.AssessRequest,
    identity: Identity = Depends(require_identity),
    settings: Settings = Depends(get_settings),
) -> S.AssessResponse:
    language = body.language or settings.default_lang
    try:
        result = ai_client.assess_and_route(
            description=body.description,
            language=language,
            lat=body.lat,
            lon=body.lon,
        )
    except Exception as exc:  # noqa: BLE001 — assess must answer, never 500 on AI error
        log.exception("assess failed")
        raise HTTPException(status_code=502, detail=f"assessment failed: {exc}")
    return S.AssessResponse(
        severity=result.severity,
        rationale=result.rationale,
        area_tags=result.area_tags,
        category=result.category,  # type: ignore[arg-type]
        priority=result.priority,  # type: ignore[arg-type]
        suggested_skills=result.suggested_skills,
        model=result.model,
        latency_ms=result.latency_ms,
    )
