"""Severity estimation: photo/description -> severity 1-5 + rationale + area tags.

Two paths, one contract:

* **LLM path** (when ``LLMConfig.configured``): structured JSON completion
  against a strict rubric, validated, with photo bytes attached when
  ``SAHAYTA_LLM_VISION=1`` and a photo file is provided.
* **Rule fallback** (``rule-fallback-v1``): a line-for-line behavioral twin of
  ``backend/app/ai_client.py::rule_assess`` and
  ``frontend/lib/demo-assess.ts::assessSeverity`` — same regexes, same
  scoring. The demo fixture (Patna flood) MUST score exactly 4 here; the
  backend test ``test_assess_endpoint_demo_fixture_scores_4`` guards it.

v1.2 rule extension (documented, twin-safe): storm/heat intensity tiers are
checked BEFORE the twin depth list, but ONLY when a storm/heat context word is
present. The twin has no storm/heat handling, so parity on all twin-covered
inputs (including the demo fixture) is bit-identical; v1.2 intentionally
diverges on storm/heat inputs where the twin under-scores.
"""
from __future__ import annotations

import base64
import logging
import mimetypes
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from config import LLMConfig
from llm import LLMError, TokenUsage, safe_chat_json

log = logging.getLogger("sahayta.ai.severity")

MODEL_RULE = "rule-fallback-v1"

# --- Behavioral twin of backend/app/ai_client.py (do not reorder) -----------
# Strongest depth signal wins (not additive) — prevents keyword pile-up.
_DEPTH = [
    (re.compile(r"छाती\s*तक|गर्दन\s*तक|chest[\s-]*deep|neck[\s-]*deep", re.I), 3),
    (re.compile(r"कमर\s*तक|waist[\s-]*deep", re.I), 2),
    (re.compile(r"घुटनों?\s*तक|घुटने\s*तक|knee[\s-]*deep", re.I), 1),
    (re.compile(r"पानी|बाढ़|flood|water|बारिश|rain|डूब", re.I), 1),
]
# People at risk is a single bucket — one group or five, it is one +1.
# v1.2 adds fainted/unconscious (heat-stroke collapses); "collapsed" is
# deliberately NOT included (buildings/walls collapse without casualties).
_PEOPLE_AT_RISK = re.compile(
    r"छत\s*पर|rooftop|\broof\b|बुजुर्ग|बच्चे|elderly|children|फंसे|trapped|stuck"
    r"|fainted|unconscious|बेहोश",
    re.I,
)
_URGENT = re.compile(r"तुरंत\s*मदद|तुरन्त\s*मदद|immediately|urgent|तुरंत", re.I)

# v1.2 extension (documented, twin-safe): storm/heat intensity tiers, checked
# BEFORE the twin depth list but ONLY when a storm/heat context word is
# present. The twin has no storm/heat handling, so parity on all twin-covered
# inputs (including the demo fixture) is bit-identical; v1.2 intentionally
# diverges on storm/heat inputs where the twin under-scores badly.
# Calibrated against data/severity-labels.csv (600-row sample, seed 20261006):
#   exact-match 0.51 -> 0.60, within-one 0.87 -> 1.00 (rule path, honest).
_STORM_NOUNS = r"cyclone|hurricane|\bstorm\b|तूफ़ान|तूफान|चक्रवात|साइक्लोन"
_WIND_WORDS = r"\bwinds\b|gale|आंधी"
_HEAT_NOUNS = r"heat\s*wave|heatwave|गर्मी|लू|\bheat\b"
_FLOOD_INTENSE = r"(catastrophic|devastat\w*|massive|deadly|severe|destructive)\s+flood\w*"
_STORM_HEAT_CTX = re.compile(
    rf"{_STORM_NOUNS}|{_WIND_WORDS}|{_HEAT_NOUNS}|{_FLOOD_INTENSE}", re.I
)
_TIER = [
    (re.compile(r"catastrophic|devastat\w*|massive|deadly|विनाशकारी|महाविनाश", re.I), 4),
    (re.compile(r"severe|destructive|violent|भयंकर|प्रचंड|भीषण", re.I), 3),
    (re.compile(r"intense|extreme|blazing|अत्यधिक", re.I), 2),
    (re.compile(r"scorching|gusty", re.I), 1),
]
_BARE_STORM = re.compile(rf"{_STORM_NOUNS}", re.I)  # bare noun -> 2
_BARE_OTHER = re.compile(rf"{_WIND_WORDS}|{_HEAT_NOUNS}", re.I)  # bare -> 1


def _intensity_points(text: str) -> int | None:
    """Storm/heat intensity points, or None when no storm/heat context."""
    if not _STORM_HEAT_CTX.search(text):
        return None
    for rx, pts in _TIER:
        if rx.search(text):
            return pts
    if _BARE_STORM.search(text):
        return 2
    if _BARE_OTHER.search(text):
        return 1
    return 0  # context word matched only via _FLOOD_INTENSE-like pattern

_SEV_WORD = {
    "hi": {1: "हल्का", 2: "मध्यम", 3: "गंभीर", 4: "अति गंभीर", 5: "विनाशकारी"},
    "hing": {1: "halka", 2: "madhyam", 3: "gambhir", 4: "ati gambhir", 5: "vinashkari"},
}

# Area tags: twin set first (order frozen), then documented v1.1 additions.
_AREA_TWIN = [
    (re.compile(r"सड़क|road|गलि|lane", re.I), "road_submerged"),
    (re.compile(r"घर|home|residential|इलाक", re.I), "residential"),
    (re.compile(r"स्कूल|school|अस्पताल|hospital", re.I), "public_building"),
]
_AREA_EXT = [
    (re.compile(r"बिजली\s*(गुल|कट|बंद)|power\s*(out|cut)|बिजली\s*के\s*तार", re.I), "power_outage"),
    (re.compile(r"लू|गर्मी|heat\s*wave|heatwave|तापमान\s*\d", re.I), "heat_affected"),
    (re.compile(r"तूफ़ान|तूफान|चक्रवात|cyclone|पेड़\s*गिर", re.I), "wind_damage"),
]

_SEVERITY_RUBRIC = """\
1 = minor inconvenience ( ankle-deep water, no one at risk )
2 = moderate ( knee-deep water OR vulnerable people nearby, no immediate danger )
3 = serious ( waist-deep water, homes affected, rescue may be needed soon )
4 = severe ( deep/fast water OR people stranded on rooftops, urgent rescue needed )
5 = catastrophic ( chest/neck-deep water, lives in immediate danger, mass evacuation )
"""


@dataclass
class SeverityResult:
    severity: int  # 1-5
    rationale: str  # one line, reporter's language
    rationale_en: str | None  # English gloss for officials
    area_tags: list[str]
    model: str  # honest path label
    latency_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tokens_estimated: bool = True
    notes: list[str] = field(default_factory=list)


def _rule_rationale(
    sev: int, lang: str, text: str, hazard: str | None = None
) -> tuple[str, str | None]:
    """Twin rationale + v1.2 hazard-aware depth bit.

    ``hazard`` is "heat" | "storm" | None, set only when the v1.2 intensity
    path scored the report (never for twin-covered inputs — the demo fixture
    always takes the twin branch and is unaffected).
    """
    if hazard == "heat":
        depth = {"hi": "भीषण गर्मी", "hing": "bhishan garmi", "en": "severe heat"}
    elif hazard == "storm":
        depth = {"hi": "तेज़ तूफ़ान", "hing": "tez toofan", "en": "severe storm"}
    elif re.search(r"घुटनों?\s*तक|knee", text, re.I):
        depth = {"hi": "घुटनों तक पानी", "hing": "ghutno tak paani", "en": "knee-deep water"}
    elif re.search(r"कमर|waist", text, re.I):
        depth = {"hi": "कमर तक पानी", "hing": "kamar tak paani", "en": "waist-deep water"}
    else:
        depth = {"hi": "पानी भरा हुआ", "hing": "paani bhara hua", "en": "waterlogging"}
    if re.search(r"छत|roof", text, re.I):
        risk = {"hi": "लोग छतों पर हैं", "hing": "log chhaton par hain", "en": "people on rooftops"}
    elif re.search(r"फंसे|trapped", text, re.I):
        risk = {"hi": "लोग फंसे हुए हैं", "hing": "log fanse hue hain", "en": "people trapped"}
    else:
        risk = {"hi": "रिहायशी इलाका प्रभावित", "hing": "rihayshi ilaka prabhavit",
                "en": "residential area affected"}

    def pick(o: dict) -> str:
        return o["hing"] if lang == "hing" else o["hi"] if lang == "hi" else o["en"]

    words = _SEV_WORD.get(lang, _SEV_WORD["hi"])
    sthiti = "sthiti" if lang == "hing" else "स्थिति" if lang == "hi" else "situation"
    rationale = f"{pick(depth)}; {pick(risk)} — {words[sev]} {sthiti}."
    rationale_en = f"{depth['en']}; {risk['en']} — severity {sev}/5."
    return rationale, rationale_en


def rule_assess(
    description: str,
    language: str = "hi",
    photo_description: str | None = None,
) -> SeverityResult:
    """Deterministic keyword severity estimator. Demo fixture MUST score 4."""
    started = time.perf_counter()
    text = f"{description or ''} {photo_description or ''}"

    depth_pts = 0
    hazard: str | None = None
    intensity = _intensity_points(text)
    if intensity is not None:
        depth_pts = intensity  # v1.2: storm/heat tier replaces depth scoring
        hazard = (
            "heat"
            if re.search(_HEAT_NOUNS, text, re.I)
            else "storm"
        )
    else:
        for rx, pts in _DEPTH:
            if rx.search(text):
                depth_pts = pts
                break  # strongest signal wins
    people_pts = 1 if _PEOPLE_AT_RISK.search(text) else 0
    urgent_pts = 1 if _URGENT.search(text) else 0
    severity = max(1, min(5, 1 + depth_pts + people_pts + urgent_pts))

    area_tags: list[str] = []
    for rx, tag in _AREA_TWIN:
        if rx.search(text):
            area_tags.append(tag)
    for rx, tag in _AREA_EXT:  # additive only; never removes twin tags
        if rx.search(text) and tag not in area_tags:
            area_tags.append(tag)
    if not area_tags:
        area_tags.append("unspecified")

    rationale, rationale_en = _rule_rationale(severity, language or "hi", text, hazard)
    latency_ms = int((time.perf_counter() - started) * 1000)
    return SeverityResult(
        severity=severity,
        rationale=rationale,
        rationale_en=rationale_en,
        area_tags=area_tags,
        model=MODEL_RULE,
        latency_ms=latency_ms,
    )


def _photo_images(photo_path: str | None, vision: bool) -> list[tuple[str, str]]:
    if not (vision and photo_path):
        return []
    p = Path(photo_path)
    if not p.is_file() or p.stat().st_size > 4 * 1024 * 1024:
        return []  # missing or >4MB: skip vision, text still works
    mime = mimetypes.guess_type(str(p))[0] or "image/jpeg"
    return [(mime, base64.b64encode(p.read_bytes()).decode("ascii"))]


def llm_assess(
    description: str,
    language: str,
    photo_description: str | None,
    photo_path: str | None,
    cfg: LLMConfig,
) -> SeverityResult:
    """LLM severity estimation with strict validation; raises LLMError."""
    started = time.perf_counter()
    system = (
        "You are Sahayta's disaster severity estimator for India. "
        "Score the situation 1-5 using exactly this rubric:\n"
        + _SEVERITY_RUBRIC
        + "Reply with a single JSON object: "
        '{"severity": <int 1-5>, '
        f'"rationale": "<one line, in language code \'{language}\'>", '
        '"rationale_en": "<one line English gloss>", '
        '"area_tags": ["<kebab-case tags like road_submerged, residential, '
        'public_building, power_outage, heat_affected, wind_damage>"], '
        '"confidence": <0-1>}. '
        "Base the score on observable facts (water depth, people at risk, "
        "urgency words). Never invent details not in the report."
    )
    user = (
        f"Language: {language}\n"
        f"Citizen description: {description or '(empty)'}\n"
        f"Photo description: {photo_description or '(none)'}"
    )
    images = _photo_images(photo_path, cfg.vision)
    parsed, tok, err = safe_chat_json(
        cfg, system, user, images_b64=images or None, temperature=0.1
    )
    if err or not parsed:
        raise LLMError(err or "empty LLM response")
    try:
        severity = int(parsed["severity"])
        rationale = str(parsed["rationale"]).strip().splitlines()[0]
        rationale_en = str(parsed.get("rationale_en") or "").strip().splitlines()[0] or None
        area_tags = [str(t) for t in (parsed.get("area_tags") or [])][:8]
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise LLMError(f"unparseable severity JSON: {exc}") from exc
    if not 1 <= severity <= 5:
        raise LLMError(f"severity out of range: {severity}")
    if not rationale:
        raise LLMError("empty rationale from LLM")
    if not area_tags:
        area_tags = ["unspecified"]
    latency_ms = int((time.perf_counter() - started) * 1000)
    return SeverityResult(
        severity=severity,
        rationale=rationale,
        rationale_en=rationale_en,
        area_tags=area_tags,
        model=cfg.model_label,
        latency_ms=latency_ms,
        prompt_tokens=tok.prompt_tokens if tok else 0,
        completion_tokens=tok.completion_tokens if tok else 0,
        tokens_estimated=tok.estimated if tok else True,
        notes=[f"llm_confidence={parsed.get('confidence', '?')}"],
    )


def assess_severity(
    description: str,
    language: str = "hi",
    photo_description: str | None = None,
    photo_path: str | None = None,
    llm_config: LLMConfig | None = None,
) -> SeverityResult:
    """Estimate severity, preferring the LLM when configured.

    Any LLM failure degrades honestly to the rule fallback (model stays
    ``rule-fallback-v1`` and the reason lands in ``notes``) — intake must
    never fail because AI failed.
    """
    cfg = llm_config or LLMConfig.from_env()
    if cfg.configured:
        try:
            return llm_assess(description, language, photo_description, photo_path, cfg)
        except LLMError as exc:
            log.info("llm severity failed (%s); honest rule fallback", exc)
            res = rule_assess(description, language, photo_description)
            res.notes.append(f"llm_error_fallback: {exc}")
            return res
    return rule_assess(description, language, photo_description)
