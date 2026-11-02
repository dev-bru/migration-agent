# What you will learn: an FDE turns customer choices into a checked move.
# The model proposes a plan. A human approves it. Code moves the records.
# Read README.md for the full sequence and why each gate exists.
"""Explain the migration steps without moving data.

Why: a human owns the meaning of the move, so approval comes before writes.
Steps: inspect the source, propose a plan, answer questions, approve, preview,
move, check, and report. src/migration_agent/demo.py:26 connects these steps;
src/migration_agent/signoff.py:41 checks the approval before migration.
Run: .venv/Scripts/python.exe lessons/01_fde.py --fake
Expected: FDE: plan -> signoff -> dry-run -> run -> validate -> report
Quiz: Can the model approve its own mapping? Answer: No; a human reviews it.
"""

import argparse

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--fake", action="store_true", required=True)
parser.parse_args()
print("FDE: plan -> signoff -> dry-run -> run -> validate -> report")
