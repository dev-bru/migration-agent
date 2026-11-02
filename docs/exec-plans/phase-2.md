# Phase 2: The migration agent (F-007..F-012)

Status: planned (2026-11-02). Starts after phase 1 is green.

## Features (in order)
1. F-007 mapping plan, questions, sign-off
2. F-008 transform and dry run
3. F-009 resumable idempotent batches with checkpoint
4. F-010 validation
5. F-011 customer report
6. F-012 CLI, demo, lessons

## Done when
`uv run migration-agent demo` runs the whole flow offline on the sample export and writes plan, signoff,
checkpoint, validation and report. A forced crash in lesson 05 resumes with no duplicates. `uv run pytest` green.

## Notes
- Optional live check: one real `plan` call against local Qwen or a free hosted model, marked `live`.
- After this phase: the interactive architecture diagram (REQ-018) and a second fixture set.
