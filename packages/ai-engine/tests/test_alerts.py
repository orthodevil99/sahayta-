"""Tests for alerts.py — template ground truth, caps, novel-alert paths."""
from __future__ import annotations

import alerts
from alerts import (
    HARD_CAP_CHARS,
    LANGS,
    TARGET_CHARS,
    load_templates,
    render_multilingual,
)


class TestTemplates:
    def test_all_types_load(self, no_llm_env):
        for t in ("flood", "heatwave", "cyclone"):
            tpl = load_templates(t)
            assert tpl is not None
            assert set(LANGS) <= set(tpl.keys())

    def test_template_render_all_languages_within_target(self, no_llm_env):
        r = render_multilingual("flood", LANGS, "Patna", None, "बाढ़ चेतावनी",
                                {"helpline": "1078"})
        assert set(r.messages.keys()) == set(LANGS)
        for lang, msg in r.messages.items():
            assert len(msg) <= TARGET_CHARS, f"{lang}: {len(msg)} chars"
            assert r.sources[lang] == "template"
        assert r.model == "template-ground-truth-v1"
        assert "Patna" in r.messages["hi"]
        assert "1078" in r.messages["hi"]

    def test_hard_cap_never_exceeded(self, no_llm_env):
        long_body = "पानी बढ़ रहा है। " * 200
        r = render_multilingual("flood", ["hi"], "Patna", long_body, "t", {})
        assert len(r.messages["hi"]) <= HARD_CAP_CHARS
        assert any("truncated" in n for n in r.notes)

    def test_body_appended(self, no_llm_env):
        r = render_multilingual("flood", ["hi"], "Patna", "कैंप खुले हैं।",
                                "t", {})
        assert "कैंप खुले हैं।" in r.messages["hi"]

    def test_unknown_language_code_defaults_to_all(self, no_llm_env):
        r = render_multilingual("flood", ["xx"], "Patna", None, "t", {})
        # unknown lang code filtered -> defaults to all 10
        assert set(r.messages.keys()) == set(LANGS)

    def test_district_list_joined(self, no_llm_env):
        r = render_multilingual("flood", ["hing"], ["Patna", "Vaishali"],
                                None, "t", {})
        assert "Patna, Vaishali" in r.messages["hing"]

    def test_extra_temp_wind_placeholders(self, no_llm_env):
        r = render_multilingual("heatwave", ["hi"], "Nagpur", None, "t",
                                {"temp": "46"})
        assert "46" in r.messages["hi"]


class TestNovelAlerts:
    def test_novel_without_llm_uses_generic_skeleton(self, no_llm_env):
        r = render_multilingual("earthquake", ["hi", "ta"], "Patna",
                                "भूकंप के झटके।", "भूकंप चेतावनी", {})
        assert r.model == "generic-skeleton-v1"
        assert r.sources["hi"] == "generic"
        assert "Patna" in r.messages["hi"]
        assert len(r.messages["ta"]) <= TARGET_CHARS

    def test_novel_with_llm_composes(self, monkeypatch, no_llm_env):
        from config import LLMConfig
        from llm import TokenUsage

        calls = []

        def fake_safe(cfg, system, user, **kw):
            calls.append(system)
            return ({"message": "TEST ALERT " + system[:10]},
                    TokenUsage(10, 5, "m", True), None)

        monkeypatch.setattr(alerts, "safe_chat_json", fake_safe)
        cfg = LLMConfig(base_url="http://x", model="m", timeout_s=1)
        r = render_multilingual("earthquake", ["hi", "bn"], "Patna", "b",
                                "t", {}, llm_config=cfg)
        assert r.sources["hi"] == "llm"
        assert r.model == "llm:m"
        assert r.prompt_tokens == 20
        assert len(calls) == 2

    def test_novel_llm_failure_falls_back_to_generic(self, monkeypatch, no_llm_env):
        from config import LLMConfig

        def fake_safe(cfg, system, user, **kw):
            return (None, None, "down")

        monkeypatch.setattr(alerts, "safe_chat_json", fake_safe)
        cfg = LLMConfig(base_url="http://x", model="m", timeout_s=1)
        r = render_multilingual("earthquake", ["hi"], "Patna", None, "t",
                                {}, llm_config=cfg)
        assert r.sources["hi"] == "generic"
        assert "Patna" in r.messages["hi"]
