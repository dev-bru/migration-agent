# Phase 1: Foundation and target (F-001..F-006)

Status: planned (2026-11-02). One feature at a time through /delegate; spec per feature from the harness
template; evaluator review; `verify_feature.py` sets status.

## Features (in order)
1. F-001 project setup (Python), settings
2. F-002 source models, reader, sample export
3. F-003 target store: SQLite schema and Notion-like model (Python)
4. F-004 target MCP server (FastMCP) with idempotent upsert tools
5. F-005 Python target client, FakeTarget, contract tests
6. F-006 model client, fake model, socket guard

## Done when
`uv run pytest` is green. The sample export loads. A contract test upserts the same
page twice through the real FastMCP server over stdio and gets one page. No model needed.

## Notes
- Install pinned packages only after the human approves the dependency list (harness rule).
- Server pattern: Agent Lab `mcp_server.py` and `mcp_client.py` (FastMCP 4.1.4).
