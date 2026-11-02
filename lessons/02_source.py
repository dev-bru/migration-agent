# What you will learn: source warnings are data to review, not rows to drop.
# The typed reader keeps an unknown member and reports the missing link.
# Count records first so later checks have a source of truth.
"""Read the made-up source and show its messy parts.

Why: dropping messy records would hide data loss from the customer.
Steps: read bytes and compute a hash, check typed fields, collect warnings,
then count cards. See src/migration_agent/source.py:120. The unknown member
is kept on the source card so the preview can explain the empty target field.
Run: .venv/Scripts/python.exe lessons/02_source.py --fake
Expected: Source: 2 cards, followed by the unknown member warning.
Quiz: Does an unknown member remove a card? Answer: No; it creates a warning.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import argparse
from migration_agent.source import read_export

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--fake", action="store_true", required=True)
parser.parse_args()
export = read_export(ROOT / "fixtures/acme_board.json")
print(f"Source: {sum(len(b.cards) for b in export.boards)} cards")
for warning in export.warnings:
    print(warning)
