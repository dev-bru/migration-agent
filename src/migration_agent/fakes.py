"""Provide local substitutes for tests.

Keep target data in memory and model replies in a script.
Never start a server or call a model from these fakes.
"""

from copy import deepcopy
import json
from pathlib import Path
import sqlite3

from migration_agent.model import Reply
from migration_agent.target import Target, TargetError
from migration_agent.target_server.store import Store, StoreError


class ScriptExhausted(RuntimeError):
    """Report that the fake has no replies left."""


class FakeModel:
    """Replay text replies without a model or network."""

    def __init__(self, script: list | str | Path):
        """Read a JSON script or copy a list of text replies."""
        if isinstance(script, (str, Path)):
            try:
                script = json.loads(Path(script).read_text(encoding="utf-8"))
            except (OSError, UnicodeError, ValueError) as error:
                raise ValueError("cannot read fake model script") from error
        if not isinstance(script, list):
            raise ValueError("fake model script must be a list")
        for index, reply in enumerate(script):
            if not isinstance(reply, dict) or set(reply) != {"text"} or not isinstance(reply["text"], str):
                raise ValueError(f"reply {index}: expected an object with text")
        self.script = deepcopy(script)
        self.requests = []
        self._index = 0

    def chat(self, messages, response_format=None) -> Reply:
        """Record a request and return the next scripted reply."""
        self.requests.append(deepcopy(dict(messages=messages, response_format=response_format)))
        if self._index == len(self.script):
            raise ScriptExhausted("script has no replies left")
        reply = Reply(self.script[self._index]["text"], {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
        self._index += 1
        return reply


class FakeTarget(Target):
    """Use the real value checks with an in-memory workspace."""

    def __init__(self):
        """Open an empty workspace and reset its write counter."""
        self.store = Store()
        self.write_calls = 0

    async def __aenter__(self):
        """Return this workspace for a group of calls."""
        return self

    async def __aexit__(self, *args):
        """Close the workspace after use."""
        self.close()

    def close(self):
        """Release the in-memory database."""
        self.store.close()

    async def _call(self, name, arguments):
        if name in {"create_database", "upsert_person", "upsert_page"}:
            self.write_calls += 1
        try:
            return getattr(self.store, name)(**arguments)
        except (StoreError, sqlite3.Error, OSError) as error:
            raise TargetError(str(error)) from error
