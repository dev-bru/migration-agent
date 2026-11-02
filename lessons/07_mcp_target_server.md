# What you will learn: follow a target write through Python MCP

The target mimics a small workspace so we can learn the migration contract
without accounts or a hosted service. Python moves the data. The model never
receives a target client and cannot call a write tool.

1. **Start the process.** `src/migration_agent/target_server/__main__.py:15`
   reads the configured database path, creates the store and starts FastMCP over
   stdio. `src/migration_agent/target.py:63` starts it with `sys.executable`, so
   client and child use the same Python environment on Windows. The client sets
   `MIGRATION_AGENT_DB_PATH`; no server address or API key is needed.
2. **Build the tool surface.** `src/migration_agent/target_server/server.py:29`
   registers seven typed tools: create_database, list_databases, upsert_person,
   upsert_page, get_page, list_pages and count_pages. FastMCP builds their input
   schemas. The local wrapper turns store errors into ToolError, so the client
   gets an error result rather than losing the server process.
3. **Create a schema.** `src/migration_agent/target_server/store.py:80`
   checks property names, property types and relation destinations before writing
   databases and properties. Create Projects before Tasks, then Subtasks and
   Comments, because a relation must name an existing database.
4. **Write by source ID.** `src/migration_agent/target_server/store.py:137`
   upserts people. `src/migration_agent/target_server/store.py:189` checks page
   values and relation IDs before committing. Tables hold schemas, pages,
   page_values and people. The pair (database, external_id) is unique: a replay
   updates the old record. An identical replay keeps stored values unchanged.
5. **Read and verify.** `src/migration_agent/target_server/store.py:234`
   reconstructs one page; list_pages paginates and count_pages counts records.
   `src/migration_agent/target.py:28` gives the same interface to the fake and
   MCP implementations. Tool errors become TargetError at the client boundary.
6. **Keep the safety gates in the caller.** `src/migration_agent/signoff.py:41`
   checks the exact reviewed plan; `src/migration_agent/migrate.py:29` orders
   dependencies and saves progress. The store guarantees safe individual writes,
   while the runner owns retries and batches.

Run from the project root:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_target_store.py tests/test_target_server.py tests/test_target_contract.py --basetemp=.pytest-tmp-server-lesson
```

Expected: `31 passed`. This includes an in-memory FastMCP client, matching fake
and stdio target contracts, and a real child-process smoke test. It needs no
model or remote network. Starting the module alone waits for MCP messages;
it is not an interactive terminal program.

## Quiz

- Why send external IDs in relations? The server can resolve stable source IDs after replay.
- Where does an unknown relation fail? In the store, before page values are changed.
- Who can approve the real run? The human; a model reply cannot create sign-off.
