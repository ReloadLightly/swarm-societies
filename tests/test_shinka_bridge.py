"""Transport integrity: never claim a failed response is a completed mutation."""
import json

import pytest

from swarm_societies.shinka_bridge import parse_codex_events, subscription_environment


def test_completed_response_preserves_reported_usage():
    stdout = "\n".join(json.dumps(event) for event in [
        {"type": "thread.started", "thread_id": "example"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "```python\nx=1\n```"}},
        {"type": "turn.completed", "usage": {"input_tokens": 41, "cached_input_tokens": 7,
                                                   "output_tokens": 9, "reasoning_output_tokens": 3}},
    ])
    text, usage = parse_codex_events(stdout)
    assert text == "```python\nx=1\n```"
    assert usage["input_tokens"] == 41
    assert usage["cached_input_tokens"] == 7
    assert usage["thinking_tokens"] == 3
    assert usage["cost_basis"] == "subscription"


@pytest.mark.parametrize("events", [[], [{"type": "turn.failed", "error": "quota"}],
    [{"type": "item.completed", "item": {"type": "agent_message", "text": "partial"}}]])
def test_partial_or_failed_turn_is_not_a_mutation(events):
    with pytest.raises(RuntimeError, match="No completed Codex response"):
        parse_codex_events("\n".join(json.dumps(event) for event in events))


def test_provider_api_keys_do_not_reach_codex(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-not-a-secret")
    monkeypatch.setenv("GOOGLE_API_KEY", "dummy-not-a-secret")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid")
    monkeypatch.setenv("CODEX_HOME", "/tmp/test-codex-auth")
    env = subscription_environment()
    assert "OPENAI_API_KEY" not in env
    assert "GOOGLE_API_KEY" not in env
    assert "OPENAI_BASE_URL" not in env
    assert env["CODEX_HOME"] == "/tmp/test-codex-auth"
