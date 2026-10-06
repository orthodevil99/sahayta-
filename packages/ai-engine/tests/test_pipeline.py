"""Tests for pipeline.py — the strict backend seam contract."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import pipeline
from pipeline import assess_and_route

SEAM_KEYS = {
    "severity", "rationale", "rationale_en", "area_tags", "category",
    "priority", "suggested_skills", "model",
}
EXTRA_KEYS = {
    "latency_ms", "prompt_tokens", "completion_tokens", "tokens_estimated",
    "cost_usd_estimate", "route", "notify_preview", "notes",
}


class TestSeamContract:
    def test_required_keys_present(self, demo_description, no_llm_env):
        r = assess_and_route(demo_description, "hi", 25.5941, 85.1376)
        assert SEAM_KEYS <= set(r.keys())
        assert isinstance(r["severity"], int) and 1 <= r["severity"] <= 5
        assert isinstance(r["area_tags"], list)
        assert isinstance(r["suggested_skills"], list)

    def test_demo_fixture_acceptance(self, demo_description, no_llm_env):
        r = assess_and_route(demo_description, "hi", 25.5941, 85.1376)
        assert r["severity"] == 4
        assert r["category"] == "rescue"
        assert r["priority"] == "critical"
        assert r["suggested_skills"] == ["rescue", "driving"]
        assert r["area_tags"] == ["road_submerged", "residential"]
        assert "\n" not in r["rationale"]  # one line, Hindi
        assert r["model"] == "rule-fallback-v1"

    def test_token_accounting_rule_path(self, no_llm_env):
        r = assess_and_route("waist-deep water", "en")
        assert r["prompt_tokens"] == 0
        assert r["completion_tokens"] == 0
        assert r["cost_usd_estimate"] == 0.0
        assert r["tokens_estimated"] is True

    def test_route_and_notify_present(self, no_llm_env):
        r = assess_and_route("waist-deep water; people on rooftops", "en")
        assert r["route"]["recommended_channel"] == "sms+app+ivrs"
        assert r["route"]["verify_recommended"] is True
        prev = r["notify_preview"]
        assert prev["alert_type"] == "flood"
        assert "en" not in prev["messages"]  # 'en' not a template lang -> hi
        assert "hi" in prev["messages"]

    def test_never_raises_on_garbage(self, no_llm_env):
        r = assess_and_route(None, None)  # type: ignore[arg-type]
        assert r["severity"] >= 1
        assert r["model"] == "rule-fallback-v1"


class FakeLLMHandler(BaseHTTPRequestHandler):
    """Minimal OpenAI-compatible chat-completions stub."""

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        system = json.dumps(body["messages"][0])
        if "severity estimator" in system:
            content = {"severity": 5, "rationale": "llm rationale line",
                       "rationale_en": "llm gloss", "area_tags": ["residential"],
                       "confidence": 0.95}
        else:
            content = {"category": "rescue",
                       "suggested_skills": ["rescue", "driving"],
                       "reason": "flood context"}
        envelope = {
            "choices": [{"message": {"content": json.dumps(content)}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 25},
        }
        data = json.dumps(envelope).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):  # silence
        pass


@pytest.fixture()
def fake_llm(monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), FakeLLMHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("SAHAYTA_LLM_BASE_URL",
                       f"http://127.0.0.1:{server.server_address[1]}")
    monkeypatch.setenv("SAHAYTA_LLM_MODEL", "fake-flash")
    monkeypatch.setenv("SAHAYTA_LLM_TIMEOUT_S", "5")
    yield server
    server.shutdown()


class TestLLMIntegration:
    def test_full_pipeline_over_http(self, fake_llm):
        r = assess_and_route("flood water rising fast", "en")
        assert r["severity"] == 5
        assert r["rationale"] == "llm rationale line"
        assert r["category"] == "rescue"
        assert r["model"] == "llm:fake-flash"
        assert r["prompt_tokens"] == 240  # 120 x 2 stages
        assert r["completion_tokens"] == 50
        assert r["cost_usd_estimate"] > 0

    def test_llm_down_falls_back_honestly(self, monkeypatch, no_llm_env):
        monkeypatch.setenv("SAHAYTA_LLM_BASE_URL", "http://127.0.0.1:1")
        monkeypatch.setenv("SAHAYTA_LLM_MODEL", "fake-flash")
        monkeypatch.setenv("SAHAYTA_LLM_TIMEOUT_S", "1")
        r = assess_and_route("knee-deep water", "en")
        assert r["severity"] == 2
        assert r["model"] == "rule-fallback-v1"
        assert any("llm" in n for n in r["notes"])
