"""Keep approval tied to the human's exact reviewed plan."""

from copy import deepcopy
import hashlib
import json

import pytest
from typer.testing import CliRunner

from migration_agent.cli import app
from migration_agent.signoff import SignoffError, require_signoff, signoff

PLAN = {"version": 1, "source_hash": "made-up-hash", "entities": [
    {"source": "card", "target_database": "Tasks", "fields": []}],
    "questions": [{"id": "q1", "text": "Approve?", "options": ["Yes"], "answer": None}], "signed_off": False}


def _plan(tmp_path, answer=None):
    data = deepcopy(PLAN)
    data["questions"][0]["answer"] = answer
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.mark.parametrize("answer", [None, "", "   "])
def test_unanswered_question_refuses_signoff(tmp_path, answer):
    """Show unanswered question IDs without writing approval."""
    path = _plan(tmp_path, answer)
    before = path.read_bytes()
    with pytest.raises(SignoffError, match="q1"):
        signoff(path, tmp_path / "signoff.json", "Ada")
    assert path.read_bytes() == before
    result = CliRunner().invoke(app, ["signoff", "--plan-path", str(path), "--signed-by", "Ada"])
    assert result.exit_code == 1
    assert "q1" in result.output
    assert not (tmp_path / "signoff.json").exists()


def test_answered_signoff_hash_and_cli_name(tmp_path):
    """Save the typed reviewer's name and the hash of the final plan."""
    path = _plan(tmp_path, "Yes")
    result = CliRunner().invoke(app, ["signoff", "--plan-path", str(path)], input="Ada\n")
    assert result.exit_code == 0, result.output
    approval = json.loads((tmp_path / "signoff.json").read_text(encoding="utf-8"))
    assert approval["plan_hash"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert approval["signed_by"] == "Ada"
    assert approval["signed_at"]
    assert json.loads(path.read_bytes())["signed_off"] is True
    require_signoff(path, tmp_path / "signoff.json")
    assert CliRunner().invoke(app, ["run", "--plan-path", str(path)]).exit_code == 0


def test_run_guard_missing_and_changed_approval(tmp_path):
    """Refuse missing or stale sign-off before a run can write."""
    path = _plan(tmp_path, "Yes")
    approval_path = tmp_path / "signoff.json"
    with pytest.raises(SignoffError, match="missing"):
        require_signoff(path, approval_path)
    runner = CliRunner()
    assert runner.invoke(app, ["run", "--plan-path", str(path)]).exit_code == 1
    signoff(path, approval_path, "Ada")
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(SignoffError, match="does not match"):
        require_signoff(path, approval_path)
    assert runner.invoke(app, ["run", "--plan-path", str(path)]).exit_code == 1


def test_dry_run_does_not_need_signoff(tmp_path):
    """Allow the preview entry point to read an unsigned plan."""
    path = _plan(tmp_path)
    result = CliRunner().invoke(app, ["dry-run", "--plan-path", str(path)])
    assert result.exit_code == 0, result.output
    assert not (tmp_path / "signoff.json").exists()


def test_empty_reviewer_is_refused(tmp_path):
    """Require a human name before saving approval."""
    path = _plan(tmp_path, "Yes")
    with pytest.raises(SignoffError, match="signed_by"):
        signoff(path, tmp_path / "signoff.json", " ")
