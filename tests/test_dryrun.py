"""Check that preview output needs no approval and writes nothing."""

import asyncio

import pytest

from migration_agent.dryrun import dry_run
from migration_agent.fakes import FakeTarget
from migration_agent.mapping import PlanError
from test_transform import example


def test_dry_run_reads_only_and_prints_preview(capsys):
    """Show counts, empty fields, warnings and the first mapped card."""
    async def check():
        export, plan, schema = example()
        async with FakeTarget() as target:
            for spec in schema:
                await target.create_database(spec)
            target.write_calls = 0
            result = await dry_run(export, plan, target)
            assert target.write_calls == 0
            assert result["entities"]["card"]["create"] == 2
            assert "Due" in result["entities"]["card"]["empty_fields"]
    asyncio.run(check())
    output = capsys.readouterr().out
    assert "unknown member member-missing" in output
    assert '"Title": "Choose pretend seeds"' in output


def test_missing_required_source_fails():
    """Name a required property that the plan forgot to map."""
    async def check():
        export, plan, schema = example()
        schema[1]["properties"].append(dict(name="Required extra", type="text", required=True))
        async with FakeTarget() as target:
            for spec in schema:
                await target.create_database(spec)
            with pytest.raises(PlanError, match="Required extra"):
                await dry_run(export, plan, target)
    asyncio.run(check())
