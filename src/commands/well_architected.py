"""Well-Architected Framework report command.

This module provides the 'report well-architected' command for generating
comprehensive Azure Well-Architected Framework (WAF) analysis reports.

Issue #716: Complete CLI command migration
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.commands.base import async_command
from src.config_manager import create_neo4j_config_from_env, setup_logging
from src.utils.neo4j_startup import ensure_neo4j_running
from src.well_architected_reporter import WellArchitectedReporter


@click.command("well-architected")
@click.option(
    "--output-dir",
    type=click.Path(),
    help="Output directory for results (default: outputs/well_architected_report_<timestamp>)",
)
@click.option(
    "--no-visualizations",
    is_flag=True,
    help="Skip generating matplotlib visualizations",
)
@click.option(
    "--skip-description-updates",
    is_flag=True,
    help="Skip updating Neo4j resource descriptions with WAF links",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def well_architected_report(
    ctx: click.Context,
    output_dir: Optional[str],
    no_visualizations: bool,
    skip_description_updates: bool,
    no_container: bool,
) -> None:
    """Generate Azure Well-Architected Framework analysis report.

    This command generates a comprehensive WAF report including:
    - Pattern analysis with WAF insights
    - Markdown report documenting findings
    - Interactive Jupyter notebook for exploration
    - Resource description updates with WAF links (optional)
    - Visualization charts (optional)

    The report evaluates your architecture against the five pillars:
    - Cost Optimization
    - Operational Excellence
    - Performance Efficiency
    - Reliability
    - Security

    Examples:
        # Generate full report
        atg report well-architected

        # Custom output directory
        atg report well-architected --output-dir my-waf-report

        # Skip Neo4j updates
        atg report well-architected --skip-description-updates

        # Skip visualizations (faster, no matplotlib required)
        atg report well-architected --no-visualizations
    """
    await well_architected_report_command_handler(
        ctx, output_dir, no_visualizations, skip_description_updates, no_container
    )


async def well_architected_report_command_handler(
    ctx: click.Context,
    output_dir: Optional[str] = None,
    no_visualizations: bool = False,
    skip_description_updates: bool = False,
    no_container: bool = False,
) -> None:
    """
    Handle the well-architected report command logic.

    Generates a comprehensive Well-Architected Framework report including:
    - Pattern analysis with WAF insights
    - Markdown report
    - Interactive Jupyter notebook
    - Resource description updates with WAF links

    Args:
        ctx: Click context
        output_dir: Output directory for results
        no_visualizations: Skip generating matplotlib visualizations
        skip_description_updates: Skip updating Neo4j resource descriptions
        no_container: Do not auto-start Neo4j container
    """
    console = Console()

    ensure_neo4j_running()

    try:
        # Create configuration (Neo4j-only)
        config = create_neo4j_config_from_env()
        config.logging.level = ctx.obj["log_level"]

        # Setup logging
        setup_logging(config.logging)

        # Determine output directory
        if output_dir:
            output_path = Path(output_dir)
        else:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path("outputs") / f"well_architected_report_{ts}"

        output_path.mkdir(parents=True, exist_ok=True)

        console.print(
            Panel.fit(
                "[bold blue]🏗️  Azure Well-Architected Framework Analysis[/bold blue]\n"
                f"Output directory: {output_path}",
                border_style="blue",
            )
        )

        # Get OpenAI API key if available
        openai_api_key = os.environ.get("OPENAI_API_KEY")

        # Create reporter
        reporter = WellArchitectedReporter(
            config.neo4j.uri or "",
            config.neo4j.user,
            config.neo4j.password,
            openai_api_key,
        )

        # Run analysis
        console.print("\n[yellow]⚙️  Analyzing architectural patterns...[/yellow]")

        with console.status(
            "[bold green]Generating Well-Architected Framework report..."
        ):
            summary = reporter.generate_full_report(
                output_path,
                update_descriptions=not skip_description_updates,
                generate_visualizations=not no_visualizations,
            )

        # Display summary
        console.print("\n[bold green]✅ Report Generated![/bold green]\n")

        # Summary statistics table
        stats_table = Table(title="Report Summary", show_header=True)
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="magenta")

        stats_table.add_row("Patterns Detected", str(summary["patterns_detected"]))
        stats_table.add_row(
            "Total Relationships Analyzed", f"{summary['total_relationships']:,}"
        )
        if not skip_description_updates:
            stats_table.add_row(
                "Resources Updated", f"{summary['resources_updated']:,}"
            )

        console.print(stats_table)

        # Output files
        console.print("\n[bold]📁 Output Files:[/bold]")
        console.print(
            f"  • Markdown Report: [cyan]{summary['output_files']['markdown']}[/cyan]"
        )
        console.print(
            f"  • Interactive Notebook: [cyan]{summary['output_files']['notebook']}[/cyan]"
        )
        console.print(f"  • JSON Data: [cyan]{summary['output_files']['json']}[/cyan]")

        if summary["output_files"]["visualizations"]:
            console.print("  • Visualizations:")
            for viz_file in summary["output_files"]["visualizations"]:
                console.print(str(f"    - [cyan]{viz_file}[/cyan]"))

        console.print(
            f"\n[bold green]✨ Report complete! Results saved to: {output_path}[/bold green]"
        )

        console.print("\n[bold]📓 To view the interactive notebook:[/bold]")
        console.print(str(f"  cd {output_path.parent}"))
        console.print(
            f"  jupyter notebook {output_path.name}/well_architected_analysis.ipynb"
        )

    except ImportError as e:
        if "matplotlib" in str(e) or "scipy" in str(e):
            console.print(
                Panel.fit(
                    "[bold red]❌ Missing Dependencies[/bold red]\n\n"
                    "The visualization feature requires matplotlib and scipy.\n"
                    "Install them with:\n\n"
                    "[yellow]uv pip install matplotlib scipy[/yellow]\n\n"
                    "Or run without visualizations:\n"
                    "[yellow]atg report well-architected --no-visualizations[/yellow]",
                    border_style="red",
                )
            )
        else:
            console.print(str(f"[red]❌ Import error: {e}[/red]"))
        sys.exit(1)
    except Exception as e:
        console.print(str(f"[red]❌ Failed to generate report: {e}[/red]"))
        import traceback

        traceback.print_exc()
        sys.exit(1)


# For backward compatibility
well_architected_report_command = well_architected_report

__all__ = ["well_architected_report", "well_architected_report_command_handler"]
