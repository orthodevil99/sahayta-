# Sahayta — Data Models

**Version:** 1.0 (Wave 1 — Product Architect)
**Status:** Implements `docs/api-contracts.md` §0.6 enumerations. Wave 2 Agent 5 builds
these verbatim as SQLAlchemy 2.0 (async) models + Pydantic v2 schemas + Alembic migrations.

Conventions:

- Primary keys: UUID v4 stored as `String(36)` (portable across SQLite/Postgres; no
  native-UUID dependency in dev).
- Timestamps: timezone-aware UTC `DateTime`, `server_default=func.now()`.
- Money/geo: lat/lon as `Float`; distances computed in Python (haversine).
- Soft enums: `String` columns validated by Pydantic `Literal[...]`; CHECK constraints
  added in the Alembic migration for Postgres.
- Every table has an index on `(district_id)` where present and on `created_at`.
- `is_demo_data` flags synthetic rows; the seed script sets them, runtime writes set
  `False` — EXCEPT shelters/alerts templates which are always synthetic in v1.

---

## 1. SQLAlchemy Models (`backend/app/models/*.py`)

### 1.1 `District` — operational unit (seeded; 20 districts in v1)

```python
class District(Base):
    __tablename__ = "districts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # slug, e.g. "patna"
    name: Mapped[str] = mapped_column(String(120), nullable=False)  # "Patna"
    state: Mapped[str] = mapped_column(String(120), nullable=False)  # "Bihar"
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    population: Mapped[int | None] = mapped_column(Integer)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True)

    # relationships
    sos_reports: Mapped[list["SOSReport"]] = relationship(back_populates="district")
    shelters: Mapped[list["Shelter"]] = relationship(back_populates="district")
    risks: Mapped[list["DistrictRisk"]] = relationship(back_populates="district")
    volunteers: Mapped[list["Volunteer"]] = relationship(back_populates="district")

    __table_args__ = (Index("ix_districts_state", "state"),)
```

### 1.2 `User` — device-anchored identity (citizens + volunteers + officials)

One row per `X-Device-Id`; officials additionally present `X-Admin-Key` (checked
against env, not stored). No passwords in v1 — this is a deliberate hackathon scope
cut, documented in `docs/safety.md` by Wave 4.

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    device_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="citizen")
    # role ∈ {"citizen", "volunteer", "official"}  (official only via admin key)
    display_name: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(32))
    preferred_lang: Mapped[str] = mapped_column(String(12), default="hi")
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    volunteer_profile: Mapped["Volunteer | None"] = relationship(back_populates="user")

    __table_args__ = (Index("ix_users_device", "device_id"),)
```

### 1.3 `SOSReport` — the core entity

```python
class SOSReport(Base):
    __tablename__ = "sos_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    client_report_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    # idempotency key for offline-outbox replay (see architecture.md §1.5)

    description: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(12), default="hi")

    category: Mapped[str] = mapped_column(String(24), default="other")
    # ∈ {"medical","rescue","food","shelter","infrastructure","other"}
    severity: Mapped[int | None] = mapped_column(Integer)  # 1–5, null until assessed
    priority: Mapped[str] = mapped_column(String(12), default="medium")
    status: Mapped[str] = mapped_column(String(16), default="reported", index=True)
    # ∈ {"reported","verified","help_on_way","resolved","duplicate","rejected"}

    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    district_id: Mapped[str | None] = mapped_column(ForeignKey("districts.id"), index=True)

    photo_url: Mapped[str | None] = mapped_column(String(512))
    photo_hash: Mapped[str | None] = mapped_column(String(64), index=True)  # pHash hex
    photo_description: Mapped[str | None] = mapped_column(Text)  # text-mode fallback

    reporter_name: Mapped[str | None] = mapped_column(String(120))
    reporter_phone: Mapped[str | None] = mapped_column(String(32))
    reporter_device_id: Mapped[str | None] = mapped_column(String(64))

    needed_skills: Mapped[list] = mapped_column(JSON, default=list)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    district: Mapped["District | None"] = relationship(back_populates="sos_reports")
    assessment: Mapped["SeverityAssessment | None"] = relationship(back_populates="sos_report", uselist=False, cascade="all, delete-orphan")
    tasks: Mapped[list["Task"]] = relationship(back_populates="sos", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_sos_district_status", "district_id", "status"),
        Index("ix_sos_severity", "severity"),
        CheckConstraint("severity IS NULL OR (severity BETWEEN 1 AND 5)", name="ck_sos_severity_range"),
    )
```

### 1.4 `SeverityAssessment` — one row per AI assessment (audit trail of AI decisions)

```python
class SeverityAssessment(Base):
    __tablename__ = "severity_assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    sos_report_id: Mapped[str] = mapped_column(ForeignKey("sos_reports.id"), unique=True, nullable=False)

    severity: Mapped[int] = mapped_column(Integer, nullable=False)  # 1–5
    rationale: Mapped[str] = mapped_column(Text, nullable=False)  # one line, reporter's language
    rationale_en: Mapped[str | None] = mapped_column(Text)  # English gloss for officials
    area_tags: Mapped[list] = mapped_column(JSON, default=list)
    # e.g. ["road_submerged","residential","power_lines_down"]
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    priority: Mapped[str] = mapped_column(String(12), nullable=False)
    suggested_skills: Mapped[list] = mapped_column(JSON, default=list)

    model: Mapped[str] = mapped_column(String(80), nullable=False)
    # e.g. "glm-4-flash" | "rule-fallback-v1" — never hide which path ran
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)

    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sos_report: Mapped["SOSReport"] = relationship(back_populates="assessment")
```

### 1.5 `Volunteer`

```python
class Volunteer(Base):
    __tablename__ = "volunteers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    district_id: Mapped[str | None] = mapped_column(ForeignKey("districts.id"), index=True)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)

    skills: Mapped[list] = mapped_column(JSON, default=list)
    # ∈ {"medical","rescue","driving","cooking","shelter_mgmt","translation","logistics","counseling","engineering"}
    languages: Mapped[list] = mapped_column(JSON, default=list)  # lang codes
    availability: Mapped[dict | str] = mapped_column(JSON, default="anytime")
    # "anytime" | [{"day":"mon","start":"09:00","end":"18:00"}, …]
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    reputation: Mapped[int] = mapped_column(Integer, default=50)  # 0–100, server-managed
    tasks_completed: Mapped[int] = mapped_column(Integer, default=0)
    tasks_declined: Mapped[int] = mapped_column(Integer, default=0)
    avg_response_min: Mapped[float | None] = mapped_column(Float)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User | None"] = relationship(back_populates="volunteer_profile")
    district: Mapped["District | None"] = relationship(back_populates="volunteers")
    tasks: Mapped[list["Task"]] = relationship(back_populates="volunteer")

    __table_args__ = (Index("ix_volunteers_district_active", "district_id", "active"),)
```

### 1.6 `Task` — assignment lifecycle

```python
class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    sos_id: Mapped[str] = mapped_column(ForeignKey("sos_reports.id"), nullable=False, index=True)
    volunteer_id: Mapped[str] = mapped_column(ForeignKey("volunteers.id"), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(16), default="assigned", index=True)
    # ∈ {"assigned","accepted","declined","en_route","completed","cancelled"}
    note: Mapped[str | None] = mapped_column(Text)
    decline_reason: Mapped[str | None] = mapped_column(Text)
    proof_photo_url: Mapped[str | None] = mapped_column(String(512))

    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    en_route_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    sos: Mapped["SOSReport"] = relationship(back_populates="tasks")
    volunteer: Mapped["Volunteer"] = relationship(back_populates="tasks")

    __table_args__ = (
        Index("ix_tasks_sos_status", "sos_id", "status"),
        # one active task per (sos, volunteer): enforced in application logic
        # (partial unique index on Postgres; app-level check on SQLite)
    )
```

---

### 1.7 `Shelter` — relief-camp directory (ALL rows synthetic in v1)

```python
class Shelter(Base):
    __tablename__ = "shelters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    district_id: Mapped[str] = mapped_column(ForeignKey("districts.id"), nullable=False, index=True)
    area: Mapped[str | None] = mapped_column(String(200))  # locality/ward
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)

    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    occupied: Mapped[int] = mapped_column(Integer, default=0)
    facilities: Mapped[list] = mapped_column(JSON, default=list)
    # ∈ {"drinking_water","medical","food","pet_friendly","wheelchair_access","power_backup"}

    contact_name: Mapped[str | None] = mapped_column(String(120))
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)

    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True)  # ALWAYS true in v1
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    district: Mapped["District"] = relationship(back_populates="shelters")

    __table_args__ = (Index("ix_shelters_district_open", "district_id", "is_open"),)
```

### 1.8 `Alert` — one row per broadcast (multilingual renderings in JSON)

```python
class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    district_ids: Mapped[list] = mapped_column(JSON, default=list)
    type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # ∈ {"flood","heatwave","cyclone","custom"}
    severity: Mapped[int | None] = mapped_column(Integer)  # 1–5, optional
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)  # source language text
    source_lang: Mapped[str] = mapped_column(String(12), default="hi")

    messages: Mapped[dict] = mapped_column(JSON, default=dict)
    # {"hi": "…", "hing": "…", …} — SMS-length (≤480 chars each), ai-engine rendered
    languages: Mapped[list] = mapped_column(JSON, default=list)

    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recipient_estimate: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[str | None] = mapped_column(String(64))  # "admin:demo" | device id | "system"

    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
```

### 1.9 `DistrictRisk` — time series of computed risk (one row per recompute)

```python
class DistrictRisk(Base):
    __tablename__ = "district_risks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    district_id: Mapped[str] = mapped_column(ForeignKey("districts.id"), nullable=False, index=True)
    risk: Mapped[int] = mapped_column(Integer, nullable=False)  # 0–100
    risk_level: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    # ∈ {"low","moderate","high","severe"}  (0–39 / 40–69 / 70–84 / 85–100)
    factors: Mapped[list] = mapped_column(JSON, default=list)
    # [{"name","value","weight","contribution","note"}, …] — see GET /districts/{id}/risk
    advisory: Mapped[str | None] = mapped_column(Text)
    weather_source: Mapped[str] = mapped_column(String(12), default="simulated")
    # ∈ {"live","simulated"} — drives the SIMULATED FEED label in the UI
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    district: Mapped["District"] = relationship(back_populates="risks")

    __table_args__ = (Index("ix_risk_district_time", "district_id", "computed_at"),)
```

"Current risk" = latest row per district (`ORDER BY computed_at DESC LIMIT 1`).

### 1.10 Supporting tables

```python
class DistrictWeatherSample(Base):  # raw ingested series (debuggable, backtestable)
    __tablename__ = "district_weather_samples"
    id = String(36) PK; district_id FK index; ts DateTime tz index
    rain_mm Float; temp_c Float; humidity_pct Float; wind_kph Float
    river_level_m Float | None; river_trend String(12) | None  # rising|steady|falling
    source String(12)  # live|simulated
    ingested_at DateTime tz server_default

class AuditLog(Base):  # every status change, broadcast, verify, admin action
    __tablename__ = "audit_log"
    id String(36) PK; ts DateTime tz server_default index
    actor String(64)  # "admin:demo" | "device:<uuid>" | "system"
    action String(64) index  # e.g. "sos.status_changed"
    target_type String(24); target_id String(36) index
    details JSON default dict

class SafetyFlag(Base):  # dedup / misinformation / spam signals
    __tablename__ = "safety_flags"
    id String(36) PK; type String(32) index
    # ∈ {"possible_duplicate","conflicting_reports","spam_burst","reporter_flag"}
    sos_ids JSON default list; district_id FK nullable index
    evidence Text; status String(12) default "open" index  # open|resolved|dismissed
    resolution String(32) | None; resolved_by String(64) | None
    created_at / updated_at
```

---

## 2. Pydantic Schemas (`backend/app/schemas/*.py`)

Shared base (all schemas inherit):

```python
from pydantic import BaseModel, Field, field_validator
from typing import Literal

Severity = int  # validated 1–5 via Field(ge=1, le=5)
SOSStatus = Literal["reported","verified","help_on_way","resolved","duplicate","rejected"]
SOSCategory = Literal["medical","rescue","food","shelter","infrastructure","other"]
Priority = Literal["low","medium","high","critical"]
TaskStatus = Literal["assigned","accepted","declined","en_route","completed","cancelled"]
AlertType = Literal["flood","heatwave","cyclone","custom"]
RiskLevel = Literal["low","moderate","high","severe"]
LangCode = Literal["hi","hing","bn","ta","te","mr","gu","kn","ml","pa","en"]
VolunteerSkill = Literal["medical","rescue","driving","cooking","shelter_mgmt",
                         "translation","logistics","counseling","engineering"]

class SOSCreate(BaseModel):
    description: str = Field(min_length=10, max_length=2000)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    district_id: str | None = None
    language: LangCode | None = None
    reporter_name: str | None = Field(default=None, max_length=120)
    reporter_phone: str | None = Field(default=None, max_length=32)
    client_report_id: str  # uuid, required for idempotency
    photo_description: str | None = None  # text-mode fallback

    @field_validator("lat", "lon") ...  # both-or-neither with district fallback:
    # valid iff (lat and lon) OR district_id — enforced in router, documented here

class SOSRead(BaseModel):
    id: str; client_report_id: str; description: str; language: str
    category: SOSCategory; severity: int | None; priority: Priority; status: SOSStatus
    lat: float | None; lon: float | None; district_id: str | None
    photo_url: str | None; photo_hash: str | None
    reporter_name: str | None
    needed_skills: list[VolunteerSkill]
    needs_review: bool; is_demo_data: bool
    created_at: datetime; updated_at: datetime
    assessment: "AssessmentRead | None" = None

class AssessmentRead(BaseModel):
    id: str; severity: int; rationale: str; rationale_en: str | None
    area_tags: list[str]; category: SOSCategory; priority: Priority
    suggested_skills: list[VolunteerSkill]; model: str
    assessed_at: datetime

class StatusPatch(BaseModel):
    status: SOSStatus; note: str | None = Field(default=None, max_length=500)

class VerifyBody(BaseModel):
    verdict: Literal["verified","rejected","duplicate"]
    duplicate_of: str | None = None; note: str | None = None

class VolunteerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str | None = None; district_id: str | None = None
    lat: float | None = None; lon: float | None = None
    skills: list[VolunteerSkill] = Field(min_length=1)
    languages: list[LangCode] = Field(default=["hi"])
    availability: str | list[dict] = "anytime"
    active: bool = True

class TaskCreate(BaseModel):
    sos_id: str; volunteer_id: str; note: str | None = None

class TaskComplete(BaseModel):
    note: str | None = None; proof_photo_id: str | None = None

class BroadcastCreate(BaseModel):
    district_ids: list[str] = Field(min_length=1)
    type: AlertType; title: str = Field(max_length=200)
    body: str = Field(min_length=10, max_length=2000)
    severity: int | None = Field(default=None, ge=1, le=5)
    languages: list[LangCode] | None = None  # default: all 10
    scheduled_at: datetime | None = None

class Paginated(BaseModel):  # wrapper used by all list endpoints
    items: list; total: int; limit: int; offset: int
```

**ORM mode:** all `*Read` schemas set `model_config = ConfigDict(from_attributes=True)`.

**Frontend mirror:** `frontend/lib/types.ts` MUST declare the same shapes (Wave 2
Agent 4). Field names are frozen — `snake_case` on the wire, end to end.

---

## 3. Seed-Data Mapping (`backend/scripts/seed.py` → `data/`)

| File | Target table(s) | Notes |
|---|---|---|
| `data/districts.json` (Agent 2 creates) | `districts` | 20 districts, slugs as PKs |
| `data/sos-reports.json` | `sos_reports` (+ derived `severity_assessments` rows with `model="seed-synthetic-v1"`) | 3,000 rows, 72-h simulated timeline |
| `data/shelters.json` | `shelters` | 500 rows, `is_demo_data=true` |
| `data/volunteers.json` | `volunteers` (+ stub `users` rows) | 1,000 rows |
| `data/weather-sample.json` | `district_weather_samples` + initial `district_risks` | 30 days × districts |
| `data/alert-templates/` | NOT a table — read at runtime by `ai-engine/alerts.py` | 10 langs × 3 disaster types |

Seed is idempotent: re-running clears `is_demo_data=true` rows first, then reloads.
