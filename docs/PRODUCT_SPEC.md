# Migration Agent: product spec

Status: draft for the SPEC GATE (2026-11-02). Source: `plan/idea.md`.

## Vision
A small codebase that shows how a Forward Deployed Engineer (FDE) migrates a customer team from one tool to
another. The source is a Trello-like board export (JSON). The target is a Notion-like workspace, served by a
TypeScript MCP server over local SQLite. A Python agent proposes how fields map. The human signs off. Plain code
then moves the data in safe batches, checks the result and writes a report for the customer.

## User
One learner (the human) on a Windows PC. Knows Python. New to TypeScript, MCP servers in Node and migration work.
The project is also a portfolio piece that shows real migration practice.

## Success
1. `migration-agent plan` on the sample export writes a mapping plan with a confidence per field and questions.
2. `migration-agent dry-run` shows what would be created and changes nothing.
3. `migration-agent run` refuses to start without a signed-off plan.
4. A run killed halfway and started again gives the same target data as one clean run (no duplicates).
5. `migration-agent validate` checks counts, required fields, relation links and sampled content.
6. `migration-agent report` writes a customer-facing report in plain language.
7. `uv run pytest` and `npm test --prefix server` pass with no model and no network.
8. Every source file has plain-English comments (eli5, ASD-STE100 style).

## Journeys
- **Learn one idea.** Read a lesson, run its script, read the commented source.
- **Run a migration.** `plan` -> read questions -> edit answers -> sign off -> `dry-run` -> `run` -> `validate` ->
  `report`.
- **Recover.** Stop `run` mid-way (Ctrl+C). Run it again. It resumes from the checkpoint file.
- **Test offline.** Tests use a scripted fake model and a temp SQLite file.

## Scope
**Must**
- Fixtures: made-up Trello-like exports (boards, lists, cards, labels, members, checklists, comments, attachment
  links), including messy cases (missing due date, unknown member, duplicate label names, empty list).
- TypeScript MCP server (official MCP TypeScript SDK) with a Notion-like model: databases, pages, properties,
  relations, people. SQLite store. Tools for create, upsert, read, list and count.
- Python MCP client for the target. In-memory fake target for fast tests.
- LiteLLM model client; provider by env var or local Qwen `llama-server`; scripted fake model.
- Mapping plan: field map, confidence, questions for the customer. Human sign-off file.
- Dry run, resumable idempotent batches with a checkpoint file, validation, customer report.
- CLI, step-by-step lessons, later an interactive architecture diagram.

**Should**
- A second fixture set with different quirks to show the plan adapts.
- Retry with back-off for failed batches.

**Won't (v1)**
- Real Trello or Notion APIs. Real customer data. A web UI. Cloud hosting. Two-way sync.
- Hiring, assessment or edtech topics.

## Cost and constraints
INR 0 per month. Free-tier or local models only. Keys from env vars, never in files.
