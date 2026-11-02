"""Check repeatable model scripts without a model server."""

import json

import pytest

from migration_agent.fakes import FakeModel, ScriptExhausted


def test_script_replay_and_request_copy(tmp_path):
    """Read JSON replies in order and keep requests after callers change them."""
    path = tmp_path / "script.json"
    path.write_text(json.dumps([{"text": "first"}, {"text": "second"}]), encoding="utf-8")
    fake = FakeModel(path)
    messages = [{"role": "user", "content": "hello"}]
    format = {"type": "json_object"}
    assert fake.chat(messages, format).text == "first"
    messages[0]["content"] = "changed"
    format["type"] = "changed"
    assert fake.requests == [{"messages": [{"role": "user", "content": "hello"}],
                              "response_format": {"type": "json_object"}}]
    assert fake.chat([]).text == "second"
    with pytest.raises(ScriptExhausted):
        fake.chat([])


@pytest.mark.parametrize("script", [{}, [{"text": 3}], [{"other": "x"}]])
def test_bad_scripts(script):
    """Refuse scripts that cannot produce a text reply."""
    with pytest.raises(ValueError):
        FakeModel(script)
