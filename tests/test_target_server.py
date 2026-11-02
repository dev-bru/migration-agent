"""Test the seven target tools with FastMCP clients.

Use made-up records in isolated SQLite workspaces.
Check both in-memory calls and a real stdio child process.
"""

import asyncio
import json
import os
from pathlib import Path
import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
import pytest

from migration_agent.target_server.server import create_server
from migration_agent.target_server.store import Store


TOOLS = {"create_database", "list_databases", "upsert_person", "upsert_page", "get_page", "list_pages", "count_pages"}
TASKS = {"name": "Tasks", "properties": [
    {"name": "Title", "type": "title", "required": True},
    {"name": "Done", "type": "checkbox"},
    {"name": "Estimate", "type": "number"},
]}


def _data(result):
    assert not result.is_error, result.content
    return result.data


def _error(result):
    assert result.is_error
    return " ".join(item.text for item in result.content if hasattr(item, "text"))


@pytest.fixture
def workspace():
    """Give each test its own server and SQLite connection."""
    store = Store()
    yield store, create_server(store)
    store.close()


def test_tool_names_and_typed_schemas(workspace):
    """Expose exactly seven tools with schemas built from typed parameters."""
    async def run():
        async with Client(workspace[1], mode="legacy") as client:
            tools = await client.list_tools()
            assert {tool.name for tool in tools} == TOOLS
            for tool in tools:
                schema = tool.input_schema
                assert schema["type"] == "object"
                assert all("type" in field or "anyOf" in field for field in schema.get("properties", {}).values())
    asyncio.run(run())


def test_upserts_and_unchanged_value_bytes(workspace):
    """Retry writes without adding rows or rewriting identical page values."""
    async def run():
        store = workspace[0]
        async with Client(workspace[1], mode="legacy") as client:
            assert _data(await client.call_tool("create_database", {"spec": TASKS}))["name"] == "Tasks"
            args = {"db": "Tasks", "external_id": "card-1", "values": {"Title": "Ship a kite", "Done": False, "Estimate": 0}}
            assert _data(await client.call_tool("upsert_page", args)) == "created"
            snapshot = [tuple(row) for row in store.connection.execute("SELECT rowid, * FROM page_values ORDER BY property_id")]
            changes = store.connection.total_changes
            assert _data(await client.call_tool("upsert_page", args)) == "updated"
            assert [tuple(row) for row in store.connection.execute("SELECT rowid, * FROM page_values ORDER BY property_id")] == snapshot
            assert store.connection.total_changes == changes
            assert _data(await client.call_tool("count_pages", {"db": "Tasks"})) == 1
            args["values"] = {"Title": "Ship two kites", "Done": True}
            assert _data(await client.call_tool("upsert_page", args)) == "updated"
            page = _data(await client.call_tool("get_page", {"db": "Tasks", "external_id": "card-1"}))
            assert page == {"external_id": "card-1", "values": args["values"], "relations": {}}
            assert _data(await client.call_tool("list_pages", {"db": "Tasks"})) == [page]
            assert _data(await client.call_tool("list_pages", {"db": "Tasks", "offset": 1})) == []
            person = {"db": "Tasks", "external_id": "member-1", "name": "Ada", "email": "ada@example.test"}
            assert _data(await client.call_tool("upsert_person", person)) == "created"
            person["name"] = "Bea"
            assert _data(await client.call_tool("upsert_person", person)) == "updated"
            assert store.connection.execute("SELECT COUNT(*) FROM people").fetchone()[0] == 1
            assert store.connection.execute("SELECT name FROM people").fetchone()[0] == "Bea"
            assert _data(await client.call_tool("get_page", {"db": "Tasks", "external_id": "missing"})) is None
            assert _data(await client.call_tool("list_databases"))[0]["name"] == "Tasks"
    asyncio.run(run())


@pytest.mark.parametrize("values,expected", [
    ({}, "Title"), ({"Title": 5}, "Title.*title"),
    ({"Title": "Kite", "Done": "yes"}, "Done.*checkbox"),
    ({"Title": "Kite", "Estimate": True}, "Estimate.*number"),
    ({"Title": "Kite", "Extra": "bad"}, "Extra.*valid properties"),
])
def test_bad_page_returns_error_without_changing_data(workspace, values, expected):
    """Keep a saved page intact when an update has invalid values."""
    import re

    async def run():
        async with Client(workspace[1], mode="legacy") as client:
            await client.call_tool("create_database", {"spec": TASKS})
            args = {"db": "Tasks", "external_id": "card-1", "values": {"Title": "Original"}}
            await client.call_tool("upsert_page", args)
            args["values"] = values
            result = await client.call_tool("upsert_page", args, raise_on_error=False)
            assert re.search(expected, _error(result))
            assert _data(await client.call_tool("count_pages", {"db": "Tasks"})) == 1
            assert _data(await client.call_tool("get_page", {"db": "Tasks", "external_id": "card-1"}))["values"] == {"Title": "Original"}
    asyncio.run(run())


def test_relations_resolve_external_ids_and_reject_unknown_ids(workspace):
    """Resolve links to target pages and return source IDs when reading them."""
    async def run():
        async with Client(workspace[1], mode="legacy") as client:
            await client.call_tool("create_database", {"spec": {"name": "Projects", "properties": []}})
            await client.call_tool("upsert_page", {"db": "Projects", "external_id": "board-1", "values": {}})
            await client.call_tool("create_database", {"spec": {"name": "Tasks", "properties": [
                {"name": "Project", "type": "relation", "required": True, "relation_database": "Projects"},
            ]}})
            args = {"db": "Tasks", "external_id": "card-1", "values": {}, "relations": {"Project": ["missing-board"]}}
            assert "missing-board" in _error(await client.call_tool("upsert_page", args, raise_on_error=False))
            assert _data(await client.call_tool("count_pages", {"db": "Tasks"})) == 0
            args["relations"]["Project"] = ["board-1"]
            assert _data(await client.call_tool("upsert_page", args)) == "created"
            page = _data(await client.call_tool("get_page", {"db": "Tasks", "external_id": "card-1"}))
            assert page["relations"] == {"Project": ["board-1"]}
            saved = workspace[0].connection.execute("SELECT value FROM page_values").fetchone()[0]
            assert json.loads(saved) == [workspace[0].connection.execute("SELECT id FROM pages WHERE db = 'Projects'").fetchone()[0]]
    asyncio.run(run())


def test_bad_database_and_tool_arguments_do_not_stop_server(workspace):
    """Return tool errors and keep answering later requests."""
    async def run():
        async with Client(workspace[1], mode="legacy") as client:
            result = await client.call_tool("count_pages", {"db": "Missing"}, raise_on_error=False)
            assert "Missing" in _error(result)
            result = await client.call_tool("count_pages", {}, raise_on_error=False)
            assert "db" in _error(result)
            result = await client.call_tool("create_database", {"spec": {"name": "Bad", "properties": [
                {"name": "Title", "type": "unknown"},
            ]}}, raise_on_error=False)
            assert "valid types" in _error(result)
            assert _data(await client.call_tool("list_databases")) == []
    asyncio.run(run())


def test_stdio_round_trip_with_current_python(tmp_path):
    """Start the module with this Python and count pages through stdio."""
    async def run():
        root = Path(__file__).resolve().parents[1]
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("MIGRATION_AGENT_") and key not in {"GEMINI_API_KEY", "GROQ_API_KEY", "NVIDIA_NIM_API_KEY"}}
        env.update({"MIGRATION_AGENT_DB_PATH": str(tmp_path / "target.sqlite"),
                    "PYTHONPATH": str(root / "src"), "FASTMCP_CHECK_FOR_UPDATES": "off"})
        transport = StdioTransport(command=sys.executable, args=["-m", "migration_agent.target_server"],
                                   env=env, cwd=str(tmp_path), keep_alive=False)
        async with Client(transport, mode="legacy", timeout=20) as client:
            await client.call_tool("create_database", {"spec": {"name": "Tasks", "properties": []}})
            assert _data(await client.call_tool("count_pages", {"db": "Tasks"})) == 0
    asyncio.run(run())
    store = Store(tmp_path / "target.sqlite")
    try:
        assert store.get_database("Tasks")["name"] == "Tasks"
    finally:
        store.close()
