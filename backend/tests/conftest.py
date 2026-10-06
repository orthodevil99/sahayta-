"""Pytest fixtures — isolated async test DB, seeded once per session.

Isolation strategy: one SQLite file per test session (seeded via the real
seed.py loaders); each test gets a session joined to an outer transaction
that is rolled back at teardown, so tests never see each other's writes
even though app code calls session.commit() (savepoint-joined sessions).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# --- test env (must be set before app.config is imported) -----------------
TEST_DIR = Path("/tmp/sahayta_test")
TEST_DIR.mkdir(exist_ok=True)
os.environ["SAHAYTA_DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DIR}/test.db"
os.environ["SAHAYTA_MEDIA_DIR"] = str(TEST_DIR / "media")
os.environ["SAHAYTA_ADMIN_KEY"] = "demo-admin-key"

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app import auth as auth_module  # noqa: E402
from app import ws as ws_module  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.database import Base, get_session, reset_engine  # noqa: E402
from app.main import create_app  # noqa: E402

import seed as seed_module  # noqa: E402

ADMIN_KEY = "demo-admin-key"
DEVICE_A = "test-device-aaaa"
DEVICE_B = "test-device-bbbb"

DEMO_DESCRIPTION = (
    "पटना के कंकड़बाग इलाके में घुटनों तक पानी भर गया है। "
    "दो गलियों में घरों में पानी घुस गया है, बुजुर्ग छत पर हैं। "
    "तुरंत मदद चाहिए।"
)


def _guest_headers(device: str = DEVICE_A) -> dict:
    return {"X-Device-Id": device}


def _admin_headers(device: str = DEVICE_A) -> dict:
    return {"X-Device-Id": device, "X-Admin-Key": ADMIN_KEY}


@pytest_asyncio.fixture(scope="session")
def seeded_template():
    """Create the seeded template DB file once per session (sync seed path)."""
    template = TEST_DIR / "template.db"
    if template.exists():
        template.unlink()
    sync_engine = create_engine(f"sqlite:///{template}")
    Base.metadata.create_all(sync_engine)

    from sqlalchemy.orm import Session, sessionmaker

    with Session(sync_engine) as s:
        seed_module.clear_demo_data(s)
        seed_module.seed_districts(s)
        seed_module.seed_sos(s)
        seed_module.seed_shelters(s)
        seed_module.seed_volunteers(s)
        seed_module.seed_weather(s)
    sync_engine.dispose()
    return template


@pytest_asyncio.fixture
async def session(seeded_template):
    """Function-scoped session on a private copy of the template DB.

    The app commits normally; the whole file is discarded at teardown, so
    tests can never see each other's writes.
    """
    import shutil
    import uuid as _uuid

    db_path = TEST_DIR / f"test_{_uuid.uuid4().hex}.db"
    shutil.copy(seeded_template, db_path)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    sess = AsyncSession(bind=engine, expire_on_commit=False)
    yield sess
    await sess.close()
    await engine.dispose()
    try:
        db_path.unlink()
    except OSError:
        pass


@pytest_asyncio.fixture
async def client(session):
    """Async HTTP client with the app's session dependency overridden."""
    reset_engine()
    auth_module.reset_rate_limits()
    ws_module.reset_hub()
    get_settings().media_path.mkdir(parents=True, exist_ok=True)

    app = create_app()

    async def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
