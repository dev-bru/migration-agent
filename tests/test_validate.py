"""Find missing records, changed values and broken links offline."""

import asyncio
import json

import pytest

from migration_agent.fakes import FakeTarget
from migration_agent.migrate import migrate
from migration_agent.signoff import signoff
from migration_agent.validate import validate
from test_transform import example


async def _migrated(tmp_path, target):
    export, plan, schema = example()
    for spec in schema:
        await target.create_database(spec)
    path = tmp_path / "plan.json"
    path.write_text(plan.model_dump_json(), encoding="utf-8", newline="\n")
    signoff(path, tmp_path / "signoff.json", "Example Reviewer")
    await migrate(export, path, target, tmp_path / "checkpoint.json", batch_size=2)
    return export, plan


def test_clean_migration_and_seeded_sample(tmp_path):
    """Pass all four checks and select the same records with the same seed."""
    async def check():
        async with FakeTarget() as target:
            export, plan = await _migrated(tmp_path, target)
            before = target.write_calls
            path = tmp_path / "validation.json"
            first = await validate(export, plan, target, path, sample_size=4, seed=42)
            second = await validate(export, plan, target, path, sample_size=4, seed=42)
            assert first == second == json.loads(path.read_bytes())
            assert len(first["checks"]) == 4
            assert all(c["status"] == "pass" for c in first["checks"])
            assert first["sample_size"] == len(first["sample"]) == 4
            assert target.write_calls == before
    asyncio.run(check())


@pytest.mark.parametrize("damage,check_name,field", [
    ("delete", "counts", "comment"),
    ("title", "content_sample", "Title"),
    ("relation", "relations", "Task"),
    ("required", "required_properties", "Title"),
])
def test_detects_damaged_target(tmp_path, damage, check_name, field):
    """Name the changed record and the failed check in the saved result."""
    async def check():
        async with FakeTarget() as target:
            export, plan = await _migrated(tmp_path, target)
            connection = target.store.connection
            db, external_id = ("Comments", "comment-one") if damage == "delete" else ("Subtasks", "item-mint")
            page_id = connection.execute("SELECT id FROM pages WHERE db=? AND external_id=?", (db, external_id)).fetchone()[0]
            if damage == "delete":
                connection.execute("DELETE FROM page_values WHERE page_id=?", (page_id,))
                connection.execute("DELETE FROM pages WHERE id=?", (page_id,))
            else:
                prop = "Task" if damage == "relation" else "Title"
                value = '[]' if damage == "relation" else ('null' if damage == "required" else '"Changed title"')
                connection.execute("UPDATE page_values SET value=? WHERE page_id=? AND property_id="
                                   "(SELECT id FROM properties WHERE db=? AND name=?)", (value, page_id, db, prop))
            connection.commit()
            result = await validate(export, plan, target, tmp_path / "validation.json", sample_size=100)
            failed = next(c for c in result["checks"] if c["name"] == check_name)
            assert failed["status"] == "fail"
            assert external_id in failed["ids"]
            assert field in failed["detail"]
            if damage == "delete":
                assert "difference -1" in failed["detail"]
    asyncio.run(check())


def test_paginates_all_target_pages(tmp_path):
    """Check more than one read page instead of stopping at fifty records."""
    from test_migrate import batch_example

    async def check():
        from migration_agent.mapping import read_plan
        export, path, spec = batch_example(tmp_path)
        async with FakeTarget() as target:
            await target.create_database(spec)
            await migrate(export, path, target, tmp_path / "checkpoint.json")
            result = await validate(export, read_plan(path), target, tmp_path / "validation.json", sample_size=120)
            assert result["sample_size"] == 120
            assert all(c["status"] == "pass" for c in result["checks"])
    asyncio.run(check())
