# AGENTS.md: map of migration-agent

Teaching project (P4): an AI-assisted migration of a team's work data from a Trello-like export into a
Notion-like workspace. The target is a Python MCP server (FastMCP) over SQLite. A Python agent proposes the field
mapping; plain code moves the data. Built through the crosscheck harness (Claude orchestrates, Codex implements).
Role play: a Forward Deployed Engineer (FDE) migrating a customer team.

## Rules
1. Code moves the data. The LLM only proposes mappings and writes summaries. It never writes to the target.
2. The real run needs a mapping plan signed off by the human (REQ-010). No sign-off file, no real run.
3. No API keys in files. Keys come from env vars only: GEMINI_API_KEY, GROQ_API_KEY, NVIDIA_NIM_API_KEY.
4. Offline tests need no model and no network: scripted fake model, in-memory or temp-file SQLite. Live tests use
   `@pytest.mark.live`. The target server tests run in the same `uv run pytest`.
5. Only touch files listed in the task spec. Never weaken tests. Feature status changes only via the harness
   `verify_feature.py`.
6. Exact dependency pins; log every dependency in docs/DEPENDENCIES.md. No installs without human approval.
7. Plain-English comments (eli5 level, ASD-STE100 style) on every module and public function, Python only (backend and agent code are Python; TypeScript is for frontends, none here).
8. Fixtures are made-up data only. No real customer data.
9. Native Windows; pathlib; UTF-8, LF. Python 3.12 via uv.

## Map
| Path | What |
|---|---|
| progress.md | Current state, next step |
| docs/PRODUCT_SPEC.md | Vision, scope, journeys |
| docs/REQUIREMENTS.md | REQ-### with acceptance criteria |
| docs/ARCHITECTURE.md | Stack, layout, contracts, data mapping |
| docs/DECISIONS.md | Decisions and assumptions |
| docs/DEPENDENCIES.md | Planned packages (pins at setup) |
| docs/exec-plans/ | Phase plans |
| feature_list.json | Features F-001..F-012 |
| plan/ | Intake artifacts (idea.md, plan.json); later the interactive architecture diagram |
| src/migration_agent/ | Python agent (mapping, dry run, migrate, validate, report) |
| src/migration_agent/target_server/ | Python FastMCP server (Notion-like target over stdlib sqlite3) |
| fixtures/ | Made-up Trello-like board exports |
| lessons/ | Step-by-step lessons |

## Commands
- Python tests: `uv run pytest` (offline)
- Live model tests: `uv run pytest -m live -n 0`
