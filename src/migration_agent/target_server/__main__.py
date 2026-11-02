"""Run the target workspace as a local MCP child process.

Read the same settings as the migration agent.
Use standard input and output for MCP messages.
"""

from migration_agent.settings import load_settings
from migration_agent.target_server.server import create_server
from migration_agent.target_server.store import Store


def main() -> None:
    """Open the workspace, serve MCP calls, and close the file on exit."""
    store = Store(load_settings().db_path)
    try:
        create_server(store).run(transport="stdio", show_banner=False)
    finally:
        store.close()


if __name__ == "__main__":
    main()
