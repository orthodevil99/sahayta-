"""Provider-agnostic LLM client (OpenAI chat-completions wire format).

Uses only the standard library (urllib) so the engine has zero runtime
dependencies. Every call returns parsed JSON plus honest token accounting:
real ``usage`` when the provider reports it, a documented estimate otherwise.

Cost figures are rough per-1M-token estimates for the demo — verify against
your provider's pricing page before budgeting real traffic.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from config import LLMConfig

log = logging.getLogger("sahayta.ai.llm")


class LLMError(RuntimeError):
    """Raised for any LLM failure (network, auth, bad payload, bad JSON)."""


@dataclass
class TokenUsage:
    """Per-call token accounting. ``estimated`` is True when the provider
    did not report usage and we fell back to estimate_tokens()."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    estimated: bool = True

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def cost_usd(self) -> float:
        """Rough cost estimate in USD. Documented estimate, not a quote."""
        per_m = _COST_PER_MTOK.get(self.model, _COST_PER_MTOK["__default__"])
        return round(
            self.prompt_tokens / 1e6 * per_m[0]
            + self.completion_tokens / 1e6 * per_m[1],
            6,
        )


# (input, output) USD per 1M tokens — rough estimates, verify with provider.
_COST_PER_MTOK: dict[str, tuple[float, float]] = {
    "glm-4-flash": (0.10, 0.10),
    "glm-4-flashx": (0.10, 0.10),
    "glm-4": (1.00, 1.00),
    "glm-4-plus": (5.00, 5.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "__default__": (0.50, 1.50),
}


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars/token for Latin, ~2.5 for Devanagari/CJK.

    Devanagari UTF-8 bytes are ~3x Latin; tokenizers typically spend ~1 token
    per 2-3 Devanagari characters. Documented heuristic, not exact.
    """
    if not text:
        return 0
    latin = sum(1 for c in text if ord(c) < 0x250)
    other = len(text) - latin
    return max(1, int(latin / 4 + other / 2.5))


def _headers(cfg: LLMConfig) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"
    headers.update(cfg.extra_headers)
    return headers


def chat_json(
    cfg: LLMConfig,
    system: str,
    user: str,
    *,
    images_b64: list[tuple[str, str]] | None = None,
    temperature: float = 0.2,
) -> tuple[dict, TokenUsage]:
    """POST one chat-completions request, parse the JSON object reply.

    Returns (parsed_dict, TokenUsage). Raises LLMError on any failure —
    callers are expected to fall back to rules and label honestly.
    """
    if not cfg.configured:
        raise LLMError("LLM not configured (SAHAYTA_LLM_BASE_URL/MODEL unset)")

    if images_b64:
        content: object = [{"type": "text", "text": user}]
        for mime, b64 in images_b64:
            content.append(
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
            )
    else:
        content = user
    payload = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
        "temperature": temperature,
        "max_tokens": cfg.max_tokens,
        "response_format": {"type": "json_object"},
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        cfg.endpoint, data=body, headers=_headers(cfg), method="POST"
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=cfg.timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise LLMError(f"HTTP {exc.code}: {detail}") from exc
    except Exception as exc:  # timeout, DNS, refused, TLS ...
        raise LLMError(f"request failed: {exc}") from exc
    latency_ms = int((time.perf_counter() - started) * 1000)
    log.debug("llm call ok status=%s latency_ms=%d", status, latency_ms)

    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMError(f"non-JSON envelope: {raw[:200]}") from exc
    try:
        text = envelope["choices"][0]["message"]["content"]
        parsed = json.loads(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise LLMError(f"bad completion shape: {str(exc)[:200]}") from exc
    if not isinstance(parsed, dict):
        raise LLMError("completion JSON was not an object")

    usage = envelope.get("usage") or {}
    if isinstance(usage.get("prompt_tokens"), int) and isinstance(
        usage.get("completion_tokens"), int
    ):
        tok = TokenUsage(
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            model=cfg.model,
            estimated=False,
        )
    else:
        tok = TokenUsage(
            prompt_tokens=estimate_tokens(system + user),
            completion_tokens=estimate_tokens(text),
            model=cfg.model,
            estimated=True,
        )
    return parsed, tok


def safe_chat_json(
    cfg: LLMConfig, system: str, user: str, **kwargs
) -> tuple[dict | None, TokenUsage | None, str | None]:
    """Never-raising wrapper: (parsed, usage, error)."""
    try:
        parsed, tok = chat_json(cfg, system, user, **kwargs)
        return parsed, tok, None
    except LLMError as exc:
        log.info("llm call failed (%s); caller should use rules", exc)
        return None, None, str(exc)
