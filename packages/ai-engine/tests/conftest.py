"""Shared fixtures for the ai-engine test suite."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the engine importable however pytest is invoked.
_PKG = Path(__file__).resolve().parent.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

REPO_ROOT = _PKG.parent.parent


@pytest.fixture()
def demo_description() -> str:
    return (REPO_ROOT / "data" / "demo" / "patna-flood" / "description.txt").read_text(
        encoding="utf-8"
    ).strip()


@pytest.fixture()
def no_llm_env(monkeypatch):
    """Force the deterministic rule path (unset all SAHAYTA_LLM_*)."""
    for var in (
        "SAHAYTA_LLM_BASE_URL",
        "SAHAYTA_LLM_MODEL",
        "SAHAYTA_LLM_API_KEY",
        "SAHAYTA_LLM_TIMEOUT_S",
        "SAHAYTA_LLM_MAX_TOKENS",
        "SAHAYTA_LLM_VISION",
    ):
        monkeypatch.delenv(var, raising=False)
