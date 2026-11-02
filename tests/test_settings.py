"""Check settings from files and the environment."""

from pathlib import Path
import tomllib

import pytest

from migration_agent.settings import Settings, SettingsError, load_settings

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    """Keep each test free from the user's local settings."""
    for key in Settings.model_fields:
        monkeypatch.delenv(f"MIGRATION_AGENT_{key.upper()}", raising=False)


def test_example_defaults():
    """Load every default from the committed example."""
    example = ROOT / "migration-agent.example.toml"
    settings = load_settings(example)
    assert settings == Settings.model_validate(tomllib.loads(example.read_text(encoding="utf-8")))
    assert settings == Settings()
    assert settings.batch_size == 50
    assert settings.source == Path("fixtures/acme_board.json")


def test_local_file_and_missing_optional_file(tmp_path, monkeypatch):
    """Use a local file when present and defaults when absent."""
    monkeypatch.chdir(tmp_path)
    assert load_settings() == Settings()
    (tmp_path / "migration-agent.toml").write_text('batch_size = 12\n', encoding="utf-8")
    assert load_settings().batch_size == 12


@pytest.mark.parametrize("key,value,expected", [
    ("batch_size", "5", 5),
    ("source", "another.json", Path("another.json")),
    ("target_server", "node another.js", "node another.js"),
    ("db_path", "another.sqlite", Path("another.sqlite")),
    ("model", "groq/example", "groq/example"),
    ("api_base", "http://localhost:9000/v1", "http://localhost:9000/v1"),
    ("runs_dir", "output", Path("output")),
])
def test_environment_overrides_file(monkeypatch, key, value, expected):
    """Each named environment value wins over the file."""
    monkeypatch.setenv(f"MIGRATION_AGENT_{key.upper()}", value)
    assert getattr(load_settings(ROOT / "migration-agent.example.toml"), key) == expected


@pytest.mark.parametrize("value", ["five", "1.5", "1.0", "0", "-1"])
def test_bad_batch_size_names_key(monkeypatch, value):
    """Bad batch sizes name the key so the user can fix it."""
    monkeypatch.setenv("MIGRATION_AGENT_BATCH_SIZE", value)
    with pytest.raises(SettingsError, match="MIGRATION_AGENT_BATCH_SIZE"):
        load_settings(ROOT / "migration-agent.example.toml")


@pytest.mark.parametrize("text", ["batch_size = true", "batch_size = 2.5", 'batch_size = "five"'])
def test_bad_file_batch_size(tmp_path, text):
    """Reject wrong file types instead of changing their meaning."""
    path = tmp_path / "settings.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(SettingsError, match="batch_size"):
        load_settings(path)


def test_missing_and_bad_files(tmp_path):
    """Name files that cannot be read or parsed."""
    path = tmp_path / "settings.toml"
    with pytest.raises(SettingsError, match="settings.toml"):
        load_settings(path)
    path.write_text("not = [", encoding="utf-8")
    with pytest.raises(SettingsError, match="settings.toml"):
        load_settings(path)


def test_keys_are_not_settings(tmp_path, monkeypatch):
    """Keep provider keys outside settings and out of errors."""
    monkeypatch.setenv("GEMINI_API_KEY", "private-test-value")
    assert "private-test-value" not in repr(load_settings(ROOT / "migration-agent.example.toml"))
    path = tmp_path / "settings.toml"
    path.write_text('api_key = "private-test-value"', encoding="utf-8")
    with pytest.raises(SettingsError) as error:
        load_settings(path)
    assert "api_key" in str(error.value)
    assert "private-test-value" not in str(error.value)
