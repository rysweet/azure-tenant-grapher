"""Cost management commands.

This module provides commands for Azure cost analysis:
- 'cost-analysis': Analyze Azure costs
- 'cost-forecast': Forecast future costs
- 'cost-report': Generate comprehensive cost reports

Issue #482: CLI Modularization
"""

import sys
from datetime import date, timedelta
from typing import Optional

import click

from src.commands.base import async_command, get_neo4j_config_from_env
from src.utils.neo4j_startup import ensure_neo4j_running


@click.command("cost-analysis")
@click.option(
    "--subscription-id",
    required=True,
    help="Azure subscription ID",
)
@click.option(
    "--resource-group",
    help="Resource group name (optional)",
)
@click.option(
    "--resource-id",
    help="Specific resource ID (optional)",
)
@click.option(
    "--start-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Start date (YYYY-MM-DD)",
)
@click.option(
    "--end-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="End date (YYYY-MM-DD)",
)
@click.option(
    "--granularity",
    type=click.Choice(["daily", "monthly"], case_sensitive=False),
    default="daily",
    help="Data granularity (default: daily)",
)
@click.option(
    "--group-by",
    type=click.Choice(
        ["resource", "resource_group", "service_name", "tag"], case_sensitive=False
    ),
    help="Group results by field",
)
@click.option(
    "--tag-key",
    help="Tag key for grouping (if group-by=tag)",
)
@click.option(
    "--sync",
    is_flag=True,
    help="Sync costs from Azure before querying",
)
@click.pass_context
@async_command
async def cost_analysis(
    ctx: click.Context,
    subscription_id: str,
    resource_group: Optional[str],
    resource_id: Optional[str],
    start_date: Optional[click.DateTime],
    end_date: Optional[click.DateTime],
    granularity: str,
    group_by: Optional[str],
    tag_key: Optional[str],
    sync: bool,
) -> None:
    """Analyze Azure costs for resources tracked in the graph.

    This command queries cost data from Azure Cost Management API and stores it
    in the Neo4j graph database for analysis. You can filter by subscription,
    resource group, or specific resource.

    Examples:

        # Analyze subscription costs for current month with sync
        atg cost-analysis --subscription-id xxx-xxx-xxx --sync

        # Analyze specific resource group costs
        atg cost-analysis --subscription-id xxx-xxx-xxx \\
                          --resource-group my-rg \\
                          --start-date 2025-01-01 \\
                          --end-date 2025-01-31

        # Group costs by service
        atg cost-analysis --subscription-id xxx-xxx-xxx \\
                          --group-by service_name \\
                          --sync
    """
    await cost_analysis_command_handler(
        ctx=ctx,
        subscription_id=subscription_id,
        resource_group=resource_group,
        resource_id=resource_id,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        group_by=group_by,
        tag_key=tag_key,
        sync=sync,
    )


async def cost_analysis_command_handler(
    ctx: click.Context,
    subscription_id: str,
    resource_group: Optional[str],
    resource_id: Optional[str],
    start_date: Optional[click.DateTime],
    end_date: Optional[click.DateTime],
    granularity: str,
    group_by: Optional[str],
    tag_key: Optional[str],
    sync: bool,
) -> None:
    """Analyze Azure costs for resources tracked in the graph."""
    from azure.identity import DefaultAzureCredential
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    from src.models.cost_models import Granularity, TimeFrame
    from src.services.cost_management_service import (
        CostManagementError,
        CostManagementService,
    )

    console = Console()

    # Ensure Neo4j is running
    ensure_neo4j_running()

    # Get Neo4j connection details
    neo4j_uri, neo4j_user, neo4j_password = get_neo4j_config_from_env()

    # Validate group_by and tag_key
    if group_by == "tag" and not tag_key:
        console.print("[red]--tag-key is required when using --group-by=tag[/red]")
        sys.exit(1)

    # Set default dates if not provided
    if not end_date:
        end_date_val = date.today()
    else:
        end_date_val = end_date.date()

    if not start_date:
        start_date_val = end_date_val - timedelta(days=30)
    else:
        start_date_val = start_date.date()

    # Validate date range
    if start_date_val > end_date_val:
        console.print("[red]Start date must be before end date[/red]")
        sys.exit(1)

    # Build scope string
    scope = f"/subscriptions/{subscription_id}"
    if resource_group:
        scope += f"/resourceGroups/{resource_group}"
    if resource_id:
        scope = resource_id

    try:
        # Initialize Neo4j driver
        from neo4j import AsyncGraphDatabase

        driver = AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

        # Initialize Azure credential
        credential = DefaultAzureCredential()

        # Create cost management service
        service = CostManagementService(driver, credential)
        await service.initialize()

        # Sync costs from Azure if requested
        if sync:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task(description="Syncing costs from Azure...", total=None)

                # Fetch and store costs
                costs = await service.fetch_costs(
                    scope=scope,
                    time_frame=TimeFrame.CUSTOM,
                    start_date=start_date_val,
                    end_date=end_date_val,
                    granularity=Granularity.DAILY
                    if granularity == "daily"
                    else Granularity.MONTHLY,
                )

                stored_count = await service.store_costs(costs)
                console.print(
                    f"[green]Synced {stored_count} cost records from Azure[/green]"
                )

        # Query costs from Neo4j
        summary = await service.query_costs(
            scope=scope,
            start_date=start_date_val,
            end_date=end_date_val,
            group_by=group_by,
            tag_key=tag_key,
        )

        # Display summary panel
        summary_text = f"""
[bold]Scope:[/bold] {summary.scope}
[bold]Period:[/bold] {summary.start_date} to {summary.end_date}
[bold]Total Cost:[/bold] {summary.total_cost:.2f} {summary.currency}
[bold]Resources:[/bold] {summary.resource_count}
[bold]Average Daily Cost:[/bold] {summary.average_daily_cost:.2f} {summary.currency}
[bold]Average Cost per Resource:[/bold] {summary.average_cost_per_resource:.2f} {summary.currency}
        """
        console.print(Panel(summary_text, title="Cost Summary", border_style="blue"))

        # Display service breakdown if available
        if summary.service_breakdown:
            table = Table(
                title="Cost by Service", show_header=True, header_style="bold magenta"
            )
            table.add_column("Service", style="cyan")
            table.add_column("Cost", justify="right", style="green")
            table.add_column("Percentage", justify="right", style="yellow")

            sorted_services = sorted(
                summary.service_breakdown.items(), key=lambda x: x[1], reverse=True
            )

            for service_name, cost in sorted_services:
                percentage = (
                    (cost / summary.total_cost * 100) if summary.total_cost > 0 else 0
                )
                table.add_row(
                    service_name, f"{cost:.2f} {summary.currency}", f"{percentage:.1f}%"
                )

            console.print(table)

        # Close connections
        await driver.close()

    except CostManagementError as e:
        console.print(str(f"[red]Cost management error: {e}[/red]"))
        sys.exit(1)
    except Exception as e:
        console.print(str(f"[red]Unexpected error: {e}[/red]"))
        import traceback

        traceback.print_exc()
        sys.exit(1)


@click.command("cost-forecast")
@click.option(
    "--subscription-id",
    required=True,
    help="Azure subscription ID",
)
@click.option(
    "--resource-group",
    help="Resource group name (optional)",
)
@click.option(
    "--days",
    default=30,
    type=int,
    help="Number of days to forecast (default: 30)",
)
@click.option(
    "--output",
    help="Output file path (JSON)",
)
@click.pass_context
@async_command
async def cost_forecast(
    ctx: click.Context,
    subscription_id: str,
    resource_group: Optional[str],
    days: int,
    output: Optional[str],
) -> None:
    """Forecast future costs based on historical trends.

    This command uses historical cost data stored in Neo4j to generate cost
    forecasts using linear regression. Requires at least 14 days of historical
    cost data.

    Examples:

        # Forecast subscription costs for next 30 days
        atg cost-forecast --subscription-id xxx-xxx-xxx

        # Forecast resource group costs for next 90 days
        atg cost-forecast --subscription-id xxx-xxx-xxx \\
                          --resource-group my-rg \\
                          --days 90

        # Export forecast to JSON
        atg cost-forecast --subscription-id xxx-xxx-xxx \\
                          --output forecast.json
    """
    await cost_forecast_command_handler(
        ctx=ctx,
        subscription_id=subscription_id,
        resource_group=resource_group,
        days=days,
        output=output,
    )


async def cost_forecast_command_handler(
    ctx: click.Context,
    subscription_id: str,
    resource_group: Optional[str],
    days: int,
    output: Optional[str],
) -> None:
    """Forecast future costs based on historical trends."""
    import json

    from azure.identity import DefaultAzureCredential
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    from src.services.cost_management_service import (
        CostManagementError,
        CostManagementService,
    )

    console = Console()

    # Ensure Neo4j is running
    ensure_neo4j_running()

    # Get Neo4j connection details
    neo4j_uri, neo4j_user, neo4j_password = get_neo4j_config_from_env()

    # Build scope string
    scope = f"/subscriptions/{subscription_id}"
    if resource_group:
        scope += f"/resourceGroups/{resource_group}"

    try:
        # Initialize Neo4j driver
        from neo4j import AsyncGraphDatabase

        driver = AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

        # Initialize Azure credential
        credential = DefaultAzureCredential()

        # Create cost management service
        service = CostManagementService(driver, credential)
        await service.initialize()

        # Generate forecast
        console.print(str(f"[blue]Forecasting costs for next {days} days...[/blue]"))
        forecasts = await service.forecast_costs(scope, forecast_days=days)

        if not forecasts:
            console.print(
                "[yellow]No forecast data generated (insufficient historical data)[/yellow]"
            )
            await driver.close()
            return

        # Calculate total predicted cost
        total_predicted = sum(f.predicted_cost for f in forecasts)

        # Display summary
        summary_text = f"""
[bold]Scope:[/bold] {scope}
[bold]Forecast Period:[/bold] {days} days
[bold]Total Predicted Cost:[/bold] {total_predicted:.2f} USD
[bold]Average Daily Cost:[/bold] {total_predicted / days:.2f} USD
        """
        console.print(
            Panel(summary_text, title="Forecast Summary", border_style="blue")
        )

        # Display forecast table (first 7 days)
        table = Table(
            title="Cost Forecast (first 7 days)",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Date", style="cyan")
        table.add_column("Predicted Cost", justify="right", style="green")
        table.add_column("Confidence Range", justify="right", style="yellow")

        for forecast in forecasts[:7]:
            table.add_row(
                str(forecast.forecast_date),
                f"{forecast.predicted_cost:.2f} USD",
                f"{forecast.confidence_lower:.2f} - {forecast.confidence_upper:.2f}",
            )

        console.print(table)

        # Write to output file if specified
        if output:
            forecast_data = [
                {
                    "date": f.forecast_date.isoformat(),
                    "predicted_cost": f.predicted_cost,
                    "confidence_lower": f.confidence_lower,
                    "confidence_upper": f.confidence_upper,
                }
                for f in forecasts
            ]
            with open(output, "w") as f:
                json.dump(forecast_data, f, indent=2)
            console.print(str(f"[green]Forecast data written to {output}[/green]"))

        # Close connections
        await driver.close()

    except CostManagementError as e:
        console.print(str(f"[red]Cost management error: {e}[/red]"))
        sys.exit(1)
    except Exception as e:
        console.print(str(f"[red]Unexpected error: {e}[/red]"))
        import traceback

        traceback.print_exc()
        sys.exit(1)


@click.command("cost-report")
@click.option(
    "--subscription-id",
    required=True,
    help="Azure subscription ID",
)
@click.option(
    "--resource-group",
    help="Resource group name (optional)",
)
@click.option(
    "--start-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Start date (YYYY-MM-DD)",
)
@click.option(
    "--end-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="End date (YYYY-MM-DD)",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["markdown", "json"], case_sensitive=False),
    default="markdown",
    help="Output format (default: markdown)",
)
@click.option(
    "--include-forecast/--no-forecast",
    default=True,
    help="Include cost forecast (default: include)",
)
@click.option(
    "--include-anomalies/--no-anomalies",
    default=True,
    help="Include anomaly detection (default: include)",
)
@click.option(
    "--output",
    help="Output file path",
)
@click.pass_context
@async_command
async def cost_report(
    ctx: click.Context,
    subscription_id: str,
    resource_group: Optional[str],
    start_date: Optional[click.DateTime],
    end_date: Optional[click.DateTime],
    format_type: str,
    include_forecast: bool,
    include_anomalies: bool,
    output: Optional[str],
) -> None:
    """Generate comprehensive cost report.

    This command generates a detailed cost report including historical costs,
    optional forecasts, and anomaly detection. Reports can be generated in
    markdown or JSON format.

    Examples:

        # Generate markdown report for current month
        atg cost-report --subscription-id xxx-xxx-xxx

        # Generate detailed report with forecast and anomalies
        atg cost-report --subscription-id xxx-xxx-xxx \\
                        --include-forecast \\
                        --include-anomalies \\
                        --output report.md

        # Generate JSON report for specific period
        atg cost-report --subscription-id xxx-xxx-xxx \\
                        --start-date 2025-01-01 \\
                        --end-date 2025-01-31 \\
                        --format json \\
                        --output report.json
    """
    await cost_report_command_handler(
        ctx=ctx,
        subscription_id=subscription_id,
        resource_group=resource_group,
        start_date=start_date,
        end_date=end_date,
        format_type=format_type,
        include_forecast=include_forecast,
        include_anomalies=include_anomalies,
        output=output,
    )


async def cost_report_command_handler(
    ctx: click.Context,
    subscription_id: str,
    resource_group: Optional[str],
    start_date: Optional[click.DateTime],
    end_date: Optional[click.DateTime],
    format_type: str,
    include_forecast: bool,
    include_anomalies: bool,
    output: Optional[str],
) -> None:
    """Generate comprehensive cost report."""
    from azure.identity import DefaultAzureCredential
    from rich.console import Console

    from src.services.cost_management_service import (
        CostManagementError,
        CostManagementService,
    )

    console = Console()

    # Ensure Neo4j is running
    ensure_neo4j_running()

    # Get Neo4j connection details
    neo4j_uri, neo4j_user, neo4j_password = get_neo4j_config_from_env()

    # Set default dates if not provided
    if not end_date:
        end_date_val = date.today()
    else:
        end_date_val = end_date.date()

    if not start_date:
        start_date_val = end_date_val - timedelta(days=30)
    else:
        start_date_val = start_date.date()

    # Validate date range
    if start_date_val > end_date_val:
        console.print("[red]Start date must be before end date[/red]")
        sys.exit(1)

    # Build scope string
    scope = f"/subscriptions/{subscription_id}"
    if resource_group:
        scope += f"/resourceGroups/{resource_group}"

    try:
        # Initialize Neo4j driver
        from neo4j import AsyncGraphDatabase

        driver = AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

        # Initialize Azure credential
        credential = DefaultAzureCredential()

        # Create cost management service
        service = CostManagementService(driver, credential)
        await service.initialize()

        # Generate report
        console.print("[blue]Generating comprehensive cost report...[/blue]")
        report_content = await service.generate_report(
            scope=scope,
            start_date=start_date_val,
            end_date=end_date_val,
            output_format=format_type,
            include_forecast=include_forecast,
            include_anomalies=include_anomalies,
        )

        # Display or save report
        if output:
            with open(output, "w") as f:
                f.write(report_content)
            console.print(str(f"[green]Report written to {output}[/green]"))
        else:
            # Display to console
            if format_type == "json":
                console.print(report_content)
            else:
                # Pretty print markdown
                from rich.markdown import Markdown

                md = Markdown(report_content)
                console.print(md)

        # Close connections
        await driver.close()

    except CostManagementError as e:
        console.print(str(f"[red]Cost management error: {e}[/red]"))
        sys.exit(1)
    except Exception as e:
        console.print(str(f"[red]Unexpected error: {e}[/red]"))
        import traceback

        traceback.print_exc()
        sys.exit(1)


# For backward compatibility
cost_analysis_command = cost_analysis
cost_forecast_command = cost_forecast
cost_report_command = cost_report

__all__ = [
    "cost_analysis",
    "cost_analysis_command",
    "cost_analysis_command_handler",
    "cost_forecast",
    "cost_forecast_command",
    "cost_forecast_command_handler",
    "cost_report",
    "cost_report_command",
    "cost_report_command_handler",
]
