"""Multilingual alert rendering.

v1 path (honest, deterministic): fill the hand-written templates in
``data/alert-templates/{flood,heatwave,cyclone}.json`` with the request's
placeholders ({district}, {helpline}, {temp}, {wind}), then append the admin's
custom body (truncated) so district-specific detail like "Kankarbagh" survives.
Every message is capped at SMS length (<=480 chars / 3 segments).

When ``packages/ai-engine/alerts.py`` exists with ``render_multilingual`` and an
LLM is configured, Agent 6's engine is used for novel alerts; template rendering
remains the ground-truth fallback. (Wave 2: engine does not exist yet, so the
template path always runs — labeled accordingly.)
"""
from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path

from ..config import get_settings

log = logging.getLogger("sahayta.alerts")

# backend/app/services/alerts_render.py -> services -> app -> backend -> sahayta/
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
TEMPLATE_DIR = REPO_ROOT / "data" / "alert-templates"
AI_ALERTS_PY = REPO_ROOT / "packages" / "ai-engine" / "alerts.py"

SMS_MAX_CHARS = 480
TEN_LANGS = ["hi", "hing", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa"]


def _load_templates(alert_type: str) -> dict | None:
    path = TEMPLATE_DIR / f"{alert_type}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — corrupt template -> custom path
        log.warning("alert template %s unreadable: %s", path, exc)
        return None


def _fill(template: str, values: dict[str, str]) -> str:
    out = template
    for key, val in values.items():
        out = out.replace("{" + key + "}", val)
    return out


def _truncate_sms(text: str) -> str:
    text = text.strip()
    if len(text) <= SMS_MAX_CHARS:
        return text
    return text[: SMS_MAX_CHARS - 1].rstrip() + "…"


def render_with_templates(
    alert_type: str,
    languages: list[str],
    district_names: list[str],
    body: str,
    title: str,
    extra: dict[str, str] | None = None,
) -> tuple[dict[str, str], str]:
    """Returns (rendered_map, renderer_label)."""
    settings = get_settings()
    values = {
        "district": ", ".join(district_names) if district_names else "",
        "helpline": settings.demo_helpline,
        "temp": (extra or {}).get("temp", ""),
        "wind": (extra or {}).get("wind", ""),
    }
    bundle = _load_templates(alert_type)
    rendered: dict[str, str] = {}
    if bundle and isinstance(bundle.get("templates"), dict):
        templates = bundle["templates"]
        for lang in languages:
            tpl = templates.get(lang) or templates.get("hi") or ""
            msg = _fill(tpl, values)
            if body and body not in msg:
                msg = f"{msg} {body}".strip()
            rendered[lang] = _truncate_sms(msg)
        return rendered, "template-v1"
    # No template (e.g. type=custom): title + body, truncated.
    for lang in languages:
        rendered[lang] = _truncate_sms(f"{title} {body}".strip())
    return rendered, "custom-v1"


def _load_ai_engine():
    if not AI_ALERTS_PY.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("sahayta_ai_alerts", AI_ALERTS_PY)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module if hasattr(module, "render_multilingual") else None
    except Exception as exc:  # noqa: BLE001
        log.warning("ai-engine alerts failed to load: %s", exc)
        return None


def render_multilingual(
    alert_type: str,
    languages: list[str],
    district_names: list[str],
    body: str,
    title: str,
    extra: dict[str, str] | None = None,
) -> tuple[dict[str, str], str]:
    """Render one alert into SMS-length messages per language.

    Returns (rendered_map, renderer_label) where the label is honest about
    which path produced the text.
    """
    settings = get_settings()
    engine = _load_ai_engine() if settings.llm_configured else None
    if engine is not None:
        try:
            out = engine.render_multilingual(
                alert_type=alert_type,
                languages=languages,
                district_names=district_names,
                body=body,
                title=title,
                extra=extra or {},
            )
            rendered = {k: _truncate_sms(str(v)) for k, v in dict(out).items()}
            return rendered, f"ai-engine:{settings.llm_model}"
        except Exception as exc:  # noqa: BLE001 — engine error -> template truth
            log.warning("ai-engine render failed (%s); template fallback", exc)
    return render_with_templates(alert_type, languages, district_names, body, title, extra)


def estimate_recipients(district_populations: list[int | None]) -> int:
    """Deterministic back-of-envelope reach estimate.

    ~0.13% of district population (models SMS-gateway subscriber penetration
    for a district broadcast). Labeled an *estimate* on the wire.
    """
    total = sum(p or 0 for p in district_populations)
    return int(total * 0.0013)
