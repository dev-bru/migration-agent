# Migration Agent: architecture

Status: draft for the SPEC GATE (2026-11-02). REQUIREMENTS.md wins on any detail. Interactive diagram comes later
in `plan/`.

## Stack
| Part | Chosen | Rejected (why) |
|---|---|---|
| Agent language | Python 3.12 via uv | Node for the agent too (the owner knows Python; TS is practised on the server) |
| Server language | TypeScript on Node LTS | Python MCP server (misses the Node/TypeScript gap) |
| MCP server | Official MCP TypeScript SDK, stdio | Hand-written JSON-RPC (teaches less; easy to get wrong) |
| MCP client | Python `mcp` package | Calling SQLite directly from Python (skips the MCP lesson) |
| Store | SQLite via better-sqlite3 (UNVERIFIED on this Node/Windows) | Node built-in `node:sqlite` (still young; check at setup) ; Postgres (needs a service) |
| Schema validation | zod (SDK uses it) | Hand checks (the SDK expects zod) |
| TS tests | vitest | jest (more config for TypeScript) |
| Model API | LiteLLM (one API for every provider) | Raw provider SDKs (one per provider) |
| Models | Local Qwen on `llama-server`; free Gemini, Groq, NVIDIA NIM by env var | Paid APIs (cost), keys in files (leak risk) |
| Typed data | Pydantic | dataclasses plus hand checks (more code for plan validation) |
| CLI | Typer | argparse (more code for six commands) |
| Source data | JSON fixtures in Trello-like shape | Real Trello API (accounts, keys, network) |
| Tests | pytest + scripted fakes; vitest for the server | Live model in every test (slow, flaky) |

Versions are chosen at setup and logged in `docs/DEPENDENCIES.md`.

## Layout
```
migration-agent/
  pyproject.toml  uv.lock  migration-agent.example.toml  README.md
  src/migration_agent/
    settings.py      # REQ-002
    source.py        # REQ-003: typed models + read_export
    model.py         # REQ-008: chat() on LiteLLM
    fakes.py         # FakeModel, FakeTarget
    target.py        # REQ-007: McpTarget (+ shared Target protocol)
    mapping.py       # REQ-009: build prompt, parse and check the plan
    signoff.py       # REQ-010
    transform.py     # source record -> target record using the plan (pure functions)
    dryrun.py        # REQ-011
    migrate.py       # REQ-012: batches + checkpoint
    validate.py      # REQ-013
    report.py        # REQ-014
    cli.py           # REQ-015
    fake_scripts/    # JSON model scripts (plan, repair, summary)
  server/
    package.json  package-lock.json  tsconfig.json
    src/store.ts     # REQ-004: SQLite schema + functions
    src/tools.ts     # REQ-005/006: tool handlers with zod schemas
    src/index.ts     # stdio entry point
    test/*.test.ts
  fixtures/acme_board.json  (and a second set later)
  lessons/01..06 *.py, 07_mcp_in_typescript.md
  tests/conftest.py (socket guard)  tests/test_*.py  tests/live/
  docs/  plan/
  .migration-agent/  # checkpoint (gitignored)
  runs/              # plan, signoff, validation, report (gitignored)
```

## Flow
```
export.json -> source.py -> mapping.py + model (LLM) -> plan.json -> human answers + signoff -> signoff.json
                         \-> dryrun.py (reads only)
export.json + plan.json -> transform.py -> migrate.py -> McpTarget -> TS MCP server -> SQLite
                                            |-> checkpoint.json
validate.py: reads source + target -> validation.json -> report.py (+ LLM summary) -> report.md
```
The LLM is called in two places only: `mapping.py` and `report.py`. Everything else is deterministic.

## Components and contracts
- **Target protocol** (Python): `create_database(spec)`, `upsert_person(db, external_id, name, email)`,
  `upsert_page(db, external_id, values, relations) -> "created"|"updated"`, `count_pages(db)`,
  `list_pages(db, offset, limit)`, `get_page(db, external_id)`. Implemented by `McpTarget` and `FakeTarget`.
- **MCP tools** (TypeScript): the same names in snake_case. Errors are results with `isError: true`.
- **Mapping plan JSON**: see REQUIREMENTS shared definitions. Field `type` is one of the 11 property types.
- **Checkpoint JSON**: `{plan_hash, batch_size, entities: {name: {done_batches, total_batches, created, updated}}}`.
- **Signoff JSON**: `{plan_hash, signed_by, signed_at}`.
- **Validation JSON**: `{checks: [{name, status, detail, ids}], seed, sample_size}`.
- **Model reply for the plan**: JSON only; one repair retry with the error text.

## Data model mapping (default plan the model should find)
| Trello-like source | Notion-like target | Notes |
|---|---|---|
| member | people row (`external_id`, name, email) | Unknown member id on a card: warn, leave empty |
| board | page in database `Projects` | Name, description, closed flag |
| list | `Status` select on a task | List order kept as option order; empty list = no tasks, still an option |
| card | page in database `Tasks` | Title, description, due date, status, assignees (person), tags, project (relation) |
| label | `Tags` multi-select option | Duplicate label names merge; the merge is listed in the report |
| checklist item | page in database `Subtasks` | Title, done (checkbox), task (relation) |
| comment | page in database `Comments` | Text, author (person), created (date), task (relation) |
| attachment link | `Links` url values on the task | Links only; no file is copied |

Dependency order for `run`: people -> projects -> tasks -> subtasks -> comments.

## Risks
| Risk | Mitigation |
|---|---|
| Small local model writes bad plan JSON | Strict check, one repair retry, fixed fake scripts for tests, free hosted models as option |
| Free-tier limits change | Provider by setting; UNVERIFIED limits; offline tests do not need them |
| better-sqlite3 has no prebuilt binary for this Node on Windows | Check at F-001; fall back to `node:sqlite` (D-006) |
| Crash between target write and checkpoint | Idempotent upsert by external id (REQ-006/012) |
| Model invents numbers in the report | Numbers come from code; unknown numbers are dropped (REQ-014) |
| Customer text sent to a hosted model | Prompt holds 3 samples per field only; fixtures are made up; noted in the lessons |
| Windows path and process issues for the stdio child | Use the `node` path from settings; test with a smoke test |
