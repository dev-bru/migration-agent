"""Keep the customer report complete and its numbers tied to saved facts."""

import json
import re

import pytest

from migration_agent.fakes import FakeModel
from migration_agent.report import report


@pytest.fixture
def evidence(tmp_path):
    """Save small made-up inputs, including a failed check and an answered question."""
    data = [dict(entities=[dict(source="card", target_database="Tasks", fields=[dict(
        source_field="name", target_property="Title", type="title", reason="Keep the name")])],
        questions=[dict(id="q-choice", text="Merge labels?", answer="Yes")]),
        dict(entities=dict(card=dict(created=2, updated=0))),
        dict(checks=[dict(name="content_sample", status="fail", detail="Changed Title",
                         ids=["card-seeds"])], sample_size=2, seed=0)]
    paths = [tmp_path / name for name in ("plan.json", "checkpoint.json", "validation.json")]
    for path, value in zip(paths, data):
        path.write_text(json.dumps(value), encoding="utf-8", newline="\n")
    return paths


def test_scripted_report_sections_and_facts(evidence, tmp_path):
    """Keep summary prose and all code-written facts in their expected sections."""
    model = FakeModel([dict(text="The workspace needs a review.")])
    path = tmp_path / "report.md"
    text = report(*evidence, path, model, warnings=["Unknown member was left empty"])
    assert text == path.read_text(encoding="utf-8")
    for heading in ("Summary", "What moved", "What changed", "What did not move", "Checks", "Next steps"):
        assert f"## {heading}\n" in text
    for fact in ("The workspace needs a review.", "created 2, updated 0", "card.name -> Tasks.Title",
                 "Answer: Yes", "Unknown member", "FAIL content_sample", "card-seeds"):
        assert fact in text
    assert len(model.requests) == 1
    assert set(re.findall(r"\d+(?:\.\d+)?", text)) <= set(re.findall(
        r"\d+(?:\.\d+)?", "".join(p.read_text(encoding="utf-8") for p in evidence)))


def test_no_llm_makes_no_call(evidence, tmp_path):
    """Write the full template even when no model reply exists."""
    model = FakeModel([])
    text = report(*evidence, tmp_path / "report.md", model, no_llm=True)
    assert not model.requests
    assert "## Next steps" in text and "FAIL" in text


@pytest.mark.parametrize("claim", ["Moved 99999 records.", "Moved 2.75 records.", "Moved card-invented."])
def test_unsupported_claim_uses_template(evidence, tmp_path, claim):
    """Drop an unsupported paragraph while keeping a separate safe paragraph."""
    text = report(*evidence, tmp_path / "report.md", FakeModel([dict(text=claim + "\n\nPlease review the checks.")]))
    assert claim not in text
    assert "The migration results are listed below." in text
    assert "Please review the checks." in text
