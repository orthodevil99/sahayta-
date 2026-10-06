"""Pipeline: assess -> triage -> route -> notify as ONE call.

This module is the strict backend seam (see backend/NOTES-agent5.md)::

    assess_and_route(description, language, lat, lon,
                     photo_description, photo_path) -> dict

Required keys: severity, rationale, rationale_en, area_tags, category,
priority, suggested_skills, model (+ optional prompt_tokens,
completion_tokens, latency_ms).

Extra keys returned (the backend seam tolerates them): cost_usd_estimate,
route, notify_preview, notes.

Import-safety: the backend loads this file with importlib from its path
(without package context), so sibling imports are resolved by prepending
this directory to sys.path here. Any import failure raises at load time and
the backend falls back to rules — intake never breaks.

Honest model attribution: "llm:<model-id>" when a real model produced the
result, "rule-fallback-v1" when deterministic rules did (including when an
LLM was configured but failed — the reason lands in ``notes``).
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from alerts import LANGS, render_multilingual  # noqa: E402
from config import LLMConfig  # noqa: E402
from llm import TokenUsage  # noqa: E402
from severity import assess_severity  # noqa: E402
from triage import triage_report  # noqa: E402

log = logging.getLogger("sahayta.ai.pipeline")


def _infer_alert_type(description: str, photo_description: str | None) -> str:
    """Map report text to an alert template family for the notify preview."""
    import re

    text = f"{description or ''} {photo_description or ''}"
    if re.search(r"लू|गर्मी|heat\s*wave|heatwave|तापमान", text, re.I):
        return "heatwave"
    if re.search(r"तूफ़ान|तूफान|चक्रवात|साइक्लोन|cyclone|hurricane|आंधी", text, re.I):
        return "cyclone"
    return "flood"


def _route_for(category: str, priority: str, suggested_skills: list[str]) -> dict:
    """Route step: dispatch recommendation for the matching engine."""
    channel = (
        "sms+app+ivrs" if priority == "critical"
        else "sms+app" if priority == "high"
        else "app"
    )
    return {
        "suggested_skills": suggested_skills,
        "priority": priority,
        "category": category,
        "recommended_channel": channel,
        "verify_recommended": priority in ("critical", "high"),
        "notes": (
            "auto-dispatch candidate: broadcast to nearby volunteers with "
            f"skills {', '.join(suggested_skills)}"
            if priority in ("critical", "high")
            else "queue for triage board; no auto-dispatch"
        ),
    }


def assess_and_route(
    description: str,
    language: str = "hi",
    lat: float | None = None,
    lon: float | None = None,
    photo_description: str | None = None,
    photo_path: str | None = None,
) -> dict:
    """Run assess -> triage -> route -> notify as one call (backend seam).

    Never raises for assessment failure: LLM errors degrade to the rule
    fallback inside the sub-modules, and any unexpected exception here is
    caught and converted to an honest rule-path result with a note.
    """
    started = time.perf_counter()
    language = language or "hi"
    cfg = LLMConfig.from_env()
    notes: list[str] = []
    try:
        sev = assess_severity(description, language, photo_description, photo_path, cfg)
        tri = triage_report(description, sev.severity, language, photo_description, cfg)

        route = _route_for(tri.category, tri.priority, tri.suggested_skills)

        # Notify preview: multilingual render for the reporter's language.
        # {district} is left for the backend broadcast (which knows the district).
        alert_type = _infer_alert_type(description, photo_description)
        preview_langs = [language] if language in LANGS else ["hi"]
        rendered = render_multilingual(
            alert_type,
            preview_langs,
            "{district}",
            body=None,
            title=None,
            extra={},
            llm_config=cfg,
        )
        notify_preview = {
            "alert_type": alert_type,
            "languages": preview_langs,
            "messages": rendered.messages,
            "sources": rendered.sources,
        }
        notes.extend(sev.notes)
        notes.extend(tri.notes)
        notes.extend(rendered.notes)

        prompt_tokens = (
            sev.prompt_tokens + tri.prompt_tokens + rendered.prompt_tokens
        )
        completion_tokens = (
            sev.completion_tokens + tri.completion_tokens + rendered.completion_tokens
        )
        tokens_estimated = (
            sev.tokens_estimated and tri.tokens_estimated and rendered.tokens_estimated
        )
        used_llm = cfg.model_label in (sev.model, tri.model, rendered.model)
        model = cfg.model_label if used_llm else "rule-fallback-v1"
        if cfg.configured and not used_llm:
            notes.append("llm_configured_but_unused: all stages fell back to rules")

        cost = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=cfg.model if used_llm else "",
            estimated=tokens_estimated,
        ).cost_usd()

        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "severity": sev.severity,
            "rationale": sev.rationale,
            "rationale_en": sev.rationale_en,
            "area_tags": sev.area_tags,
            "category": tri.category,
            "priority": tri.priority,
            "suggested_skills": tri.suggested_skills,
            "model": model,
            "latency_ms": latency_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "tokens_estimated": tokens_estimated,
            "cost_usd_estimate": cost,
            "route": route,
            "notify_preview": notify_preview,
            "notes": notes,
        }
    except Exception as exc:  # noqa: BLE001 — intake must never fail
        log.warning("pipeline unexpected error (%s); emergency rule result", exc)
        sev = assess_severity(description, language, photo_description, None, None)
        tri = triage_report(description, sev.severity, language, photo_description, None)
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "severity": sev.severity,
            "rationale": sev.rationale,
            "rationale_en": sev.rationale_en,
            "area_tags": sev.area_tags,
            "category": tri.category,
            "priority": tri.priority,
            "suggested_skills": tri.suggested_skills,
            "model": "rule-fallback-v1",
            "latency_ms": latency_ms,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "tokens_estimated": True,
            "cost_usd_estimate": 0.0,
            "route": _route_for(tri.category, tri.priority, tri.suggested_skills),
            "notify_preview": {"alert_type": "flood", "languages": ["hi"],
                               "messages": {}, "sources": {}},
            "notes": [f"pipeline_error_fallback: {exc}"],
        }
