"""Root Typer application with global options."""

import typer

app = typer.Typer(
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug-level logging"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Warnings and errors only"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON to stdout"),
):
    """Extract structured context and data from documents using AI."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet
    ctx.obj["json"] = json_output
