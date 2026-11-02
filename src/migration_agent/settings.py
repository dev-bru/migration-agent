"""Read settings for a migration.

Environment values take the place of file values.
Keep API keys in the environment, outside these settings.
"""

import os
from pathlib import Path
import tomllib

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class SettingsError(ValueError):
    """A setting could not be read or has a bad value."""


class Settings(BaseModel):
    """Hold the paths and options for one migration."""

    model_config = ConfigDict(extra="forbid")

    source: Path = Path("fixtures/acme_board.json")
    target_server: str = "python -m migration_agent.target_server"
    db_path: Path = Path(".migration-agent/target.sqlite")
    batch_size: int = Field(default=50, gt=0, strict=True)
    model: str = "openai/local-qwen"
    api_base: str = "http://127.0.0.1:8080/v1"
    runs_dir: Path = Path("runs")


def load_settings(path: str | Path | None = None) -> Settings:
    """Read a TOML file, then apply the named environment values."""
    settings_path = Path(path) if path is not None else Path("migration-agent.toml")
    values = {}
    if path is not None or settings_path.exists():
        try:
            values = tomllib.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
            raise SettingsError(f"{settings_path}: {exc}") from exc
    for key in Settings.model_fields:
        env_key = f"MIGRATION_AGENT_{key.upper()}"
        if env_key in os.environ:
            values[key] = os.environ[env_key]
            if key == "batch_size":
                try:
                    values[key] = int(values[key])
                except ValueError as exc:
                    raise SettingsError(f"{env_key}: expected an integer") from exc
    try:
        return Settings.model_validate(values)
    except ValidationError as exc:
        # Name each key without printing values that may be private.
        errors = "; ".join(
            f"MIGRATION_AGENT_{str(error['loc'][0]).upper()} ({error['loc'][0]}): {error['msg']}"
            for error in exc.errors()
        )
        raise SettingsError(errors) from exc
