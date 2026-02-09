"""Workspace commands — list and reset workspaces."""

import typer

from context_builder.cli._app import app
from context_builder.cli._common import (
    ensure_initialized,
    get_project_root,
    setup_logging,
)
from context_builder.cli._console import console, print_ok, print_err, print_warn, output_result, output_table

workspace_app = typer.Typer(
    no_args_is_help=True,
    help="Manage workspaces (reset, list).",
)
app.add_typer(workspace_app, name="workspace")


@workspace_app.command("list", help="List all registered workspaces.")
def workspace_list(
    ctx: typer.Context,
):
    """List all registered workspaces."""
    ensure_initialized()
    setup_logging(verbose=ctx.obj["verbose"], quiet=ctx.obj["quiet"])

    from context_builder.api.services.workspace import WorkspaceService

    project_root = get_project_root()
    workspace_service = WorkspaceService(project_root)

    workspaces = workspace_service.list_workspaces()
    active_id = workspace_service.get_active_workspace_id()

    if not workspaces:
        console.print("No workspaces registered.")
        return

    if ctx.obj["json"]:
        rows = []
        for ws in workspaces:
            row = {
                "workspace_id": ws.workspace_id,
                "name": ws.name,
                "path": str(ws.path),
                "active": ws.workspace_id == active_id,
            }
            if hasattr(ws, "description") and ws.description:
                row["description"] = ws.description
            rows.append(row)
        output_result({"workspaces": rows, "active_id": active_id}, ctx=ctx)
        return

    console.print(f"\nRegistered workspaces ({len(workspaces)}):\n")
    for ws in workspaces:
        active_marker = " [green](active)[/green]" if ws.workspace_id == active_id else ""
        console.print(f"  {ws.workspace_id}{active_marker}")
        if ctx.obj["verbose"]:
            console.print(f"    Name: {ws.name}")
            console.print(f"    Path: {ws.path}")
            if hasattr(ws, "created_at"):
                console.print(f"    Created: {ws.created_at}")
            if hasattr(ws, "description") and ws.description:
                console.print(f"    Description: {ws.description}")
            console.print()


@workspace_app.command("reset", help="Clear all data from a workspace (preserves config).")
def workspace_reset(
    ctx: typer.Context,
    workspace_id: str = typer.Option(
        None,
        "--workspace-id",
        help="Workspace ID to reset (default: active workspace)",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview what would be deleted"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompt"),
):
    """Reset a workspace — delete all data, preserve config."""
    ensure_initialized()
    setup_logging(verbose=ctx.obj["verbose"], quiet=ctx.obj["quiet"])

    from context_builder.api.services.workspace import WorkspaceService

    project_root = get_project_root()
    workspace_service = WorkspaceService(project_root)

    if workspace_id:
        workspace = workspace_service.get_workspace(workspace_id)
    else:
        workspace = workspace_service.get_active_workspace()

    if not workspace:
        print_err(f"Workspace not found: {workspace_id or 'active'}")
        raise SystemExit(1)

    # Always preview first
    preview = workspace_service.reset_workspace(
        workspace_id=workspace.workspace_id,
        dry_run=True,
    )

    if dry_run:
        if ctx.obj["json"]:
            output_result(preview, ctx=ctx)
        else:
            console.print(f"\n[bold]DRY RUN[/bold] — Would reset workspace: {workspace.workspace_id}")
            console.print(f"  Path: {preview['workspace_path']}")
            console.print(f"\n  Would clear:")
            for d in preview["cleared_dirs"]:
                console.print(f"    - {d}/")
            console.print(f"\n  Would preserve:")
            for d in preview["preserved_dirs"]:
                console.print(f"    - {d}/")
            console.print(f"\n  Files to delete: {preview['files_deleted']}")
            console.print(f"  Dirs to delete:  {preview['dirs_deleted']}")
            console.print(f"\n  To execute: remove --dry-run flag")
        return

    # Confirm unless --force
    if not force:
        console.print(f"\n[bold red]About to reset workspace: {workspace.workspace_id}[/bold red]")
        console.print(f"  Path: {preview['workspace_path']}")
        console.print(f"  Files to delete: {preview['files_deleted']}")
        console.print(f"  Dirs to delete:  {preview['dirs_deleted']}")
        console.print(f"\n  This will DELETE all claims, runs, logs, and indexes.")
        console.print(f"  Config (users, extractors, prompts) will be preserved.")
        console.print(f"\n  [bold]THIS ACTION CANNOT BE UNDONE.[/bold]")

        confirm = typer.prompt("\n  Type APPROVED to confirm", default="")
        if confirm != "APPROVED":
            print_warn("Aborted. You must type APPROVED (case-sensitive).")
            return

    stats = workspace_service.reset_workspace(
        workspace_id=workspace.workspace_id,
        dry_run=False,
    )

    if ctx.obj["json"]:
        output_result(stats, ctx=ctx)
    elif not ctx.obj["quiet"]:
        print_ok(f"Workspace reset: {stats['workspace_id']}")
        console.print(f"  Cleared: {', '.join(stats['cleared_dirs'])}")
        console.print(f"  Files deleted: {stats['files_deleted']}")
        console.print(f"  Dirs deleted:  {stats['dirs_deleted']}")
        console.print(f"  Preserved: {', '.join(stats['preserved_dirs'])}")
