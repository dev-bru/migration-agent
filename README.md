# Migration Agent

A teaching project for an FDE moving a team's board data into a small
Notion-like workspace. A model proposes a mapping. A human reviews its meaning
and approves the exact plan file. Python moves records through a FastMCP server
into SQLite, then compares the target with the source.

## Run the offline demo

Use the existing Python 3.12 environment from the project root:

```powershell
.venv/Scripts/python.exe -m migration_agent.cli demo --runs-dir runs/demo
```

Expected: a JSON preview with an unknown member warning, then
`Demo complete: runs/demo`. The folder contains `plan.json`, `signoff.json`,
`checkpoint.json`, `validation.json`, `report.md`, and a local fake workspace.
All four validation checks pass. All fixture records and reviewer answers are
made up. The demo uses bundled replies and canned approval; it never contacts a
model or starts the MCP server. It can run again without duplicate pages.

With a working uv installation, the equivalent is
`uv run --offline --no-sync migration-agent demo --runs-dir runs/demo`.
No dependency install or update is needed for either command.

## Follow the logic

1. Read and hash the export at `src/migration_agent/source.py:120`.
   Typed fields catch malformed records; unknown members become warnings so
   cards are kept. The source hash prevents a plan from moving a different export.
2. Propose and check a plan at `src/migration_agent/mapping.py:151`.
   Only a few samples enter the prompt. Code checks field names, property types
   and required values. It permits one model repair before it refuses the plan.
3. Answer the questions and approve at `src/migration_agent/signoff.py:22`.
   The plan must have every answer. Approval saves a hash, reviewer and timestamp;
   editing the plan after approval invalidates it. For a real run, a human must
   perform this review; never reuse the demo's canned approval as a real review.
4. Preview with `src/migration_agent/dryrun.py:11` and inspect the unknown member,
   empty due date, merged labels and attachment links. Preview and migration both
   use `src/migration_agent/transform.py:10`, so they apply the same mapping.
   Links are kept as text to preserve both links; no files are copied.
5. Move approved records at `src/migration_agent/migrate.py:29` in dependency
   order: people, projects, tasks, subtasks, comments. Upserts use stable source
   IDs. Complete batches get an atomic checkpoint, so a crash can safely replay
   a batch that reached the target but did not reach the checkpoint.
6. Check counts, required values, links and a seeded content sample at
   `src/migration_agent/validate.py:13`. Then `src/migration_agent/report.py:15`
   builds the customer report from saved facts. A model can write summary prose;
   unsupported numbers cause a paragraph to fall back to fixed text.

`src/migration_agent/demo.py:26` connects the same functions for the offline demo.
The model never receives a target client. The fake workspace is in memory by
default; CLI fake runs retain it in the runs folder so separate commands see the
same records. A real target uses the Python MCP child, never direct SQLite calls
from the agent. See [the server walkthrough](lessons/07_mcp_target_server.md).

## Use the commands

Each command accepts `--settings migration-agent.toml`. Copy and edit
`migration-agent.example.toml` for source, target command, database path, batch
size, model, local API base and runs directory. Environment settings override the
file. Provider keys come only from environment variables. Defaults use local
Qwen; hosted calls are optional and never part of offline tests.

For the demo artifacts above, set the runs directory before inspecting them:

```powershell
$env:MIGRATION_AGENT_RUNS_DIR = 'runs/demo'
.venv/Scripts/python.exe -m migration_agent.cli dry-run --fake
.venv/Scripts/python.exe -m migration_agent.cli run --fake
.venv/Scripts/python.exe -m migration_agent.cli validate --fake --sample-size 20 --seed 0
.venv/Scripts/python.exe -m migration_agent.cli report --no-llm
```

Expected: the preview, `Migration complete`, `Validation saved`, and
`Report saved`. The finished checkpoint makes this repeat run perform no record
writes. `--no-llm` uses fixed report prose and needs no model.

For a fresh fake flow, `plan --fake` writes a plan from the built-in script.
Open `plan.json`, read every question and fill each `answer`. Then run
`signoff --signed-by 'Your reviewer name'` before `run --fake`. The `signoff`
command also prompts for a name if it is omitted. It refuses unanswered
questions. Only `demo` supplies canned answers automatically.

For a real workspace, `plan` reads the existing schema over MCP. To start an
empty workspace with the sample schema, pass
`--schema src/migration_agent/fake_scripts/schema.json` to `plan`, then to the
approved `run`. The latter creates databases in file order through MCP before
moving records. You can use a different reviewed schema JSON file with the same
shape. `--script` on `plan` supplies a saved model script instead of a live model.
`dry-run` needs no approval and never creates real target databases.
Known data, settings, model and target failures print one line and exit with code
one. `validate` writes pass/fail/warn findings; inspect `validation.json` even
when the command completes successfully.

## Learn and check

[Six standalone lessons](lessons/README.md) explain each step and include a
forced checkpoint crash. Each has a run command, expected output and a quiz.

```powershell
.venv/Scripts/python.exe -m pytest --basetemp=.pytest-tmp-offline
```

Expected: the offline suite passes with no model server or provider keys.
The socket guard rejects remote connections. Live tests are opt-in with
`-m live`; do not use that flag for the offline run. Test temp folders stay
under the project. Dependencies and versions are recorded in
[docs/DEPENDENCIES.md](docs/DEPENDENCIES.md).

## Quiz

- Why is the model kept out of writes? Code must apply the reviewed mapping predictably.
- What invalidates approval? Any change to the saved plan bytes changes its hash.
- Why can a crashed batch run again? The source ID updates the same target record.
- Why validate after successful writes? Counts alone cannot detect a changed title or missing link.
