"""Volunteer matching engine — implements the FROZEN formula from
docs/api-contracts.md §5 (Wave 1, Agent 1):

    score = 0.45*skill_match + 0.30*distance_score
          + 0.15*availability + 0.10*reputation_norm
    distance_score = max(0, 1 - distance_km / max_distance_km)

Wave 3 (Agent 8) may extend the *inputs* (e.g. better availability windows);
the formula itself must not drift — the demo-director depends on it.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..geo import haversine_km
from ..models import SOSReport, Volunteer

W_SKILL = 0.45
W_DISTANCE = 0.30
W_AVAILABILITY = 0.15
W_REPUTATION = 0.10


def _skill_match(needed: list[str], have: list[str]) -> float:
    if not needed:
        return 1.0
    have_set = {s.lower() for s in (have or [])}
    hits = sum(1 for s in needed if s.lower() in have_set)
    return hits / len(needed)


def _availability_score(availability, now: datetime | None = None) -> tuple[float, str]:
    """Returns (score, reason-fragment)."""
    if availability == "anytime" or not availability:
        return 1.0, "available now"
    if isinstance(availability, list):
        now = now or datetime.now(timezone.utc)
        day = now.strftime("%a").lower()  # mon..sun
        hm = now.strftime("%H:%M")
        for window in availability:
            try:
                if (
                    str(window.get("day", "")).lower().startswith(day)
                    and str(window.get("start", "00:00")) <= hm <= str(window.get("end", "23:59"))
                ):
                    return 1.0, "available now"
            except Exception:  # noqa: BLE001 — malformed window -> not available
                continue
        return 0.0, "not in availability window"
    return 0.5, "availability unclear"


def score_volunteer(
    sos: SOSReport,
    volunteer: Volunteer,
    max_distance_km: float,
) -> tuple[float, float, list[str]]:
    """Returns (score_0_100, distance_km, reasons)."""
    needed = list(sos.needed_skills or [])
    have = list(volunteer.skills or [])
    skill = _skill_match(needed, have)

    if sos.lat is not None and sos.lon is not None and volunteer.lat is not None and volunteer.lon is not None:
        distance_km = haversine_km(sos.lat, sos.lon, volunteer.lat, volunteer.lon)
    else:
        distance_km = max_distance_km  # no coords -> worst distance score, still listed
    distance_score = max(0.0, 1.0 - distance_km / max_distance_km)

    avail_score, avail_reason = _availability_score(volunteer.availability)
    reputation_norm = max(0, min(100, volunteer.reputation or 0)) / 100.0

    score = (
        W_SKILL * skill
        + W_DISTANCE * distance_score
        + W_AVAILABILITY * avail_score
        + W_REPUTATION * reputation_norm
    )
    score_100 = round(score * 100, 1)

    reasons: list[str] = []
    matched_skills = [s for s in needed if s.lower() in {h.lower() for h in have}]
    if matched_skills:
        reasons.append(f"skill match: {', '.join(matched_skills)}")
    elif needed:
        reasons.append("no skill overlap")
    reasons.append(f"{distance_km:.1f} km away")
    reasons.append(avail_reason)
    reasons.append(f"reputation {volunteer.reputation}")
    return score_100, round(distance_km, 2), reasons


def rank_volunteers(
    sos: SOSReport,
    volunteers: list[Volunteer],
    max_results: int = 5,
    max_distance_km: float = 25.0,
) -> list[tuple[Volunteer, float, float, list[str]]]:
    """Filter to active volunteers within range, score, sort desc.

    Tie-breakers (Wave 3, Agent 8 — deterministic, formula untouched):
    score desc → reputation desc → distance asc → volunteer id asc.
    The demo-director depends on a stable order when scores tie.
    """
    scored = []
    for v in volunteers:
        if not v.active:
            continue
        score, dist, reasons = score_volunteer(sos, v, max_distance_km)
        if dist <= max_distance_km:
            scored.append((v, score, dist, reasons))
    scored.sort(key=lambda t: (-t[1], -(t[0].reputation or 0), t[2], t[0].id))
    return scored[:max_results]


def score_breakdown(
    sos: SOSReport,
    volunteer: Volunteer,
    max_distance_km: float,
) -> dict[str, float]:
    """Explainability: the 0–1 components feeding the frozen formula.

    score = 0.45*skill + 0.30*distance + 0.15*availability + 0.10*reputation
    """
    needed = list(sos.needed_skills or [])
    have = list(volunteer.skills or [])
    skill = _skill_match(needed, have)
    if sos.lat is not None and sos.lon is not None and volunteer.lat is not None and volunteer.lon is not None:
        distance_km = haversine_km(sos.lat, sos.lon, volunteer.lat, volunteer.lon)
    else:
        distance_km = max_distance_km
    distance = max(0.0, 1.0 - distance_km / max_distance_km)
    availability, _ = _availability_score(volunteer.availability)
    reputation = max(0, min(100, volunteer.reputation or 0)) / 100.0
    return {
        "skill": round(skill, 3),
        "distance": round(distance, 3),
        "availability": round(availability, 3),
        "reputation": round(reputation, 3),
    }
