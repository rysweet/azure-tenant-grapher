"""Architectural pattern analysis command.

This module provides the 'analyze-patterns' command for analyzing
Azure resource graphs to identify architectural patterns.

Issue #716: Complete CLI command migration
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.architectural_pattern_analyzer import ArchitecturalPatternAnalyzer
from src.commands.base import async_command
from src.config_manager import create_neo4j_config_from_env, setup_logging
from src.utils.neo4j_startup import ensure_neo4j_running


@click.command("analyze-patterns")
@click.option(
    "--output-dir",
    type=click.Path(),
    help="Output directory for results (default: outputs/pattern_analysis_<timestamp>)",
)
@click.option(
    "--no-visualizations",
    is_flag=True,
    help="Skip generating matplotlib visualizations",
)
@click.option(
    "--top-n-nodes",
    default=30,
    type=int,
    help="Number of top nodes to include in visualizations (default: 30)",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def analyze_patterns(
    ctx: click.Context,
    output_dir: Optional[str],
    no_visualizations: bool,
    top_n_nodes: int,
    no_container: bool,
) -> None:
    """Analyze Azure resource graph to identify architectural patterns.

    This command analyzes the Neo4j graph database to:
    - Identify common architectural patterns
    - Generate pattern visualizations
    - Export analysis results in multiple formats
    - Detect pattern completeness and recommendations

    Examples:
        # Basic analysis
        atg analyze-patterns

        # Custom output directory
        atg analyze-patterns --output-dir my-analysis

        # Skip visualizations (faster, no matplotlib required)
        atg analyze-patterns --no-visualizations

        # Analyze top 50 nodes
        atg analyze-patterns --top-n-nodes 50
    """
    await analyze_patterns_command_handler(
        ctx, output_dir, no_visualizations, top_n_nodes, no_container
    )


async def analyze_patterns_command_handler(
    ctx: click.Context,
    output_dir: Optional[str] = None,
    no_visualizations: bool = False,
    top_n_nodes: int = 30,
    no_container: bool = False,
) -> None:
    """
    Handle the analyze-patterns command logic.

    Analyzes the Azure resource graph to identify architectural patterns
    and generate visualizations.

    Args:
        ctx: Click context
        output_dir: Output directory for results (default: outputs/pattern_analysis_<timestamp>)
        no_visualizations: Skip generating matplotlib visualizations
        top_n_nodes: Number of top nodes to include in visualizations
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
            output_path = Path("outputs") / f"pattern_analysis_{ts}"

        output_path.mkdir(parents=True, exist_ok=True)

        console.print(
            Panel.fit(
                "[bold blue]🔍 Azure Architectural Pattern Analysis[/bold blue]\n"
                f"Output directory: {output_path}",
                border_style="blue",
            )
        )

        # Create analyzer
        analyzer = ArchitecturalPatternAnalyzer(
            config.neo4j.uri or "",
            config.neo4j.user,
            config.neo4j.password,
        )

        # Run analysis
        console.print("\n[yellow]⚙️  Analyzing resource graph...[/yellow]")

        with console.status("[bold green]Processing relationships..."):
            summary = analyzer.analyze_and_export(
                output_path,
                generate_visualizations=not no_visualizations,
                top_n_nodes=top_n_nodes,
            )

        # Display summary
        console.print("\n[bold green]✅ Analysis Complete![/bold green]\n")

        # Summary statistics table
        stats_table = Table(title="Analysis Statistics", show_header=True)
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="magenta")

        stats_table.add_row(
            "Total Relationships", f"{summary['total_relationships']:,}"
        )
        stats_table.add_row("Unique Patterns", f"{summary['unique_patterns']:,}")
        stats_table.add_row("Resource Types", f"{summary['resource_types']:,}")
        stats_table.add_row("Graph Edges", f"{summary['graph_edges']:,}")
        stats_table.add_row("Detected Patterns", str(summary["detected_patterns"]))

        console.print(stats_table)

        # Top resource types table
        console.print("\n")
        top_types_table = Table(title="Top 10 Resource Types", show_header=True)
        top_types_table.add_column("Resource Type", style="cyan")
        top_types_table.add_column("Connection Count", style="magenta", justify="right")

        for item in summary["top_resource_types"][:10]:
            top_types_table.add_row(item["type"], f"{item['connection_count']:,}")

        console.print(top_types_table)

        # Detected patterns table
        if summary["patterns"]:
            console.print("\n")
            patterns_table = Table(
                title="Detected Architectural Patterns", show_header=True
            )
            patterns_table.add_column("Pattern", style="cyan")
            patterns_table.add_column("Completeness", style="green", justify="right")
            patterns_table.add_column("Matched Resources", style="yellow")
            patterns_table.add_column("Connections", style="magenta", justify="right")

            for pattern_name, pattern_data in list(summary["patterns"].items())[:10]:
                matched = ", ".join(pattern_data["matched_resources"][:3])
                if len(pattern_data["matched_resources"]) > 3:
                    matched += f", +{len(pattern_data['matched_resources']) - 3} more"

                patterns_table.add_row(
                    pattern_name,
                    f"{pattern_data['completeness']:.0f}%",
                    matched,
                    f"{pattern_data['connection_count']:,}",
                )

            console.print(patterns_table)

        # Output files
        console.print("\n[bold]📁 Output Files:[/bold]")
        console.print(
            f"  • JSON Export: [cyan]{summary['output_files']['json']}[/cyan]"
        )
        console.print(
            f"  • Summary Report: [cyan]{output_path / 'analysis_summary.json'}[/cyan]"
        )

        if summary["output_files"]["visualizations"]:
            console.print("  • Visualizations:")
            for viz_file in summary["output_files"]["visualizations"]:
                console.print(str(f"    - [cyan]{viz_file}[/cyan]"))

        console.print(
            f"\n[bold green]✨ Analysis complete! Results saved to: {output_path}[/bold green]"
        )

    except ImportError as e:
        if "matplotlib" in str(e) or "scipy" in str(e):
            console.print(
                Panel.fit(
                    "[bold red]❌ Missing Dependencies[/bold red]\n\n"
                    "The pattern analysis feature requires matplotlib and scipy.\n"
                    "Install them with:\n\n"
                    "[yellow]uv pip install matplotlib scipy[/yellow]\n\n"
                    "Or run without visualizations:\n"
                    "[yellow]atg analyze-patterns --no-visualizations[/yellow]",
                    border_style="red",
                )
            )
        else:
            console.print(str(f"[red]❌ Import error: {e}[/red]"))
        sys.exit(1)
    except Exception as e:
        console.print(str(f"[red]❌ Failed to analyze patterns: {e}[/red]"))
        import traceback

        traceback.print_exc()
        sys.exit(1)


# For backward compatibility
analyze_patterns_command = analyze_patterns

__all__ = ["analyze_patterns", "analyze_patterns_command_handler"]
