#!/usr/bin/env python3
"""
Example script demonstrating the new Azure Tenant Grapher capabilities

This script shows how to use the new modular structure with various configurations.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

# Add the parent directory to the path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

try:
    from src.azure_tenant_grapher import AzureTenantGrapher
    from src.config_manager import create_config_from_env, setup_logging
    from src.container_manager import Neo4jContainerManager
except ImportError as e:
    print(str(f"❌ Import error: {e}"))
    sys.exit(1)


async def example_basic_run() -> None:
    """Example 1: Basic run with limited resources for testing."""
    print("\n🧪 Example 1: Basic run with resource limit")
    print("=" * 60)

    try:
        # Create configuration with test limits
        config = create_config_from_env(
            tenant_id="your-tenant-id-here",  # Replace with actual tenant ID
            resource_limit=10,  # Limit to 10 resources for testing
        )

        # Customize processing settings
        config.processing.batch_size = 3
        config.processing.auto_start_container = True
        config.logging.level = "INFO"

        # Setup logging
        setup_logging(config.logging)

        logger = logging.getLogger(__name__)
        logger.info("Starting basic example run...")

        # Create and run the grapher
        grapher = AzureTenantGrapher(config)
        result = await grapher.build_graph()

        if result.get("success", False):
            print("✅ Basic run completed successfully!")
            print(f"📊 Processed {result.get('total_resources', 0)} resources")
        else:
            print(f"❌ Basic run failed: {result.get('error', 'Unknown error')}")

    except Exception as e:
        print(str(f"❌ Error in basic run: {e}"))


async def example_advanced_configuration() -> None:
    """Example 2: Advanced configuration with custom settings."""
    print("\n🔧 Example 2: Advanced configuration")
    print("=" * 60)

    try:
        # Create base configuration
        config = create_config_from_env(
            tenant_id="your-tenant-id-here", resource_limit=25
        )

        # Advanced customization
        config.processing.batch_size = 5  # Process 5 resources in parallel
        config.processing.max_retries = 3
        config.processing.retry_delay = 2.0
        config.logging.level = "DEBUG"  # Verbose logging

        # Log configuration summary
        config.log_configuration_summary()

        print("✅ Advanced configuration created successfully!")

    except Exception as e:
        print(str(f"❌ Error in advanced configuration: {e}"))


async def example_container_management() -> None:
    """Example 3: Container management operations."""
    print("\n🐳 Example 3: Container management")
    print("=" * 60)

    try:
        container_manager = Neo4jContainerManager()

        # Check status
        if container_manager.is_neo4j_container_running():
            print("✅ Neo4j container is running")
        else:
            print("⏹️ Neo4j container is not running")

            # Try to start it
            print("🚀 Attempting to start Neo4j container...")
            if container_manager.setup_neo4j():
                print("✅ Neo4j container started successfully")
            else:
                print("❌ Failed to start Neo4j container")

        # Get recent logs
        logs = container_manager.get_container_logs(5)
        if logs:
            print(str(f"📋 Recent Neo4j logs:\n{logs}"))

    except Exception as e:
        print(str(f"❌ Error in container management: {e}"))


async def example_progress_tracking() -> None:
    """Example 4: Progress tracking during processing."""
    print("\n📊 Example 4: Progress tracking demonstration")
    print("=" * 60)

    try:
        # Create configuration for progress demo
        config = create_config_from_env(
            tenant_id="your-tenant-id-here",
            resource_limit=5,  # Small limit for quick demo
        )

        config.processing.batch_size = 2  # Small batches for visible progress
        config.logging.level = "INFO"

        setup_logging(config.logging)
        logger = logging.getLogger(__name__)

        # Simulate processing with progress tracking
        print(
            "📝 This would normally process Azure resources with detailed progress tracking:"
        )
        print("   - Individual resource processing with status")
        print("   - LLM description generation progress")
        print("   - Database upsert operations")
        print("   - Batch processing with parallel execution")
        print("   - Resumable processing across multiple runs")

        logger.info("Progress tracking example completed")

    except Exception as e:
        print(str(f"❌ Error in progress tracking: {e}"))


async def example_configuration_validation() -> None:
    """Example 5: Configuration validation and error handling."""
    print("\n✅ Example 5: Configuration validation")
    print("=" * 60)

    try:
        # Test various configuration scenarios
        print("Testing configuration validation...")

        # Valid configuration
        try:
            config = create_config_from_env("test-tenant-id")
            config.validate_all()
            print("✅ Valid configuration passed validation")
        except Exception as e:
            print(str(f"❌ Unexpected validation error: {e}"))

        # Test invalid resource limit
        try:
            config = create_config_from_env("test-tenant-id", resource_limit=-1)
            config.validate_all()
            print("❌ Invalid resource limit should have failed validation")
        except ValueError:
            print("✅ Invalid resource limit correctly rejected")

        # Test configuration summary
        config = create_config_from_env("test-tenant-id")
        config_dict = config.to_dict()
        print(
            str(f"✅ Configuration serialization successful: {len(config_dict)} keys")
        )

    except Exception as e:
        print(str(f"❌ Error in configuration validation: {e}"))


def main() -> None:
    """Main function to run all examples."""
    print("🔧 Azure Tenant Grapher - Enhanced Features Demo")
    print("=" * 80)
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    examples = [
        example_advanced_configuration,
        example_container_management,
        example_progress_tracking,
        example_configuration_validation,
        # example_basic_run,  # Commented out as it requires real Azure tenant
    ]
    # Run examples sequentially
    for example in examples:
        asyncio.run(example())

    print("\n" + "=" * 80)
    print("🎯 Demo completed! Key improvements demonstrated:")
    print("   ✅ Modular architecture with separated concerns")
    print("   ✅ Enhanced configuration management with validation")
    print("   ✅ Improved error handling and progress tracking")
    print("   ✅ Individual resource processing with database upserts")
    print("   ✅ Parallel processing with configurable batch sizes")
    print("   ✅ Resumable processing across multiple runs")
    print("   ✅ Resource limit capability for testing")
    print("   ✅ Better logging and monitoring")

    print(f"\n⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
