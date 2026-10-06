"""Async SQLAlchemy 2.0 engine/session plumbing.

Default is SQLite (aiosqlite) for dev/demo; production uses
``postgresql+asyncpg://...`` via SAHAYTA_DATABASE_URL — same models work on both.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all Sahayta models."""


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        # SQLite + asyncio needs a single serialized writer for the demo.
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url, **_engine_kwargs(settings.database_url)
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency — yields one session per request."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


def reset_engine() -> None:
    """Test hook — drop cached engine/session factory between test runs."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None
