"""SOS triage: text/photo -> category + priority + suggested volunteer skills.

Frozen enums (docs/api-contracts.md):
    category: medical | rescue | food | shelter | infrastructure | other
    priority: low | medium | high | critical   (derived from severity)

Priority is ALWAYS derived from severity with the frozen mapping below —
the LLM may refine category/skills but never priority. This keeps triage
consistent between the rule path and the LLM path.

Rule path is a behavioral twin of backend/app/ai_client.py's category hints
(rescue checked first: flood/water contexts dominate; vulnerability markers
mean rescue, not medical).
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

from config import LLMConfig
from llm import LLMError, safe_chat_json

log = logging.getLogger("sahayta.ai.triage")

MODEL_RULE = "rule-fallback-v1"

CATEGORIES = ("medical", "rescue", "food", "shelter", "infrastructure", "other")
PRIORITIES = ("low", "medium", "high", "critical")

# Exact port of backend/app/ai_client.py::_CATEGORY_HINTS (order frozen).
_CATEGORY_HINTS = [
    (re.compile(r"पानी|बाढ़|flood|water|छत|roof|फंसे|trapped|नाव|boat|rescue", re.I),
     "rescue", ["rescue", "driving"]),
    (re.compile(r"चोट|खून|बीमार|medical|injured|blood|sick|दवा|एम्बुलेंस|ambulance", re.I),
     "medical", ["medical", "driving"]),
    (re.compile(r"खाना|भूख|food|hungry|राशन", re.I),
     "food", ["cooking", "logistics"]),
    (re.compile(r"शिविर|ठहर|shelter|camp|रहने", re.I),
     "shelter", ["shelter_mgmt", "logistics"]),
    (re.compile(r"सड़क|बिजली|पुल|road|power|bridge|तार", re.I),
     "infrastructure", ["engineering", "logistics"]),
]

# v1.1 additive hints for disaster types the twin doesn't cover.
# Checked only if NO twin hint matched — twin parity preserved.
_CATEGORY_EXT = [
    (re.compile(r"तूफ़ान|तूफान|चक्रवात|साइक्लोन|cyclone|hurricane|आंधी", re.I),
     "infrastructure", ["engineering", "logistics"]),
    (re.compile(r"लू|गर्मी|heat\s*wave|heatwave", re.I),
     "medical", ["medical", "logistics"]),
    (re.compile(r"भूकंप|भुकंप|earthquake|भूस्खलन|landslide", re.I),
     "rescue", ["rescue", "medical"]),
]

# Skill vocabulary shared with volunteers.json / matching engine.
SKILLS = (
    "rescue", "medical", "driving", "cooking", "logistics",
    "shelter_mgmt", "engineering", "comms",
)


@dataclass
class TriageResult:
    category: str
    priority: str
    suggested_skills: list[str]
    model: str
    latency_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tokens_estimated: bool = True
    notes: list[str] = field(default_factory=list)


def priority_for(severity: int) -> str:
    """Frozen severity -> priority mapping (matches backend + frontend)."""
    if severity >= 4:
        return "critical"
    if severity == 3:
        return "high"
    if severity == 2:
        return "medium"
    return "low"


def rule_triage(
    description: str,
    severity: int,
    photo_description: str | None = None,
) -> TriageResult:
    """Deterministic keyword triage. Category hints checked in frozen order."""
    started = time.perf_counter()
    text = f"{description or ''} {photo_description or ''}"

    category, suggested = "other", ["logistics"]
    for rx, cat, skills in _CATEGORY_HINTS:
        if rx.search(text):
            category, suggested = cat, skills
            break
    if category == "other":  # v1.1 extensions, twin-safe
        for rx, cat, skills in _CATEGORY_EXT:
            if rx.search(text):
                category, suggested = cat, skills
                break

    latency_ms = int((time.perf_counter() - started) * 1000)
    return TriageResult(
        category=category,
        priority=priority_for(severity),
        suggested_skills=suggested,
        model=MODEL_RULE,
        latency_ms=latency_ms,
    )


def llm_triage(
    description: str,
    severity: int,
    language: str,
    photo_description: str | None,
    cfg: LLMConfig,
) -> TriageResult:
    """LLM triage; refines category/skills, never priority. Raises LLMError."""
    started = time.perf_counter()
    system = (
        "You classify disaster SOS reports for Sahayta (India). "
        f"Allowed categories: {', '.join(CATEGORIES)}. "
        f"Allowed skills: {', '.join(SKILLS)}. "
        "Reply with a single JSON object: "
        '{"category": "<one of the allowed categories>", '
        '"suggested_skills": ["<2-3 skills, most needed first>"], '
        '"reason": "<one short phrase>"}. '
        "Rules: flood/water/rooftop/trapped contexts are 'rescue'; injuries or "
        "sickness are 'medical'; hunger is 'food'; displacement is 'shelter'; "
        "roads/power/bridges are 'infrastructure'. When in doubt choose 'other'."
    )
    user = (
        f"Severity (already scored): {severity}/5\n"
        f"Description: {description or '(empty)'}\n"
        f"Photo description: {photo_description or '(none)'}"
    )
    parsed, tok, err = safe_chat_json(cfg, system, user, temperature=0.1)
    if err or not parsed:
        raise LLMError(err or "empty LLM response")
    category = str(parsed.get("category", "other")).strip().lower()
    if category not in CATEGORIES:
        raise LLMError(f"invalid category: {category!r}")
    skills = [s for s in (parsed.get("suggested_skills") or []) if s in SKILLS][:3]
    if not skills:
        raise LLMError("no valid skills returned")
    latency_ms = int((time.perf_counter() - started) * 1000)
    return TriageResult(
        category=category,
        priority=priority_for(severity),
        suggested_skills=skills,
        model=cfg.model_label,
        latency_ms=latency_ms,
        prompt_tokens=tok.prompt_tokens if tok else 0,
        completion_tokens=tok.completion_tokens if tok else 0,
        tokens_estimated=tok.estimated if tok else True,
        notes=[f"llm_reason={parsed.get('reason', '?')}"],
    )


def triage_report(
    description: str,
    severity: int,
    language: str = "hi",
    photo_description: str | None = None,
    llm_config: LLMConfig | None = None,
) -> TriageResult:
    """Triage an SOS, preferring the LLM when configured.

    LLM failure degrades honestly to rules (``rule-fallback-v1`` + note).
    """
    cfg = llm_config or LLMConfig.from_env()
    if cfg.configured:
        try:
            return llm_triage(description, severity, language, photo_description, cfg)
        except LLMError as exc:
            log.info("llm triage failed (%s); honest rule fallback", exc)
            res = rule_triage(description, severity, photo_description)
            res.notes.append(f"llm_error_fallback: {exc}")
            return res
    return rule_triage(description, severity, photo_description)
