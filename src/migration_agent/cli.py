"""Show the migration commands.

These commands are placeholders for later project steps.
They do not read or write target data.
"""

import typer

app = typer.Typer(help="Move a board export with a human-approved mapping plan.")


@app.command()
def plan() -> None:
    """Propose a field mapping for review."""
    typer.echo("not implemented yet")


@app.command()
def signoff() -> None:
    """Record human approval of a mapping plan."""
    typer.echo("not implemented yet")


@app.command()
def dry_run() -> None:
    """Preview the move without writing target data."""
    typer.echo("not implemented yet")


@app.command()
def run() -> None:
    """Move data after the human approves the plan."""
    typer.echo("not implemented yet")


@app.command()
def validate() -> None:
    """Check the moved data against the source."""
    typer.echo("not implemented yet")


@app.command()
def report() -> None:
    """Write a summary of the move and its checks."""
    typer.echo("not implemented yet")
