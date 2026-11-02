# Start here: Migration Agent learning pack

## What this project is (eli5)

A customer team keeps its work in a Trello-like board. They want it in a Notion-like workspace.
You are the Forward Deployed Engineer (FDE) who moves the data.

A model reads the export and *proposes* how fields map. A human answers the open questions and signs the plan.
Then plain Python code moves the records, in small batches, through a small MCP server into SQLite.
Last, code checks what landed and writes a report for the customer.

The model never writes data. The code does. That one rule is the whole project (`AGENTS.md` rule 1, `docs/DECISIONS.md` D-002).

All data is made up (`fixtures/acme_board.json`). No network or key is needed for any step in this pack.

## What you will learn

| Topic | Where |
|---|---|
| LLM proposes, deterministic code moves data | TOPICS 1, deep-01 |
| Mapping plans with confidence and questions | TOPICS 2, deep-01 |
| Human-in-the-loop sign-off by plan hash | TOPICS 3 |
| Dry run with the same transform | TOPICS 4 |
| Idempotent upserts and resumable batches | TOPICS 5-6, deep-02 |
| MCP server design with FastMCP | TOPICS 7, existing lesson 07 |
| Contract tests with fakes | TOPICS 8, deep-03 |
| Validation: counts, required fields, relations, sampling | TOPICS 9, deep-04 |
| Customer report with grounded numbers | TOPICS 10, deep-04 |
| FDE habits (warn, do not drop; ask, do not guess) | INTERVIEW |

## Prerequisites

- Read and write basic Python (functions, dicts, `async`/`await` at a "I can follow it" level).
- Know what JSON and SQL are.
- You do not need to know MCP, FastMCP or pydantic. The pack explains them.

## Run it offline in 3 commands

From `D:\Projects\migration-agent` (project Python 3.12 in `.venv`):

```powershell
.venv/Scripts/python.exe -m migration_agent.cli demo --runs-dir runs/demo
$env:MIGRATION_AGENT_RUNS_DIR = 'runs/demo'; .venv/Scripts/python.exe -m migration_agent.cli validate --fake --sample-size 20 --seed 0
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
```

Expected (MEASURED 2026-11-02):

1. A JSON preview with the warning `Board board-acme, card card-pots: unknown member member-missing`, then `Demo complete: runs/demo`.
   The folder holds `plan.json`, `signoff.json`, `checkpoint.json`, `validation.json`, `report.md`.
2. `Validation saved` (UNVERIFIED as a standalone command here; the README documents it after the demo, and the demo itself ran and passed all four checks).
3. `167 passed` (79 s on this machine). Offline: a socket guard blocks non-loopback network (`tests/conftest.py:1`).

## The learning path

Existing lessons come from feature F-012. They are runnable scripts. Do them first, in order.
The `deep-*` lessons in this pack go under the thin spots. Read each deep lesson after the lesson it follows.

| Order | Read or run | Time | Why |
|---|---|---|---|
| 1 | `docs/learn/ARCHITECTURE.md`, then open `architecture.html` | 20 min | Whole picture, where the LLM sits |
| 2 | `lessons/01_fde.py --fake` ([lessons/README.md](../../lessons/README.md)) | 10 min | See the full flow run |
| 3 | `lessons/02_source.py --fake` | 10 min | Source reading, warnings |
| 4 | `lessons/03_mapping.py --fake` | 15 min | Plan, confidence, questions |
| 5 | [lessons/deep-01-llm-boundary.md](lessons/deep-01-llm-boundary.md) | 40 min | The trust boundary in detail |
| 6 | `lessons/04_dry_run.py --fake` | 10 min | Preview |
| 7 | `lessons/05_batches.py --fake` | 15 min | Forced crash and resume |
| 8 | [lessons/deep-02-idempotency-and-resume.md](lessons/deep-02-idempotency-and-resume.md) | 45 min | Why the replay is safe, and where it is not |
| 9 | [lessons/07_mcp_target_server.md](../../lessons/07_mcp_target_server.md) | 20 min | MCP tools into SQLite |
| 10 | [lessons/deep-03-contract-tests-and-fakes.md](lessons/deep-03-contract-tests-and-fakes.md) | 40 min | Fakes that cannot drift |
| 11 | `lessons/06_validation_report.py --fake` | 10 min | Checks and report |
| 12 | [lessons/deep-04-validation-and-grounded-report.md](lessons/deep-04-validation-and-grounded-report.md) | 40 min | Validation strategy, grounded numbers |
| 13 | `TOPICS.md`, `GLOSSARY.md`, `INTERVIEW.md` | 60 min | Review and rehearse |

## Coming next

All 12 features (F-001..F-012) have status `passing` in `feature_list.json`, so nothing in this pack is a "coming next" feature.
Out of scope for v1 (`docs/DECISIONS.md` A-1): real Trello or Notion APIs, real customer data, a web UI, cloud hosting, two-way sync.

## Notes on accuracy

- Line numbers (`path:line`) were checked against the code on 2026-11-02. If code moves, search for the function name.
- The README's line references match the code. Some existing lesson text says "Six standalone lessons"; there are six scripts plus one walkthrough.
- Claims are MEASURED (a command ran here) or point to a test. Anything else is marked UNVERIFIED.
