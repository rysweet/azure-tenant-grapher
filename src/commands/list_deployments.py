"""List deployments command for viewing registered IaC deployments.

This module provides the CLI command for listing all registered deployments.
"""

import json
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ..deployment_registry import DeploymentRegistry, DeploymentStatus

console = Console()


@click.command()
@click.option(
    '--tenant',
    help='Filter by tenant'
)
@click.option(
    '--status',
    type=click.Choice(['active', 'destroyed', 'failed', 'all']),
    default='active',
    help='Filter by deployment status'
)
@click.option(
    '--json',
    'output_json',
    is_flag=True,
    help='Output as JSON'
)
def list_deployments(tenant: str, status: str, output_json: bool) -> None:
    """List all registered IaC deployments.
    
    This command shows deployments tracked in the deployment registry,
    including their status, resources, and directories.
    
    Examples:
        atg list-deployments
        atg list-deployments --status all
        atg list-deployments --tenant tenant-2 --json
    """
    registry = DeploymentRegistry()
    
    # Get deployments based on filters
    if status == 'all':
        deployments = registry.list_deployments(tenant=tenant)
    else:
        status_enum = DeploymentStatus(status)
        deployments = registry.list_deployments(tenant=tenant, status=status_enum)
    
    if not deployments:
        click.echo("No deployments found matching the criteria.")
        return
    
    # JSON output
    if output_json:
        click.echo(json.dumps(deployments, indent=2, default=str))
        return
    
    # Create rich table
    table = Table(title="Registered Deployments")
    table.add_column("ID", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Tenant")
    table.add_column("Resources")
    table.add_column("Deployed At")
    table.add_column("Directory", style="dim")
    
    for dep in deployments:
        # Format status with color
        status_str = dep['status']
        if status_str == 'active':
            status_str = f"[green]{status_str}[/green]"
        elif status_str == 'destroyed':
            status_str = f"[dim]{status_str}[/dim]"
        elif status_str == 'failed':
            status_str = f"[red]{status_str}[/red]"
        
        # Count total resources
        resource_count = sum(dep.get('resources', {}).values())
        resource_str = f"{resource_count} resources"
        
        # Format timestamp
        deployed_at = dep.get('deployed_at', '')
        if deployed_at:
            try:
                dt = datetime.fromisoformat(deployed_at)
                deployed_at = dt.strftime("%Y-%m-%d %H:%M")
            except:
                pass
        
        # Shorten directory path if too long
        directory = dep.get('directory', '')
        if len(directory) > 40:
            directory = "..." + directory[-37:]
        
        table.add_row(
            dep['id'],
            status_str,
            dep.get('tenant', ''),
            resource_str,
            deployed_at,
            directory
        )
    
    console.print(table)
    
    # Show summary
    active_count = sum(1 for d in deployments if d['status'] == 'active')
    if active_count > 0:
        console.print(f"\n💡 {active_count} active deployment(s) can be destroyed using 'atg undeploy'")