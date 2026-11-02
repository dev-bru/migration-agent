"""Check pure mappings with made-up boards and explicit property names."""

from pathlib import Path

import pytest

from migration_agent.mapping import MappingPlan, PlanError
from migration_agent.source import read_export
from migration_agent.transform import transform


def example():
    """Return a board, its mapping and the target schemas."""
    export = read_export(Path(__file__).resolve().parents[1] / "fixtures/acme_board.json")
    definitions = [
        ("board", "Projects", [("name", "Name", "title")]),
        ("card", "Tasks", [("name", "Title", "title"), ("id", "Project", "relation"),
                            ("list_id", "Status", "select"), ("label_ids", "Tags", "multi_select"),
                            ("member_ids", "Owners", "person"), ("due", "Due", "date"),
                            ("attachments", "Links", "text")]),
        ("checklist_item", "Subtasks", [("name", "Title", "title"), ("done", "Done", "checkbox"),
                                        ("id", "Task", "relation")]),
        ("comment", "Comments", [("text", "Text", "text"), ("member_id", "Author", "person"),
                                 ("created_at", "Created", "date"), ("id", "Task", "relation")]),
    ]
    entities, schema = [], []
    for source, db, fields in definitions:
        entities.append(dict(source=source, target_database=db, fields=[dict(
            source_field=s, target_property=t, type=k, confidence=1.0, reason="Example mapping")
            for s, t, k in fields]))
        schema.append(dict(name=db, properties=[dict(name=t, type=k, **(
            {"relation_database": "Projects" if t == "Project" else "Tasks"} if k == "relation" else {}),
            required=k == "title") for _, t, k in fields]))
    return export, MappingPlan(source_hash=export.source_hash, entities=entities), schema


def test_transform_keeps_values_parents_and_input():
    """Resolve names, people and parent links without changing the input."""
    export, plan, schema = example()
    before = export.model_dump_json(), plan.model_dump_json()
    result = transform(export, plan, schema)
    task = result["card"][0]
    assert task["values"]["Title"] == export.boards[0].cards[0].name
    assert task["values"]["Status"] == "To do"
    assert task["values"]["Tags"] == ["Garden"]
    assert task["values"]["Due"] is None
    assert len(task["values"]["Links"].splitlines()) == 2
    assert result["card"][1]["values"]["Owners"] == []
    assert result["card"][1]["values"]["Links"] == ""
    assert task["relations"] == {"Project": ["board-acme"]}
    assert result["checklist_item"][0]["relations"] == {"Task": ["card-seeds"]}
    assert result["checklist_item"][1]["values"]["Done"] is False
    assert result == transform(export, plan, schema)
    assert before == (export.model_dump_json(), plan.model_dump_json())


def test_transform_refuses_wrong_source_and_duplicate_ids():
    """Stop changed sources or repeated IDs before target writes."""
    export, plan, schema = example()
    plan.source_hash = "different"
    with pytest.raises(PlanError, match="source_hash"):
        transform(export, plan, schema)
    plan.source_hash = export.source_hash
    export.boards[0].cards.append(export.boards[0].cards[0])
    with pytest.raises(PlanError, match="duplicate"):
        transform(export, plan, schema)
