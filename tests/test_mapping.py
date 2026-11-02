"""Check model proposals with made-up data and scripted replies."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from migration_agent.fakes import FakeModel
from migration_agent.mapping import MappingPlan, PlanError, plan, read_plan
from migration_agent.source import read_export
from migration_agent.cli import app
from typer.testing import CliRunner

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/acme_board.json"
SCHEMA = [{"name": "Tasks", "properties": [{"name": "Title", "type": "title", "required": True}]}]
PROPOSAL = {"version": 1, "entities": [{"source": "card", "target_database": "Tasks", "fields": [
    {"source_field": "name", "target_property": "Title", "type": "title", "confidence": 0.9, "reason": "Task name"}
]}], "questions": [], "signed_off": False}


def test_valid_reply_writes_plan(tmp_path):
    """Keep a checked plan and the actual export hash."""
    export = read_export(FIXTURE)
    data = dict(PROPOSAL, source_hash="model-cannot-set-this")
    fake = FakeModel([{"text": json.dumps(data)}])
    path = tmp_path / "runs" / "plan.json"
    proposal = plan(export, SCHEMA, fake, path)
    assert MappingPlan.model_validate_json(path.read_bytes()) == proposal == read_plan(path)
    assert proposal.source_hash == export.source_hash
    assert proposal.signed_off is False
    assert len(fake.requests) == 1
    assert fake.requests[0]["response_format"] == {"type": "json_object"}


def test_plan_cli_with_script(tmp_path):
    """Use the selected settings and script from the command line."""
    script = tmp_path / "script.json"
    script.write_text(json.dumps([{"text": json.dumps(PROPOSAL)}]), encoding="utf-8")
    schema = tmp_path / "schema.json"
    schema.write_text(json.dumps(SCHEMA), encoding="utf-8")
    config = tmp_path / "settings.toml"
    config.write_text(f"source = '{FIXTURE.as_posix()}'\nruns_dir = '{tmp_path.as_posix()}'\n", encoding="utf-8")
    result = CliRunner().invoke(app, ["plan", "--settings", str(config), "--script", str(script), "--schema", str(schema)])
    assert result.exit_code == 0, result.output
    assert read_plan(tmp_path / "plan.json").source_hash == read_export(FIXTURE).source_hash


def test_bad_source_field_repairs_once(tmp_path):
    """Send the field error back and accept a corrected proposal."""
    bad = deepcopy(PROPOSAL)
    bad["entities"][0]["fields"][0]["source_field"] = "invented"
    fake = FakeModel([{"text": json.dumps(bad)}, {"text": json.dumps(PROPOSAL)}])
    plan(read_export(FIXTURE), SCHEMA, fake, tmp_path / "plan.json")
    assert len(fake.requests) == 2
    assert "unknown source field invented" in fake.requests[1]["messages"][-1]["content"]


@pytest.mark.parametrize("problem", ["source", "target", "required", "confidence", "type", "json", "approval"])
def test_two_bad_replies_leave_no_plan(tmp_path, problem):
    """Refuse invalid proposals after exactly one repair."""
    bad = deepcopy(PROPOSAL)
    field = bad["entities"][0]["fields"][0]
    if problem == "source":
        field["source_field"] = "invented"
    elif problem == "target":
        field["target_property"] = "invented"
    elif problem == "required":
        bad["entities"][0]["fields"] = []
    elif problem == "confidence":
        field["confidence"] = 1.5
    elif problem == "type":
        field["type"] = "number"
    elif problem == "approval":
        bad["signed_off"] = True
    text = "{" if problem == "json" else json.dumps(bad)
    fake = FakeModel([{"text": text}, {"text": text}])
    path = tmp_path / "plan.json"
    with pytest.raises(PlanError, match="after one repair"):
        plan(read_export(FIXTURE), SCHEMA, fake, path)
    assert len(fake.requests) == 2
    assert not path.exists()


def test_low_confidence_adds_open_question(tmp_path):
    """Ask a human to review each field below the confidence threshold."""
    data = deepcopy(PROPOSAL)
    data["entities"][0]["fields"][0]["confidence"] = 0.5
    proposal = plan(read_export(FIXTURE), SCHEMA, FakeModel([{"text": json.dumps(data)}]), tmp_path / "plan.json")
    assert len(proposal.questions) == 1
    assert proposal.questions[0].answer is None
    assert "card.name" in proposal.questions[0].text


def test_new_property_must_be_marked_create(tmp_path):
    """Allow a planned property that does not exist yet."""
    data = deepcopy(PROPOSAL)
    data["entities"][0]["fields"][0]["create"] = True
    proposal = plan(read_export(FIXTURE), [], FakeModel([{"text": json.dumps(data)}]), tmp_path / "plan.json")
    assert proposal.entities[0].fields[0].create


def test_prompt_caps_samples_without_nested_card_text(tmp_path):
    """Keep the prompt size fixed when more cards are added."""
    export = read_export(FIXTURE)
    template = export.boards[0].cards[0]
    export.boards[0].cards = [template.model_copy(update={"id": f"card-{i}", "name": f"name-{i}",
        "description": f"private-card-text-{i}", "comments": [], "checklists": [], "attachments": []}) for i in range(100)]
    fake = FakeModel([{"text": json.dumps(PROPOSAL)}])
    plan(export, SCHEMA, fake, tmp_path / "plan.json")
    request = fake.requests[0]["messages"][1]["content"]
    summary = json.loads(request)["source"]
    for entity in summary.values():
        assert all(len(field["samples"]) <= 3 for field in entity["fields"].values())
    assert summary["card"]["count"] == 100
    assert "private-card-text-3" not in request
    assert len(request) < 15000
