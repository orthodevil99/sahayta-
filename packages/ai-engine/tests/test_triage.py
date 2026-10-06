"""Tests for triage.py — category mapping, frozen priority, LLM paths."""
from __future__ import annotations

import triage
from triage import MODEL_RULE, priority_for, rule_triage, triage_report


class TestRuleTriage:
    def test_demo_fixture_is_rescue(self, demo_description, no_llm_env):
        r = rule_triage(demo_description, 4)
        assert r.category == "rescue"
        assert r.priority == "critical"
        assert r.suggested_skills == ["rescue", "driving"]
        assert r.model == MODEL_RULE

    def test_rescue_checked_first(self, no_llm_env):
        # flood context dominates even with a medical word present
        r = rule_triage("Flood water rising; need medicine for the elderly on roof.", 4)
        assert r.category == "rescue"

    def test_medical(self, no_llm_env):
        r = rule_triage("A man is injured and bleeding, need ambulance.", 3)
        assert (r.category, r.suggested_skills) == ("medical", ["medical", "driving"])

    def test_food(self, no_llm_env):
        r = rule_triage("खाना खत्म हो गया है, बच्चे भूखे हैं।", 2)
        assert r.category == "food"
        assert r.suggested_skills == ["cooking", "logistics"]

    def test_shelter(self, no_llm_env):
        assert rule_triage("Need shelter camp for displaced families.", 2).category == "shelter"

    def test_infrastructure(self, no_llm_env):
        r = rule_triage("Power lines down, bridge damaged on the highway.", 3)
        assert r.category == "infrastructure"

    def test_other_fallback(self, no_llm_env):
        r = rule_triage("Just checking whether the helpline works.", 1)
        assert r.category == "other"
        assert r.suggested_skills == ["logistics"]

    def test_cyclone_extension(self, no_llm_env):
        # no rescue keywords (water/roof/trapped) -> infrastructure via power/road
        r = rule_triage("Cyclone snapped power lines; roads blocked by fallen trees.", 4)
        assert r.category == "infrastructure"
        assert r.suggested_skills == ["engineering", "logistics"]

    def test_heatwave_extension_is_medical(self, no_llm_env):
        assert rule_triage("Severe heatwave across the district.", 3).category == "medical"


class TestPriorityFrozen:
    def test_mapping(self, no_llm_env):
        assert [priority_for(s) for s in (1, 2, 3, 4, 5)] == [
            "low", "medium", "high", "critical", "critical",
        ]


class TestLLMPath:
    def _cfg(self):
        from config import LLMConfig

        return LLMConfig(base_url="http://x", model="test-model", timeout_s=1)

    def test_llm_success_never_changes_priority(self, monkeypatch, no_llm_env):
        def fake_safe(cfg, system, user, **kw):
            from llm import TokenUsage

            return (
                {"category": "medical", "suggested_skills": ["medical", "driving"],
                 "reason": "injuries mentioned"},
                TokenUsage(50, 10, "test-model", False),
                None,
            )

        monkeypatch.setattr(triage, "safe_chat_json", fake_safe)
        r = triage_report("someone is hurt", 2, "en", llm_config=self._cfg())
        assert r.category == "medical"
        assert r.priority == "medium"  # frozen mapping from severity, not LLM
        assert r.model == "llm:test-model"

    def test_llm_invalid_category_falls_back(self, monkeypatch, no_llm_env):
        def fake_safe(cfg, system, user, **kw):
            return ({"category": "alien", "suggested_skills": []}, None, None)

        monkeypatch.setattr(triage, "safe_chat_json", fake_safe)
        r = triage_report("flood water everywhere", 4, "en", llm_config=self._cfg())
        assert r.model == MODEL_RULE
        assert r.category == "rescue"

    def test_llm_error_falls_back(self, monkeypatch, no_llm_env):
        def fake_safe(cfg, system, user, **kw):
            return (None, None, "boom")

        monkeypatch.setattr(triage, "safe_chat_json", fake_safe)
        r = triage_report("need food packets", 2, "en", llm_config=self._cfg())
        assert r.model == MODEL_RULE
        assert r.category == "food"
