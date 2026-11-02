"""Check project pins, command help and safe text files."""

from pathlib import Path
import re
import struct
import tomllib

import pytest
from typer.testing import CliRunner

from migration_agent.cli import app

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = ("plan", "signoff", "dry-run", "run", "validate", "report")


def test_python_dependency_pins():
    """Require one exact version for each runtime and dev package."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = project["project"]["dependencies"] + project["dependency-groups"]["dev"]
    for dependency in dependencies:
        assert re.fullmatch(r"[\w.-]+(?:\[[\w,.-]+\])?==[\w.+!-]+", dependency), dependency


def test_python_only_repository():
    """Keep package manifests and TypeScript out of project files."""
    unwanted = []
    for folder, directories, files in ROOT.walk():
        directories[:] = [name for name in directories
                          if name not in {".git", ".venv", "__pycache__", ".pytest_cache"}]
        unwanted.extend(str((folder / name).relative_to(ROOT)) for name in files
                        if name == "package.json" or name.endswith(".ts"))
    assert not unwanted, unwanted


def test_dependency_record():
    """List all locked Python packages and build requirements."""
    document = (ROOT / "docs/DEPENDENCIES.md").read_text(encoding="utf-8")
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    for package in lock["package"]:
        if package["name"] != "migration-agent":
            assert f"| {package['name']} | {package['version']} |" in document
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    for requirement in project["build-system"]["requires"]:
        assert requirement in document


def test_cli_help_and_entry_point():
    """Expose the six commands through the configured console script."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["scripts"]["migration-agent"] == "migration_agent.cli:app"
    result = CliRunner().invoke(app, ["--help"], color=False)
    assert result.exit_code == 0, result.output
    for command in COMMANDS:
        assert command in result.output


@pytest.mark.parametrize("command", COMMANDS)
def test_command_help_and_placeholder(command, tmp_path, monkeypatch):
    """Each command explains itself and makes no migration files yet."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(app, [command, "--help"]).exit_code == 0
    result = runner.invoke(app, [command])
    assert result.exit_code == 0
    assert "not implemented yet" in result.output
    assert list(tmp_path.iterdir()) == []


def _text_files():
    """Read tracked files without running git, plus new task files."""
    index = (ROOT / ".git/index").read_bytes()
    signature, version, count = struct.unpack_from("!4sII", index)
    assert signature == b"DIRC" and version in (2, 3), "Expected a normal git index"
    offset = 12
    paths = set()
    for _ in range(count):
        start = offset
        flags = struct.unpack_from("!H", index, offset + 60)[0]
        offset += 62 + (2 if flags & 0x4000 else 0)
        end = index.index(b"\0", offset)
        paths.add(ROOT / index[offset:end].decode("utf-8"))
        offset = start + ((end + 1 - start + 7) // 8) * 8
    # Include task files before the human adds them to the index.
    for folder in ("src", "tests", "fixtures"):
        paths.update(path for path in (ROOT / folder).rglob("*") if path.is_file())
    paths.update((ROOT / "migration-agent.example.toml", ROOT / "docs/DEPENDENCIES.md"))
    for path in sorted(paths):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        raw = path.read_bytes()
        if b"\0" in raw:
            continue
        try:
            yield path.relative_to(ROOT), raw.decode("utf-8")
        except UnicodeDecodeError:
            continue


def test_no_keys_or_machine_paths_in_project_text():
    """Catch likely credentials and local machine paths in project text."""
    # Prefix names in the requirements are safe; a token after one is not.
    key = re.compile(r"(?:AI" + r"za|gs" + r"k_|nv" + r"api-)[A-Za-z0-9_-]{20,}")
    drive_path = re.compile(r"(?i)\b[a-z]:[\\/](?![\\/])")
    problems = []
    for path, text in _text_files():
        for number, line in enumerate(text.splitlines(), 1):
            if path.as_posix() == "docs/REQUIREMENTS.md":
                # The rule names a generic user folder, not a user's machine.
                line = line.replace("`C:" + chr(92) + "Users`", "`Windows user folder`")
            if key.search(line) or drive_path.search(line):
                problems.append(f"{path}:{number}")
    assert not problems, "Key or machine path found at: " + ", ".join(problems)
