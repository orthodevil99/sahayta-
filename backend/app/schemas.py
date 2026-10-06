"""Pydantic v2 schemas — mirrors docs/data-models.md §2 and the wire shapes in
docs/api-contracts.md. Field names are frozen snake_case end to end.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Severity = Annotated[int, Field(ge=1, le=5)]
SOSStatus = Literal["reported", "verified", "help_on_way", "resolved", "duplicate", "rejected"]
SOSCategory = Literal["medical", "rescue", "food", "shelter", "infrastructure", "other"]
Priority = Literal["low", "medium", "high", "critical"]
TaskStatus = Literal["assigned", "accepted", "declined", "en_route", "completed", "cancelled"]
AlertType = Literal["flood", "heatwave", "cyclone", "custom"]
RiskLevel = Literal["low", "moderate", "high", "severe"]
WeatherSource = Literal["live", "simulated"]
LangCode = Literal["hi", "hing", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "en"]
VolunteerSkill = Literal[
    "medical", "rescue", "driving", "cooking", "shelter_mgmt",
    "translation", "logistics", "counseling", "engineering",
]
SafetyFlagType = Literal["possible_duplicate", "conflicting_reports", "spam_burst", "reporter_flag"]
SafetyFlagStatus = Literal["open", "resolved", "dismissed"]

TEN_LANGS: list[str] = ["hi", "hing", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa"]

LANG_META: list[dict[str, str]] = [    {"code": "hi", "name": "Hindi", "native_name": "हिन्दी"},
    {"code": "hing", "name": "Hinglish", "native_name": "Hinglish"},
    {"code": "bn", "name": "Bengali", "native_name": "বাংলা"},
    {"code": "ta", "name": "Tamil", "native_name": "தமிழ்"},
    {"code": "te", "name": "Telugu", "native_name": "తెలుగు"},
    {"code": "mr", "name": "Marathi", "native_name": "मराठी"},
    {"code": "gu", "name": "Gujarati", "native_name": "ગુજરાતી"},
    {"code": "kn", "name": "Kannada", "native_name": "ಕನ್ನಡ"},
    {"code": "ml", "name": "Malayalam", "native_name": "മലയാളം"},
    {"code": "pa", "name": "Punjabi", "native_name": "ਪੰਜਾਬੀ"},
]


# ------------------------------------------------------------------ validation helpers (Wave 3, Agent 8)

_VALID_DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
_VALID_LANG_CODES = set(TEN_LANGS) | {"en"}


def _validate_languages(v: Any) -> Any:
    if v is None:
        return v
    bad = [c for c in v if c not in _VALID_LANG_CODES]
    if bad:
        raise ValueError(f"unknown language codes: {bad} (use the 10 UI locales or 'en')")
    return v


def _validate_availability(v: Any) -> Any:
    """'anytime' or a list of {day, start, end} windows with HH:MM bounds."""
    if v is None or v == "anytime":
        return v
    if not isinstance(v, list):
        raise ValueError("availability must be 'anytime' or a list of {day,start,end} windows")
    for i, w in enumerate(v):
        if not isinstance(w, dict):
            raise ValueError(f"availability[{i}] must be an object")
        day = str(w.get("day", "")).lower()
        if day not in _VALID_DAYS:
            raise ValueError(f"availability[{i}].day must be one of {sorted(_VALID_DAYS)}")
        for bound in ("start", "end"):
            val = str(w.get(bound, ""))
            try:
                hh, mm = val.split(":")
                if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59 and len(hh) == 2 and len(mm) == 2):
                    raise ValueError
            except ValueError:
                raise ValueError(f"availability[{i}].{bound} must be HH:MM (24h), got {val!r}")
        if w["start"] >= w["end"]:
            raise ValueError(f"availability[{i}]: start must be before end")
    return v


def _as_utc(v: Any) -> datetime:
    """SQLite stores naive datetimes — re-attach UTC on the way out so the
    wire always carries unambiguous ISO 8601 UTC timestamps."""
    if isinstance(v, datetime) and v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


class _RM(BaseModel):
    """Read model base: ORM mode + UTC-normalized datetimes."""

    model_config = ConfigDict(from_attributes=True)

    @field_validator("*", mode="before", check_fields=False)
    @classmethod
    def _utc(cls, v: Any) -> Any:
        return _as_utc(v)


# ------------------------------------------------------------------ SOS

class SOSCreate(BaseModel):
    description: str = Field(min_length=10, max_length=2000)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    district_id: str | None = None
    language: str | None = None
    reporter_name: str | None = Field(default=None, max_length=120)
    reporter_phone: str | None = Field(default=None, max_length=32)
    client_report_id: str = Field(min_length=1, max_length=64)
    photo_description: str | None = None
    photo_id: str | None = None  # id of an already-uploaded photo (POST /api/media)

    @field_validator("language")
    @classmethod
    def _lang_default(cls, v: str | None) -> str:
        return v or "hi"


class AssessmentRead(_RM):
    id: str
    severity: int
    rationale: str
    rationale_en: str | None = None
    area_tags: list[str] = []
    category: SOSCategory
    priority: Priority
    suggested_skills: list[str] = []
    model: str
    assessed_at: datetime


class TaskSummary(_RM):
    id: str
    volunteer_id: str
    volunteer_name: str | None = None
    status: TaskStatus


class SOSRead(_RM):
    id: str
    client_report_id: str
    description: str
    language: str
    category: SOSCategory
    severity: int | None = None
    severity_rationale: str | None = None
    priority: Priority
    status: SOSStatus
    lat: float | None = None
    lon: float | None = None
    district_id: str | None = None
    photo_url: str | None = None
    photo_hash: str | None = None
    photo_description: str | None = None
    reporter_name: str | None = None
    reporter_phone: str | None = None
    needed_skills: list[str] = []
    needs_review: bool = False
    # Verify-queue context only (Wave 2 amendment, issue #9). None elsewhere.
    reason: str | None = None
    # Persisted duplicate-merge link (Wave 4, Agent 10). None unless an admin
    # confirmed this report duplicates another.
    duplicate_of: str | None = None
    # Reporter trust tier for the verify queue (Wave 4, Agent 10):
    # "trusted" | "standard" | "new" | "flagged". None elsewhere.
    reporter_trust_tier: str | None = None
    is_demo_data: bool = False
    created_at: datetime
    updated_at: datetime
    assessment: AssessmentRead | None = None
    tasks: list[TaskSummary] = []


class StatusPatch(BaseModel):
    status: SOSStatus
    note: str | None = Field(default=None, max_length=500)


class VerifyBody(BaseModel):
    verdict: Literal["verified", "rejected", "duplicate"]
    duplicate_of: str | None = None
    note: str | None = Field(default=None, max_length=500)


class FlagBody(BaseModel):
    reason: Literal["duplicate", "misinformation", "spam", "other"]
    note: str | None = Field(default=None, max_length=500)


class AssessRequest(BaseModel):
    description: str = Field(min_length=1, max_length=2000)
    language: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    photo_id: str | None = None


class AssessResponse(BaseModel):
    severity: int
    rationale: str
    area_tags: list[str]
    category: SOSCategory
    priority: Priority
    suggested_skills: list[str]
    model: str
    latency_ms: int


class MediaUploadResponse(BaseModel):
    photo_id: str
    url: str
    photo_hash: str | None = None


# ------------------------------------------------------------------ shelters / districts

class ShelterRead(_RM):
    id: str
    name: str
    district_id: str
    area: str | None = None
    lat: float | None = None
    lon: float | None = None
    capacity: int
    occupied: int
    facilities: list[str] = []
    contact_name: str | None = None
    contact_phone: str | None = None
    is_demo_data: bool = True
    updated_at: datetime


class DistrictRead(_RM):
    id: str
    name: str
    state: str
    lat: float
    lon: float
    population: int | None = None
    risk: int
    risk_level: RiskLevel
    active_sos: int
    active_volunteers: int
    updated_at: datetime


class RiskFactor(BaseModel):
    name: str
    value: float | str
    weight: float
    contribution: float
    note: str


class DistrictRiskRead(BaseModel):
    district_id: str
    risk: int
    risk_level: RiskLevel
    factors: list[RiskFactor]
    computed_at: datetime
    weather_source: WeatherSource
    advisory: str

    @field_validator("computed_at", mode="before")
    @classmethod
    def _utc2(cls, v: Any) -> Any:
        return _as_utc(v)


class ForecastHour(BaseModel):
    ts: datetime
    rain_mm: float
    temp_c: float
    humidity: float
    wind_kph: float
    risk: int
    risk_level: RiskLevel

    @field_validator("ts", mode="before")
    @classmethod
    def _utc3(cls, v: Any) -> Any:
        return _as_utc(v)


class ForecastRead(BaseModel):
    district_id: str
    weather_source: WeatherSource
    hours: list[ForecastHour]


# ------------------------------------------------------------------ volunteers / tasks

class VolunteerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    district_id: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    skills: list[VolunteerSkill] = Field(min_length=1)
    languages: list[str] = Field(default=["hi"])
    availability: str | list[dict[str, Any]] = "anytime"
    active: bool = True

    _languages = field_validator("languages")(_validate_languages)
    _availability = field_validator("availability")(_validate_availability)

    @model_validator(mode="after")
    def _lat_lon_together(self) -> "VolunteerCreate":
        if (self.lat is None) != (self.lon is None):
            raise ValueError("lat and lon must be provided together or not at all")
        return self


class VolunteerPatch(BaseModel):
    """Accepted PATCH /api/volunteers/{id} fields (Wave 2 amendment, issue #3)."""

    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    district_id: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    skills: list[VolunteerSkill] | None = None
    languages: list[str] | None = None
    availability: str | list[dict[str, Any]] | None = None
    active: bool | None = None

    _languages = field_validator("languages")(_validate_languages)
    _availability = field_validator("availability")(_validate_availability)

    @model_validator(mode="after")
    def _lat_lon_together(self) -> "VolunteerPatch":
        if (self.lat is None) != (self.lon is None):
            raise ValueError("lat and lon must be provided together or not at all")
        return self


class VolunteerRead(_RM):
    id: str
    name: str
    phone: str | None = None
    district_id: str | None = None
    lat: float | None = None
    lon: float | None = None
    skills: list[str] = []
    languages: list[str] = []
    availability: Any = "anytime"
    active: bool = True
    reputation: int = 50
    tasks_completed: int = 0
    avg_response_min: float | None = None
    created_at: datetime


class VolunteerMatchRead(BaseModel):
    volunteer: VolunteerRead
    score: float
    distance_km: float
    reasons: list[str]
    # Wave 3 (Agent 8, additive): 0–1 components feeding the frozen formula —
    # score = 0.45*skill + 0.30*distance + 0.15*availability + 0.10*reputation
    score_breakdown: dict[str, float] | None = None


class MatchRequest(BaseModel):
    sos_id: str
    max_results: int = Field(default=5, ge=1, le=20)
    max_distance_km: float = Field(default=25.0, gt=0, le=500)


class MatchResponse(BaseModel):
    sos_id: str
    matches: list[VolunteerMatchRead]


class TaskCreate(BaseModel):
    sos_id: str
    volunteer_id: str
    note: str | None = Field(default=None, max_length=500)


class TaskDecline(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class TaskComplete(BaseModel):
    note: str | None = Field(default=None, max_length=500)
    proof_photo_id: str | None = None


class TaskRead(_RM):
    id: str
    sos_id: str
    volunteer_id: str
    status: TaskStatus
    note: str | None = None
    assigned_at: datetime
    accepted_at: datetime | None = None
    completed_at: datetime | None = None
    proof_photo_url: str | None = None
    created_at: datetime
    updated_at: datetime
    volunteer: VolunteerRead | None = None
    sos: dict[str, Any] | None = None


# ------------------------------------------------------------------ alerts

class BroadcastCreate(BaseModel):
    district_ids: list[str] = Field(min_length=1)
    type: AlertType
    title: str = Field(max_length=200)
    body: str = Field(min_length=10, max_length=2000)
    severity: int | None = Field(default=None, ge=1, le=5)
    languages: list[str] | None = None  # default: all 10
    scheduled_at: datetime | None = None


class BroadcastResponse(BaseModel):
    broadcast_id: str
    status: str
    rendered: dict[str, str]
    recipient_estimate: int
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def _utc4(cls, v: Any) -> Any:
        return _as_utc(v)


class AlertItemRead(_RM):
    id: str
    district_ids: list[str]
    type: AlertType
    severity: int | None = None
    languages: list[str] = []
    message: str
    # Full per-language map: only on GET /api/alerts/{id}, or on list when
    # ?lang=all (Wave 2 amendment, issue #1).
    messages: dict[str, str] | None = None
    created_at: datetime


# ------------------------------------------------------------------ admin / safety / users

class AdminOverviewRead(BaseModel):
    district_id: str | None = None
    # NOTE: sos_by_severity keeps STRING keys "1"-"5" (contract freeze, issue #6).
    sos_by_status: dict[str, int]
    sos_by_severity: dict[str, int]
    active_tasks: int
    volunteers_active: int
    volunteers_on_task: int
    shelters_open: int
    shelter_occupancy_pct: float
    district_risk: int | None = None
    risk_level: RiskLevel | None = None
    pending_verifications: int
    open_safety_flags: int
    generated_at: datetime

    @field_validator("generated_at", mode="before")
    @classmethod
    def _utc5(cls, v: Any) -> Any:
        return _as_utc(v)


class SafetyFlagRead(_RM):
    id: str
    type: str
    sos_ids: list[str] = []
    district_id: str | None = None
    evidence: str | None = None
    status: str = "open"
    created_at: datetime


class FlagResolveBody(BaseModel):
    # "confirmed" covers confirmed spam_burst / conflicting_reports;
    # "confirmed_duplicate" additionally triggers duplicate-merge.
    resolution: Literal["confirmed_duplicate", "confirmed", "false_alarm"]
    note: str | None = Field(default=None, max_length=500)


class AuditEntryRead(_RM):
    id: str
    ts: datetime
    actor: str
    action: str
    target_type: str
    target_id: str
    details: dict[str, Any] = {}


class UserPatch(BaseModel):
    """PATCH /api/users/me (Wave 2 amendment, issue #4)."""

    preferred_lang: str | None = None
    display_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=32)


class UserRead(_RM):
    id: str
    device_id: str
    role: str
    display_name: str | None = None
    phone: str | None = None
    preferred_lang: str = "hi"
    created_at: datetime


class ExportIncidentJSON(BaseModel):
    district_id: str
    exported_at: datetime
    district: dict[str, Any]
    risk: dict[str, Any] | None
    sos_reports: list[dict[str, Any]]
    tasks: list[dict[str, Any]]
    alerts: list[dict[str, Any]]

    @field_validator("exported_at", mode="before")
    @classmethod
    def _utc6(cls, v: Any) -> Any:
        return _as_utc(v)


# ------------------------------------------------------------------ meta

class HealthRead(BaseModel):
    status: str
    version: str
    db: str
    llm: str  # "configured" | "fallback"
    weather: str  # "live" | "simulated"
    ts: datetime

    @field_validator("ts", mode="before")
    @classmethod
    def _utc7(cls, v: Any) -> Any:
        return _as_utc(v)


class WarningsStatusRead(BaseModel):
    enabled: bool
    mode: WeatherSource
    weather_api: str
    districts_tracked: int
    last_ingest_at: datetime | None = None
    last_ingest_ok: bool
    last_risk_recompute_at: datetime | None = None
    next_ingest_at: datetime | None = None

    @field_validator("last_ingest_at", "last_risk_recompute_at", "next_ingest_at", mode="before")
    @classmethod
    def _utc8(cls, v: Any) -> Any:
        return _as_utc(v)


class Paginated(BaseModel):
    items: list[Any]
    total: int
    limit: int
    offset: int


class LanguageMeta(BaseModel):
    code: str
    name: str
    native_name: str
