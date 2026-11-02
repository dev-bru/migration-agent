# What you will learn: a model reply is a proposal that code must check.
# A fake returns a saved reply so this lesson works offline.
# Open questions still need human answers before the move.
"""Build and inspect a checked mapping proposal.

Why: valid JSON can still name fields that do not exist.
Steps: src/migration_agent/mapping.py:72 limits samples in the prompt;
src/migration_agent/mapping.py:108 checks field names and required properties;
src/migration_agent/mapping.py:151 allows one repair, then saves a valid plan.
Run: .venv/Scripts/python.exe lessons/03_mapping.py --fake
Expected: Mapping: 4 entities; human answers needed, followed by questions.
Quiz: What happens after two bad replies? Answer: PlanError; no plan is saved.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import argparse
import tempfile
from migration_agent.demo import SCRIPTS, read_script
from migration_agent.fakes import FakeModel
from migration_agent.mapping import plan
from migration_agent.source import read_export

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--fake", action="store_true", required=True)
parser.parse_args()
with tempfile.TemporaryDirectory(dir=ROOT, prefix=".pytest-tmp-lesson-") as folder:
    proposal = plan(read_export(ROOT / "fixtures/acme_board.json"), read_script("schema.json"),
                    FakeModel(SCRIPTS / "plan.json"), Path(folder) / "plan.json")
    print(f"Mapping: {len(proposal.entities)} entities; human answers needed")
    for question in proposal.questions:
        print(question.text)
