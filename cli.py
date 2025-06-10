#!/usr/bin/env python3
"""
Enhanced CLI wrapper for Azure Tenant Grapher

This script provides an improved command-line interface with better error handling,
configuration validation, and progress tracking.
"""

import asyncio
import sys
import os
import logging
from typing import Optional

# Add the current directory to the path for imports
sys.path.append(os.path.dirname(__file__))

try:
    import click
    from config_manager import create_config_from_env, setup_logging
    from azure_tenant_grapher import AzureTenantGrapher
    from container_manager import Neo4jContainerManager
    from graph_visualizer import GraphVisualizer
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Please ensure all required packages are installed:")
    print("pip install -r requirements.txt")
    sys.exit(1)


@click.group()
@click.option('--log-level', default='INFO', help='Logging level (DEBUG, INFO, WARNING, ERROR)')
@click.pass_context
def cli(ctx, log_level):
    """Azure Tenant Grapher - Enhanced CLI for building Neo4j graphs of Azure resources."""
    ctx.ensure_object(dict)
    ctx.obj['log_level'] = log_level.upper()


@cli.command()
@click.option('--tenant-id', required=True, help='Azure tenant ID')
@click.option('--resource-limit', type=int, help='Maximum number of resources to process (for testing)')
@click.option('--batch-size', type=int, default=5, help='Number of resources to process in parallel (default: 5)')
@click.option('--no-container', is_flag=True, help='Do not auto-start Neo4j container')
@click.option('--generate-spec', is_flag=True, help='Generate tenant specification after graph building')
@click.option('--visualize', is_flag=True, help='Generate graph visualization after building')
@click.pass_context
async def build(ctx, tenant_id, resource_limit, batch_size, no_container, generate_spec, visualize):
    """Build the complete Azure tenant graph with enhanced processing."""
    
    try:
        # Create and validate configuration
        config = create_config_from_env(tenant_id, resource_limit)
        config.processing.batch_size = batch_size
        config.processing.auto_start_container = not no_container
        config.logging.level = ctx.obj['log_level']
        
        # Setup logging
        setup_logging(config.logging)
        
        # Validate configuration
        config.validate_all()
        
        logger = logging.getLogger(__name__)
        
        # Create and run the grapher
        grapher = AzureTenantGrapher(config)
        
        logger.info("🚀 Starting Azure Tenant Graph building...")
        result = await grapher.build_graph()
        
        if result.get('success', False):
            click.echo("🎉 Graph building completed successfully!")
            click.echo(f"📊 Summary:")
            click.echo(f"   - Subscriptions: {result.get('subscriptions', 0)}")
            click.echo(f"   - Total Resources: {result.get('total_resources', 0)}")
            click.echo(f"   - Successful: {result.get('successful_resources', 0)}")
            click.echo(f"   - Failed: {result.get('failed_resources', 0)}")
            
            if 'skipped_resources' in result:
                click.echo(f"   - Skipped: {result['skipped_resources']}")
            if 'llm_descriptions_generated' in result:
                click.echo(f"   - LLM Descriptions: {result['llm_descriptions_generated']}")
            
            click.echo(f"   - Success Rate: {result.get('success_rate', 0):.1f}%")
            
            # Generate visualization if requested
            if visualize:
                try:
                    click.echo("🎨 Generating graph visualization...")
                    visualizer = GraphVisualizer(
                        config.neo4j.uri, 
                        config.neo4j.user, 
                        config.neo4j.password
                    )
                    viz_path = await visualizer.create_interactive_visualization()
                    click.echo(f"✅ Visualization saved to: {viz_path}")
                except Exception as e:
                    click.echo(f"❌ Failed to generate visualization: {e}", err=True)
            
            # Generate tenant specification if requested and LLM is available
            if generate_spec and config.azure_openai.is_configured():
                try:
                    click.echo("📋 Generating tenant specification...")
                    await grapher.generate_tenant_specification()
                    click.echo("✅ Tenant specification generated successfully")
                except Exception as e:
                    click.echo(f"❌ Failed to generate tenant specification: {e}", err=True)
            elif generate_spec:
                click.echo("⚠️ Tenant specification requires Azure OpenAI configuration", err=True)
        else:
            click.echo(f"❌ Graph building failed: {result.get('error', 'Unknown error')}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--tenant-id', required=True, help='Azure tenant ID')
@click.option('--limit', type=int, default=50, help='Maximum number of resources to process (default: 50)')
@click.pass_context
async def test(ctx, tenant_id, limit):
    """Run a test with limited resources to validate setup."""
    
    click.echo(f"🧪 Running test mode with up to {limit} resources...")
    
    ctx.invoke(build, 
              tenant_id=tenant_id, 
              resource_limit=limit, 
              batch_size=3, 
              no_container=False, 
              generate_spec=False, 
              visualize=False)


@cli.command()
def container():
    """Manage Neo4j container."""
    
    @click.group()
    def container_group():
        pass
    
    @container_group.command()
    def start():
        """Start Neo4j container."""
        container_manager = Neo4jContainerManager()
        if container_manager.setup_neo4j():
            click.echo("✅ Neo4j container started successfully")
        else:
            click.echo("❌ Failed to start Neo4j container", err=True)
            sys.exit(1)
    
    @container_group.command()
    def stop():
        """Stop Neo4j container."""
        container_manager = Neo4jContainerManager()
        if container_manager.stop_neo4j():
            click.echo("✅ Neo4j container stopped successfully")
        else:
            click.echo("❌ Failed to stop Neo4j container", err=True)
            sys.exit(1)
    
    @container_group.command()
    def status():
        """Check Neo4j container status."""
        container_manager = Neo4jContainerManager()
        if container_manager.is_neo4j_container_running():
            click.echo("✅ Neo4j container is running")
        else:
            click.echo("⏹️ Neo4j container is not running")
    
    return container_group


@cli.command()
@click.option('--tenant-id', required=True, help='Azure tenant ID')
@click.pass_context
async def spec(ctx, tenant_id):
    """Generate only the tenant specification (requires existing graph)."""
    
    try:
        # Create configuration
        config = create_config_from_env(tenant_id)
        config.logging.level = ctx.obj['log_level']
        
        # Setup logging
        setup_logging(config.logging)
        
        # Validate Azure OpenAI configuration
        if not config.azure_openai.is_configured():
            click.echo("❌ Azure OpenAI not configured. Tenant specification requires LLM capabilities.", err=True)
            sys.exit(1)
        
        # Create grapher and generate specification
        grapher = AzureTenantGrapher(config)
        
        click.echo("📋 Generating tenant specification from existing graph...")
        await grapher.generate_tenant_specification()
        click.echo("✅ Tenant specification generated successfully")
        
    except Exception as e:
        click.echo(f"❌ Failed to generate specification: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--tenant-id', required=True, help='Azure tenant ID')
@click.pass_context
async def visualize(ctx, tenant_id):
    """Generate graph visualization from existing data."""
    
    try:
        # Create configuration
        config = create_config_from_env(tenant_id)
        config.logging.level = ctx.obj['log_level']
        
        # Setup logging
        setup_logging(config.logging)
        
        # Create visualizer
        visualizer = GraphVisualizer(
            config.neo4j.uri, 
            config.neo4j.user, 
            config.neo4j.password
        )
        
        click.echo("🎨 Generating graph visualization...")
        viz_path = await visualizer.create_interactive_visualization()
        click.echo(f"✅ Visualization saved to: {viz_path}")
        
    except Exception as e:
        click.echo(f"❌ Failed to generate visualization: {e}", err=True)
        sys.exit(1)


@cli.command()
def config():
    """Show current configuration (without sensitive data)."""
    
    try:
        # Create dummy configuration to show structure
        config = create_config_from_env("example-tenant-id")
        
        click.echo("🔧 Current Configuration Template:")
        click.echo("=" * 60)
        
        config_dict = config.to_dict()
        
        def print_dict(d, indent=0):
            for key, value in d.items():
                if isinstance(value, dict):
                    click.echo("  " * indent + f"{key}:")
                    print_dict(value, indent + 1)
                else:
                    click.echo("  " * indent + f"{key}: {value}")
        
        print_dict(config_dict)
        click.echo("=" * 60)
        click.echo("💡 Set environment variables to customize configuration")
        
    except Exception as e:
        click.echo(f"❌ Failed to display configuration: {e}", err=True)


@cli.command()
@click.option('--tenant-id', required=True, help='Azure tenant ID')
@click.pass_context
async def progress(ctx, tenant_id):
    """Check processing progress in the database."""
    
    try:
        # Import and run the progress checker
        from check_progress import main as check_progress_main
        
        config = create_config_from_env(tenant_id)
        config.logging.level = ctx.obj['log_level']
        setup_logging(config.logging)
        
        click.echo("📊 Checking processing progress...")
        await check_progress_main()
        
    except ImportError:
        click.echo("❌ Progress checker not available", err=True)
    except Exception as e:
        click.echo(f"❌ Failed to check progress: {e}", err=True)


def main():
    """Main entry point that handles asyncio properly."""
    
    # Check if we need to run async commands
    async_commands = ['build', 'test', 'spec', 'visualize', 'progress']
    
    if len(sys.argv) > 1 and sys.argv[1] in async_commands:
        # Extract the command and create a new CLI instance for async execution
        import inspect
        
        # Get the command function
        cmd_name = sys.argv[1]
        cmd_func = None
        
        for name, func in cli.commands.items():
            if name == cmd_name:
                cmd_func = func
                break
        
        if cmd_func and inspect.iscoroutinefunction(cmd_func.callback):
            # Run async command
            asyncio.run(cli())
        else:
            # Run sync command
            cli()
    else:
        # Run normal CLI
        cli()


if __name__ == "__main__":
    main()
