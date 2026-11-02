"""Exercise batches, approval and crash recovery without a server."""

import asyncio
import json

import pytest

from migration_agent import migrate as runner
from migration_agent.fakes import FakeTarget
from migration_agent.mapping import MappingPlan
from migration_agent.signoff import SignoffError, signoff
from migration_agent.target import TargetError
from test_transform import example


def batch_example(tmp_path):
    """Make one hundred and twenty unique tasks and an approved plan."""
    export, proposal, schema = example()
    template = export.boards[0].cards[0]
    export.boards[0].cards = [template.model_copy(update={"id": f"card-{i}"}) for i in range(120)]
    proposal = MappingPlan(source_hash=export.source_hash, entities=[dict(source="card", target_database="Tasks",
        fields=[dict(source_field="name", target_property="Title", type="title", confidence=1.0, reason="Name")])])
    path = tmp_path / "plan.json"
    path.write_text(proposal.model_dump_json(), encoding="utf-8", newline="\n")
    signoff(path, tmp_path / "signoff.json", "Example Reviewer")
    return export, path, dict(name="Tasks", properties=[dict(name="Title", type="title", required=True)])


def test_three_batches_and_finished_resume(tmp_path, monkeypatch):
    """Save three complete batches and perform no writes on a finished rerun."""
    async def check():
        export, path, spec = batch_example(tmp_path)
        checkpoint = tmp_path / "checkpoint.json"
        saved = []
        original = runner.write_checkpoint

        def save(path, data):
            original(path, data)
            saved.append(json.loads(path.read_bytes()))

        monkeypatch.setattr(runner, "write_checkpoint", save)
        async with FakeTarget() as target:
            await target.create_database(spec)
            result = await runner.migrate(export, path, target, checkpoint)
            assert [p["entities"]["card"]["done_batches"] for p in saved] == [1, 2, 3]
            assert result["entities"]["card"]["created"] == 120
            assert await target.count_pages("Tasks") == 120
            before = target.write_calls
            assert await runner.migrate(export, path, target, checkpoint) == result
            assert target.write_calls == before
    asyncio.run(check())


def test_failed_batch_retries_then_resumes(tmp_path, monkeypatch):
    """Keep batch one intact when batch two fails on every retry."""
    async def check():
        export, path, spec = batch_example(tmp_path)
        checkpoint = tmp_path / "checkpoint.json"
        async with FakeTarget() as target:
            await target.create_database(spec)
            original = target.upsert_page
            failures = []

            async def fail(db, external_id, values, relations=None):
                if external_id == "card-50":
                    failures.append(external_id)
                    raise TargetError("forced outage")
                return await original(db, external_id, values, relations)

            monkeypatch.setattr(target, "upsert_page", fail)
            with pytest.raises(runner.MigrationError, match="batch 2"):
                await runner.migrate(export, path, target, checkpoint)
            assert len(failures) == 4
            assert json.loads(checkpoint.read_bytes())["entities"]["card"]["done_batches"] == 1
            monkeypatch.setattr(target, "upsert_page", original)
            await runner.migrate(export, path, target, checkpoint)
            assert await target.count_pages("Tasks") == 120
    asyncio.run(check())


def test_crash_before_checkpoint_replays_without_duplicates(tmp_path, monkeypatch):
    """Replay a written batch when its checkpoint never reached disk."""
    async def check():
        export, path, spec = batch_example(tmp_path)
        checkpoint = tmp_path / "checkpoint.json"
        original = runner.write_checkpoint

        def crash(path, data):
            if data["entities"]["card"]["done_batches"] == 2:
                raise OSError("forced crash")
            original(path, data)

        async with FakeTarget() as target:
            await target.create_database(spec)
            monkeypatch.setattr(runner, "write_checkpoint", crash)
            with pytest.raises(OSError, match="forced crash"):
                await runner.migrate(export, path, target, checkpoint)
            assert await target.count_pages("Tasks") == 100
            assert json.loads(checkpoint.read_bytes())["entities"]["card"]["done_batches"] == 1
            monkeypatch.setattr(runner, "write_checkpoint", original)
            await runner.migrate(export, path, target, checkpoint)
            assert await target.count_pages("Tasks") == 120
    asyncio.run(check())


def test_guards_before_writes(tmp_path):
    """Refuse absent approval, a different plan and a changed batch size."""
    async def check():
        export, path, spec = batch_example(tmp_path)
        checkpoint = tmp_path / "checkpoint.json"
        async with FakeTarget() as target:
            await target.create_database(spec)
            await runner.migrate(export, path, target, checkpoint)
            before = target.write_calls
            with pytest.raises(runner.MigrationError, match="batch_size"):
                await runner.migrate(export, path, target, checkpoint, batch_size=10)
            data = json.loads(checkpoint.read_bytes())
            data["plan_hash"] = "other plan"
            runner.write_checkpoint(checkpoint, data)
            with pytest.raises(runner.MigrationError, match="plan hash"):
                await runner.migrate(export, path, target, checkpoint)
            path.with_name("signoff.json").unlink()
            with pytest.raises(SignoffError, match="missing"):
                await runner.migrate(export, path, target, checkpoint)
            assert target.write_calls == before
    asyncio.run(check())


def test_checkpoint_replace_keeps_old_json_on_failure(tmp_path, monkeypatch):
    """Leave the previous file valid if the final rename fails."""
    path = tmp_path / "checkpoint.json"
    runner.write_checkpoint(path, {"old": True})

    def fail(*args):
        raise OSError("rename blocked")

    monkeypatch.setattr(type(path), "replace", fail)
    with pytest.raises(OSError):
        runner.write_checkpoint(path, {"new": True})
    assert json.loads(path.read_bytes()) == {"old": True}
