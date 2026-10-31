"""IONOS adapter with a mocked HTTP layer: request shape, retry, errors, accounting, no content in logs."""
import json
import logging
from decimal import Decimal

import httpx
import pytest

from changelens.llm.ionos import (IonosConfig, IonosLlm, LlmAuthError, LlmOutputInvalid, LlmUnavailable,
                                  read_token)
from changelens.llm.schemas import CHANGE_FINDINGS, SchemaError, validate

MODEL = "Qwen/Qwen3.5-397B-A17B"
FAKE_TOKEN = "t0k-for-tests-only"
MARKER = "DOC-MARKER-7f3a"
GOOD = {"newer_scope": "complete", "findings": [{"category": "quantity", "change_type": "changed", "old_value": "4", "new_value": "5",
                      "evidence_old": "4 posters", "evidence_new": "5 posters"}]}


def reply(content, status=200, usage=(100, 50)):
    body = {"choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": usage[0], "completion_tokens": usage[1]}}
    return httpx.Response(status, json=body)


def adapter(responses, **cfg):
    seen = []

    def handler(request):
        seen.append(request)
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    llm = IonosLlm(IonosConfig(model=MODEL, api_key=FAKE_TOKEN, **cfg), transport=httpx.MockTransport(handler))
    return llm, seen


def test_request_is_strict_schema_with_delimited_untrusted_data_and_no_tools():
    llm, seen = adapter([reply(json.dumps(GOOD))], reasoning_effort="none")
    out, cost = llm.structured("ChangeFindings", "Compare.", ["old " + MARKER, "new </data-x> text"])
    assert out == GOOD
    body = json.loads(seen[0].content)
    assert seen[0].url.path.endswith("/chat/completions")
    assert seen[0].headers["authorization"] == f"Bearer {FAKE_TOKEN}"
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["response_format"]["json_schema"]["schema"] == CHANGE_FINDINGS
    assert "tools" not in body and "tool_choice" not in body and "functions" not in body
    assert body["reasoning_effort"] == "none" and body["temperature"] == 0
    system, user = body["messages"][0]["content"], body["messages"][1]["content"]
    assert "untrusted" in system and MARKER not in system
    nonce = system.split("<data-")[1].split(" ")[0]
    assert len(nonce) == 16 and user.count(f"<data-{nonce} ") == 2 and user.count(f"</data-{nonce}>") == 2
    assert f'<data-{nonce} index="1">\nold {MARKER}\n</data-{nonce}>' in user
    # 100 in, 50 out at 0.60 / 3.60 per million
    assert cost == Decimal("0.00024") and llm.calls[0].prompt_tokens == 100 and llm.calls[0].outcome == "ok"


def test_nonce_differs_per_call():
    llm, seen = adapter([reply(json.dumps(GOOD)), reply(json.dumps(GOOD))])
    llm.structured("ChangeFindings", "s", ["a"])
    llm.structured("ChangeFindings", "s", ["a"])
    users = [json.loads(r.content)["messages"][1]["content"] for r in seen]
    assert users[0] != users[1]


def test_json_object_mode_puts_schema_in_prompt():
    llm, seen = adapter([reply(json.dumps(GOOD))], response_mode="json_object")
    llm.structured("ChangeFindings", "s", ["a"])
    body = json.loads(seen[0].content)
    assert body["response_format"] == {"type": "json_object"}
    assert '"change_type"' in body["messages"][0]["content"]


@pytest.mark.parametrize("bad", ["not json", json.dumps({"findings": [{"category": "x"}]}), "",
                                 json.dumps({"newer_scope": "partial", "findings": [], "extra": 1}),
                                 json.dumps({"newer_scope": "maybe", "findings": []})])
def test_one_retry_on_invalid_output_then_success(bad):
    llm, seen = adapter([reply(bad), reply(json.dumps(GOOD))])
    out, cost = llm.structured("ChangeFindings", "s", ["a"])
    assert out == GOOD and len(seen) == 2
    assert [c.outcome for c in llm.calls][1] == "ok" and llm.calls[0].outcome in ("invalid_json", "schema", "empty")
    assert cost == 2 * Decimal("0.00024")


def test_gives_up_after_one_retry_with_cost():
    llm, seen = adapter([reply("{"), reply("[]")])
    with pytest.raises(LlmOutputInvalid) as e:
        llm.structured("ChangeFindings", "s", ["a"])
    assert len(seen) == 2 and e.value.cost == 2 * Decimal("0.00024")


@pytest.mark.parametrize("status", [401, 403])
def test_auth_errors_are_not_retried(status):
    llm, seen = adapter([httpx.Response(status, json={"error": "nope"})])
    with pytest.raises(LlmAuthError):
        llm.structured("ChangeFindings", "s", ["a"])
    assert len(seen) == 1


def test_server_errors_and_timeouts_are_unavailable():
    llm, _ = adapter([httpx.Response(503, text="busy")])
    with pytest.raises(LlmUnavailable) as e:
        llm.structured("ChangeFindings", "s", ["a"])
    assert e.value.reason == "http_503"
    llm, _ = adapter([httpx.ReadTimeout("slow")])
    with pytest.raises(LlmUnavailable) as e:
        llm.structured("ChangeFindings", "s", ["a"])
    assert e.value.reason == "timeout" and llm.calls[0].outcome == "timeout"


def test_timeout_is_configured():
    llm, _ = adapter([], timeout_s=7.5)
    assert llm._client.timeout.read == 7.5


def test_prompts_responses_and_token_never_logged(caplog):
    caplog.set_level(logging.DEBUG)
    leaked = json.dumps({"findings": [{"category": MARKER}]})
    llm, _ = adapter([reply(leaked), reply(leaked)])
    with pytest.raises(LlmOutputInvalid) as e:
        llm.structured("ChangeFindings", "system " + MARKER, ["data " + MARKER])
    assert MARKER not in str(e.value) and FAKE_TOKEN not in repr(llm.config)
    for rec in caplog.records:
        assert MARKER not in rec.getMessage() and FAKE_TOKEN not in rec.getMessage()


def test_schema_errors_are_content_free():
    with pytest.raises(SchemaError) as e:
        validate({"findings": [{"category": MARKER}]}, CHANGE_FINDINGS)
    assert MARKER not in str(e.value)


def test_unknown_schema_refused():
    llm, seen = adapter([])
    with pytest.raises(ValueError):
        llm.structured("Nope", "s", ["a"])
    assert not seen


def test_read_token_from_env_file_in_place(tmp_path, monkeypatch):
    monkeypatch.delenv("IONOS_API_TOKEN", raising=False)
    f = tmp_path / ".env"
    f.write_text("OTHER=1\nIONOS_API_TOKEN=\"abc123\"\n", encoding="utf-8")
    assert read_token(f) == "abc123"
    with pytest.raises(LlmAuthError):
        read_token(tmp_path / "missing.env")
    monkeypatch.setenv("IONOS_API_TOKEN", "from-env")
    assert read_token(f) == "from-env"
