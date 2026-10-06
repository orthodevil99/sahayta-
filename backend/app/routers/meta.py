"""Meta router — contracts §9 + §11: health, languages, warnings status."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import ai_client, schemas as S
from ..auth import Identity, require_identity
from ..config import Settings, get_settings
from ..database import get_session
from ..models import District, DistrictRisk, DistrictWeatherSample
from .common import utcnow

router = APIRouter(prefix="/api", tags=["meta"])

VERSION = "1.0.0-wave2"


@router.get("/health", summary="Health check")
async def health(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> S.HealthRead:
    db_ok = "ok"
    try:
        await session.execute(select(1))
    except Exception:  # noqa: BLE001 — report, don't crash
        db_ok = "error"
    return S.HealthRead(
        status="ok" if db_ok == "ok" else "degraded",
        version=VERSION,
        db=db_ok,
        llm=ai_client.engine_status(),
        weather=settings.weather_mode if settings.weather_mode in ("live", "simulated") else "simulated",
        ts=utcnow(),
    )


@router.get("/meta/languages", summary="Supported UI/alert languages")
async def meta_languages() -> dict:
    return {"languages": S.LANG_META}


@router.get("/warnings/status", summary="Early-warning pipeline health")
async def warnings_status(
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> S.WarningsStatusRead:
    mode = settings.weather_mode if settings.weather_mode in ("live", "simulated") else "simulated"
    districts_tracked = (await session.execute(select(func.count()).select_from(District))).scalar_one()

    last_sample = (
        await session.execute(
            select(DistrictWeatherSample.ingested_at)
            .order_by(DistrictWeatherSample.ingested_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    last_risk = (
        await session.execute(
            select(DistrictRisk.computed_at)
            .order_by(DistrictRisk.computed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    next_ingest = (
        last_sample + timedelta(minutes=settings.weather_ingest_minutes)
        if last_sample
        else None
    )
    return S.WarningsStatusRead(
        enabled=True,
        mode=mode,  # type: ignore[arg-type]
        weather_api=settings.weather_api_url,
        districts_tracked=int(districts_tracked),
        last_ingest_at=last_sample,
        last_ingest_ok=last_sample is not None,
        last_risk_recompute_at=last_risk,
        next_ingest_at=next_ingest,
    )
