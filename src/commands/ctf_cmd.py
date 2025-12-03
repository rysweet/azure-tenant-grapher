"""CTF (Capture The Flag) overlay management command group.

This module provides the ctf command group for CTF scenario management:
- ctf import: Import Terraform resources with CTF annotations
- ctf deploy: Deploy CTF scenario from Neo4j resources
- ctf list: List CTF scenarios and resources
- ctf clear: Remove CTF scenario annotations

Philosophy:
- Ruthless simplicity: Delegate to services, focus on CLI usability
- Zero-BS implementation: Every command works, idempotent operations
- Properties-only architecture: No separate CTF nodes

Issue #552: CTF Overlay System Implementation
"""

import json
from pathlib import Path
from typing import Optional

import click
import structlog

from src.config_manager import create_neo4j_config_from_env
from src.services.ctf_annotation_service import CTFAnnotationService
from src.services.ctf_deploy_service import CTFDeployService
from src.services.ctf_import_service import CTFImportService
from src.utils.session_manager import create_session_manager

logger = structlog.get_logger(__name__)


def get_services():
    """Get CTF services with Neo4j connection.

    Returns:
        Tuple of (import_service, deploy_service, annotation_service)
    """
    config = create_neo4j_config_from_env()
    session_manager = create_session_manager(config.neo4j)
    session_manager.connect()
    driver = session_manager._driver

    import_service = CTFImportService(neo4j_driver=driver)
    deploy_service = CTFDeployService(neo4j_driver=driver)
    annotation_service = CTFAnnotationService(neo4j_driver=driver)

    return import_service, deploy_service, annotation_service


# =============================================================================
# CTF Command Group
# =============================================================================


@click.group(name="ctf")
def ctf() -> None:
    """CTF (Capture The Flag) overlay management commands."""
    pass


# =============================================================================
# ctf import
# =============================================================================


@ctf.command(name="import")
@click.option(
    "--terraform-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Path to Terraform directory containing .tf files",
)
@click.option(
    "--state-file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
    help="Path to Terraform state file (terraform.tfstate)",
)
@click.option(
    "--layer-id",
    default="default",
    help="Layer identifier (default: default)",
)
@click.option(
    "--exercise",
    required=True,
    help="CTF exercise identifier (e.g., M003)",
)
@click.option(
    "--scenario",
    required=True,
    help="CTF scenario variant (e.g., v2-cert)",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help="Output format (default: table)",
)
def ctf_import(
    terraform_dir: Optional[Path],
    state_file: Optional[Path],
    layer_id: str,
    exercise: str,
    scenario: str,
    format_type: str
) -> None:
    """Import Terraform resources with CTF annotations.

    Parse Terraform configurations or state files and annotate
    the corresponding Neo4j resources with CTF properties.

    Examples:

        # Import from state file
        atg ctf import --state-file terraform.tfstate --exercise M003 --scenario v2-cert

        # Import from Terraform directory
        atg ctf import --terraform-dir ./terraform/m003 --exercise M003 --scenario v2-cert
    """
    if not terraform_dir and not state_file:
        click.echo("Error: Either --terraform-dir or --state-file must be provided", err=True)
        raise click.Abort()

    try:
        import_service, _, _ = get_services()

        click.echo(f"Importing CTF scenario {exercise}/{scenario}...")

        result = import_service.import_terraform(
            terraform_dir=terraform_dir,
            state_file=state_file,
            layer_id=layer_id,
            ctf_exercise=exercise,
            ctf_scenario=scenario
        )

        if format_type == "json":
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"\nImport completed:")
            click.echo(f"  Resources imported: {result['resources_imported']}")
            click.echo(f"  Resources failed: {result['resources_failed']}")

            if result.get("warnings"):
                click.echo(f"\nWarnings ({len(result['warnings'])}):")
                for warning in result["warnings"][:5]:  # Show first 5
                    click.echo(f"  - {warning}")
                if len(result["warnings"]) > 5:
                    click.echo(f"  ... and {len(result['warnings']) - 5} more")

    except Exception as e:
        logger.error(f"CTF import failed: {e}")
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


# =============================================================================
# ctf deploy
# =============================================================================


@ctf.command(name="deploy")
@click.option(
    "--layer-id",
    default="default",
    help="Layer identifier (default: default)",
)
@click.option(
    "--exercise",
    required=True,
    help="CTF exercise identifier (e.g., M003)",
)
@click.option(
    "--scenario",
    required=True,
    help="CTF scenario variant (e.g., v2-cert)",
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help="Directory for Terraform output",
)
@click.option(
    "--auto-import/--no-auto-import",
    default=True,
    help="Automatically import deployed resources (default: true)",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help="Output format (default: table)",
)
def ctf_deploy(
    layer_id: str,
    exercise: str,
    scenario: str,
    output_dir: Path,
    auto_import: bool,
    format_type: str
) -> None:
    """Deploy CTF scenario from Neo4j resources.

    Query resources by CTF properties, export to Terraform,
    and optionally deploy them.

    Examples:

        # Export Terraform without deploying
        atg ctf deploy --exercise M003 --scenario v2-cert --output-dir ./terraform/deployed

        # Deploy and auto-import
        atg ctf deploy --exercise M003 --scenario v2-cert --output-dir ./terraform/deployed --auto-import
    """
    try:
        _, deploy_service, _ = get_services()

        click.echo(f"Deploying CTF scenario {exercise}/{scenario}...")

        result = deploy_service.deploy_scenario(
            layer_id=layer_id,
            ctf_exercise=exercise,
            ctf_scenario=scenario,
            output_dir=output_dir,
            auto_import=auto_import,
            deploy_args=None  # Don't actually deploy, just export
        )

        if format_type == "json":
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"\nDeployment completed:")
            click.echo(f"  Resources exported: {result['resources_deployed']}")
            click.echo(f"  Terraform directory: {result['terraform_dir']}")

            if result.get("import_result"):
                import_result = result["import_result"]
                click.echo(f"\nAuto-import results:")
                click.echo(f"  Resources imported: {import_result['resources_imported']}")
                click.echo(f"  Resources failed: {import_result['resources_failed']}")

    except Exception as e:
        logger.error(f"CTF deploy failed: {e}")
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


# =============================================================================
# ctf list
# =============================================================================


@ctf.command(name="list")
@click.option(
    "--layer-id",
    help="Filter by layer ID",
)
@click.option(
    "--exercise",
    help="Filter by exercise ID",
)
@click.option(
    "--scenario",
    help="Filter by scenario variant",
)
@click.option(
    "--role",
    help="Filter by resource role",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help="Output format (default: table)",
)
def ctf_list(
    layer_id: Optional[str],
    exercise: Optional[str],
    scenario: Optional[str],
    role: Optional[str],
    format_type: str
) -> None:
    """List CTF scenarios and resources.

    Examples:

        # List all CTF resources
        atg ctf list

        # List specific exercise
        atg ctf list --exercise M003

        # List specific scenario
        atg ctf list --exercise M003 --scenario v2-cert

        # List by role
        atg ctf list --exercise M003 --role target
    """
    try:
        _, deploy_service, _ = get_services()

        # Build query based on filters
        query = "MATCH (r:Resource)"
        where_clauses = []
        params = {}

        if layer_id:
            where_clauses.append("r.layer_id = $layer_id")
            params["layer_id"] = layer_id

        if exercise:
            where_clauses.append("r.ctf_exercise = $exercise")
            params["exercise"] = exercise

        if scenario:
            where_clauses.append("r.ctf_scenario = $scenario")
            params["scenario"] = scenario

        if role:
            where_clauses.append("r.ctf_role = $role")
            params["role"] = role

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        query += """
        RETURN r.id AS id,
               r.name AS name,
               r.resource_type AS resource_type,
               r.layer_id AS layer_id,
               r.ctf_exercise AS exercise,
               r.ctf_scenario AS scenario,
               r.ctf_role AS role
        ORDER BY r.ctf_exercise, r.ctf_scenario, r.name
        LIMIT 100
        """

        result_records, _, _ = deploy_service.neo4j_driver.execute_query(query, **params)

        resources = [dict(record) for record in result_records]

        if format_type == "json":
            click.echo(json.dumps(resources, indent=2))
        else:
            click.echo(f"\nCTF Resources ({len(resources)}):")
            click.echo("-" * 80)

            for resource in resources:
                click.echo(f"  {resource['exercise']}/{resource['scenario']} - {resource['name']}")
                click.echo(f"    Role: {resource['role']}")
                click.echo(f"    Type: {resource['resource_type']}")
                click.echo(f"    Layer: {resource['layer_id']}")
                click.echo()

    except Exception as e:
        logger.error(f"CTF list failed: {e}")
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


# =============================================================================
# ctf clear
# =============================================================================


@ctf.command(name="clear")
@click.option(
    "--layer-id",
    help="Layer identifier to clear",
)
@click.option(
    "--exercise",
    required=True,
    help="Exercise identifier to clear",
)
@click.option(
    "--scenario",
    required=True,
    help="Scenario variant to clear",
)
@click.option(
    "--confirm/--no-confirm",
    default=True,
    help="Require confirmation before clearing (default: true)",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help="Output format (default: table)",
)
def ctf_clear(
    layer_id: Optional[str],
    exercise: str,
    scenario: str,
    confirm: bool,
    format_type: str
) -> None:
    """Clear CTF scenario annotations.

    Remove CTF properties from resources matching the scenario.

    Examples:

        # Clear specific scenario
        atg ctf clear --exercise M003 --scenario v2-cert

        # Clear without confirmation
        atg ctf clear --exercise M003 --scenario v2-cert --no-confirm
    """
    try:
        _, deploy_service, _ = get_services()

        if confirm:
            click.confirm(
                f"Are you sure you want to clear {exercise}/{scenario}?",
                abort=True
            )

        # Remove CTF properties from resources
        query = """
        MATCH (r:Resource)
        WHERE r.ctf_exercise = $exercise
          AND r.ctf_scenario = $scenario
        """

        params = {
            "exercise": exercise,
            "scenario": scenario
        }

        if layer_id:
            query += " AND r.layer_id = $layer_id"
            params["layer_id"] = layer_id

        query += """
        REMOVE r.ctf_exercise, r.ctf_scenario, r.ctf_role
        RETURN count(r) AS cleared_count
        """

        result_records, _, _ = deploy_service.neo4j_driver.execute_query(query, **params)

        cleared_count = result_records[0]["cleared_count"] if result_records else 0

        if format_type == "json":
            click.echo(json.dumps({"cleared_count": cleared_count}, indent=2))
        else:
            click.echo(f"\nCleared {cleared_count} resources from {exercise}/{scenario}")

    except Exception as e:
        logger.error(f"CTF clear failed: {e}")
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


__all__ = ["ctf"]
