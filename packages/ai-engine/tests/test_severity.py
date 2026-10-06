"""Tests for severity.py — rule twin parity, demo fixture, LLM paths."""
from __future__ import annotations

import severity
from severity import MODEL_RULE, assess_severity, rule_assess


class TestDemoFixture:
    def test_scores_4(self, demo_description, no_llm_env):
        r = rule_assess(demo_description, "hi")
        assert r.severity == 4
        assert r.model == MODEL_RULE

    def test_rationale_one_line_hindi(self, demo_description, no_llm_env):
        r = rule_assess(demo_description, "hi")
        assert "\n" not in r.rationale
        assert "घुटनों तक पानी" in r.rationale
        assert "छत" in r.rationale  # people on rooftops
        assert "अति गंभीर" in r.rationale

    def test_rationale_en_gloss(self, demo_description, no_llm_env):
        r = rule_assess(demo_description, "hi")
        assert r.rationale_en is not None
        assert "severity 4/5" in r.rationale_en

    def test_area_tags(self, demo_description, no_llm_env):
        r = rule_assess(demo_description, "hi")
        assert r.area_tags == ["road_submerged", "residential"]

    def test_latency_nonnegative(self, demo_description, no_llm_env):
        assert rule_assess(demo_description, "hi").latency_ms >= 0


class TestTwinParity:
    """Canonical inputs scored by the documented twin formula
    (strongest depth wins; +1 people; +1 urgent; clamp 1-5)."""

    def test_empty_is_1(self, no_llm_env):
        assert rule_assess("", "hi").severity == 1

    def test_chest_deep_alone_is_4(self, no_llm_env):
        assert rule_assess("Chest-deep water on the main road.", "en").severity == 4

    def test_chest_deep_plus_people_plus_urgent_caps_at_5(self, no_llm_env):
        r = rule_assess("Neck-deep water; children trapped; urgent help needed!", "en")
        assert r.severity == 5

    def test_strongest_depth_wins_not_additive(self, no_llm_env):
        # waist-deep (2) beats knee-deep (1); must NOT sum to 3+1+1+1.
        r = rule_assess("कमर तक पानी, घुटनों तक पानी, बुजुर्ग फंसे हैं।", "hi")
        assert r.severity == 4  # 1 + 2 + 1 + 0

    def test_knee_deep_plus_urgent(self, no_llm_env):
        assert rule_assess("knee-deep water, immediately send help", "en").severity == 3

    def test_people_bucket_counts_once(self, no_llm_env):
        r = rule_assess("बुजुर्ग और बच्चे छत पर फंसे हैं, पानी भरा है।", "hi")
        assert r.severity == 3  # 1 + 1(water) + 1(people, once) + 0

    def test_hinglish_rationale(self, no_llm_env):
        # Latin-script input: twin regexes are Devanagari/English only, so no
        # keyword matches at all -> severity 1, waterlogging/residential bits.
        r = rule_assess("kamar tak paani, log chhat par hain", "hing")
        assert r.severity == 1
        assert r.rationale == "paani bhara hua; rihayshi ilaka prabhavit — halka sthiti."

    def test_unknown_language_falls_back_to_english(self, no_llm_env):
        # Twin behavior: non hi/hing language -> English rationale words.
        r = rule_assess("waist-deep water", "ta")
        assert "waist-deep water" in r.rationale


class TestStormHeatTiers:
    """v1.2 documented divergence from the twin (twin has no storm/heat)."""

    def test_cyclone_catastrophic_is_5(self, no_llm_env):
        r = rule_assess("Catastrophic cyclone devastation; collapsed buildings.", "en")
        assert r.severity == 5

    def test_destructive_winds_is_4(self, no_llm_env):
        r = rule_assess("Destructive winds battering the town; streets flooded.", "en")
        assert r.severity == 4

    def test_cyclonic_storm_bare_is_3(self, no_llm_env):
        r = rule_assess("Cyclonic storm hitting the coast; fallen trees.", "en")
        assert r.severity == 3

    def test_deadly_heatwave_is_5(self, no_llm_env):
        r = rule_assess("Deadly heatwave; hospital entrance crowded.", "en")
        assert r.severity == 5

    def test_scorching_heat_is_2(self, no_llm_env):
        assert rule_assess("Scorching heat in the market.", "en").severity == 2

    def test_plain_sunny_day_is_1(self, no_llm_env):
        assert rule_assess("Hot sunny afternoon; people using umbrellas.", "en").severity == 1

    def test_area_tag_wind_damage(self, no_llm_env):
        r = rule_assess("Cyclone uprooted trees; power lines down.", "en")
        assert "wind_damage" in r.area_tags


class TestLLMPath:
    def _cfg(self):
        from config import LLMConfig

        return LLMConfig(base_url="http://x", model="test-model", timeout_s=1)

    def test_llm_success_labels_honestly(self, monkeypatch, no_llm_env):
        def fake_safe(cfg, system, user, **kw):
            from llm import TokenUsage

            return (
                {"severity": 4, "rationale": "r", "rationale_en": "re",
                 "area_tags": ["rescue_zone"], "confidence": 0.9},
                TokenUsage(prompt_tokens=100, completion_tokens=20,
                           model="test-model", estimated=False),
                None,
            )

        monkeypatch.setattr(severity, "safe_chat_json", fake_safe)
        r = assess_severity("flood water", "en", llm_config=self._cfg())
        assert r.severity == 4
        assert r.model == "llm:test-model"
        assert r.prompt_tokens == 100
        assert r.completion_tokens == 20
        assert r.tokens_estimated is False

    def test_llm_out_of_range_falls_back_honestly(self, monkeypatch, no_llm_env):
        def fake_safe(cfg, system, user, **kw):
            return ({"severity": 9, "rationale": "x"}, None, None)

        monkeypatch.setattr(severity, "safe_chat_json", fake_safe)
        r = assess_severity("knee-deep water", "en", llm_config=self._cfg())
        assert r.model == MODEL_RULE
        assert r.severity == 2  # rule: 1 + 1(knee)
        assert any("llm_error_fallback" in n for n in r.notes)

    def test_llm_error_falls_back_honestly(self, monkeypatch, no_llm_env):
        def fake_safe(cfg, system, user, **kw):
            return (None, None, "timeout")

        monkeypatch.setattr(severity, "safe_chat_json", fake_safe)
        r = assess_severity("waist-deep water", "en", llm_config=self._cfg())
        assert r.model == MODEL_RULE
        assert r.severity == 3

    def test_unconfigured_uses_rules(self, no_llm_env):
        r = assess_severity("waist-deep water", "en")
        assert r.model == MODEL_RULE
        assert r.prompt_tokens == 0
