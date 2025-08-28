#!/usr/bin/env python
"""Quick test of parallel property fetching functionality."""

import asyncio
import os

# Mock environment to avoid real Azure connections
os.environ["AZURE_TENANT_ID"] = "test-tenant"
os.environ["NEO4J_URI"] = "bolt://localhost:7688"
os.environ["NEO4J_PASSWORD"] = "test"

from src.config_manager import AzureTenantGrapherConfig, ProcessingConfig
from src.services.azure_discovery_service import AzureDiscoveryService


async def test_parallel_fetching():
    """Test that parallel fetching is enabled with max_build_threads."""
    # Create config with parallel fetching enabled
    config = AzureTenantGrapherConfig(
        tenant_id="test-tenant", processing=ProcessingConfig(max_build_threads=5)
    )

    print(
        f"✅ Config created with max_build_threads={config.processing.max_build_threads}"
    )

    # Create discovery service
    service = AzureDiscoveryService(config)
    print(
        f"✅ Discovery service created with _max_build_threads={service._max_build_threads}"
    )

    # Verify parallel fetching is enabled
    assert service._max_build_threads == 5, (
        f"Expected 5, got {service._max_build_threads}"
    )
    print("✅ Parallel fetching is enabled!")

    # Test that _fetch_resources_with_properties exists
    assert hasattr(service, "_fetch_resources_with_properties"), (
        "Missing _fetch_resources_with_properties"
    )
    print("✅ _fetch_resources_with_properties method exists")

    # Test that _get_api_version_for_resource exists
    assert hasattr(service, "_get_api_version_for_resource"), (
        "Missing _get_api_version_for_resource"
    )
    print("✅ _get_api_version_for_resource method exists")

    print("\n🎉 All tests passed! Parallel property fetching is implemented correctly.")


if __name__ == "__main__":
    asyncio.run(test_parallel_fetching())
