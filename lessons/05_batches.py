# What you will learn: a crash can leave a written batch without a checkpoint.
# Source IDs make replay safe after that crash.
# This lesson crashes on purpose, then checks the resumed page count.
"""Force a checkpoint failure and resume without duplicate pages.

Why: a crash may occur after target writes and before progress reaches disk.
Steps: approve the canned example, use one record per batch, stop just before
saving a task checkpoint, confirm the old checkpoint, then run again.
src/migration_agent/migrate.py:20 replaces complete JSON atomically;
src/migration_agent/migrate.py:29 skips saved batches and replays unsaved ones.
Run: .venv/Scripts/python.exe lessons/05_batches.py --fake
Expected: Forced crash: task write has no saved checkpoint
Expected: Resume: 2 tasks, no duplicates
Quiz: Why is replay safe? Answer: An upsert uses the source ID as a stable key.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import argparse
import asyncio
import json
import tempfile
from unittest.mock import patch
from migration_agent import migrate as runner
from migration_agent.demo import SCRIPTS, read_script
from migration_agent.fakes import FakeModel, FakeTarget
from migration_agent.mapping import plan
from migration_agent.signoff import signoff
from migration_agent.source import read_export


async def main():
    """Crash before saving the task batch and replay it by source ID."""
    export = read_export(ROOT / "fixtures/acme_board.json")
    schema = read_script("schema.json")
    with tempfile.TemporaryDirectory(dir=ROOT, prefix=".pytest-tmp-lesson-") as folder:
        folder = Path(folder)
        path, checkpoint = folder / "plan.json", folder / "checkpoint.json"
        proposal = plan(export, schema, FakeModel(SCRIPTS / "plan.json"), path)
        for question in proposal.questions:
            question.answer = read_script("answers.json")[question.id]
        path.write_text(proposal.model_dump_json(), encoding="utf-8", newline="\n")
        signoff(path, folder / "signoff.json", "Canned lesson reviewer")
        save = runner.write_checkpoint

        def crash(path, data):
            """Stop after the task write but before its checkpoint reaches disk."""
            if data["entities"].get("card", {}).get("done_batches") == 1:
                raise OSError("forced checkpoint crash")
            save(path, data)

        async with FakeTarget(schema=schema) as target:
            with patch.object(runner, "write_checkpoint", crash):
                try:
                    await runner.migrate(export, path, target, checkpoint, batch_size=1)
                except OSError as error:
                    assert str(error) == "forced checkpoint crash"
                    print("Forced crash: task write has no saved checkpoint")
            assert json.loads(checkpoint.read_bytes())["entities"]["card"]["done_batches"] == 0
            await runner.migrate(export, path, target, checkpoint, batch_size=1)
            assert await target.count_pages("Tasks") == 2
            print("Resume: 2 tasks, no duplicates")


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--fake", action="store_true", required=True)
parser.parse_args()
asyncio.run(main())
