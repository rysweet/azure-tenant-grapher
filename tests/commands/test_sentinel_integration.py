"""
Integration Tests for Azure Sentinel and Log Analytics Automation (Issue #518)

Tests for Python-to-Bash integration, Neo4j integration, and CLI integration.

Testing pyramid: 30% integration tests (multiple components)

All tests will FAIL until implementation exists - this is TDD methodology.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import Mock, patch

import pytest

from src.commands.sentinel import (
    ResourceDiscovery,
    SentinelConfig,
    SentinelSetupOrchestrator,
    setup_sentinel_command,
)


# ============================================================================
# Python-to-Bash Integration Tests
# ============================================================================


class TestPythonToBashIntegration:
    """Test integration between Python orchestrator and Bash modules."""

    @patch("subprocess.run")
    def test_full_orchestration_success(self, mock_run, tmp_path):
        """Test end-to-end orchestration with mocked bash execution."""
        # Mock successful bash execution for all modules
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Module executed successfully",
            stderr="",
        )

        config = SentinelConfig(
            tenant_id="12345678-1234-1234-1234-123456789012",
            subscription_id="87654321-4321-4321-4321-210987654321",
            workspace_name="test-workspace",
        )

        # Create dummy bash scripts
        scripts_dir = tmp_path / "scripts" / "sentinel"
        scripts_dir.mkdir(parents=True)

        modules = [
            "01-validate-prerequisites.sh",
            "02-create-workspace.sh",
            "03-enable-sentinel.sh",
            "04-configure-data-connectors.sh",
            "05-configure-diagnostics.sh",
        ]

        for module in modules:
            script = scripts_dir / module
            script.write_text(f"#!/bin/bash\necho 'Executing {module}'")
            script.chmod(0o755)

        # Create common lib
        lib_dir = scripts_dir / "lib"
        lib_dir.mkdir()
        (lib_dir / "common.sh").write_text("# Common functions")

        orchestrator = SentinelSetupOrchestrator(
            config=config,
            scripts_dir=scripts_dir,
            work_dir=tmp_path,
        )

        results = orchestrator.execute_all_modules()

        # All modules should execute successfully
        assert len(results) == 5
        assert all(r["success"] for r in results)
        assert mock_run.call_count == 5

    @patch("subprocess.run")
    def test_config_env_passed_to_bash(self, mock_run, tmp_path):
        """Test that environment variables are passed correctly to bash."""
        config = SentinelConfig(
            tenant_id="12345678-1234-1234-1234-123456789012",
            subscription_id="87654321-4321-4321-4321-210987654321",
            workspace_name="test-workspace",
            location="westus2",
            retention_days=180,
        )

        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        script = scripts_dir / "01-test.sh"
        script.write_text("#!/bin/bash\necho $WORKSPACE_NAME")
        script.chmod(0o755)

        orchestrator = SentinelSetupOrchestrator(
            config=config,
            scripts_dir=scripts_dir,
            work_dir=tmp_path,
        )

        # Generate config env
        config_file = orchestrator.generate_config_env()
        assert config_file.exists()

        # Execute module and check that env vars were passed
        mock_run.return_value = Mock(returncode=0, stdout="test-workspace", stderr="")
        orchestrator.execute_module("test", script)

        # Verify subprocess was called with correct environment
        call_args = mock_run.call_args
        env = call_args[1]["env"]

        assert env["TENANT_ID"] == "12345678-1234-1234-1234-123456789012"
        assert env["SUBSCRIPTION_ID"] == "87654321-4321-4321-4321-210987654321"
        assert env["WORKSPACE_NAME"] == "test-workspace"
        assert env["LOCATION"] == "westus2"
        assert env["RETENTION_DAYS"] == "180"

    @patch("subprocess.run")
    def test_resources_json_created(self, mock_run, tmp_path):
        """Test that resources list file is created for bash modules."""
        config = SentinelConfig(
            tenant_id="12345678-1234-1234-1234-123456789012",
            subscription_id="87654321-4321-4321-4321-210987654321",
        )

        resources = [
            {
                "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "name": "vm1",
            },
            {
                "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/sa1",
                "type": "Microsoft.Storage/storageAccounts",
                "name": "sa1",
            },
        ]

        orchestrator = SentinelSetupOrchestrator(
            config=config,
            work_dir=tmp_path,
        )

        resources_file = orchestrator.create_resources_file(resources)

        assert resources_file.exists()

        # Verify JSON content
        with open(resources_file) as f:
            loaded_resources = json.load(f)

        assert len(loaded_resources) == 2
        assert loaded_resources[0]["name"] == "vm1"
        assert loaded_resources[1]["name"] == "sa1"

    @patch("subprocess.run")
    def test_workspace_id_shared_between_modules(self, mock_run, tmp_path):
        """Test that workspace ID from module 2 is shared with later modules."""
        config = SentinelConfig(
            tenant_id="12345678-1234-1234-1234-123456789012",
            subscription_id="87654321-4321-4321-4321-210987654321",
        )

        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()

        # Module 2 outputs workspace ID
        module2 = scripts_dir / "02-create-workspace.sh"
        module2.write_text("""#!/bin/bash
echo '{"workspace_id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.OperationalInsights/workspaces/test-workspace"}'
""")
        module2.chmod(0o755)

        # Module 3 should receive workspace ID
        module3 = scripts_dir / "03-enable-sentinel.sh"
        module3.write_text("#!/bin/bash\necho $WORKSPACE_ID")
        module3.chmod(0o755)

        orchestrator = SentinelSetupOrchestrator(
            config=config,
            scripts_dir=scripts_dir,
            work_dir=tmp_path,
        )

        # Mock module 2 returning workspace ID
        workspace_id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.OperationalInsights/workspaces/test-workspace"
        mock_run.side_effect = [
            Mock(returncode=0, stdout=json.dumps({"workspace_id": workspace_id}), stderr=""),
            Mock(returncode=0, stdout=workspace_id, stderr=""),
        ]

        # Execute modules
        result2 = orchestrator.execute_module("create-workspace", module2)

        # Extract workspace ID from module 2 output
        assert result2["success"]
        orchestrator.set_module_output("create-workspace", json.loads(result2["stdout"]))

        # Module 3 should have access to workspace ID
        result3 = orchestrator.execute_module("enable-sentinel", module3)

        # Verify workspace ID was passed to module 3
        call_args = mock_run.call_args_list[1]
        env = call_args[1]["env"]
        assert "WORKSPACE_ID" in env
        assert env["WORKSPACE_ID"] == workspace_id


# ============================================================================
# Neo4j Integration Tests
# ============================================================================


@pytest.mark.integration
class TestNeo4jIntegration:
    """Test resource discovery with real Neo4j database (using testcontainers)."""

    @pytest.mark.asyncio
    async def test_resource_discovery_with_testcontainers(self, neo4j_container):
        """Test resource discovery using testcontainers Neo4j."""
        from neo4j import GraphDatabase

        uri, user, password = neo4j_container
        driver = GraphDatabase.driver(uri, auth=(user, password))

        try:
            # Create sample abstracted resources in Neo4j
            with driver.session() as session:
                session.run("""
                    CREATE (r:Resource {
                        abstracted_id: '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm',
                        type: 'Microsoft.Compute/virtualMachines',
                        name: 'test-vm',
                        location: 'eastus'
                    })
                """)

            discovery = ResourceDiscovery(neo4j_driver=driver)
            resources = await discovery.discover_from_neo4j(
                subscription_id="test-sub",
                resource_types=["Microsoft.Compute/virtualMachines"],
            )

            assert len(resources) == 1
            assert resources[0]["name"] == "test-vm"
            assert resources[0]["type"] == "Microsoft.Compute/virtualMachines"

        finally:
            driver.close()

    @pytest.mark.asyncio
    async def test_query_abstracted_resources(self, neo4j_container):
        """Test that query targets abstracted nodes, not original nodes."""
        from neo4j import GraphDatabase

        uri, user, password = neo4j_container
        driver = GraphDatabase.driver(uri, auth=(user, password))

        try:
            # Create both abstracted and original nodes
            with driver.session() as session:
                session.run("""
                    CREATE (r:Resource {
                        abstracted_id: '/subscriptions/ABSTRACT_SUBSCRIPTION/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/vm-abcd1234',
                        type: 'Microsoft.Compute/virtualMachines',
                        name: 'vm-abcd1234',
                        location: 'eastus'
                    })
                    CREATE (o:Resource:Original {
                        abstracted_id: '/subscriptions/source-sub-123/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/real-vm',
                        type: 'Microsoft.Compute/virtualMachines',
                        name: 'real-vm',
                        location: 'eastus'
                    })
                    CREATE (r)-[:SCAN_SOURCE_NODE]->(o)
                """)

            discovery = ResourceDiscovery(neo4j_driver=driver)
            resources = await discovery.discover_from_neo4j(
                subscription_id="test-sub",
                resource_types=["Microsoft.Compute/virtualMachines"],
            )

            # Should only return abstracted nodes (not Original nodes)
            assert len(resources) == 1
            assert resources[0]["name"] == "vm-abcd1234"
            assert "ABSTRACT_SUBSCRIPTION" in resources[0]["abstracted_id"]

        finally:
            driver.close()

    @pytest.mark.asyncio
    async def test_cross_tenant_resource_ids(self, neo4j_container):
        """Test that resources have correct subscription IDs for cross-tenant."""
        from neo4j import GraphDatabase

        uri, user, password = neo4j_container
        driver = GraphDatabase.driver(uri, auth=(user, password))

        try:
            # Create abstracted resource with target tenant subscription
            with driver.session() as session:
                session.run("""
                    CREATE (r:Resource {
                        abstracted_id: '/subscriptions/target-sub-456/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/sa-abcd1234',
                        type: 'Microsoft.Storage/storageAccounts',
                        name: 'sa-abcd1234',
                        location: 'westus'
                    })
                """)

            discovery = ResourceDiscovery(neo4j_driver=driver)
            resources = await discovery.discover_from_neo4j(
                subscription_id="target-sub-456",
                resource_types=["Microsoft.Storage/storageAccounts"],
            )

            assert len(resources) == 1
            assert "target-sub-456" in resources[0]["abstracted_id"]
            assert resources[0]["name"] == "sa-abcd1234"

        finally:
            driver.close()


# ============================================================================
# CLI Integration Tests
# ============================================================================


class TestCLIIntegration:
    """Test CLI command registration and argument parsing."""

    def test_cli_command_registration(self):
        """Test that setup-sentinel command is registered correctly."""
        from click.testing import CliRunner
        from scripts.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "setup-sentinel" in result.output

    def test_cli_argument_parsing(self):
        """Test that all command-line flags are parsed correctly."""
        from click.testing import CliRunner
        from scripts.cli import cli

        runner = CliRunner()

        with patch("src.commands.sentinel.setup_sentinel_command") as mock_command:
            mock_command.return_value = None

            result = runner.invoke(cli, [
                "setup-sentinel",
                "--tenant-id", "12345678-1234-1234-1234-123456789012",
                "--subscription-id", "87654321-4321-4321-4321-210987654321",
                "--workspace-name", "test-workspace",
                "--resource-group", "test-rg",
                "--location", "eastus",
                "--retention-days", "90",
                "--sku", "PerGB2018",
                "--discovery-strategy", "neo4j",
                "--strict",
            ])

            # Command should be called with correct arguments
            mock_command.assert_called_once()
            call_args = mock_command.call_args[1]

            assert call_args["tenant_id"] == "12345678-1234-1234-1234-123456789012"
            assert call_args["subscription_id"] == "87654321-4321-4321-4321-210987654321"
            assert call_args["workspace_name"] == "test-workspace"
            assert call_args["resource_group"] == "test-rg"
            assert call_args["location"] == "eastus"
            assert call_args["retention_days"] == 90
            assert call_args["sku"] == "PerGB2018"
            assert call_args["discovery_strategy"] == "neo4j"
            assert call_args["strict"] is True

    def test_cli_environment_variable_fallback(self):
        """Test that environment variables work as defaults."""
        from click.testing import CliRunner
        from scripts.cli import cli

        runner = CliRunner()

        env_vars = {
            "AZURE_TENANT_ID": "env-tenant-123",
            "AZURE_SUBSCRIPTION_ID": "env-sub-456",
        }

        with patch("src.commands.sentinel.setup_sentinel_command") as mock_command:
            mock_command.return_value = None

            result = runner.invoke(
                cli,
                ["setup-sentinel"],
                env=env_vars,
            )

            # Should use environment variables as defaults
            mock_command.assert_called_once()
            call_args = mock_command.call_args[1]

            assert call_args["tenant_id"] == "env-tenant-123"
            assert call_args["subscription_id"] == "env-sub-456"

    def test_cli_explicit_args_override_env(self):
        """Test that explicit arguments override environment variables."""
        from click.testing import CliRunner
        from scripts.cli import cli

        runner = CliRunner()

        env_vars = {
            "AZURE_TENANT_ID": "env-tenant-123",
            "AZURE_SUBSCRIPTION_ID": "env-sub-456",
        }

        with patch("src.commands.sentinel.setup_sentinel_command") as mock_command:
            mock_command.return_value = None

            result = runner.invoke(
                cli,
                [
                    "setup-sentinel",
                    "--tenant-id", "explicit-tenant-789",
                    "--subscription-id", "explicit-sub-012",
                ],
                env=env_vars,
            )

            # Should use explicit args, not env vars
            mock_command.assert_called_once()
            call_args = mock_command.call_args[1]

            assert call_args["tenant_id"] == "explicit-tenant-789"
            assert call_args["subscription_id"] == "explicit-sub-012"

    @patch("subprocess.run")
    def test_integration_with_generate_iac_flag(self, mock_run, tmp_path):
        """Test --setup-sentinel flag integration with generate-iac command."""
        from click.testing import CliRunner
        from scripts.cli import cli

        runner = CliRunner()

        # Mock Neo4j connection
        with patch("neo4j.GraphDatabase.driver"):
            with patch("src.commands.sentinel.setup_sentinel_command") as mock_sentinel:
                mock_sentinel.return_value = {
                    "workspace_id": "/subscriptions/test/resourceGroups/test/providers/Microsoft.OperationalInsights/workspaces/test",
                }

                result = runner.invoke(cli, [
                    "generate-iac",
                    "--tenant-id", "12345678-1234-1234-1234-123456789012",
                    "--setup-sentinel",
                ])

                # Sentinel setup should be triggered
                mock_sentinel.assert_called_once()

    @patch("subprocess.run")
    def test_integration_with_create_tenant_flag(self, mock_run, tmp_path):
        """Test --setup-sentinel flag integration with create-tenant command."""
        from click.testing import CliRunner
        from scripts.cli import cli

        runner = CliRunner()

        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Test Spec\n\n## Resources\n\n- VM: test-vm")

        with patch("src.commands.sentinel.setup_sentinel_command") as mock_sentinel:
            mock_sentinel.return_value = {
                "workspace_id": "/subscriptions/test/resourceGroups/test/providers/Microsoft.OperationalInsights/workspaces/test",
            }

            result = runner.invoke(cli, [
                "create-tenant",
                "--spec", str(spec_file),
                "--setup-sentinel",
            ])

            # Sentinel setup should be triggered after tenant creation
            mock_sentinel.assert_called_once()
