# What you will learn: a dry run shows values without changing the target.
# The preview uses the same pure transform as the real move.
# Approval is not needed because no target data is changed.
"""Preview the made-up migration and prove it makes no writes.

Why: previewing the same mapping rules exposes surprises before any move.
Steps: make a checked plan, prepare a fake schema, call the read-only preview,
then assert its write counter is zero. src/migration_agent/transform.py:10
is shared with migration. src/migration_agent/dryrun.py:11 shows empty fields,
source warnings, counts and the first mapped records.
Run: .venv/Scripts/python.exe lessons/04_dry_run.py --fake
Expected: a JSON preview, then Dry run: zero target writes.
Quiz: Does a preview need sign-off? Answer: No, because it cannot move data.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import argparse
import asyncio
import tempfile
from migration_agent.demo import SCRIPTS, read_script
from migration_agent.dryrun import dry_run
from migration_agent.fakes import FakeModel, FakeTarget
from migration_agent.mapping import plan
from migration_agent.source import read_export


async def main():
    """Preview a proposal and check the target write counter."""
    export = read_export(ROOT / "fixtures/acme_board.json")
    schema = read_script("schema.json")
    with tempfile.TemporaryDirectory(dir=ROOT, prefix=".pytest-tmp-lesson-") as folder:
        proposal = plan(export, schema, FakeModel(SCRIPTS / "plan.json"), Path(folder) / "plan.json")
        async with FakeTarget(schema=schema) as target:
            await dry_run(export, proposal, target)
            assert target.write_calls == 0
            print("Dry run: zero target writes")


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--fake", action="store_true", required=True)
parser.parse_args()
asyncio.run(main())
