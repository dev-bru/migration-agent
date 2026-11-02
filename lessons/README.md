# Learn the migration by running it

All data is made up. Run each lesson alone from the project root with the
project Python. No model server, keys or network are needed. Temporary folders
use `.pytest-tmp-lesson-*` under this project and are removed when the lesson ends.

1. Run `.venv/Scripts/python.exe lessons/01_fde.py --fake`.
   Expected: `FDE: plan -> signoff -> dry-run -> run -> validate -> report`.
   Start here to see why a human owns the decisions. The full flow is in
   `src/migration_agent/demo.py:26`.
2. Run `.venv/Scripts/python.exe lessons/02_source.py --fake`.
   Expected: `Source: 2 cards` and an unknown member warning.
   `src/migration_agent/source.py:120` keeps bad links visible instead of dropping cards.
3. Run `.venv/Scripts/python.exe lessons/03_mapping.py --fake`.
   Expected: `Mapping: 4 entities; human answers needed`.
   `src/migration_agent/mapping.py:151` checks a scripted proposal and saves it.
4. Run `.venv/Scripts/python.exe lessons/04_dry_run.py --fake`.
   Expected: a JSON preview and `Dry run: zero target writes`.
   `src/migration_agent/dryrun.py:11` shows the exact transform the move will use.
5. Run `.venv/Scripts/python.exe lessons/05_batches.py --fake`.
   Expected: `Forced crash: task write has no saved checkpoint`, then
   `Resume: 2 tasks, no duplicates`. `src/migration_agent/migrate.py:29` replays
   the unsaved batch; the stable source ID prevents duplicate pages.
6. Run `.venv/Scripts/python.exe lessons/06_validation_report.py --fake`.
   Expected: `Validation: all checks pass; report saved` and the report text.
   `src/migration_agent/validate.py:13` compares facts; `src/migration_agent/report.py:15`
   prints those facts and checks proposed summary text for unsupported numbers.
7. Read [the server walkthrough](07_mcp_target_server.md) to follow MCP calls into SQLite.

## Quiz

- Why share one transform between preview, move and checks? So the same plan has the same meaning.
- Can an old approval cover a changed plan? No; the file hash changes.
- Does a finished checkpoint alone prove target content is correct? No; validate it.
