"""SQLAlchemy 2.0 models — mirrors docs/data-models.md verbatim.

Conventions (from data-models.md):
- PKs: UUID v4 as String(36) — portable across SQLite/Postgres.
- Timestamps: tz-aware UTC, server_default=func.now().
- Enums: soft String columns validated by Pydantic Literals; CHECK constraints
  in the Alembic migration.
- Every table indexed on (district_id) where present and on created_at.
- ``is_demo_data`` flags synthetic rows; runtime writes set False, except
  shelters which are always synthetic in v1.

Additive Wave-2 additions (documented in docs/api-contracts.md changelog):
- ``MediaFile`` — backing store for POST /api/media (photo_id minting).
- ``SOSReport.needs_review_reason`` — powers the verify-queue ``reason`` field.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def uuid4_str() -> str:
    return str(uuid.uuid4())


class District(Base):
    """Operational unit — 20 canonical districts seeded from data/districts.json."""

    __tablename__ = "districts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # slug, e.g. "patna"
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(120), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    population: Mapped[int | None] = mapped_column(Integer)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True)

    sos_reports: Mapped[list["SOSReport"]] = relationship(back_populates="district")
    shelters: Mapped[list["Shelter"]] = relationship(back_populates="district")
    risks: Mapped[list["DistrictRisk"]] = relationship(back_populates="district")
    volunteers: Mapped[list["Volunteer"]] = relationship(back_populates="district")

    __table_args__ = (Index("ix_districts_state", "state"),)


class User(Base):
    """Device-anchored identity — one row per X-Device-Id. No passwords in v1."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    device_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="citizen")
    # role in {"citizen", "volunteer", "official"} (official only via admin key)
    display_name: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(32))
    preferred_lang: Mapped[str] = mapped_column(String(12), default="hi")
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    volunteer_profile: Mapped["Volunteer | None"] = relationship(
        back_populates="user"
    )

    __table_args__ = (Index("ix_users_device", "device_id"),)


class SOSReport(Base):
    """The core entity — one citizen SOS report."""

    __tablename__ = "sos_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    # Idempotency key for offline-outbox replay — replays return the existing row.
    client_report_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False
    )

    description: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(12), default="hi")

    category: Mapped[str] = mapped_column(String(24), default="other")
    severity: Mapped[int | None] = mapped_column(Integer)  # 1-5, null until assessed
    priority: Mapped[str] = mapped_column(String(12), default="medium")
    status: Mapped[str] = mapped_column(String(16), default="reported", index=True)

    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    district_id: Mapped[str | None] = mapped_column(
        ForeignKey("districts.id"), index=True
    )

    photo_url: Mapped[str | None] = mapped_column(String(512))
    photo_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    photo_description: Mapped[str | None] = mapped_column(Text)

    reporter_name: Mapped[str | None] = mapped_column(String(120))
    reporter_phone: Mapped[str | None] = mapped_column(String(32))
    reporter_device_id: Mapped[str | None] = mapped_column(String(64))

    needed_skills: Mapped[list] = mapped_column(JSON, default=list)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    # Machine-readable reason powering the verify-queue `reason` field, e.g.
    # "assessment_failed" | "possible_duplicate" | "conflicting_reports" |
    # "spam_burst" | "reporter_flagged" | None.
    needs_review_reason: Mapped[str | None] = mapped_column(String(48))
    # Set when an admin confirms this report duplicates another (Wave 4,
    # Agent 10). The duplicate stays visible and queryable — never deleted.
    duplicate_of: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sos_reports.id"), default=None
    )
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    district: Mapped["District | None"] = relationship(back_populates="sos_reports")
    assessment: Mapped["SeverityAssessment | None"] = relationship(
        back_populates="sos_report", uselist=False, cascade="all, delete-orphan"
    )
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="sos", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_sos_district_status", "district_id", "status"),
        Index("ix_sos_severity", "severity"),
        CheckConstraint(
            "severity IS NULL OR (severity BETWEEN 1 AND 5)",
            name="ck_sos_severity_range",
        ),
    )


class SeverityAssessment(Base):
    """One row per AI assessment — audit trail of AI decisions."""

    __tablename__ = "severity_assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    sos_report_id: Mapped[str] = mapped_column(
        ForeignKey("sos_reports.id"), unique=True, nullable=False
    )

    severity: Mapped[int] = mapped_column(Integer, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    rationale_en: Mapped[str | None] = mapped_column(Text)
    area_tags: Mapped[list] = mapped_column(JSON, default=list)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    priority: Mapped[str] = mapped_column(String(12), nullable=False)
    suggested_skills: Mapped[list] = mapped_column(JSON, default=list)

    # e.g. "glm-4-flash" | "rule-fallback-v1" — never hide which path ran.
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)

    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    sos_report: Mapped["SOSReport"] = relationship(back_populates="assessment")


class Volunteer(Base):
    __tablename__ = "volunteers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    district_id: Mapped[str | None] = mapped_column(
        ForeignKey("districts.id"), index=True
    )
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)

    skills: Mapped[list] = mapped_column(JSON, default=list)
    languages: Mapped[list] = mapped_column(JSON, default=list)
    # "anytime" | [{"day":"mon","start":"09:00","end":"18:00"}, ...]
    availability: Mapped[dict | str] = mapped_column(JSON, default="anytime")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Server-managed reputation 0-100: starts 50, +2/completed (cap 100),
    # -5/declined-after-accept (floor 0). Never client-set.
    reputation: Mapped[int] = mapped_column(Integer, default=50)
    tasks_completed: Mapped[int] = mapped_column(Integer, default=0)
    tasks_declined: Mapped[int] = mapped_column(Integer, default=0)
    avg_response_min: Mapped[float | None] = mapped_column(Float)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User | None"] = relationship(back_populates="volunteer_profile")
    district: Mapped["District | None"] = relationship(back_populates="volunteers")
    tasks: Mapped[list["Task"]] = relationship(back_populates="volunteer")

    __table_args__ = (Index("ix_volunteers_district_active", "district_id", "active"),)


class Task(Base):
    """Volunteer assignment lifecycle."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    sos_id: Mapped[str] = mapped_column(
        ForeignKey("sos_reports.id"), nullable=False, index=True
    )
    volunteer_id: Mapped[str] = mapped_column(
        ForeignKey("volunteers.id"), nullable=False, index=True
    )

    status: Mapped[str] = mapped_column(String(16), default="assigned", index=True)
    note: Mapped[str | None] = mapped_column(Text)
    decline_reason: Mapped[str | None] = mapped_column(Text)
    proof_photo_url: Mapped[str | None] = mapped_column(String(512))

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    en_route_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sos: Mapped["SOSReport"] = relationship(back_populates="tasks")
    volunteer: Mapped["Volunteer"] = relationship(back_populates="tasks")

    __table_args__ = (Index("ix_tasks_sos_status", "sos_id", "status"),)
    # One active task per (sos, volunteer): partial unique index on Postgres;
    # enforced in application logic on SQLite (see routers/tasks.py).


class Shelter(Base):
    """Relief-camp directory — ALL rows synthetic in v1 (is_demo_data=true)."""

    __tablename__ = "shelters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    district_id: Mapped[str] = mapped_column(
        ForeignKey("districts.id"), nullable=False, index=True
    )
    area: Mapped[str | None] = mapped_column(String(200))
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)

    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    occupied: Mapped[int] = mapped_column(Integer, default=0)
    facilities: Mapped[list] = mapped_column(JSON, default=list)

    contact_name: Mapped[str | None] = mapped_column(String(120))
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)

    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    district: Mapped["District"] = relationship(back_populates="shelters")

    __table_args__ = (Index("ix_shelters_district_open", "district_id", "is_open"),)


class Alert(Base):
    """One row per broadcast — multilingual renderings stored in JSON."""

    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    district_ids: Mapped[list] = mapped_column(JSON, default=list)
    type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    severity: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    source_lang: Mapped[str] = mapped_column(String(12), default="hi")

    # {"hi": "...", "hing": "..."} — SMS-length (<=480 chars each).
    messages: Mapped[dict] = mapped_column(JSON, default=dict)
    languages: Mapped[list] = mapped_column(JSON, default=list)

    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recipient_estimate: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[str | None] = mapped_column(String(64))

    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class DistrictRisk(Base):
    """Time series of computed risk — one row per recompute; latest row wins."""

    __tablename__ = "district_risks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    district_id: Mapped[str] = mapped_column(
        ForeignKey("districts.id"), nullable=False, index=True
    )
    risk: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100
    risk_level: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    # [{"name","value","weight","contribution","note"}, ...]
    factors: Mapped[list] = mapped_column(JSON, default=list)
    advisory: Mapped[str | None] = mapped_column(Text)
    # "live" | "simulated" — drives the SIMULATED FEED label in the UI.
    weather_source: Mapped[str] = mapped_column(String(12), default="simulated")
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    district: Mapped["District"] = relationship(back_populates="risks")

    __table_args__ = (Index("ix_risk_district_time", "district_id", "computed_at"),)


class DistrictWeatherSample(Base):
    """Raw ingested weather series — debuggable and backtestable."""

    __tablename__ = "district_weather_samples"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    district_id: Mapped[str] = mapped_column(
        ForeignKey("districts.id"), nullable=False, index=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    rain_mm: Mapped[float | None] = mapped_column(Float)
    temp_c: Mapped[float | None] = mapped_column(Float)
    humidity_pct: Mapped[float | None] = mapped_column(Float)
    wind_kph: Mapped[float | None] = mapped_column(Float)
    river_level_m: Mapped[float | None] = mapped_column(Float)
    river_trend: Mapped[str | None] = mapped_column(String(12))
    source: Mapped[str] = mapped_column(String(12), default="simulated")
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AuditLog(Base):
    """Every status change, broadcast, verify, and admin action."""

    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    actor: Mapped[str] = mapped_column(String(64))  # "admin:demo"|"device:<uuid>"|"system"
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str] = mapped_column(String(24))
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class SafetyFlag(Base):
    """Dedup / misinformation / spam signals."""

    __tablename__ = "safety_flags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    type: Mapped[str] = mapped_column(String(32), index=True)
    # "possible_duplicate" | "conflicting_reports" | "spam_burst" | "reporter_flag"
    sos_ids: Mapped[list] = mapped_column(JSON, default=list)
    district_id: Mapped[str | None] = mapped_column(
        ForeignKey("districts.id"), index=True
    )
    evidence: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="open", index=True)
    resolution: Mapped[str | None] = mapped_column(String(32))
    resolved_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MediaFile(Base):
    """Uploaded photos — minted by POST /api/media, referenced by photo_id.

    Wave-2 addition: the contracts reference ``photo_id`` (POST /api/assess,
    task proof photos) but nothing minted one. This table closes the loop.
    """

    __tablename__ = "media_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    url: Mapped[str] = mapped_column(String(512), nullable=False)  # "/media/sos/....jpg"
    photo_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    content_type: Mapped[str | None] = mapped_column(String(64))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    uploaded_by: Mapped[str | None] = mapped_column(String(64))  # device id
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
