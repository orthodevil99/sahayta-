"""Sahayta AI Engine — provider-agnostic disaster-intelligence modules.

Modules:
    config   — environment-driven LLM configuration (never hardcode keys/URLs)
    llm      — OpenAI-compatible chat client over stdlib HTTP + token accounting
    severity — photo/description -> severity 1-5 + rationale + area tags
    triage   — SOS -> category + priority + suggested volunteer skills
    alerts   — one alert -> 10-language SMS-length messages
    risk     — weather series -> district risk 0-100 with contributing factors
    pipeline — assess_and_route(): the strict backend seam (assess->triage->route->notify)

Every result honestly reports its ``model`` path: ``"llm:<model-id>"`` when a
real model answered, ``"rule-fallback-v1"`` when deterministic rules did.
"""
from __future__ import annotations

__version__ = "1.0.0"
__all__ = ["config", "llm", "severity", "triage", "alerts", "risk", "pipeline"]
