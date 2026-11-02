# Migration Agent: requirements

Status: draft for the SPEC GATE (2026-11-02). Priority: M = must, S = should.
Source: I = idea (`plan/idea.md`), H = harness rule, A = assumption (confirm at the gate).

## Shared definitions
- **Source export**: a JSON file in the Trello-like shape: `boards`, each with `lists`, `cards`, `labels`,
  `members`; each card has `checklists`, `comments`, `attachments` (links only, no files).
- **External id**: the id a record has in the source. Every target record stores it. It is the idempotency key.
- **Mapping plan**: JSON file `plan.json` made by `plan`. Fields: `version`, `source_hash`, `entities` (list of
  `{source, target_database, fields: [{source_field, target_property, type, confidence 0..1, reason}]}`),
  `questions` (list of `{id, text, options, answer}`), `signed_off` (false until sign-off).
- **Sign-off file**: `signoff.json` written by `migration-agent signoff`. Holds the SHA-256 of `plan.json`, a
  timestamp and the name typed by the human. The real run checks that the hash still matches.
- **Batch**: N source records (default 50) of one entity type, sent in order.
- **Checkpoint file**: `.migration-agent/checkpoint.json`. Holds the plan hash, per entity the last finished batch
  index and counts. Written after each finished batch (write to temp file, then rename).
- **Fake model**: `migration_agent.fakes.FakeModel(script)`. Same `chat()` signature as the real model. Returns
  scripted replies in order, records requests. A finished script raises `ScriptExhausted`.
- **Fake target**: `migration_agent.fakes.FakeTarget`. In-memory object with the same methods as the MCP target
  client. Used for fast tests of dry run, batches and validation.
- **Sample export**: `fixtures/acme_board.json`. Made-up. Includes: a card with no due date, a card with an unknown
  member id, two labels with the same name, an empty list, a card with 3 checklists items and 2 comments, a card
  with 2 attachment links.

## Foundation
**REQ-001 (M, I/H) Project setup.** Python 3.12 with uv, package `migration_agent` under `src/`, console script
`migration-agent`. Node project in `server/` with a lock file. Python dependencies use `==` pins; `uv.lock` has
hashes. npm dependencies are exact versions in `package.json` with `package-lock.json`.
- AC1: `uv sync --locked` and `npm ci --prefix server` succeed on a fresh clone.
- AC2: a test parses `pyproject.toml`: every runtime dependency uses `==`.
- AC3: a test parses `server/package.json`: no dependency version starts with `^` or `~`.
- AC4: `uv run migration-agent --help` lists `plan`, `signoff`, `dry-run`, `run`, `validate`, `report`.
- AC5: every dependency is listed in `docs/DEPENDENCIES.md`.

**REQ-002 (M, H) Settings and secrets.** `migration-agent.toml` (example committed as
`migration-agent.example.toml`) holds: `source` path, `target_server` command, `db_path`, `batch_size` (50),
`model` (provider/model name), `api_base` (for local `llama-server`), `runs_dir`. Env vars
`MIGRATION_AGENT_<KEY>` override the file. API keys are read only from `GEMINI_API_KEY`, `GROQ_API_KEY`,
`NVIDIA_NIM_API_KEY`.
- AC1: a test loads the example file and gets the defaults above.
- AC2: `MIGRATION_AGENT_BATCH_SIZE=5` gives 5; a non-integer gives an error naming the key.
- AC3: a test scans the repo text files for key-like strings (`AIza`, `gsk_`, `nvapi-`) and finds none.
- AC4: a test scans `src`, `server/src`, `tests` for `C:\Users` and drive-letter paths and finds none.

## Source side
**REQ-003 (M, I) Source reader and fixtures.** Typed models for board, list, card, label, member, checklist,
comment, attachment. `read_export(path)` returns them. Bad input raises `SourceError` naming the file, the record
and the field.
- AC1: the sample export loads; counts match the file (cards, lists, labels, members, comments, attachments).
- AC2: a card with an unknown member id loads and is flagged in `export.warnings`, not dropped.
- AC3: a card with a missing `name` raises `SourceError` naming the card id.
- AC4: reading the same file twice gives equal results and the same `source_hash` (SHA-256 of the bytes).

## Target side (TypeScript)
**REQ-004 (M, I) Notion-like store.** SQLite tables: `databases`, `properties` (name, type: title, text, number,
date, select, multi_select, person, url, relation, checkbox; `required` flag; relation target database),
`pages`, `page_values`, `people`. Each page and person has `external_id`, unique per database.
- AC1: a vitest test creates a database with 3 properties and reads the schema back.
- AC2: an unknown property type is rejected with a message that lists valid types.
- AC3: a relation property must name an existing database.

**REQ-005 (M, I) MCP tools.** The server uses the official MCP TypeScript SDK over stdio. Tools:
`create_database`, `list_databases`, `upsert_person`, `upsert_page`, `get_page`, `list_pages`, `count_pages`.
Every tool has a zod input schema. Bad input returns an MCP result with `isError: true` and a message that says
what was wrong and what is valid. No exception leaves the server.
- AC1: a test starts the server in-process with the SDK in-memory transport and lists exactly those 7 tools.
- AC2: `upsert_page` with a missing required property returns `isError: true` naming the property.
- AC3: `upsert_page` with a value of the wrong type returns `isError: true` naming property and expected type.
- AC4: `count_pages` returns the page count for a database.

**REQ-006 (M, I) Idempotent upsert.** `upsert_page` and `upsert_person` with the same `external_id` update the
record and never add a second one. The result says `created` or `updated`. Relations use external ids and the
server resolves them; a relation to an unknown external id returns `isError: true`.
- AC1: two upserts with the same external id give count 1 and result `created` then `updated`.
- AC2: upsert with identical values twice leaves `page_values` byte-equal (no change).
- AC3: a relation to an unknown external id returns `isError: true` naming the id.
- AC4: a stdio smoke test starts the built server as a child process and completes one `count_pages` call.

**REQ-007 (M, I) Python target client.** `McpTarget` opens the server over stdio with the Python `mcp` package
and exposes the same methods as `FakeTarget`: `create_database`, `upsert_person`, `upsert_page`, `count_pages`,
`list_pages`, `get_page`. Tool errors become `TargetError`.
- AC1: a test runs both `FakeTarget` and `McpTarget` (temp SQLite) through the same contract tests; results match.
- AC2: an `isError` result raises `TargetError` with the server message.
- AC3: if the server command is missing, the error names the setting `target_server`.

## Agent side
**REQ-008 (M, I/H) Model client and fake.** `chat(messages, response_format=None) -> Reply` on LiteLLM. Provider
chosen by `model` setting: local `llama-server` (openai-compatible `api_base`), or `gemini/...`, `groq/...`,
`nvidia_nim/...` with keys from env vars. Missing key gives an error naming the env var. Timeouts and HTTP errors
become `ModelTimeout`, `ModelError`. LiteLLM remote lookups and telemetry are off.
- AC1: with the model call patched, `chat()` passes model, api_base, key from env and timeout.
- AC2: a missing key env var raises an error that names it and does not print other env vars.
- AC3: a socket guard in `conftest.py` blocks non-loopback connects in offline tests; importing the model module
  passes under it.
- AC4: `FakeModel` replays a JSON script and records requests; a finished script raises `ScriptExhausted`.
- AC5: the default `pytest` run executes 0 `live` tests.

**REQ-009 (M, I) Mapping plan.** `plan` sends the model a compact summary of the export (entity types, field names,
3 sample values per field, value counts) and the target schema. The model returns JSON that must parse into the
mapping plan. The code checks it: every source field named exists; every target property exists in the target
schema or is marked `create`; every required target property has a source; confidence is 0..1. One repair retry
with the error text, then fail. Any field with confidence < 0.7 produces a question for the customer.
- AC1: with a scripted valid reply, `plan.json` is written and parses.
- AC2: a reply naming a source field that does not exist triggers one repair call, then succeeds with the next
  scripted reply.
- AC3: two bad replies in a row raise `PlanError` listing the problems; no `plan.json` is written.
- AC4: a field with confidence 0.5 appears in `questions`.
- AC5: the model prompt contains no card text beyond the 3 samples per field (a test checks the request size).
- AC6: `plan.json` holds `source_hash` equal to the export hash.

**REQ-010 (M, I/H) Human sign-off.** `migration-agent signoff` shows the plan and open questions. It refuses if any
question has no answer. It writes `signoff.json` with the plan hash, time and the name typed by the human.
- AC1: with an unanswered question, `signoff` exits 1 and lists the question ids.
- AC2: with all answered, `signoff.json` is written and its hash equals the SHA-256 of `plan.json`.
- AC3: `run` exits 1 when `signoff.json` is missing, or when its hash differs from `plan.json`.
- AC4: `dry-run` works without sign-off.

## Migration
**REQ-011 (M, I) Dry run.** `dry-run` applies the plan to the export in memory and prints: per entity the number of
records to create, fields that will be empty, warnings (unknown member, truncated text), and the first 3 mapped
records as a preview. It makes zero calls that change the target.
- AC1: with `FakeTarget`, a dry run leaves `FakeTarget` write-call count at 0.
- AC2: the output lists the unknown-member warning from the sample export.
- AC3: the preview shows the mapped record for the first card with property names from the plan.
- AC4: a dry run on a plan with a required property that has no source fails with a message naming it.

**REQ-012 (M, I) Resumable idempotent batches.** `run` migrates entities in dependency order: people, projects,
tasks, subtasks, comments. It sends batches of `batch_size`, keyed by external id. After each finished batch it
writes the checkpoint. On start it reads the checkpoint (only if the plan hash matches) and skips finished batches.
A failed batch is retried up to 3 times, then the run stops with a non-zero exit and the checkpoint intact.
- AC1: 120 fake cards with batch size 50 give 3 batches and a final target count of 120.
- AC2: a `FakeTarget` that fails on batch 2 stops the run; the checkpoint says batch 1 done; a second run with a
  working target finishes and the count is 120 with no duplicates.
- AC3: a run on a finished checkpoint does nothing and exits 0.
- AC4: a checkpoint with a different plan hash is refused with a message (not silently reused).
- AC5: a run killed after the target wrote batch 2 but before the checkpoint write, then rerun, gives no
  duplicates (the idempotent upsert covers it).
- AC6: the checkpoint file is always valid JSON (write to temp file, then rename).

**REQ-013 (M, I) Validation.** `validate` compares source and target and writes `validation.json`. Checks:
(1) counts per entity; (2) required properties filled; (3) relation integrity (every task points to an existing
project, every subtask and comment to an existing task); (4) content sample: N random records (default 20, fixed
seed) re-read from the target and compared field by field with the mapped source value. Each check is `pass`,
`fail` or `warn` with the ids involved.
- AC1: on a clean migration to `FakeTarget`, all four checks pass.
- AC2: delete one page in the target: the count check fails and names the entity and the difference.
- AC3: change one title in the target: the content-sample check (sample size = all) fails and names the record
  and the field.
- AC4: remove a relation: the relation check fails and names the page id.
- AC5: the same seed gives the same sample.

**REQ-014 (M, I) Customer report.** `report` writes `report.md` for the customer: what moved (counts), what
changed shape (mapping decisions and the human's answers), what did not move (warnings), validation result,
what to do next. A model writes only the plain-English summary paragraphs; every number and id comes from the
code. A test checks that every number in the report appears in `validation.json`, `checkpoint.json` or `plan.json`.
Without a model (`--no-llm`) the report uses fixed template text.
- AC1: with a scripted summary reply, `report.md` has the sections: Summary, What moved, What changed, What did not
  move, Checks, Next steps.
- AC2: with `--no-llm` the report is complete and makes no model call.
- AC3: if the model reply contains a number that is not in the data files, it is dropped and the template text
  is used for that paragraph.
- AC4: a failed check shows as FAIL in the Checks section with the ids.

**REQ-015 (M, I) CLI.** Commands `plan`, `signoff`, `dry-run`, `run`, `validate`, `report`, each taking the
settings; `--fake` uses the fake model and fake target with the built-in scripts. A `demo` command runs the whole
flow on the sample export with `--fake`, and answers questions from a canned file.
- AC1: `migration-agent demo` exits 0 offline and writes `plan.json`, `signoff.json`, `checkpoint.json`,
  `validation.json`, `report.md` in a temp or given runs folder.
- AC2: each command exits 1 with a one-line message on a known error (no traceback).

## Teaching
**REQ-016 (M, I/H) Comments.** Every Python and TypeScript source file starts with a plain-English comment (eli5,
ASD-STE100 style): what the file does and why. Every public function has a short comment.
- AC1: a test checks each `.py` file under `src` and each `.ts` file under `server/src` starts with a comment
  block of at least 3 lines.
- AC2: a test checks every public function in `src` has a docstring.

**REQ-017 (M, I) Lessons.** Six lessons in `lessons/`, each one runs alone with `--fake` and prints a short result:
01 what an FDE does and the migration steps; 02 reading the source and its mess; 03 mapping plan with a model;
04 dry run; 05 idempotent batches and checkpoints (including a forced crash); 06 validation and the report. A
seventh doc, `lessons/07_mcp_in_typescript.md`, walks through the TS server file by file.
- AC1: a test runs each lesson script with `--fake` and checks exit 0 and one expected line.
- AC2: each lesson file starts with a "What you will learn" comment of at most 5 lines.

**REQ-018 (S, I) Architecture diagram.** Interactive single-file HTML diagram of the six flows (plan, sign-off,
dry run, run, validate, report) in `plan/`, linked from the README.
- AC1: the file opens with no network and lists all six flows.

**REQ-019 (M, H) Offline test suite.** `uv run pytest` and `npm test --prefix server` pass with no model server,
no network and no API keys set.
- AC1: both commands pass with the three key env vars unset.
- AC2: the test count never drops below the baseline in the feature list.
