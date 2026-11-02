# Keep the offline example in one place for the CLI and lessons.
# Read made-up model replies and human answers from local files.
# Use the same transform, batches and checks as a real migration.
"""Run the teaching example without a model server or network."""

import json
from pathlib import Path

from migration_agent import mapping
from migration_agent.dryrun import dry_run
from migration_agent.fakes import FakeModel, FakeTarget
from migration_agent.migrate import migrate
from migration_agent.report import report
from migration_agent.signoff import signoff
from migration_agent.source import read_export
from migration_agent.validate import validate

SCRIPTS = Path(__file__).with_name("fake_scripts")


def read_script(name: str):
    """Read one bundled made-up example file."""
    return json.loads((SCRIPTS / name).read_text(encoding="utf-8"))


async def demo(config) -> dict:
    """Run planning, canned approval, preview, migration, checks and report."""
    folder = config.runs_dir
    export = read_export(config.source)
    schema = read_script("schema.json")
    proposal = mapping.plan(export, schema, FakeModel(SCRIPTS / "plan.json"), folder / "plan.json")
    answers = read_script("answers.json")
    for question in proposal.questions:
        question.answer = answers[question.id]
    (folder / "plan.json").write_text(proposal.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    signoff(folder / "plan.json", folder / "signoff.json", "Demo reviewer (canned approval)")
    async with FakeTarget(folder / "fake-target.sqlite", schema) as target:
        await dry_run(export, mapping.read_plan(folder / "plan.json"), target)
        await migrate(export, folder / "plan.json", target, folder / "checkpoint.json", config.batch_size)
        result = await validate(export, mapping.read_plan(folder / "plan.json"), target, folder / "validation.json")
    report(folder / "plan.json", folder / "checkpoint.json", folder / "validation.json", folder / "report.md",
           FakeModel(SCRIPTS / "summary.json"), warnings=export.warnings)
    return result
