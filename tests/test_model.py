"""Check model requests with patched replies and blocked sockets."""

import importlib
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace

import pytest

from migration_agent import model
from migration_agent.settings import Settings


@pytest.mark.parametrize("provider,key", [("openai", None), ("gemini", "GEMINI_API_KEY"),
    ("groq", "GROQ_API_KEY"), ("nvidia_nim", "NVIDIA_NIM_API_KEY")])
def test_chat_passes_settings(monkeypatch, provider, key):
    """Pass only the selected provider key, endpoint and timeout."""
    import litellm
    calls = []
    if key:
        monkeypatch.setenv(key, "made-up-test-key")
    def complete(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="hello"))], usage=None)
    monkeypatch.setattr(litellm, "completion", complete)
    settings = Settings(model=f"{provider}/example")
    messages = [{"role": "user", "content": "hello"}]
    assert model.chat(messages, {"type": "json_object"}, settings=settings, timeout=8).text == "hello"
    assert calls == [dict(model=settings.model, api_base=settings.api_base if key is None else None,
        api_key="made-up-test-key" if key else "local", timeout=8, max_retries=0,
        messages=messages, response_format={"type": "json_object"})]
    assert litellm.telemetry is False
    assert os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] == "True"


@pytest.mark.parametrize("provider,key", [("gemini", "GEMINI_API_KEY"), ("groq", "GROQ_API_KEY"),
    ("nvidia_nim", "NVIDIA_NIM_API_KEY")])
def test_missing_key_names_only_variable(monkeypatch, provider, key):
    """Keep other environment values out of errors."""
    monkeypatch.setenv("UNRELATED_PRIVATE_VALUE", "do-not-show-this")
    with pytest.raises(model.ModelError) as error:
        model.chat([], settings=Settings(model=f"{provider}/example"))
    assert str(error.value) == f"missing environment variable {key}"


@pytest.mark.parametrize("kind", ["timeout", "http"])
def test_request_errors_are_safe(monkeypatch, kind):
    """Turn timeouts and HTTP errors into small safe errors."""
    import litellm
    error = (litellm.Timeout(message="private", model="test", llm_provider="openai") if kind == "timeout"
             else litellm.BadRequestError(message="private", model="test", llm_provider="openai"))
    def fail(**kwargs):
        raise error
    monkeypatch.setattr(litellm, "completion", fail)
    with pytest.raises(model.ModelTimeout if kind == "timeout" else model.ModelError) as caught:
        model.chat([], settings=Settings())
    assert "private" not in str(caught.value)


def test_guard_and_import():
    """Refuse remote sockets and allow model import under the guard."""
    assert importlib.import_module("migration_agent.model") is model
    with socket.socket() as sock:
        for method in (sock.connect, sock.connect_ex):
            with pytest.raises(OSError, match="non-loopback"):
                method(("192.0.2.1", 443))
    with pytest.raises(OSError, match="non-loopback"):
        socket.getaddrinfo("example.test", 443)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        with pytest.raises(OSError, match="non-loopback"):
            sock.sendto(b"test", ("192.0.2.1", 443))
    assert socket.getaddrinfo("127.0.0.1", 80)


def test_default_excludes_live():
    """Keep live tests out of a normal offline run."""
    # A folder inside the project, not the shared temp folder: pytest scans the folders above the test file,
    # and other programs add and delete files in the shared temp folder at the same time.
    root = Path(__file__).resolve().parents[1]
    tmp_path = Path(tempfile.mkdtemp(prefix=".pytest-tmp-selection-", dir=root))
    sentinel = tmp_path / "test_selection.py"
    sentinel.write_text(
        "import pytest\n"
        "def test_offline():\n    pass\n"
        "@pytest.mark.live\n"
        "def test_live():\n    raise AssertionError('live test must not run')\n",
        encoding="utf-8", newline="\n",
    )
    config = root / "pyproject.toml"
    try:
        result = subprocess.run([sys.executable, "-m", "pytest", "-c", str(config), "--rootdir", str(root),
                                 "-p", "no:cacheprovider", str(sentinel), "-q"],
                                capture_output=True, text=True, timeout=30)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed, 1 deselected" in result.stdout
