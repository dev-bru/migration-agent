# Phase 1: Foundation and target (F-001..F-006)

Status: planned (2026-11-02). One feature at a time through /delegate; spec per feature from the harness
template; evaluator review; `verify_feature.py` sets status.

## Features (in order)
1. F-001 project setup (Python and Node), settings
2. F-002 source models, reader, sample export
3. F-003 TS server: SQLite store and schema
4. F-004 TS server: MCP tools and idempotent upsert
5. F-005 Python target client, FakeTarget, contract tests
6. F-006 model client, fake model, socket guard

## Done when
`uv run pytest` and `npm test --prefix server` are green. The sample export loads. A contract test upserts the same
page twice through the real server over stdio and gets one page. No model needed.

## Notes
- Install pinned packages only after the human approves the dependency list (harness rule).
- Check the better-sqlite3 prebuilt binary in F-001 (D-006).
