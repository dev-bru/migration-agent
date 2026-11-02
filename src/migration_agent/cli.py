# Give each migration step a command with the same settings.
# Require human approval before real target writes.
# Keep known failures short enough to read in a terminal.
"""Run the migration steps and the offline teaching demo."""

import asyncio
from contextlib import contextmanager
from functools import partial
import json
from pathlib import Path
from types import SimpleNamespace

import typer

from migration_agent import demo as example, mapping, model
from migration_agent.dryrun import dry_run as preview
from migration_agent.fakes import FakeModel, FakeTarget, ScriptExhausted
from migration_agent.migrate import migrate
from migration_agent.report import report as write_report
from migration_agent.settings import load_settings
from migration_agent.signoff import require_signoff, signoff as save_signoff
from migration_agent.source import read_export
from migration_agent.target import McpTarget, TargetError
from migration_agent.validate import validate as check_target

app = typer.Typer(help="Move a board export with a human-approved mapping plan.")


@contextmanager
def _errors():
    try:
        yield
    except (ValueError, OSError, TargetError, model.ModelError, ScriptExhausted) as error:
        typer.echo(" ".join(str(error).splitlines()), err=True)
        raise typer.Exit(1) from None


def _model(config, fake=False, script=None, name="plan.json"):
    return (FakeModel(script or example.SCRIPTS / name) if fake or script else
            SimpleNamespace(chat=partial(model.chat, settings=config)))


def _target(config, fake):
    return (FakeTarget(config.runs_dir / "fake-target.sqlite", example.read_script("schema.json"))
            if fake else McpTarget(config))


async def _schemas(config, fake):
    if fake:
        return example.read_script("schema.json")
    async with McpTarget(config) as target:
        return await target.list_databases()


@app.command()
def plan(settings: Path | None = None, script: Path | None = None, schema: Path | None = None,
         fake: bool = False) -> None:
    """Propose a checked mapping for a human to review."""
    with _errors():
        config = load_settings(settings)
        export = read_export(config.source)
        target_schema = json.loads(schema.read_text(encoding="utf-8")) if schema else asyncio.run(_schemas(config, fake))
        destination = config.runs_dir / "plan.json"
        mapping.plan(export, target_schema, _model(config, fake, script), destination)
        typer.echo(f"Plan saved to {destination}")


@app.command()
def signoff(plan_path: Path | None = None, signed_by: str | None = None,
            settings: Path | None = None, fake: bool = False) -> None:
    """Show the plan and record the human reviewer's approval."""
    with _errors():
        config = load_settings(settings)
        path = plan_path or config.runs_dir / "plan.json"
        proposal = mapping.read_plan(path)
        unanswered = [q.id for q in proposal.questions if not q.answer or not q.answer.strip()]
        if unanswered:
            raise ValueError("unanswered questions: " + ", ".join(unanswered))
        typer.echo(proposal.model_dump_json(indent=2))
        name = signed_by if signed_by is not None else typer.prompt("Reviewer name")
        save_signoff(path, path.with_name("signoff.json"), name)
        typer.echo("Sign-off saved")


async def _step(command, config, fake, path, schema=None, sample_size=20, seed=0):
    if command == "run":
        require_signoff(path, path.with_name("signoff.json"))
    proposal = mapping.read_plan(path)
    export = read_export(config.source)
    if proposal.source_hash != export.source_hash:
        raise ValueError("source_hash does not match the export")
    async with _target(config, fake) as target:
        if command == "dry-run":
            await preview(export, proposal, target)
        elif command == "run":
            if schema:
                specs = json.loads(schema.read_text(encoding="utf-8"))
                # Check mapping rules before creating requested databases.
                from migration_agent.transform import transform
                transform(export, proposal, specs)
                for spec in specs:
                    await target.create_database(spec)
            await migrate(export, path, target, path.with_name("checkpoint.json"), config.batch_size)
            typer.echo("Migration complete")
        else:
            await check_target(export, proposal, target, path.with_name("validation.json"), sample_size, seed)
            typer.echo("Validation saved")


@app.command()
def dry_run(plan_path: Path | None = None, settings: Path | None = None, fake: bool = False) -> None:
    """Preview the mapped records without target writes or approval."""
    with _errors():
        config = load_settings(settings)
        asyncio.run(_step("dry-run", config, fake, plan_path or config.runs_dir / "plan.json"))


@app.command()
def run(plan_path: Path | None = None, settings: Path | None = None, fake: bool = False,
        schema: Path | None = None) -> None:
    """Move approved records and resume completed batches safely."""
    with _errors():
        config = load_settings(settings)
        asyncio.run(_step("run", config, fake, plan_path or config.runs_dir / "plan.json", schema))


@app.command()
def validate(plan_path: Path | None = None, settings: Path | None = None, fake: bool = False,
             sample_size: int = 20, seed: int = 0) -> None:
    """Compare the source with the saved target and write checks."""
    with _errors():
        config = load_settings(settings)
        asyncio.run(_step("validate", config, fake, plan_path or config.runs_dir / "plan.json",
                          sample_size=sample_size, seed=seed))


@app.command()
def report(settings: Path | None = None, fake: bool = False, no_llm: bool = False) -> None:
    """Write the customer report with an optional model summary."""
    with _errors():
        config = load_settings(settings)
        folder = config.runs_dir
        export = read_export(config.source)
        write_report(folder / "plan.json", folder / "checkpoint.json", folder / "validation.json",
                     folder / "report.md", None if no_llm else _model(config, fake, name="summary.json"),
                     no_llm=no_llm, warnings=export.warnings)
        typer.echo("Report saved")


@app.command()
def demo(settings: Path | None = None, runs_dir: Path | None = None,
         fake: bool = typer.Option(True, "--fake", help="Use the built-in offline example.")) -> None:
    """Run the whole sample flow with canned answers and no network."""
    with _errors():
        config = load_settings(settings)
        if runs_dir is not None:
            config = config.model_copy(update={"runs_dir": runs_dir})
        asyncio.run(example.demo(config))
        typer.echo(f"Demo complete: {config.runs_dir}")


if __name__ == "__main__":
    app()
