"""Rich console singleton and output helpers."""

import json as json_mod
import sys

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Status/progress to stderr so it doesn't pollute piped JSON output
console = Console(stderr=True)

# Data output to stdout (pipeable to jq)
stdout_console = Console(file=sys.stdout)


def print_ok(msg: str) -> None:
    """Print a success message to stderr."""
    console.print(f"[green]✓[/green] {msg}")


def print_err(msg: str) -> None:
    """Print an error message to stderr."""
    console.print(f"[red]✗[/red] {msg}")


def print_warn(msg: str) -> None:
    """Print a warning message to stderr."""
    console.print(f"[yellow]![/yellow] {msg}")


def output_result(data: dict, *, ctx: typer.Context, title: str = "") -> None:
    """Print result as JSON (stdout) or Rich table (stderr).

    When --json is active, data goes to stdout as JSON.
    Otherwise, a Rich panel is rendered to stderr.
    """
    if ctx.obj.get("json"):
        stdout_console.print_json(data=data)
    else:
        formatted = json_mod.dumps(data, indent=2, ensure_ascii=False, default=str)
        if title:
            console.print(Panel(formatted, title=title, border_style="blue"))
        else:
            console.print(formatted)


def output_table(rows: list[dict], *, ctx: typer.Context, title: str = "", columns: list[str] | None = None) -> None:
    """Print rows as JSON array or Rich table."""
    if ctx.obj.get("json"):
        stdout_console.print_json(data=rows)
        return

    if not rows:
        console.print("[dim]No data[/dim]")
        return

    cols = columns or list(rows[0].keys())
    table = Table(title=title, show_lines=False)
    for col in cols:
        table.add_column(col)
    for row in rows:
        table.add_row(*[str(row.get(c, "")) for c in cols])
    console.print(table)
