"""Run the same target checks through memory and stdio."""

import asyncio
import sys

import pytest

from migration_agent.fakes import FakeTarget
from migration_agent.settings import Settings
from migration_agent.target import McpTarget, TargetError


@pytest.mark.parametrize("kind", ["fake", "mcp"])
def test_target_contract(kind, tmp_path):
    """Keep reads, writes, errors and links equal on both targets."""
    async def check():
        target = FakeTarget() if kind == "fake" else McpTarget(Settings(db_path=tmp_path / "target.sqlite"))
        async with target:
            await target.create_database({"name": "Projects", "properties": []})
            assert await target.upsert_page("Projects", "board", {}) == "created"
            await target.create_database({"name": "Tasks", "properties": [
                {"name": "Title", "type": "title", "required": True},
                {"name": "Owner", "type": "person"},
                {"name": "Project", "type": "relation", "relation_database": "Projects"},
            ]})
            assert len(await target.list_databases()) == 2
            assert await target.upsert_person("Tasks", "person", "Ada", "ada@example.test") == "created"
            assert await target.upsert_person("Tasks", "person", "Bea", "bea@example.test") == "updated"
            values = {"Title": "Kite", "Owner": ["person"]}
            for status in ("created", "updated"):
                assert await target.upsert_page("Tasks", "card", values, {"Project": ["board"]}) == status
            assert await target.count_pages("Tasks") == 1
            page = {"external_id": "card", "values": values, "relations": {"Project": ["board"]}}
            assert await target.get_page("Tasks", "card") == page
            assert await target.list_pages("Tasks", limit=1) == [page]
            assert await target.list_pages("Tasks", offset=1) == []
            assert await target.get_page("Tasks", "absent") is None
            for bad_values, relations, message in [({}, None, "Title"), ({"Title": 7}, None, "Title.*title"),
                    (values, {"Project": ["missing"]}, "missing")]:
                with pytest.raises(TargetError, match=message):
                    await target.upsert_page("Tasks", "card", bad_values, relations)
                assert await target.get_page("Tasks", "card") == page
    asyncio.run(check())


@pytest.mark.parametrize("command", ["", "no-such-migration-server"])
def test_missing_command_names_setting(command):
    """Name the setting that must be fixed before starting."""
    with pytest.raises(TargetError, match="target_server"):
        McpTarget(Settings(target_server=command))


def test_default_command_uses_this_python(tmp_path):
    """Use the active environment rather than a different Python."""
    target = McpTarget(Settings(db_path=tmp_path / "target.sqlite"))
    assert target.transport.command == sys.executable
    assert target.transport.args == ["-m", "migration_agent.target_server"]
