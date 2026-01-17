"""Version tracking and graph rebuild commands.

This module provides commands for managing graph version tracking:
- 'version-check': Check graph construction version status
- 'rebuild-graph': Rebuild graph database with current version
- 'backup-metadata': Backup graph metadata to file

Issue #706: Graph Version Tracking System
"""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.commands.base import async_command, get_neo4j_config_from_env

console = Console()


@click.command("version-check")
@click.pass_context
def version_check(ctx: click.Context) -> None:
    """Check graph construction version status.

    Compares the semaphore file (.atg_graph_version) version with the Neo4j
    metadata node version. Displays current status and rebuild guidance if
    versions mismatch.

    Examples:
        atg version-check
    """
    try:
        from src.neo4j_session_manager import Neo4jSessionManager
        from src.version_tracking.detector import VersionDetector
        from src.version_tracking.metadata import GraphMetadataService

        # Initialize services
        uri, user, password = get_neo4j_config_from_env()
        session_manager = Neo4jSessionManager(uri=uri, user=user, password=password)
        metadata_service = GraphMetadataService(session_manager)
        detector = VersionDetector()

        # Read semaphore version
        semaphore_version = detector.read_semaphore_version()

        # Read metadata version
        try:
            metadata = metadata_service.read_metadata()
            metadata_version = metadata.get("version") if metadata else None
            last_scan_at = metadata.get("last_scan_at") if metadata else None
        except Exception as e:
            console.print(f"[red]Failed to read metadata from Neo4j: {e}[/red]")
            metadata_version = None
            last_scan_at = None

        # Create status table
        table = Table(title="Graph Version Status", show_header=True)
        table.add_column("Component", style="cyan", width=25)
        table.add_column("Version", style="green")
        table.add_column("Details", style="dim")

        # Semaphore version
        sem_ver_display = (
            semaphore_version if semaphore_version else "[dim]Not found[/dim]"
        )
        sem_path = str(detector.semaphore_path)
        table.add_row("Semaphore File", sem_ver_display, sem_path)

        # Metadata version
        meta_ver_display = (
            metadata_version if metadata_version else "[dim]Not found[/dim]"
        )
        scan_display = last_scan_at if last_scan_at else "[dim]Never scanned[/dim]"
        table.add_row("Neo4j Metadata", meta_ver_display, f"Last scan: {scan_display}")

        console.print(table)

        # Check for mismatch
        mismatch = detector.compare_versions(semaphore_version, metadata_version)

        if mismatch is None:
            console.print()
            console.print(
                Panel(
                    "[bold green]✓[/bold green] Versions match - graph is up to date",
                    style="green",
                )
            )
        else:
            console.print()
            console.print(
                Panel(
                    f"[bold yellow]⚠[/bold yellow] Version mismatch detected\n\n"
                    f"Reason: {mismatch['reason']}\n\n"
                    f"To rebuild the graph with the current version, run:\n"
                    f"[cyan]atg rebuild-graph --tenant-id <YOUR_TENANT_ID>[/cyan]",
                    style="yellow",
                    title="Action Required",
                )
            )
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]Version check failed: {e}[/red]")
        sys.exit(1)


@click.command("rebuild-graph")
@click.option(
    "--tenant-id",
    required=True,
    help="Azure tenant ID to scan and rebuild",
)
@click.option(
    "--auto",
    is_flag=True,
    help="Skip confirmation prompt (automatic mode)",
)
@click.option(
    "--backup-dir",
    type=click.Path(exists=False, file_okay=False, dir_okay=True, path_type=Path),
    help="Custom directory for metadata backups (default: ~/.atg/backups/)",
)
@click.pass_context
@async_command
async def rebuild_graph(
    ctx: click.Context,
    tenant_id: str,
    auto: bool,
    backup_dir: Optional[Path],
) -> None:
    """Rebuild graph database with current version.

    DESTRUCTIVE OPERATION: This will delete all existing graph data and rescan
    your Azure tenant. Metadata is automatically backed up before rebuild.

    Workflow:
    1. Backup existing metadata
    2. Drop all nodes/relationships
    3. Rescan Azure tenant
    4. Update metadata with new version

    Examples:
        # Interactive rebuild with confirmation
        atg rebuild-graph --tenant-id <YOUR_TENANT_ID>

        # Automatic rebuild (no confirmation)
        atg rebuild-graph --tenant-id <YOUR_TENANT_ID> --auto

        # Custom backup directory
        atg rebuild-graph --tenant-id <YOUR_TENANT_ID> --backup-dir /path/to/backups
    """
    try:
        from src.azure_tenant_grapher import AzureTenantGrapher
        from src.neo4j_session_manager import Neo4jSessionManager
        from src.version_tracking.detector import VersionDetector
        from src.version_tracking.metadata import GraphMetadataService
        from src.version_tracking.rebuild import RebuildService

        # Read current version from semaphore file
        detector = VersionDetector()
        new_version = detector.read_semaphore_version()

        if not new_version:
            console.print(
                "[red]Error: Cannot read version from semaphore file (.atg_graph_version)[/red]"
            )
            sys.exit(1)

        # Initialize services
        uri, user, password = get_neo4j_config_from_env()
        session_manager = Neo4jSessionManager(uri=uri, user=user, password=password)
        metadata_service = GraphMetadataService(session_manager)

        # Create grapher instance for discovery
        grapher = AzureTenantGrapher(tenant_id=tenant_id)

        # Initialize rebuild service
        rebuild_service = RebuildService(
            session_manager=session_manager,
            metadata_service=metadata_service,
            discovery_service=grapher,
            backup_dir=backup_dir,
        )

        # Show warning and confirm unless --auto
        if not auto:
            console.print()
            console.print(
                Panel(
                    f"[bold red]⚠ WARNING: DESTRUCTIVE OPERATION[/bold red]\n\n"
                    f"This will:\n"
                    f"  • Delete ALL existing graph data\n"
                    f"  • Backup metadata to: {rebuild_service.backup_dir}\n"
                    f"  • Rescan tenant: {tenant_id}\n"
                    f"  • Update graph to version: {new_version}\n\n"
                    f"This action cannot be undone.",
                    style="red",
                    title="Confirm Graph Rebuild",
                )
            )

            if not click.confirm("\nAre you sure you want to continue?"):
                console.print("[yellow]Rebuild cancelled.[/yellow]")
                return

        # Execute rebuild
        console.print()
        console.print("[cyan]Starting graph rebuild...[/cyan]")

        # Step 1: Backup metadata
        console.print("  [dim]1/4[/dim] Backing up metadata...")
        backup_path = rebuild_service.backup_metadata()
        if backup_path:
            console.print(f"  [green]✓[/green] Metadata backed up to: {backup_path}")
        else:
            console.print("  [dim]No existing metadata to backup[/dim]")

        # Step 2: Drop all data
        console.print("  [dim]2/4[/dim] Dropping all graph data...")
        rebuild_service.drop_all(confirm=True)
        console.print("  [green]✓[/green] Graph cleared")

        # Step 3: Rescan tenant
        console.print(f"  [dim]3/4[/dim] Scanning tenant {tenant_id}...")
        # Note: This will trigger the full scan workflow via the grapher
        stats = await grapher.build_graph()
        console.print(
            f"  [green]✓[/green] Scan complete - {stats.get('total_resources', 0)} resources processed"
        )

        # Step 4: Update metadata
        console.print("  [dim]4/4[/dim] Updating metadata...")
        from datetime import datetime

        timestamp = datetime.now().isoformat()
        metadata_service.write_metadata(version=new_version, last_scan_at=timestamp)
        console.print(f"  [green]✓[/green] Metadata updated to version {new_version}")

        console.print()
        console.print(
            Panel(
                f"[bold green]✓[/bold green] Graph rebuild complete\n\n"
                f"Version: {new_version}\n"
                f"Resources: {stats.get('total_resources', 0)}\n"
                f"Backup: {backup_path if backup_path else 'N/A'}",
                style="green",
                title="Success",
            )
        )

    except Exception as e:
        console.print(f"[red]Rebuild failed: {e}[/red]")
        sys.exit(1)


@click.command("backup-metadata")
@click.option(
    "--output-dir",
    type=click.Path(exists=False, file_okay=False, dir_okay=True, path_type=Path),
    help="Custom directory for backup file (default: ~/.atg/backups/)",
)
@click.pass_context
def backup_metadata(ctx: click.Context, output_dir: Optional[Path]) -> None:
    """Backup graph metadata to file.

    Creates a timestamped JSON backup of the current graph metadata (version
    and last scan timestamp) in the backup directory. Backup files are created
    with restrictive permissions (0o600) for security.

    Examples:
        # Backup to default location (~/.atg/backups/)
        atg backup-metadata

        # Backup to custom location
        atg backup-metadata --output-dir /path/to/backups
    """
    try:
        from src.neo4j_session_manager import Neo4jSessionManager
        from src.version_tracking.metadata import GraphMetadataService
        from src.version_tracking.rebuild import RebuildService

        # Initialize services
        uri, user, password = get_neo4j_config_from_env()
        session_manager = Neo4jSessionManager(uri=uri, user=user, password=password)
        metadata_service = GraphMetadataService(session_manager)

        # Create dummy discovery service (not used for backup)
        class DummyDiscovery:
            """Dummy discovery service for backup-only operations."""

            async def discover_all(self):
                pass

        # Initialize rebuild service
        rebuild_service = RebuildService(
            session_manager=session_manager,
            metadata_service=metadata_service,
            discovery_service=DummyDiscovery(),
            backup_dir=output_dir,
        )

        # Create backup
        console.print("[cyan]Backing up graph metadata...[/cyan]")
        backup_path = rebuild_service.backup_metadata()

        if backup_path:
            console.print()
            console.print(
                Panel(
                    f"[bold green]✓[/bold green] Metadata backed up successfully\n\n"
                    f"Location: {backup_path}\n"
                    f"Permissions: 0o600 (owner read/write only)",
                    style="green",
                    title="Backup Complete",
                )
            )
        else:
            console.print("[yellow]No metadata found in Neo4j to backup.[/yellow]")

    except Exception as e:
        console.print(f"[red]Backup failed: {e}[/red]")
        sys.exit(1)


# Export commands for registration
__all__ = [
    "backup_metadata",
    "rebuild_graph",
    "version_check",
]
