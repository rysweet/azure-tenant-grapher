"""
End-to-End Tests for Azure Sentinel and Log Analytics Automation (Issue #518)

Tests for complete workflows with real Azure resources (requires Azure credentials).

Testing pyramid: 10% E2E tests (complete workflows)

All tests marked as @pytest.mark.slow and @pytest.mark.e2e
All tests will FAIL until implementation exists - this is TDD methodology.

IMPORTANT: These tests require:
- Valid Azure credentials (service principal or user)
- AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
- Sufficient permissions to create Log Analytics workspaces and enable Sentinel
- Neo4j database running
"""

import os
from pathlib import Path
from typing import Dict

import pytest

from src.commands.sentinel import (
    SentinelConfig,
    setup_sentinel_command,
)

# ============================================================================
# E2E Test Fixtures
# ============================================================================


@pytest.fixture
def azure_credentials():
    """Check for required Azure credentials."""
    required_vars = [
        "AZURE_TENANT_ID",
        "AZURE_SUBSCRIPTION_ID",
        "AZURE_CLIENT_ID",
        "AZURE_CLIENT_SECRET",
    ]

    missing = [var for var in required_vars if not os.environ.get(var)]

    if missing:
        pytest.skip(f"Missing required environment variables: {', '.join(missing)}")

    return {
        "tenant_id": os.environ["AZURE_TENANT_ID"],
        "subscription_id": os.environ["AZURE_SUBSCRIPTION_ID"],
        "client_id": os.environ["AZURE_CLIENT_ID"],
        "client_secret": os.environ["AZURE_CLIENT_SECRET"],
    }


@pytest.fixture
def neo4j_with_real_data(neo4j_container):
    """Neo4j database with real scanned Azure data."""
    from neo4j import GraphDatabase

    uri, user, password = neo4j_container

    # Check if database has been populated with real data
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as session:
            result = session.run("MATCH (r:Resource) RETURN count(r) as count")
            record = result.single()
            resource_count = record["count"] if record else 0

            if resource_count == 0:
                pytest.skip(
                    "Neo4j database is empty. Run 'atg scan' first to populate with real data."
                )

        return driver
    except Exception as e:
        pytest.skip(f"Neo4j database not accessible: {e}")


# ============================================================================
# Standalone E2E Tests
# ============================================================================


@pytest.mark.slow
@pytest.mark.e2e
@pytest.mark.asyncio
class TestStandaloneE2E:
    """Test standalone Sentinel setup command with real Azure resources."""

    async def test_standalone_setup_sentinel_full_workflow(
        self,
        azure_credentials: Dict[str, str],
        tmp_path: Path,
    ):
        """
        Test complete standalone Sentinel setup workflow.

        This test:
        1. Discovers resources from Azure API
        2. Creates Log Analytics workspace
        3. Enables Sentinel
        4. Configures data connectors
        5. Sets up diagnostic settings for discovered resources

        WARNING: This will create real Azure resources and may incur costs.
        """
        config = SentinelConfig(
            tenant_id=azure_credentials["tenant_id"],
            subscription_id=azure_credentials["subscription_id"],
            workspace_name=f"test-sentinel-{os.urandom(4).hex()}",  # Unique name
            resource_group=f"test-sentinel-rg-{os.urandom(4).hex()}",
            location="eastus",
            retention_days=30,  # Minimum to reduce costs
            sku="PerGB2018",
        )

        try:
            # Execute full setup
            result = await setup_sentinel_command(
                tenant_id=config.tenant_id,
                subscription_id=config.subscription_id,
                workspace_name=config.workspace_name,
                resource_group=config.resource_group,
                location=config.location,
                retention_days=config.retention_days,
                sku=config.sku,
                discovery_strategy="azure_api",
                strict=True,
            )

            # Verify results
            assert result["success"] is True
            assert "workspace_id" in result
            assert "sentinel_enabled" in result
            assert result["sentinel_enabled"] is True

            # Verify workspace was created
            from azure.identity import ClientSecretCredential
            from azure.mgmt.loganalytics import LogAnalyticsManagementClient

            credential = ClientSecretCredential(
                tenant_id=azure_credentials["tenant_id"],
                client_id=azure_credentials["client_id"],
                client_secret=azure_credentials["client_secret"],
            )

            la_client = LogAnalyticsManagementClient(
                credential=credential,
                subscription_id=config.subscription_id,
            )

            workspace = la_client.workspaces.get(
                resource_group_name=config.resource_group,
                workspace_name=config.workspace_name,
            )

            assert workspace.name == config.workspace_name
            assert workspace.location == config.location
            assert workspace.sku.name == config.sku
            assert workspace.retention_in_days == config.retention_days

        finally:
            # Cleanup: Delete test resources
            from azure.identity import ClientSecretCredential
            from azure.mgmt.resource import ResourceManagementClient

            credential = ClientSecretCredential(
                tenant_id=azure_credentials["tenant_id"],
                client_id=azure_credentials["client_id"],
                client_secret=azure_credentials["client_secret"],
            )

            resource_client = ResourceManagementClient(
                credential=credential,
                subscription_id=config.subscription_id,
            )

            try:
                # Delete resource group (and all resources in it)
                poller = resource_client.resource_groups.begin_delete(
                    resource_group_name=config.resource_group
                )
                poller.wait()
            except Exception as cleanup_error:
                print(f"Warning: Cleanup failed: {cleanup_error}")

    async def test_standalone_setup_with_neo4j_discovery(
        self,
        azure_credentials: Dict[str, str],
        neo4j_with_real_data,
        tmp_path: Path,
    ):
        """
        Test Sentinel setup using Neo4j for resource discovery.

        This test requires that 'atg scan' has been run previously to populate
        the Neo4j database with Azure resources.
        """
        config = SentinelConfig(
            tenant_id=azure_credentials["tenant_id"],
            subscription_id=azure_credentials["subscription_id"],
            workspace_name=f"test-sentinel-neo4j-{os.urandom(4).hex()}",
            resource_group=f"test-sentinel-rg-{os.urandom(4).hex()}",
            location="eastus",
            retention_days=30,
        )

        try:
            # Execute setup with Neo4j discovery
            result = await setup_sentinel_command(
                tenant_id=config.tenant_id,
                subscription_id=config.subscription_id,
                workspace_name=config.workspace_name,
                resource_group=config.resource_group,
                location=config.location,
                retention_days=config.retention_days,
                discovery_strategy="neo4j",  # Use Neo4j for discovery
                neo4j_driver=neo4j_with_real_data,
                strict=True,
            )

            assert result["success"] is True
            assert "resources_configured" in result
            assert result["resources_configured"] > 0  # Should find resources in Neo4j

        finally:
            # Cleanup
            from azure.identity import ClientSecretCredential
            from azure.mgmt.resource import ResourceManagementClient

            credential = ClientSecretCredential(
                tenant_id=azure_credentials["tenant_id"],
                client_id=azure_credentials["client_id"],
                client_secret=azure_credentials["client_secret"],
            )

            resource_client = ResourceManagementClient(
                credential=credential,
                subscription_id=config.subscription_id,
            )

            try:
                poller = resource_client.resource_groups.begin_delete(
                    resource_group_name=config.resource_group
                )
                poller.wait()
            except Exception as cleanup_error:
                print(f"Warning: Cleanup failed: {cleanup_error}")

    async def test_idempotency_run_twice(
        self,
        azure_credentials: Dict[str, str],
        tmp_path: Path,
    ):
        """
        Test that running Sentinel setup twice is idempotent.

        Running setup twice should:
        - Detect existing workspace
        - Skip workspace creation
        - Still succeed
        """
        config = SentinelConfig(
            tenant_id=azure_credentials["tenant_id"],
            subscription_id=azure_credentials["subscription_id"],
            workspace_name=f"test-sentinel-idem-{os.urandom(4).hex()}",
            resource_group=f"test-sentinel-rg-{os.urandom(4).hex()}",
            location="eastus",
            retention_days=30,
        )

        try:
            # First run - create everything
            result1 = await setup_sentinel_command(
                tenant_id=config.tenant_id,
                subscription_id=config.subscription_id,
                workspace_name=config.workspace_name,
                resource_group=config.resource_group,
                location=config.location,
                retention_days=config.retention_days,
                discovery_strategy="azure_api",
                strict=True,
            )

            assert result1["success"] is True
            workspace_id_1 = result1["workspace_id"]

            # Second run - should detect existing resources
            result2 = await setup_sentinel_command(
                tenant_id=config.tenant_id,
                subscription_id=config.subscription_id,
                workspace_name=config.workspace_name,
                resource_group=config.resource_group,
                location=config.location,
                retention_days=config.retention_days,
                discovery_strategy="azure_api",
                strict=True,
            )

            assert result2["success"] is True
            workspace_id_2 = result2["workspace_id"]

            # Workspace IDs should match (same workspace)
            assert workspace_id_1 == workspace_id_2

            # Should have skipped workspace creation on second run
            assert result2["workspace_already_exists"] is True

        finally:
            # Cleanup
            from azure.identity import ClientSecretCredential
            from azure.mgmt.resource import ResourceManagementClient

            credential = ClientSecretCredential(
                tenant_id=azure_credentials["tenant_id"],
                client_id=azure_credentials["client_id"],
                client_secret=azure_credentials["client_secret"],
            )

            resource_client = ResourceManagementClient(
                credential=credential,
                subscription_id=config.subscription_id,
            )

            try:
                poller = resource_client.resource_groups.begin_delete(
                    resource_group_name=config.resource_group
                )
                poller.wait()
            except Exception as cleanup_error:
                print(f"Warning: Cleanup failed: {cleanup_error}")


# ============================================================================
# Integrated E2E Tests
# ============================================================================


@pytest.mark.slow
@pytest.mark.e2e
@pytest.mark.asyncio
class TestIntegratedE2E:
    """Test Sentinel integration with generate-iac and create-tenant commands."""

    async def test_integrated_with_generate_iac(
        self,
        azure_credentials: Dict[str, str],
        neo4j_with_real_data,
        tmp_path: Path,
    ):
        """
        Test --setup-sentinel flag with generate-iac command.

        This test:
        1. Generates IaC for tenant
        2. Sets up Sentinel workspace
        3. Configures monitoring for generated resources
        """
        from click.testing import CliRunner
        from scripts.cli import cli

        runner = CliRunner()

        workspace_name = f"test-sentinel-iac-{os.urandom(4).hex()}"
        resource_group = f"test-sentinel-rg-{os.urandom(4).hex()}"

        try:
            result = runner.invoke(
                cli,
                [
                    "generate-iac",
                    "--tenant-id",
                    azure_credentials["tenant_id"],
                    "--setup-sentinel",
                    "--sentinel-workspace-name",
                    workspace_name,
                    "--sentinel-resource-group",
                    resource_group,
                    "--sentinel-location",
                    "eastus",
                    "--output",
                    str(tmp_path / "iac_output"),
                ],
            )

            assert result.exit_code == 0

            # Verify IaC was generated
            iac_dir = tmp_path / "iac_output"
            assert iac_dir.exists()
            assert (iac_dir / "main.tf").exists()

            # Verify Sentinel was set up
            from azure.identity import ClientSecretCredential
            from azure.mgmt.loganalytics import LogAnalyticsManagementClient

            credential = ClientSecretCredential(
                tenant_id=azure_credentials["tenant_id"],
                client_id=azure_credentials["client_id"],
                client_secret=azure_credentials["client_secret"],
            )

            la_client = LogAnalyticsManagementClient(
                credential=credential,
                subscription_id=azure_credentials["subscription_id"],
            )

            workspace = la_client.workspaces.get(
                resource_group_name=resource_group,
                workspace_name=workspace_name,
            )

            assert workspace.name == workspace_name

        finally:
            # Cleanup
            from azure.identity import ClientSecretCredential
            from azure.mgmt.resource import ResourceManagementClient

            credential = ClientSecretCredential(
                tenant_id=azure_credentials["tenant_id"],
                client_id=azure_credentials["client_id"],
                client_secret=azure_credentials["client_secret"],
            )

            resource_client = ResourceManagementClient(
                credential=credential,
                subscription_id=azure_credentials["subscription_id"],
            )

            try:
                poller = resource_client.resource_groups.begin_delete(
                    resource_group_name=resource_group
                )
                poller.wait()
            except Exception as cleanup_error:
                print(f"Warning: Cleanup failed: {cleanup_error}")

    async def test_integrated_with_create_tenant(
        self,
        azure_credentials: Dict[str, str],
        tmp_path: Path,
    ):
        """
        Test --setup-sentinel flag with create-tenant command.

        This test:
        1. Creates tenant from specification
        2. Sets up Sentinel after tenant creation
        3. Configures monitoring for newly created resources
        """
        from click.testing import CliRunner
        from scripts.cli import cli

        # Create minimal spec
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""
# Test Tenant Specification

## Resource Groups
- Name: test-rg-001
- Location: eastus

## Virtual Machines
- Name: test-vm-001
- Resource Group: test-rg-001
- Size: Standard_B1s
- Location: eastus
""")

        workspace_name = f"test-sentinel-tenant-{os.urandom(4).hex()}"
        resource_group = f"test-sentinel-rg-{os.urandom(4).hex()}"

        try:
            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "create-tenant",
                    "--spec",
                    str(spec_file),
                    "--tenant-id",
                    azure_credentials["tenant_id"],
                    "--subscription-id",
                    azure_credentials["subscription_id"],
                    "--setup-sentinel",
                    "--sentinel-workspace-name",
                    workspace_name,
                    "--sentinel-resource-group",
                    resource_group,
                ],
            )

            assert result.exit_code == 0

            # Verify Sentinel was set up after tenant creation
            from azure.identity import ClientSecretCredential
            from azure.mgmt.loganalytics import LogAnalyticsManagementClient

            credential = ClientSecretCredential(
                tenant_id=azure_credentials["tenant_id"],
                client_id=azure_credentials["client_id"],
                client_secret=azure_credentials["client_secret"],
            )

            la_client = LogAnalyticsManagementClient(
                credential=credential,
                subscription_id=azure_credentials["subscription_id"],
            )

            workspace = la_client.workspaces.get(
                resource_group_name=resource_group,
                workspace_name=workspace_name,
            )

            assert workspace.name == workspace_name

            # Verify diagnostic settings were created for the test VM
            # (This would be a more complex check in real implementation)

        finally:
            # Cleanup: Delete both tenant resources and Sentinel resources
            from azure.identity import ClientSecretCredential
            from azure.mgmt.resource import ResourceManagementClient

            credential = ClientSecretCredential(
                tenant_id=azure_credentials["tenant_id"],
                client_id=azure_credentials["client_id"],
                client_secret=azure_credentials["client_secret"],
            )

            resource_client = ResourceManagementClient(
                credential=credential,
                subscription_id=azure_credentials["subscription_id"],
            )

            try:
                # Delete Sentinel resource group
                poller = resource_client.resource_groups.begin_delete(
                    resource_group_name=resource_group
                )
                poller.wait()

                # Delete tenant resource group
                poller = resource_client.resource_groups.begin_delete(
                    resource_group_name="test-rg-001"
                )
                poller.wait()
            except Exception as cleanup_error:
                print(f"Warning: Cleanup failed: {cleanup_error}")
