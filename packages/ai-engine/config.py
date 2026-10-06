"""Environment-driven LLM configuration.

Provider-agnostic by construction: the model id and base URL come ONLY from
environment variables — never hardcoded. The engine speaks the OpenAI
chat-completions wire format, so GLM (Zhipu), OpenAI, or any compatible
endpoint works by changing env vars.

Relevant variables (all optional; engine degrades to rules when unset):

    SAHAYTA_LLM_BASE_URL   e.g. https://open.bigmodel.cn/api/paas/v4
    SAHAYTA_LLM_MODEL      e.g. glm-4-flash
    SAHAYTA_LLM_API_KEY    bearer token (optional; some gateways don't need one)
    SAHAYTA_LLM_TIMEOUT_S  per-call timeout, default 8
    SAHAYTA_LLM_MAX_TOKENS max completion tokens, default 600
    SAHAYTA_LLM_VISION     "1" to attach photo bytes to severity calls
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class LLMConfig:
    """Resolved LLM configuration. ``configured`` gates every LLM attempt."""

    base_url: str = ""
    model: str = ""
    api_key: str = ""
    timeout_s: float = 8.0
    max_tokens: int = 600
    vision: bool = False
    extra_headers: dict = field(default_factory=dict)

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.model)

    @property
    def endpoint(self) -> str:
        return self.base_url.rstrip("/") + "/chat/completions"

    @property
    def model_label(self) -> str:
        """Honest attribution string stamped on every LLM-produced result."""
        return f"llm:{self.model}"

    @classmethod
    def from_env(cls, env: dict | None = None) -> "LLMConfig":
        src = env if env is not None else os.environ
        base_url = (src.get("SAHAYTA_LLM_BASE_URL") or "").strip().rstrip("/")
        model = (src.get("SAHAYTA_LLM_MODEL") or "").strip()
        api_key = (src.get("SAHAYTA_LLM_API_KEY") or "").strip()
        try:
            timeout_s = float(src.get("SAHAYTA_LLM_TIMEOUT_S", "8") or 8)
        except ValueError:
            timeout_s = 8.0
        try:
            max_tokens = int(src.get("SAHAYTA_LLM_MAX_TOKENS", "600") or 600)
        except ValueError:
            max_tokens = 600
        vision = (src.get("SAHAYTA_LLM_VISION") or "").strip() == "1"
        return cls(
            base_url=base_url,
            model=model,
            api_key=api_key,
            timeout_s=max(1.0, min(120.0, timeout_s)),
            max_tokens=max(64, min(4096, max_tokens)),
            vision=vision,
        )
