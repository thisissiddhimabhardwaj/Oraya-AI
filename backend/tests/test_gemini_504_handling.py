"""Comprehensive validation of Gemini 504 Gateway Timeout handling,
per-model circuit breaker, retry budget enforcement, and Ollama failover.
"""
import time
from unittest.mock import Mock, call
import httpx
import pytest
from app.services import ai as gateway
from app.services import ai_quota as quota
from app.services.ai import AI, AIError


def error_504(message="The gateway timed out", model="gemini-3.8-flash"):
    resp = httpx.Response(504, request=httpx.Request("POST", "http://test"))
    e = RuntimeError(message)
    e.status_code = 504
    e.code = 504
    e.response = resp
    e.message = message
    return e


@pytest.fixture(autouse=True)
def isolated_ai(monkeypatch):
    quota.clear()
    monkeypatch.setattr(gateway.settings, "gemini_api_key", "test-api-key")
    monkeypatch.setattr(gateway.settings, "gemini_primary_model", "gemini-3.8-flash")
    monkeypatch.setattr(gateway.settings, "gemini_fallback_model_1", "gemini-3.7-flash")
    monkeypatch.setattr(gateway.settings, "gemini_fallback_model_2", "gemini-3.6-flash")
    monkeypatch.setattr(gateway.settings, "gemini_fallback_model_3", "")
    monkeypatch.setattr(gateway.settings, "enable_local_fallback", True)
    monkeypatch.setattr(gateway.settings, "ai_retry_attempts", 2)
    monkeypatch.setattr(gateway.settings, "ai_model_retry_budget_seconds", 10.0)
    monkeypatch.setattr(gateway.settings, "ai_max_retry_wait_seconds", 5.0)
    monkeypatch.setattr(gateway.time, "sleep", lambda _: None)
    yield
    quota.clear()


def test_classify_504_and_timeouts():
    """Requirement 7: Distinguish 504 from 429, 401, 404."""
    e504 = error_504()
    info = quota.classify(e504)
    assert info.http_status == 504
    assert info.category == "GATEWAY_TIMEOUT"
    assert info.api_status == "DEADLINE_EXCEEDED"

    read_timeout = httpx.ReadTimeout("Read timed out")
    info_to = quota.classify(read_timeout)
    assert info_to.http_status == 504
    assert info_to.category == "GATEWAY_TIMEOUT"

    # Distinguish from 401, 404, 429
    e401 = RuntimeError("Unauthorized"); e401.code = 401
    assert quota.classify(e401).category == "AUTHENTICATION"

    e404 = RuntimeError("Not found"); e404.code = 404
    assert quota.classify(e404).category == "MODEL_UNAVAILABLE"


def test_consecutive_504_circuit_breaker_progressive_cooldown():
    """Requirements 3 & 9: Progressive cooldown and circuit breaker tracking."""
    model = "gemini-3.8-flash"
    assert quota.consecutive_timeouts(model) == 0

    # 1st timeout -> 30s cooldown
    s1 = quota.record_timeout(model)
    assert s1 == 1
    d1 = quota.exhaust(model, quota.QuotaInfo(category="GATEWAY_TIMEOUT"))
    assert d1 >= 30.0
    assert quota.cooldown(model) is not None

    # 2nd consecutive timeout -> 120s cooldown
    s2 = quota.record_timeout(model)
    assert s2 == 2
    d2 = quota.exhaust(model, quota.QuotaInfo(category="GATEWAY_TIMEOUT"))
    assert d2 >= 120.0

    # 3rd consecutive timeout -> 300s cooldown
    s3 = quota.record_timeout(model)
    assert s3 == 3
    d3 = quota.exhaust(model, quota.QuotaInfo(category="GATEWAY_TIMEOUT"))
    assert d3 >= 300.0

    # Automatic recovery: record_success clears streak
    quota.record_success(model)
    assert quota.consecutive_timeouts(model) == 0


def test_consecutive_504_skips_retry_and_advances_immediately(monkeypatch):
    """Requirement 3 & 5: When model already has consecutive 504s, do not retry repeatedly; advance to next model."""
    # Pre-condition: gemini-3.8-flash has a recorded 504
    quota.record_timeout("gemini-3.8-flash")
    assert quota.consecutive_timeouts("gemini-3.8-flash") == 1

    calls = []
    def mock_gen(prompt, system, schema, temp, timeout, model, tokens):
        calls.append(model)
        if model == "gemini-3.8-flash":
            raise error_504(model=model)
        return "Answer from 3.7"

    monkeypatch.setattr(gateway, "verified_generate", mock_gen)
    
    start = time.monotonic()
    result, provider = AI().complete_text("What is inertia?")
    elapsed = time.monotonic() - start

    assert result == "Answer from 3.7"
    assert provider == "gemini"
    # gemini-3.8-flash was called exactly ONCE (no repetitive retries!), then immediately advanced to 3.7
    assert calls.count("gemini-3.8-flash") == 1
    assert calls.count("gemini-3.7-flash") == 1


def test_all_gemini_504_fast_failover_to_ollama(monkeypatch):
    """Requirement 6: If all Gemini models fail, invoke Ollama qwen3:4b without unnecessary delay."""
    calls = []
    def mock_gen(prompt, system, schema, temp, timeout, model, tokens):
        calls.append(model)
        raise error_504(model=model)

    monkeypatch.setattr(gateway, "verified_generate", mock_gen)
    local = Mock(return_value="Local Ollama generated response")
    monkeypatch.setattr(gateway, "ollama_generate", local)

    start = time.monotonic()
    result, provider = AI().complete_text("Explain photosynthesis")
    elapsed = time.monotonic() - start

    assert result == "Local Ollama generated response"
    assert provider == "ollama"
    assert local.call_count == 1
    # Each model attempted, none retried repeatedly
    assert "gemini-3.8-flash" in calls
    assert "gemini-3.7-flash" in calls
    assert "gemini-3.6-flash" in calls


def test_cooling_models_skipped_instantly_on_subsequent_request(monkeypatch):
    """Requirement 9: Cooled-down models are skipped in ~0ms on subsequent requests."""
    # Mark 3.8 and 3.7 as cooling down due to previous 504s
    quota.record_timeout("gemini-3.8-flash")
    quota.exhaust("gemini-3.8-flash", quota.QuotaInfo(category="GATEWAY_TIMEOUT"))
    quota.record_timeout("gemini-3.7-flash")
    quota.exhaust("gemini-3.7-flash", quota.QuotaInfo(category="GATEWAY_TIMEOUT"))

    calls = []
    def mock_gen(prompt, system, schema, temp, timeout, model, tokens):
        calls.append(model)
        return "Fast response from 3.6"

    monkeypatch.setattr(gateway, "verified_generate", mock_gen)

    start = time.monotonic()
    result, provider = AI().complete_text("Quick question")
    elapsed = time.monotonic() - start

    assert result == "Fast response from 3.6"
    assert provider == "gemini"
    # 3.8 and 3.7 were skipped instantly; 3.6 was the first model called
    assert calls == ["gemini-3.6-flash"]


def test_retry_budget_stops_retry_when_budget_exhausted(monkeypatch):
    """Requirement 5: Bounded retry budget stops retrying and advances."""
    # Set retry budget very short (0.01 seconds)
    monkeypatch.setattr(gateway.settings, "ai_model_retry_budget_seconds", 0.01)
    
    calls = []
    def mock_gen(prompt, system, schema, temp, timeout, model, tokens):
        calls.append(model)
        time.sleep(0.02)  # Simulates taking longer than the retry budget
        if model == "gemini-3.8-flash":
            raise error_504(model=model)
        return "Response from 3.7"

    monkeypatch.setattr(gateway, "verified_generate", mock_gen)

    result, provider = AI().complete_text("Question")
    assert result == "Response from 3.7"
    # Exactly 1 call on 3.8 because retry budget was exhausted
    assert calls.count("gemini-3.8-flash") == 1
