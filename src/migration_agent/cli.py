"""Show the migration commands.

Mapping and approval can run before the migration commands are ready.
The later migration steps still show a placeholder.
"""

import json
from pathlib import Path

import typer

from migration_agent import mapping, model
from migration_agent.fakes import FakeModel
from migration_agent.settings import SettingsError, load_settings
from migration_agent.signoff import SignoffError, require_signoff, signoff as save_signoff
from migration_agent.source import SourceError, read_export

app = typer.Typer(help="Move a board export with a human-approved mapping plan.")


@app.command()
def plan(settings: Path | None = None, script: Path | None = None, schema: Path | None = None) -> None:
    """Propose a field mapping for review."""
    if settings is None and script is None and schema is None:
        typer.echo("not implemented yet")
        return
    try:
        config = load_settings(settings)
        target_schema = json.loads(schema.read_text(encoding="utf-8")) if schema else []
        client = FakeModel(script) if script else model
        if script is None:
            from functools import partial
            from types import SimpleNamespace
            client = SimpleNamespace(chat=partial(model.chat, settings=config))
        destination = config.runs_dir / "plan.json"
        mapping.plan(read_export(config.source), target_schema, client, destination)
        typer.echo(f"Plan saved to {destination}")
    except (SettingsError, SourceError, ValueError, OSError, model.ModelError) as error:
        typer.echo(" ".join(str(error).splitlines()), err=True)
        raise typer.Exit(1) from None


@app.command()
def signoff(plan_path: Path | None = None, signed_by: str | None = None) -> None:
    """Record human approval of a mapping plan."""
    if plan_path is None:
        typer.echo("not implemented yet")
        return
    try:
        proposal = mapping.read_plan(plan_path)
        typer.echo(proposal.model_dump_json(indent=2))
        unanswered = [q.id for q in proposal.questions if not q.answer or not q.answer.strip()]
        if unanswered:
            raise SignoffError("unanswered questions: " + ", ".join(unanswered))
        name = signed_by if signed_by is not None else typer.prompt("Reviewer name")
        save_signoff(plan_path, plan_path.with_name("signoff.json"), name)
        typer.echo("Sign-off saved")
    except (mapping.PlanError, SignoffError, OSError) as error:
        typer.echo(" ".join(str(error).splitlines()), err=True)
        raise typer.Exit(1) from None


@app.command()
def dry_run(plan_path: Path | None = None) -> None:
    """Preview the move without writing target data."""
    if plan_path is not None:
        try:
            mapping.read_plan(plan_path)
        except mapping.PlanError as error:
            typer.echo(" ".join(str(error).splitlines()), err=True)
            raise typer.Exit(1) from None
    typer.echo("not implemented yet")


@app.command()
def run(plan_path: Path | None = None) -> None:
    """Move data after the human approves the plan."""
    if plan_path is not None:
        try:
            require_signoff(plan_path, plan_path.with_name("signoff.json"))
        except SignoffError as error:
            typer.echo(str(error), err=True)
            raise typer.Exit(1) from None
    typer.echo("not implemented yet")


@app.command()
def validate() -> None:
    """Check the moved data against the source."""
    typer.echo("not implemented yet")


@app.command()
def report() -> None:
    """Write a summary of the move and its checks."""
    typer.echo("not implemented yet")
