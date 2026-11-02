# Call the target through MCP.
# Keep the same small interface for real and fake workspaces.
# Turn server failures into errors the agent can explain.
"""Call the target through MCP.

Keep the same small interface for real and fake workspaces.
Turn server failures into errors the agent can explain.
"""

import json
import os
from pathlib import Path
import shlex
import shutil
import sys
from typing import Protocol

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from migration_agent.settings import Settings


class TargetError(RuntimeError):
    """Explain why a target call failed."""


class Target(Protocol):
    """Define the calls shared by real and fake targets."""

    async def _call(self, name, arguments):
        raise NotImplementedError

    async def create_database(self, spec: dict) -> dict:
        """Create a database with the given property rules."""
        return await self._call("create_database", {"spec": spec})

    async def list_databases(self) -> list[dict]:
        """Read the available database schemas."""
        return await self._call("list_databases", {})

    async def upsert_person(self, db: str, external_id: str, name: str, email: str) -> str:
        """Save a person by source ID."""
        return await self._call("upsert_person", dict(db=db, external_id=external_id, name=name, email=email))

    async def upsert_page(self, db: str, external_id: str, values: dict, relations: dict | None = None) -> str:
        """Save page values and links by source ID."""
        return await self._call("upsert_page", dict(db=db, external_id=external_id, values=values, relations=relations))

    async def count_pages(self, db: str) -> int:
        """Count pages in a database."""
        return await self._call("count_pages", {"db": db})

    async def list_pages(self, db: str, offset: int = 0, limit: int = 50) -> list[dict]:
        """Read a slice of pages in creation order."""
        return await self._call("list_pages", dict(db=db, offset=offset, limit=limit))

    async def get_page(self, db: str, external_id: str) -> dict | None:
        """Read one page, or return None if it is missing."""
        return await self._call("get_page", dict(db=db, external_id=external_id))


class McpTarget(Target):
    """Keep a stdio server open for a group of target calls."""

    def __init__(self, settings: Settings):
        """Prepare the configured child process without starting it."""
        try:
            parts = [part.strip('"') for part in shlex.split(settings.target_server, posix=False)]
        except ValueError:
            raise TargetError("target_server: invalid command") from None
        if not parts:
            raise TargetError("target_server: command is missing")
        if parts[0] in {"python", "python.exe"}:
            parts[0] = sys.executable
        if shutil.which(parts[0]) is None:
            raise TargetError("target_server: command was not found")
        env = dict(os.environ)
        env["MIGRATION_AGENT_DB_PATH"] = str(settings.db_path.resolve())
        env["FASTMCP_CHECK_FOR_UPDATES"] = "off"
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(Path(__file__).resolve().parents[1]), env.get("PYTHONPATH")]))
        self.transport = StdioTransport(command=parts[0], args=parts[1:], env=env, keep_alive=False)
        self.client = Client(self.transport, mode="legacy", timeout=20)

    async def __aenter__(self):
        """Start the server and open its MCP session."""
        try:
            await self.client.__aenter__()
        except Exception as error:
            raise TargetError("target_server: could not start the MCP server") from error
        return self

    async def __aexit__(self, *args):
        """Close the MCP session and its child process."""
        return await self.client.__aexit__(*args)

    async def _call(self, name, arguments):
        try:
            result = await self.client.call_tool(name, arguments, raise_on_error=False)
        except Exception as error:
            raise TargetError(f"target_server: {error}") from error
        if result.is_error:
            raise TargetError("; ".join(part.text for part in result.content if hasattr(part, "text")))
        if result.structured_content is not None:
            return result.structured_content.get("result", result.structured_content)
        return json.loads(result.content[0].text)
