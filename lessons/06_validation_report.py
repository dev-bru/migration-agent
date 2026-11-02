# What you will learn: checks compare source facts with target values.
# A fixed random seed makes the content sample repeatable.
# Only summary prose comes from the model; report facts come from code.
"""Run the example, then inspect its validation and customer report.

Why: a successful write alone does not prove that the data is correct.
Steps: run the example, compare counts and required fields, check links,
re-read a seeded content sample, then write the report. See
src/migration_agent/validate.py:13 and src/migration_agent/report.py:15.
The model supplies summary prose; saved JSON supplies counts and check IDs.
Run: .venv/Scripts/python.exe lessons/06_validation_report.py --fake
Expected: Validation: all checks pass; report saved, then the report text.
Quiz: Why fix the sample seed? Answer: The same seed selects the same records.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import argparse
import asyncio
import tempfile
from migration_agent.demo import demo
from migration_agent.settings import Settings

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--fake", action="store_true", required=True)
parser.parse_args()
with tempfile.TemporaryDirectory(dir=ROOT, prefix=".pytest-tmp-lesson-") as folder:
    config = Settings(source=ROOT / "fixtures/acme_board.json", runs_dir=Path(folder))
    result = asyncio.run(demo(config))
    assert all(check["status"] == "pass" for check in result["checks"])
    print("Validation: all checks pass; report saved")
    print((Path(folder) / "report.md").read_text(encoding="utf-8"))
