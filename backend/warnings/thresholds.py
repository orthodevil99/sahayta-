"""Threshold rules — risk crossings trigger automatic multilingual broadcasts.

Rules (contracts §3 risk levels):
    risk > 70  → advisory   (level "high")
    risk > 85  → warning    (level "severe")

A crossing fires only on an UPWARD transition of the recomputed risk:
``prev_risk <= 70 < new_risk`` (advisory) or ``prev_risk <= 85 < new_risk``
(warning). When both are crossed in one jump, only the warning fires (a
warning implies the advisory).

The broadcast goes through the SAME rendering + persistence path as the admin
``POST /api/alerts/broadcast`` endpoint (``services.alerts_render``,
``Alert`` row, audit log, WS ``alert.broadcast``) — but as a direct service
call with ``actor="system:early-warning"``, never an HTTP call to ourselves.

Deduplication: at most one automatic broadcast per (district, alert type) per
24 h, so a stuck-high risk doesn't spam the alert feed every ingest cycle.

Alert type is chosen from the dominant risk factor: rainfall/river → flood,
heat → heatwave, wind → cyclone. Severity mapping: advisory → 3, warning → 4.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, District, DistrictRisk
from app.routers.common import emit, log_audit, utcnow
from app.services.alerts_render import (
    TEN_LANGS,
    estimate_recipients,
    render_multilingual,
)

log = logging.getLogger("sahayta.warnings.thresholds")

ADVISORY_THRESHOLD = 70
WARNING_THRESHOLD = 85
DEDUP_HOURS = 24
ACTOR = "system:early-warning"


def check_thresholds(
    prev_risk: int | None, new_risk: int
) -> list[dict]:
    """Return crossing events (highest level only) for a risk transition."""
    events: list[dict] = []
    prev = -1 if prev_risk is None else prev_risk
    if prev <= WARNING_THRESHOLD < new_risk:
        events.append({"kind": "warning", "threshold": WARNING_THRESHOLD,
                       "severity": 4, "prev_risk": prev_risk, "new_risk": new_risk})
    elif prev <= ADVISORY_THRESHOLD < new_risk:
        events.append({"kind": "advisory", "threshold": ADVISORY_THRESHOLD,
                       "severity": 3, "prev_risk": prev_risk, "new_risk": new_risk})
    return events


def _alert_type_for(row: DistrictRisk) -> str:
    """Pick the alert type from the dominant risk factor (contracts §6)."""
    factors = sorted(row.factors or [], key=lambda f: f.get("contribution", 0),
                     reverse=True)
    top = (factors[0].get("name") if factors else "") or ""
    if top == "heat_index":
        return "heatwave"
    if top == "wind_kph":
        return "cyclone"
    return "flood"


async def _recent_system_alert(
    session: AsyncSession, district_id: str, alert_type: str
) -> Alert | None:
    """Dedup guard: a system broadcast for this district+type in the window?"""
    cutoff = utcnow() - timedelta(hours=DEDUP_HOURS)
    recent = (
        await session.execute(
            select(Alert)
            .where(Alert.created_by == ACTOR, Alert.type == alert_type)
            .order_by(Alert.created_at.desc())
            .limit(25)
        )
    ).scalars().all()
    for a in recent:
        created = a.created_at
        if created is not None and created.tzinfo is None:
            created = created.replace(tzinfo=utcnow().tzinfo)
        if created and created >= cutoff and district_id in (a.district_ids or []):
            return a
    return None


def _compose(district: District, event: dict, risk_row: DistrictRisk) -> tuple[str, str]:
    label = "चेतावनी" if event["kind"] == "warning" else "परामर्श"
    title = (
        f"{'Flood risk WARNING' if event['kind'] == 'warning' else 'Flood risk advisory'}: "
        f"{district.name} (risk {risk_row.risk}/100)"
    )
    body = (
        f"Automatic early warning for {district.name}: district risk rose to "
        f"{risk_row.risk}/100 ({risk_row.risk_level}) crossing the "
        f"{event['kind']} threshold of {event['threshold']}. "
        f"{risk_row.advisory or ''} "
        "Avoid low-lying areas and riverbanks. Follow official instructions. "
        f"({label}: स्वचालित पूर्व-चेतावनी)"
    ).strip()
    return title, body


async def broadcast_threshold_alert(
    session: AsyncSession, district: District, event: dict, risk_row: DistrictRisk
) -> Alert | None:
    """Send (or dedup-skip) the automatic broadcast for a threshold crossing."""
    alert_type = _alert_type_for(risk_row)
    if await _recent_system_alert(session, district.id, alert_type):
        log.info("dedup: skipping %s broadcast for %s (sent < %dh ago)",
                 alert_type, district.id, DEDUP_HOURS)
        return None
    title, body = _compose(district, event, risk_row)
    rendered, renderer = render_multilingual(
        alert_type=alert_type,
        languages=TEN_LANGS,
        district_names=[district.name],
        body=body,
        title=title,
    )
    now = utcnow()
    alert = Alert(
        district_ids=[district.id],
        type=alert_type,
        severity=event["severity"],
        title=title,
        body=body,
        source_lang="hi",
        messages=rendered,
        languages=list(TEN_LANGS),
        scheduled_at=None,
        sent_at=now,
        recipient_estimate=estimate_recipients([district.population]),
        created_by=ACTOR,
    )
    session.add(alert)
    await session.flush()
    await log_audit(
        session, ACTOR, "alert.broadcast", "alert", alert.id,
        {"district_ids": [district.id], "type": alert_type,
         "languages": list(TEN_LANGS), "renderer": renderer,
         "trigger": "early_warning_threshold",
         "kind": event["kind"], "risk": risk_row.risk,
         "prev_risk": event.get("prev_risk")},
    )
    await session.commit()
    await emit(
        "alert.broadcast",
        {"broadcast_id": alert.id, "district_ids": [district.id],
         "type": alert_type, "severity": event["severity"],
         "languages": list(TEN_LANGS)},
    )
    log.warning("threshold %s fired for %s (risk %s) — broadcast %s",
                event["kind"], district.id, risk_row.risk, alert.id)
    return alert


async def process_crossings(
    session: AsyncSession,
    recomputed: list[tuple[DistrictRisk | None, DistrictRisk | None]],
) -> list[Alert]:
    """Check threshold crossings for recomputed rows; broadcast as needed.

    ``recomputed`` is the (new_row, prev_row) list from ``recompute_all``.
    Rows that were unchanged (new_row None) can't cross — they are skipped.
    """
    sent: list[Alert] = []
    for new_row, prev_row in recomputed:
        if new_row is None:
            continue
        events = check_thresholds(
            prev_row.risk if prev_row else None, new_row.risk
        )
        if not events:
            continue
        district = await session.get(District, new_row.district_id)
        if district is None:
            continue
        alert = await broadcast_threshold_alert(session, district, events[0], new_row)
        if alert is not None:
            sent.append(alert)
    return sent
