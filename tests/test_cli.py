"""Exercise the real command flow with local fakes and an MCP server."""

import json
from pathlib import Path
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from migration_agent.cli import app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config(tmp_path):
    """Keep every run artifact inside this test's project-local folder."""
    path = tmp_path / "settings.toml"
    path.write_text(f"source = '{(ROOT / 'fixtures/acme_board.json').as_posix()}'\n"
                    f"runs_dir = '{tmp_path.as_posix()}'\n"
                    f"db_path = '{(tmp_path / 'target.sqlite').as_posix()}'\n", encoding="utf-8", newline="\n")
    return path


def test_demo_offline_artifacts_and_rerun(config, tmp_path):
    """Produce all promised files and safely repeat the demo."""
    runner = CliRunner()
    for _ in range(2):
        result = runner.invoke(app, ["demo", "--settings", str(config)])
        assert result.exit_code == 0, result.output
        assert "Demo complete" in result.output
    for name in ("plan.json", "signoff.json", "checkpoint.json", "validation.json", "report.md"):
        assert (tmp_path / name).is_file()
    validation = json.loads((tmp_path / "validation.json").read_bytes())
    assert len(validation["checks"]) == 4
    assert all(check["status"] == "pass" for check in validation["checks"])
    assert "unknown member" in (tmp_path / "report.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("command", ["plan", "signoff", "dry-run", "run", "validate", "report", "demo"])
def test_known_errors_are_one_line(command, tmp_path):
    """Name a bad settings file once without a traceback."""
    result = CliRunner().invoke(app, [command, "--settings", str(tmp_path / "absent.toml"), "--fake"])
    assert result.exit_code == 1
    assert len(result.output.strip().splitlines()) == 1
    assert "Traceback" not in result.output
    assert "absent.toml" in result.output


@pytest.mark.parametrize("fake", [True, False])
def test_commands_use_one_workspace(config, tmp_path, fake):
    """Preview, approve, run twice, validate and report on fake and real MCP targets."""
    runner = CliRunner()
    common = ["--settings", str(config)] + (["--fake"] if fake else [])
    scripts = ROOT / "src/migration_agent/fake_scripts"

    def invoke(command, *options, success=True):
        args = [command, *common, *options]
        if fake:
            result = runner.invoke(app, args)
            code, output = result.exit_code, result.output
        else:
            # Give the stdio child real OS pipes, as a terminal invocation does.
            result = subprocess.run([sys.executable, "-m", "migration_agent.cli", *args],
                                    cwd=ROOT, capture_output=True, text=True, timeout=60)
            code, output = result.returncode, result.stdout + result.stderr
        assert code == (0 if success else 1), output
        return output

    invoke("plan", "--script", str(scripts / "plan.json"), "--schema", str(scripts / "schema.json"))
    path = tmp_path / "plan.json"
    invoke("run", success=False)
    assert "labels" in invoke("signoff", "--signed-by", "Example Reviewer", success=False)
    proposal = json.loads(path.read_bytes())
    for q in proposal["questions"]:
        q["answer"] = "Approved"
    path.write_text(json.dumps(proposal), encoding="utf-8", newline="\n")
    # A fresh MCP workspace has no schema until an approved run creates it.
    if fake:
        assert "Choose pretend seeds" in invoke("dry-run")
    invoke("signoff", "--signed-by", "Example Reviewer")
    for _ in range(2):
        invoke("run", *([] if fake else ["--schema", str(scripts / "schema.json")]))
    assert "Choose pretend seeds" in invoke("dry-run")
    invoke("validate", "--sample-size", "100", "--seed", "42")
    result = json.loads((tmp_path / "validation.json").read_bytes())
    assert all(c["status"] == "pass" for c in result["checks"])
    invoke("report", "--no-llm")
    assert "## What moved" in (tmp_path / "report.md").read_text(encoding="utf-8")
    path.write_bytes(path.read_bytes() + b"\n")
    assert "does not match" in invoke("run", success=False)
