"""Central configuration — every tunable comes from the environment.

No secrets are hardcoded. The app boots and demos cleanly with defaults only:
no LLM key -> deterministic rule-based fallback; weather mode simulated ->
clearly-labeled synthetic feed.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo layout: backend/app/config.py -> backend/ -> sahayta/ (repo root)
BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent

_DEFAULT_DB_URL = f"sqlite+aiosqlite:///{REPO_ROOT / 'backend' / 'sahayta.db'}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SAHAYTA_", extra="ignore")

    # -- database -----------------------------------------------------------
    # Absolute dev default (repo-root anchored, CWD-independent).
    # Prod: postgresql+asyncpg://user:pass@host:5432/sahayta
    database_url: str = _DEFAULT_DB_URL

    # -- server -------------------------------------------------------------
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: str = "http://localhost:3000"

    # -- LLM (provider-agnostic, OpenAI-compatible; blank = rule fallback) --
    llm_base_url: str = ""
    llm_model: str = ""
    llm_api_key: str = ""
    llm_max_tokens: int = 1200
    llm_timeout_s: int = 25

    # -- auth ---------------------------------------------------------------
    # Demo default; MUST be changed in any real deployment (see .env.example).
    admin_key: str = "demo-admin-key"
    api_key: str = ""
    demo_mode: bool = True

    # -- media --------------------------------------------------------------
    media_dir: str = "./backend/media"
    max_upload_mb: int = 8

    # -- weather / early warning -------------------------------------------
    weather_mode: str = "simulated"  # live | simulated
    weather_api_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_ingest_minutes: int = 15

    # -- app ----------------------------------------------------------------
    default_lang: str = "hi"
    # District slugs tracked by the early-warning worker; "all" (default) or
    # "" = every district in the DB, otherwise a comma-separated slug list.
    districts: str = "all"
    public_url: str = "http://localhost:3000"
    demo_helpline: str = "1077"

    # -- matching -----------------------------------------------------------
    match_default_max_results: int = 5
    match_default_max_distance_km: float = 25.0

    # -- rate limits (requests per rolling hour) -----------------------------
    rl_guest_sos_per_hour: int = 20
    rl_guest_other_per_hour: int = 200
    rl_privileged_per_hour: int = 1000

    # -- safety guardrails (Wave 4, Agent 10) --------------------------------
    # Spam burst: N reports from one device within M minutes -> 429 + flag.
    safety_spam_window_minutes: int = 10
    safety_spam_threshold: int = 5
    # Conflict heuristic: severe-vs-mild clusters within R km / H hours.
    safety_conflict_radius_km: float = 2.0
    safety_conflict_hours: float = 6.0
    safety_conflict_min_cluster: int = 3
    # Photo dedup: same hash within H hours and (when geo known) R km.
    safety_dup_window_hours: float = 24.0
    safety_dup_radius_km: float = 5.0

    @property
    def media_path(self) -> Path:
        p = Path(self.media_dir)
        return p if p.is_absolute() else (REPO_ROOT / p)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def using_default_admin_key(self) -> bool:
        return self.admin_key == "demo-admin-key"

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()
