# Migration Agent: decisions

Each entry: what, who decided, why. ASSUMPTION entries are Claude's defaults; the human confirms or changes them at
the SPEC GATE. Claims are labeled MEASURED, DOCUMENTED (URL + date) or UNVERIFIED.

## D-001 Project role: Forward Deployed Engineer migration (human, idea)
FDE roles do customer data migrations. This project practises the full routine: map, ask, dry run, migrate in
batches, validate, report. The owner was rejected for an FDE migrations role for lacking this.

## D-002 The LLM proposes; code moves data (human, idea)
Data movement must be repeatable and testable. The model only proposes mappings and writes summaries. Every number
in the report comes from code.

## D-003 Target is a TypeScript MCP server over SQLite (human, idea)
Covers the Node/TypeScript gap. MCP is the only way the agent reaches the target, so the server is a real product
boundary with its own tests.

## D-004 Python agent with LiteLLM (human, idea)
One API for local Qwen and free hosted models (Gemini, Groq, NVIDIA NIM). Keys from env vars only. UNVERIFIED: free
tier limits and model names; check at setup.

## D-005 Idempotency key is the source external id (Claude)
Upsert by external id makes any batch safe to send twice. This covers a crash between the target write and the
checkpoint write. Alternative (exactly-once with a transaction log) is more code and is not needed.

## D-006 SQLite driver: better-sqlite3, fallback node:sqlite (ASSUMPTION)
better-sqlite3 is widely used and sync. It needs a prebuilt binary or a compiler on Windows: UNVERIFIED. Check in
F-001. If it fails, use Node's built-in `node:sqlite` and record the change here.

## D-007 Source is JSON fixtures, not the real Trello API (Claude)
No account, keys or network. Fixtures are made up and include messy cases on purpose. A real connector is out of
scope for v1.

## D-008 Human sign-off is a hash of plan.json (Claude)
A hash makes the sign-off exact: if the plan changes after sign-off, `run` refuses. Simple and testable.

## D-009 Checkpoint per batch, atomic write (Claude)
Write to a temp file, then rename. A crash never leaves half a JSON file. The checkpoint holds the plan hash so a
changed plan never reuses old progress.

## D-010 Validation includes a seeded content sample (Claude)
Counts alone miss wrong values. A fixed-seed sample of records is compared field by field. Default 20; tests use all.

## D-011 Tests use scripted fakes and a fake target (Claude, same pattern as Agent Lab)
Fast tests use `FakeTarget`. Contract tests run the same cases on `FakeTarget` and `McpTarget` so the fake cannot
drift. The TS server has its own vitest suite.

## D-012 Exact pins on both sides (Claude, harness rule)
Python `==` pins with `uv.lock`. npm exact versions with `package-lock.json` and `npm ci`. Supply-chain care for
both ecosystems.

## D-013 Two phases (Claude)
Phase 1 builds the target and the data path (setup, source, TS server, client). Phase 2 adds the agent steps
(model, plan, sign-off, dry run, batches, validate, report, CLI, lessons).

## ASSUMPTIONS (confirm at the SPEC GATE)
- A-1 Won't in v1: real Trello or Notion APIs, real customer data, web UI, cloud hosting, two-way sync.
- A-2 Default batch size 50, default sample size 20, confidence threshold for a question 0.7.
- A-3 Checklist items become a `Subtasks` database with a relation (shows relations); comments become a `Comments`
  database.
- A-4 Default model for live runs is a free hosted one or local Qwen; the human picks the provider in the settings.
- A-5 The interactive architecture diagram is made after phase 2 (REQ-018, Should).
