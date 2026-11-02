"""Expose the SQLite workspace as seven MCP tools.

Keep data checks in the store so each tool follows the same rules.
Return useful tool errors instead of stopping the server.
"""

import os
import sqlite3
from typing import Any

os.environ["FASTMCP_CHECK_FOR_UPDATES"] = "off"

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from migration_agent.target_server.store import Store, StoreError


def _call(function, *args):
    try:
        return function(*args)
    except (StoreError, sqlite3.Error, OSError) as error:
        raise ToolError(str(error)) from None


def create_server(store: Store) -> FastMCP:
    """Build the tools for one open workspace; the caller closes the store."""
    mcp = FastMCP("migration-agent-target")

    # Each tool runs without an await so SQLite stays on one thread and writes finish in order.
    @mcp.tool
    async def create_database(spec: dict[str, Any]) -> dict:
        """Create a database from name and properties (name, type, required, relation_database)."""
        return _call(store.create_database, spec)

    @mcp.tool
    async def list_databases() -> list[dict]:
        """Read all database names and their property rules."""
        return _call(store.list_databases)

    @mcp.tool
    async def upsert_person(db: str, external_id: str, name: str, email: str) -> str:
        """Save a person by source ID in db; return created or updated."""
        return _call(store.upsert_person, db, external_id, name, email)

    @mcp.tool
    async def upsert_page(
        db: str, external_id: str, values: dict[str, Any], relations: dict[str, list[str] | None] | None = None,
    ) -> str:
        """Replace page values; relations maps property names to lists of linked source IDs."""
        return _call(store.upsert_page, db, external_id, values, relations)

    @mcp.tool
    async def get_page(db: str, external_id: str) -> dict | None:
        """Read a page by source ID, or return null if no page has that ID."""
        return _call(store.get_page, db, external_id)

    @mcp.tool
    async def list_pages(db: str, offset: int = 0, limit: int = 50) -> list[dict]:
        """Read pages in creation order with offset >= 0 and limit >= 1."""
        return _call(store.list_pages, db, offset, limit)

    @mcp.tool
    async def count_pages(db: str) -> int:
        """Count all pages in the named database."""
        return _call(store.count_pages, db)

    return mcp
