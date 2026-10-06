"""Multilingual alert generation: one alert -> 10-language SMS-length messages.

Ground truth first: ``data/alert-templates/{flood,heatwave,cyclone}.json`` are
hand-written native-script templates (verified <=160 chars). Template render
is used whenever the alert type matches — the LLM only composes *novel* alert
types, and every message is hard-capped at 480 chars (160 target).

Public entry: ``render_multilingual(alert_type, languages, district_names,
body, title, extra=None, llm_config=None)`` — the signature the backend seam
expects (see backend/NOTES-agent5.md).
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from config import LLMConfig
from llm import TokenUsage, safe_chat_json

log = logging.getLogger("sahayta.ai.alerts")

MODEL_TEMPLATE = "template-ground-truth-v1"

LANGS = ["hi", "hing", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa"]
LANG_NAMES = {
    "hi": "Hindi (Devanagari script)",
    "hing": "Hinglish (Hindi written in Latin script)",
    "bn": "Bengali", "ta": "Tamil", "te": "Telugu", "mr": "Marathi",
    "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam", "pa": "Punjabi",
}
ALERT_TYPES = ("flood", "heatwave", "cyclone")

TARGET_CHARS = 160
HARD_CAP_CHARS = 480
DEFAULT_HELPLINE = "1078"  # national disaster helpline

# Repo-root-anchored so this works however the module is imported.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE_DIR = REPO_ROOT / "data" / "alert-templates"

# Generic skeleton for novel alert types when no LLM is configured.
# Hand-written one-liners, each well under 160 chars once filled.
_GENERIC = {
    "hi": "आपात चेतावनी: {district} में सतर्क रहें। {title}। हेल्पलाइन: {helpline}",
    "hing": "Emergency alert: {district} me satark rahen. {title}. Helpline: {helpline}",
    "bn": "জরুরি সতর্কতা: {district}-এ সতর্ক থাকুন। {title}। হেল্পলাইন: {helpline}",
    "ta": "அவசர எச்சரிக்கை: {district}-இல் எச்சரிக்கையாக இருங்கள். {title}. உதவி எண்: {helpline}",
    "te": "అత్యవసర హెచ్చరిక: {district}లో అప్రమత్తంగా ఉండండి. {title}. హెల్ప్‌లైన్: {helpline}",
    "mr": "आपत्कालीन सूचना: {district} मध्ये सतर्क रहा. {title}. हेल्पलाइन: {helpline}",
    "gu": "કટોકટી ચેતવણી: {district} માં સતર્ક રહો. {title}. હેલ્પલાઇન: {helpline}",
    "kn": "ತುರ್ತು ಎಚ್ಚರಿಕೆ: {district}ನಲ್ಲಿ ಜಾಗರೂಕರಾಗಿರಿ. {title}. ಸಹಾಯವಾಣಿ: {helpline}",
    "ml": "അടിയന്തര മുന്നറിയിപ്പ്: {district}ൽ ജാഗ്രത പാലിക്കുക. {title}. ഹെൽപ്‌ലൈൻ: {helpline}",
    "pa": "ਐਮਰਜੈਂਸੀ ਚੇਤਾਵਨੀ: {district} ਵਿੱਚ ਸੁਚੇਤ ਰਹੋ। {title}। ਹੈਲਪਲਾਈਨ: {helpline}",
}

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


@dataclass
class AlertRender:
    messages: dict  # lang -> message text
    sources: dict  # lang -> "template" | "llm" | "generic" | "template:hi-fallback"
    model: str  # honest path label
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tokens_estimated: bool = True
    notes: list = field(default_factory=list)


@lru_cache(maxsize=8)
def load_templates(alert_type: str) -> dict | None:
    """Load hand-written templates for a known alert type (cached)."""
    path = TEMPLATE_DIR / f"{alert_type}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("alert template %s unreadable: %s", alert_type, exc)
        return None
    templates = data.get("templates")
    return templates if isinstance(templates, dict) and templates else None


def _fill(template: str, values: dict) -> str:
    """Fill {placeholders}; unknown placeholders are left intact (visible)."""

    def sub(m: re.Match) -> str:
        return str(values.get(m.group(1), m.group(0)))

    return _PLACEHOLDER.sub(sub, template)


def _cap(text: str, notes: list, lang: str) -> str:
    if len(text) > HARD_CAP_CHARS:
        notes.append(f"{lang}: truncated to {HARD_CAP_CHARS} chars")
        return text[: HARD_CAP_CHARS - 1] + "…"
    return text


def _district_str(district_names) -> str:
    if isinstance(district_names, (list, tuple)):
        return ", ".join(str(d) for d in district_names if d)
    return str(district_names or "")


def _llm_compose(
    cfg: LLMConfig,
    alert_type: str,
    lang: str,
    district: str,
    title: str,
    body: str,
    extra: dict,
) -> tuple[str | None, TokenUsage | None]:
    """Compose a novel alert in one language via LLM. Returns (text, usage)."""
    lang_name = LANG_NAMES.get(lang, lang)
    system = (
        "You write disaster SMS alerts for India. Rules: "
        f"write ONLY in {lang_name}; "
        f"aim for {TARGET_CHARS} characters or fewer, never exceed {HARD_CAP_CHARS}; "
        "one alert = what is happening + where + what to do + helpline. "
        "No hashtags, no emojis, no preamble. Reply with a single JSON object: "
        '{"message": "<the alert text>"}.'
    )
    user = (
        f"Alert type: {alert_type}\nTitle: {title or '(none)'}\n"
        f"District(s): {district or '(unspecified)'}\n"
        f"Details: {body or '(none)'}\n"
        f"Extra facts: {json.dumps(extra, ensure_ascii=False) if extra else '(none)'}\n"
        f"Helpline: {extra.get('helpline', DEFAULT_HELPLINE) if extra else DEFAULT_HELPLINE}"
    )
    parsed, tok, err = safe_chat_json(cfg, system, user, temperature=0.3)
    if err or not parsed:
        return None, None
    text = str(parsed.get("message", "")).strip().splitlines()
    text = " ".join(t for t in text if t).strip()
    return (text or None), tok


def render_multilingual(
    alert_type: str,
    languages,
    district_names,
    body: str | None,
    title: str | None,
    extra: dict | None = None,
    llm_config: LLMConfig | None = None,
) -> AlertRender:
    """Render one alert into SMS-length messages for each language.

    * Known alert_type (flood/heatwave/cyclone) with hand-written templates ->
      template fill (ground truth). Admin ``body`` is appended after the
      template, mirroring the backend renderer.
    * Novel alert_type + LLM configured -> LLM composes per language.
    * Novel alert_type, no LLM -> generic hand-written skeleton per language.
    * A language missing from a template falls back to the Hindi template
      (labeled ``template:hi-fallback``).
    """
    cfg = llm_config or LLMConfig.from_env()
    langs = [l for l in (languages or LANGS) if l in LANGS] or LANGS
    district = _district_str(district_names)
    extra = dict(extra or {})
    values = {
        "district": district,
        "helpline": extra.get("helpline", DEFAULT_HELPLINE),
        "title": title or "",
        "temp": extra.get("temp", ""),
        "wind": extra.get("wind", ""),
    }

    templates = load_templates(alert_type) if alert_type in ALERT_TYPES else None
    messages: dict[str, str] = {}
    sources: dict[str, str] = {}
    notes: list[str] = []
    ptok = ctok = 0
    tok_est = True
    used_llm = False

    for lang in langs:
        text: str | None = None
        if templates:
            tpl = templates.get(lang)
            src = "template"
            if not tpl:
                tpl = templates.get("hi")
                src = "template:hi-fallback"
                notes.append(f"{lang}: no {alert_type} template, used Hindi template")
            if tpl:
                text = _fill(tpl, values)
                if body:
                    text = f"{text.rstrip()}\n{body.strip()}"
                sources[lang] = src
        if text is None and cfg.configured:
            composed, tok = _llm_compose(cfg, alert_type, lang, district, title or "", body or "", extra)
            if composed:
                text = composed
                sources[lang] = "llm"
                used_llm = True
                if tok:
                    ptok += tok.prompt_tokens
                    ctok += tok.completion_tokens
                    tok_est = tok_est and tok.estimated
            else:
                notes.append(f"{lang}: llm compose failed, used generic skeleton")
        if text is None:
            text = _fill(_GENERIC[lang], {**values, "title": title or alert_type})
            if body:
                text = f"{text.rstrip()}\n{body.strip()}"
            sources[lang] = sources.get(lang, "generic")
        messages[lang] = _cap(text, notes, lang)

    if used_llm:
        model = cfg.model_label
    elif templates:
        model = MODEL_TEMPLATE
    else:
        model = "generic-skeleton-v1"
    return AlertRender(
        messages=messages,
        sources=sources,
        model=model,
        prompt_tokens=ptok,
        completion_tokens=ctok,
        tokens_estimated=tok_est,
        notes=notes,
    )
