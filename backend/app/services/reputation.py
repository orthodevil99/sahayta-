"""Reputation engine — server-managed volunteer reputation.

FORMULA (documented here; implemented below; never client-set):

    reputation ∈ [0, 100], starts at 50 on registration.

    Event                              Effect
    ---------------------------------- -------------------------------
    task completed                     +2  (cap 100)
    declined AFTER accept / en_route   −5  (floor 0)  — a broken
    (a commitment was made)                 commitment
    instant decline (assigned→declined) 0  — the pipeline re-offers the
                                            task to the next-ranked
                                            volunteer instead of punishing

    Response time: on every accept, the accept latency
    (accepted_at − assigned_at) feeds a running average
    ``avg_response_min``. It is informational — coordinators read it as the
    "response time" component — and does not move the 0–100 score directly.

    Reliability (computed, not stored):
        reliability_pct = 100 * completed / max(1, completed + declined_after_commit)
    ``tasks_declined`` counts only decline-after-commit, matching the −5 rule.

    Tiers (display only):
        ≥ 90  "guardian"    ≥ 70  "responder"
        ≥ 40  "helper"      else  "newcomer"

Contracts reference: api-contracts.md §4 (VolunteerRead.reputation) and §5
(task lifecycle side effects). The +2/−5/50 numbers are frozen by Wave 2;
this module centralizes them so routers cannot drift.
"""
from __future__ import annotations

from typing import Protocol

START_REPUTATION = 50
COMPLETE_BONUS = 2
DECLINE_AFTER_COMMIT_PENALTY = 5
REPUTATION_CAP = 100
REPUTATION_FLOOR = 0


class _VolunteerLike(Protocol):
    reputation: int
    tasks_completed: int
    tasks_declined: int
    avg_response_min: float | None


def on_task_completed(volunteer: _VolunteerLike) -> int:
    """Apply the completion bonus. Returns the new reputation."""
    volunteer.reputation = min(REPUTATION_CAP, (volunteer.reputation or 0) + COMPLETE_BONUS)
    volunteer.tasks_completed = (volunteer.tasks_completed or 0) + 1
    return volunteer.reputation


def on_decline_after_commit(volunteer: _VolunteerLike) -> int:
    """Apply the broken-commitment penalty. Returns the new reputation."""
    volunteer.reputation = max(
        REPUTATION_FLOOR, (volunteer.reputation or 0) - DECLINE_AFTER_COMMIT_PENALTY
    )
    volunteer.tasks_declined = (volunteer.tasks_declined or 0) + 1
    return volunteer.reputation


def record_response_time(volunteer: _VolunteerLike, minutes: float) -> float:
    """Fold an accept latency into the running average. Returns the new average."""
    prev = volunteer.avg_response_min
    new_avg = minutes if prev is None else round((prev + minutes) / 2, 1)
    volunteer.avg_response_min = new_avg
    return new_avg


def reliability_pct(volunteer: _VolunteerLike) -> float:
    """Share of commitments honored (0–100). Instant declines don't count —
    they never became commitments."""
    completed = volunteer.tasks_completed or 0
    broken = volunteer.tasks_declined or 0
    denom = completed + broken
    if denom == 0:
        return 100.0
    return round(100.0 * completed / denom, 1)


def reputation_tier(score: int | float) -> str:
    """Display tier for a reputation score."""
    s = score or 0
    if s >= 90:
        return "guardian"
    if s >= 70:
        return "responder"
    if s >= 40:
        return "helper"
    return "newcomer"


def reputation_detail(volunteer: _VolunteerLike, volunteer_id: str) -> dict:
    """Full reputation read-model for GET /api/volunteers/{id}/reputation."""
    score = volunteer.reputation or 0
    return {
        "volunteer_id": volunteer_id,
        "reputation": score,
        "tasks_completed": volunteer.tasks_completed or 0,
        "tasks_declined": volunteer.tasks_declined or 0,
        "avg_response_min": volunteer.avg_response_min,
        "reliability_pct": reliability_pct(volunteer),
        "tier": reputation_tier(score),
    }
