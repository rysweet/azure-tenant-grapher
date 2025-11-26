"""Database management commands.

This module provides commands for Neo4j database operations:
- 'backup' / 'backup-db': Backup database to file
- 'restore' / 'restore-db': Restore database from backup
- 'wipe': Clear all data from database
- 'container': Container management info

Issue #482: CLI Modularization
"""

import os
import sys

import click

from src.commands.base import get_neo4j_config_from_env


@click.command("backup")
@click.option(
    "--path",
    "-p",
    required=True,
    help="Path to save the backup file (e.g., /path/to/backup.dump)",
)
def backup(path: str) -> None:
    """Backup the Neo4j database to a file."""
    from src.container_manager import Neo4jContainerManager

    click.echo("Starting database backup...")
    container_manager = Neo4jContainerManager()

    if not container_manager.is_neo4j_container_running():
        click.echo("Neo4j container is not running. Please start it first.", err=True)
        sys.exit(1)

    if container_manager.backup_neo4j_database(path):
        click.echo(f"Database backed up successfully to {path}")
    else:
        click.echo("Database backup failed. Check the logs for details.", err=True)
        sys.exit(1)


@click.command("backup-db")
@click.argument(
    "backup_path", type=click.Path(dir_okay=False, writable=True, resolve_path=True)
)
def backup_db(backup_path: str) -> None:
    """Backup the Neo4j database and save it to BACKUP_PATH."""
    from src.container_manager import Neo4jContainerManager

    container_manager = Neo4jContainerManager()
    if container_manager.backup_neo4j_database(backup_path):
        click.echo(f"Neo4j backup completed and saved to {backup_path}")
    else:
        click.echo("Neo4j backup failed", err=True)
        sys.exit(1)


@click.command("restore")
@click.option(
    "--path",
    "-p",
    required=True,
    help="Path to the backup file to restore (e.g., /path/to/backup.dump)",
)
def restore(path: str) -> None:
    """Restore the Neo4j database from a backup file."""
    from src.container_manager import Neo4jContainerManager

    if not os.path.exists(path):
        click.echo(f"Backup file not found: {path}", err=True)
        sys.exit(1)

    click.echo("Starting database restore...")
    click.echo("WARNING: This will replace all current data in the database!")

    if not click.confirm("Are you sure you want to continue?"):
        click.echo("Restore cancelled.")
        return

    container_manager = Neo4jContainerManager()

    if not container_manager.is_neo4j_container_running():
        click.echo("Neo4j container is not running. Please start it first.", err=True)
        sys.exit(1)

    if container_manager.restore_neo4j_database(path):
        click.echo("Database restored successfully from backup.")
        click.echo("The Neo4j database has been restarted with the restored data.")
    else:
        click.echo("Database restore failed. Check the logs for details.", err=True)
        sys.exit(1)


# Alias for restore command
restore_db = restore


@click.command("wipe")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Skip confirmation prompt",
)
def wipe(force: bool) -> None:
    """Wipe all data from the Neo4j database."""
    from neo4j import GraphDatabase

    if not force:
        click.echo("WARNING: This will permanently delete ALL data in the database!")
        click.echo("This action cannot be undone.")
        if not click.confirm("Are you sure you want to wipe the database?"):
            click.echo("Wipe cancelled.")
            return

    click.echo("Wiping database...")

    try:
        # Get Neo4j connection details
        uri, user, password = get_neo4j_config_from_env()
        driver = GraphDatabase.driver(uri, auth=(user, password))

        with driver.session() as session:
            # Delete all nodes and relationships
            session.run("MATCH (n) DETACH DELETE n")

            # Verify the database is empty
            result = session.run("MATCH (n) RETURN count(n) as count")
            record = result.single()
            count = record["count"] if record else 0

            if count == 0:
                click.echo("Database wiped successfully. All data has been removed.")
            else:
                click.echo(f"Database wipe incomplete. {count} nodes remain.", err=True)

        driver.close()

    except Exception as e:
        click.echo(f"Failed to wipe database: {e}", err=True)
        sys.exit(1)


@click.command("container")
def container() -> None:
    """Manage Neo4j container."""
    # Note: Container management subcommands (start, stop, status) have been removed
    # as they were unused. Container management is handled automatically by the
    # build command when needed.
    click.echo("Container management is handled automatically by build commands.")
    click.echo("Use 'build --no-container' to disable automatic container management.")


# For backward compatibility
backup_command = backup
backup_db_command = backup_db
restore_command = restore
restore_db_command = restore_db
wipe_command = wipe
container_command = container

__all__ = [
    "backup",
    "backup_command",
    "backup_db",
    "backup_db_command",
    "container",
    "container_command",
    "restore",
    "restore_command",
    "restore_db",
    "restore_db_command",
    "wipe",
    "wipe_command",
]
