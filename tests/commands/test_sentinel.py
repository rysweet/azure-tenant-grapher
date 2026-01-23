"""
Unit Tests for Azure Sentinel and Log Analytics Automation (Issue #518)

Tests for SentinelConfig, ResourceDiscovery, and SentinelSetupOrchestrator classes.

Testing pyramid: 60% unit tests (fast, heavily mocked)

All tests will FAIL until implementation exists - this is TDD methodology.
"""

import json
import subprocess
from unittest.mock import Mock, patch

import pytest

from src.commands.sentinel import (
    ResourceDiscovery,
    SentinelConfig,
    SentinelSetupOrchestrator,
)

# ============================================================================
# SentinelConfig Class Tests
# ============================================================================


class TestSentinelConfig:
    """Test configuration management for Sentinel automation."""

    def test_auto_generate_workspace_name(self):
        """Test automatic workspace name generation from tenant ID and location."""
        config = SentinelConfig(
            tenant_id="12345678-1234-1234-1234-123456789012",
            subscription_id="87654321-4321-4321-4321-210987654321",
            location="eastus",
        )
        # Expected format: <first-8-chars-of-tenant>-sentinel-law-<location>
        assert config.workspace_name == "12345678-sentinel-law-eastus"

    def test_auto_generate_workspace_name_different_location(self):
        """Test workspace name generation with different location."""
        config = SentinelConfig(
            tenant_id="abcdef12-3456-7890-abcd-ef1234567890",
            subscription_id="87654321-4321-4321-4321-210987654321",
            location="westus2",
        )
        assert config.workspace_name == "abcdef12-sentinel-law-westus2"

    def test_explicit_workspace_name_overrides_auto(self):
        """Test that explicitly provided workspace name is preserved."""
        config = SentinelConfig(
            tenant_id="12345678-1234-1234-1234-123456789012",
            subscription_id="87654321-4321-4321-4321-210987654321",
            workspace_name="my-custom-workspace",
        )
        assert config.workspace_name == "my-custom-workspace"

    def test_validate_retention_days_too_low(self):
        """Test validation fails for retention days < 30."""
        with pytest.raises(
            ValueError, match="Retention days must be between 30 and 730"
        ):
            SentinelConfig(
                tenant_id="12345678-1234-1234-1234-123456789012",
                subscription_id="87654321-4321-4321-4321-210987654321",
                retention_days=29,
            ).validate()

    def test_validate_retention_days_too_high(self):
        """Test validation fails for retention days > 730."""
        with pytest.raises(
            ValueError, match="Retention days must be between 30 and 730"
        ):
            SentinelConfig(
                tenant_id="12345678-1234-1234-1234-123456789012",
                subscription_id="87654321-4321-4321-4321-210987654321",
                retention_days=731,
            ).validate()

    def test_validate_retention_days_valid_boundary_low(self):
        """Test validation passes for retention_days = 30."""
        config = SentinelConfig(
            tenant_id="12345678-1234-1234-1234-123456789012",
            subscription_id="87654321-4321-4321-4321-210987654321",
            retention_days=30,
        )
        config.validate()  # Should not raise

    def test_validate_retention_days_valid_boundary_high(self):
        """Test validation passes for retention_days = 730."""
        config = SentinelConfig(
            tenant_id="12345678-1234-1234-1234-123456789012",
            subscription_id="87654321-4321-4321-4321-210987654321",
            retention_days=730,
        )
        config.validate()  # Should not raise

    def test_validate_invalid_sku(self):
        """Test validation fails for invalid SKU."""
        with pytest.raises(ValueError, match="Invalid SKU.*Must be one of"):
            SentinelConfig(
                tenant_id="12345678-1234-1234-1234-123456789012",
                subscription_id="87654321-4321-4321-4321-210987654321",
                sku="InvalidSKU",
            ).validate()

    def test_validate_valid_skus(self):
        """Test validation passes for all valid SKUs."""
        valid_skus = ["PerGB2018", "CapacityReservation", "Free"]
        for sku in valid_skus:
            config = SentinelConfig(
                tenant_id="12345678-1234-1234-1234-123456789012",
                subscription_id="87654321-4321-4321-4321-210987654321",
                sku=sku,
            )
            config.validate()  # Should not raise

    def test_to_env_dict(self):
        """Test conversion to environment variable dictionary."""
        config = SentinelConfig(
            tenant_id="12345678-1234-1234-1234-123456789012",
            subscription_id="87654321-4321-4321-4321-210987654321",
            workspace_name="test-workspace",
            resource_group="test-rg",
            location="eastus",
            retention_days=90,
            sku="PerGB2018",
        )

        env_dict = config.to_env_dict()

        assert env_dict["TENANT_ID"] == "12345678-1234-1234-1234-123456789012"
        assert (
            env_dict["AZURE_SUBSCRIPTION_ID"] == "87654321-4321-4321-4321-210987654321"
        )
        assert env_dict["WORKSPACE_NAME"] == "test-workspace"
        assert env_dict["RESOURCE_GROUP"] == "test-rg"
        assert env_dict["LOCATION"] == "eastus"
        assert env_dict["RETENTION_DAYS"] == "90"
        assert env_dict["SKU"] == "PerGB2018"

    def test_tenant_id_required(self):
        """Test that tenant_id is required."""
        with pytest.raises(TypeError):
            SentinelConfig(subscription_id="87654321-4321-4321-4321-210987654321")

    def test_subscription_id_required(self):
        """Test that subscription_id is required."""
        with pytest.raises(TypeError):
            SentinelConfig(tenant_id="12345678-1234-1234-1234-123456789012")

    def test_default_values(self):
        """Test that default values are set correctly."""
        config = SentinelConfig(
            tenant_id="12345678-1234-1234-1234-123456789012",
            subscription_id="87654321-4321-4321-4321-210987654321",
        )

        assert config.retention_days == 90
        assert config.sku == "PerGB2018"
        assert config.location == "eastus"
        assert config.resource_group is not None  # Auto-generated


# ============================================================================
# ResourceDiscovery Class Tests
# ============================================================================


class TestResourceDiscovery:
    """Test resource discovery from Neo4j and Azure API."""

    @pytest.mark.asyncio
    async def test_discover_from_neo4j_success(self):
        """Test successful resource discovery from Neo4j."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_result = Mock()
        mock_record = Mock()
        mock_record.__getitem__ = Mock(
            side_effect=lambda key: {
                "r": {
                    "abstracted_id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
                    "type": "Microsoft.Compute/virtualMachines",
                    "name": "test-vm",
                    "location": "eastus",
                }
            }[key]
        )

        mock_result.__iter__ = Mock(return_value=iter([mock_record]))
        mock_session.run = Mock(return_value=mock_result)
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)
        mock_driver.session = Mock(return_value=mock_session)

        discovery = ResourceDiscovery(neo4j_driver=mock_driver)
        resources = await discovery.discover_from_neo4j(
            subscription_id="test-sub",
            resource_types=["Microsoft.Compute/virtualMachines"],
        )

        assert len(resources) == 1
        assert resources[0]["abstracted_id"].endswith("test-vm")
        assert resources[0]["type"] == "Microsoft.Compute/virtualMachines"

    @pytest.mark.asyncio
    async def test_discover_from_neo4j_empty_results(self):
        """Test Neo4j discovery returns empty list when no resources found."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_result = Mock()
        mock_result.__iter__ = Mock(return_value=iter([]))  # Empty results
        mock_session.run = Mock(return_value=mock_result)
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)
        mock_driver.session = Mock(return_value=mock_session)

        discovery = ResourceDiscovery(neo4j_driver=mock_driver)
        resources = await discovery.discover_from_neo4j(
            subscription_id="test-sub",
            resource_types=["Microsoft.Compute/virtualMachines"],
        )

        assert resources == []

    @pytest.mark.asyncio
    async def test_discover_from_neo4j_connection_failure(self):
        """Test fallback to Azure API when Neo4j connection fails."""
        mock_driver = Mock()
        mock_driver.session = Mock(side_effect=Exception("Connection failed"))

        with patch(
            "src.commands.sentinel.ResourceDiscovery.discover_from_azure_api"
        ) as mock_azure:
            mock_azure.return_value = [{"id": "test-resource"}]

            discovery = ResourceDiscovery(neo4j_driver=mock_driver)
            resources = await discovery.discover(
                subscription_id="test-sub",
                strategy="neo4j_with_fallback",
            )

            # Should fall back to Azure API
            mock_azure.assert_called_once()
            assert len(resources) == 1

    @pytest.mark.asyncio
    async def test_discover_from_azure_api_success(self):
        """Test successful resource discovery from Azure API."""
        mock_credential = Mock()
        mock_client = Mock()
        mock_resource = Mock()
        mock_resource.id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
        mock_resource.type = "Microsoft.Compute/virtualMachines"
        mock_resource.name = "test-vm"
        mock_resource.location = "eastus"

        mock_client.resources.list = Mock(return_value=[mock_resource])

        with patch(
            "azure.mgmt.resource.ResourceManagementClient", return_value=mock_client
        ):
            discovery = ResourceDiscovery(credential=mock_credential)
            resources = await discovery.discover_from_azure_api(
                subscription_id="test-sub",
                resource_types=["Microsoft.Compute/virtualMachines"],
            )

            assert len(resources) == 1
            assert resources[0]["id"].endswith("test-vm")
            assert resources[0]["type"] == "Microsoft.Compute/virtualMachines"

    @pytest.mark.asyncio
    async def test_discover_from_azure_api_timeout(self):
        """Test handling of Azure API timeout."""
        mock_credential = Mock()
        mock_client = Mock()
        mock_client.resources.list = Mock(side_effect=TimeoutError("Request timed out"))

        with patch(
            "azure.mgmt.resource.ResourceManagementClient", return_value=mock_client
        ):
            discovery = ResourceDiscovery(credential=mock_credential)

            with pytest.raises(TimeoutError):
                await discovery.discover_from_azure_api(
                    subscription_id="test-sub",
                    resource_types=["Microsoft.Compute/virtualMachines"],
                )

    @pytest.mark.asyncio
    async def test_discover_filters_supported_types(self):
        """Test that discovery only returns supported resource types."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_result = Mock()

        # Return both supported and unsupported resource types
        mock_records = []
        for i, resource_type in enumerate(
            [
                "Microsoft.Compute/virtualMachines",  # Supported
                "Microsoft.Unsupported/resource",  # Unsupported
                "Microsoft.Storage/storageAccounts",  # Supported
            ]
        ):
            record = Mock()
            record.__getitem__ = Mock(
                side_effect=lambda key, rt=resource_type, idx=i: {
                    "r": {
                        "abstracted_id": f"/subscriptions/test-sub/resourceGroups/test-rg/providers/{rt}/resource-{idx}",
                        "type": rt,
                        "name": f"resource-{idx}",
                        "location": "eastus",
                    }
                }[key]
            )
            mock_records.append(record)

        mock_result.__iter__ = Mock(return_value=iter(mock_records))
        mock_session.run = Mock(return_value=mock_result)
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)
        mock_driver.session = Mock(return_value=mock_session)

        discovery = ResourceDiscovery(neo4j_driver=mock_driver)
        resources = await discovery.discover_from_neo4j(
            subscription_id="test-sub",
            resource_types=[
                "Microsoft.Compute/virtualMachines",
                "Microsoft.Storage/storageAccounts",
            ],
        )

        # Should only return 2 supported resources, not the unsupported one
        assert len(resources) == 2
        resource_types = [r["type"] for r in resources]
        assert "Microsoft.Unsupported/resource" not in resource_types

    @pytest.mark.asyncio
    async def test_discover_strategy_neo4j(self):
        """Test that strategy='neo4j' uses Neo4j discovery."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_result = Mock()
        mock_result.__iter__ = Mock(return_value=iter([]))
        mock_session.run = Mock(return_value=mock_result)
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)
        mock_driver.session = Mock(return_value=mock_session)

        discovery = ResourceDiscovery(neo4j_driver=mock_driver)

        with patch.object(
            discovery, "discover_from_neo4j", wraps=discovery.discover_from_neo4j
        ) as mock_neo4j:
            await discovery.discover(
                subscription_id="test-sub",
                strategy="neo4j",
            )

            mock_neo4j.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_strategy_azure_api(self):
        """Test that strategy='azure_api' uses Azure API discovery."""
        mock_credential = Mock()
        mock_client = Mock()
        mock_client.resources.list = Mock(return_value=[])

        with patch(
            "azure.mgmt.resource.ResourceManagementClient", return_value=mock_client
        ):
            discovery = ResourceDiscovery(credential=mock_credential)

            with patch.object(
                discovery,
                "discover_from_azure_api",
                wraps=discovery.discover_from_azure_api,
            ) as mock_azure:
                await discovery.discover(
                    subscription_id="test-sub",
                    strategy="azure_api",
                )

                mock_azure.assert_called_once()


# ============================================================================
# SentinelSetupOrchestrator Class Tests
# ============================================================================


class TestSentinelSetupOrchestrator:
    """Test orchestration of Sentinel setup bash modules."""

    def test_validate_prerequisites_missing_scripts(self, tmp_path):
        """Test validation fails if bash scripts are missing."""
        config = SentinelConfig(
            tenant_id="12345678-1234-1234-1234-123456789012",
            subscription_id="87654321-4321-4321-4321-210987654321",
        )

        # Point to empty directory (no scripts)
        orchestrator = SentinelSetupOrchestrator(
            config=config,
            scripts_dir=tmp_path / "nonexistent",
        )

        with pytest.raises(FileNotFoundError, match="Bash module not found"):
            orchestrator.validate_prerequisites()

    def test_validate_prerequisites_invalid_config(self):
        """Test validation fails if config is invalid."""
        config = SentinelConfig(
            tenant_id="12345678-1234-1234-1234-123456789012",
            subscription_id="87654321-4321-4321-4321-210987654321",
            retention_days=10,  # Invalid: too low
        )

        orchestrator = SentinelSetupOrchestrator(config=config)

        with pytest.raises(ValueError, match="Retention days must be between"):
            orchestrator.validate_prerequisites()

    def test_generate_config_env(self, tmp_path):
        """Test config environment file is generated correctly."""
        config = SentinelConfig(
            tenant_id="12345678-1234-1234-1234-123456789012",
            subscription_id="87654321-4321-4321-4321-210987654321",
            workspace_name="test-workspace",
        )

        orchestrator = SentinelSetupOrchestrator(
            config=config,
            work_dir=tmp_path,
        )

        config_file = orchestrator.generate_config_env()

        assert config_file.exists()
        content = config_file.read_text()
        assert "TENANT_ID=12345678-1234-1234-1234-123456789012" in content
        assert "SUBSCRIPTION_ID=87654321-4321-4321-4321-210987654321" in content
        assert "WORKSPACE_NAME=test-workspace" in content  # pragma: allowlist secret

    @patch("subprocess.run")
    def test_execute_module_success(self, mock_run, tmp_path):
        """Test successful module execution."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Module executed successfully",
            stderr="",
        )

        config = SentinelConfig(
            tenant_id="12345678-1234-1234-1234-123456789012",
            subscription_id="87654321-4321-4321-4321-210987654321",
        )

        orchestrator = SentinelSetupOrchestrator(
            config=config,
            work_dir=tmp_path,
        )

        # Create dummy script
        script_path = tmp_path / "test-module.sh"
        script_path.write_text("#!/bin/bash\necho 'success'")
        script_path.chmod(0o755)

        result = orchestrator.execute_module(
            module_name="test-module",
            script_path=script_path,
        )

        assert result["success"] is True
        assert result["exit_code"] == 0
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_execute_module_failure(self, mock_run, tmp_path):
        """Test module execution failure is handled correctly."""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Error: Module failed",
        )

        config = SentinelConfig(
            tenant_id="12345678-1234-1234-1234-123456789012",
            subscription_id="87654321-4321-4321-4321-210987654321",
        )

        orchestrator = SentinelSetupOrchestrator(
            config=config,
            work_dir=tmp_path,
        )

        script_path = tmp_path / "test-module.sh"
        script_path.write_text("#!/bin/bash\nexit 1")
        script_path.chmod(0o755)

        result = orchestrator.execute_module(
            module_name="test-module",
            script_path=script_path,
        )

        assert result["success"] is False
        assert result["exit_code"] == 1
        assert "Error:" in result["stderr"]

    @patch("subprocess.run")
    def test_execute_module_timeout(self, mock_run, tmp_path):
        """Test module timeout is handled correctly (exit code 124)."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=60)

        config = SentinelConfig(
            tenant_id="12345678-1234-1234-1234-123456789012",
            subscription_id="87654321-4321-4321-4321-210987654321",
        )

        orchestrator = SentinelSetupOrchestrator(
            config=config,
            work_dir=tmp_path,
        )

        script_path = tmp_path / "test-module.sh"
        script_path.write_text("#!/bin/bash\nsleep 100")
        script_path.chmod(0o755)

        result = orchestrator.execute_module(
            module_name="test-module",
            script_path=script_path,
            timeout=1,
        )

        assert result["success"] is False
        assert result["exit_code"] == 124  # Standard timeout exit code
        assert "timeout" in result["stderr"].lower()

    @patch("subprocess.run")
    def test_execute_all_modules_strict_mode(self, mock_run, tmp_path):
        """Test that strict mode stops on first failure."""
        # First module succeeds, second fails, third should not be called
        mock_run.side_effect = [
            Mock(returncode=0, stdout="Module 1 success", stderr=""),
            Mock(returncode=1, stdout="", stderr="Module 2 failed"),
        ]

        config = SentinelConfig(
            tenant_id="12345678-1234-1234-1234-123456789012",
            subscription_id="87654321-4321-4321-4321-210987654321",
        )

        # Create dummy scripts
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        for i in range(1, 4):
            script = scripts_dir / f"0{i}-module.sh"
            script.write_text(f"#!/bin/bash\necho 'Module {i}'")
            script.chmod(0o755)

        orchestrator = SentinelSetupOrchestrator(
            config=config,
            scripts_dir=scripts_dir,
            work_dir=tmp_path,
        )

        results = orchestrator.execute_all_modules(strict=True)

        # Should only execute 2 modules (stop on first failure)
        assert len(results) == 2
        assert mock_run.call_count == 2
        assert results[0]["success"] is True
        assert results[1]["success"] is False

    @patch("subprocess.run")
    def test_execute_all_modules_non_strict(self, mock_run, tmp_path):
        """Test that non-strict mode continues on failure."""
        # First succeeds, second fails, third succeeds
        mock_run.side_effect = [
            Mock(returncode=0, stdout="Module 1 success", stderr=""),
            Mock(returncode=1, stdout="", stderr="Module 2 failed"),
            Mock(returncode=0, stdout="Module 3 success", stderr=""),
        ]

        config = SentinelConfig(
            tenant_id="12345678-1234-1234-1234-123456789012",
            subscription_id="87654321-4321-4321-4321-210987654321",
        )

        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        for i in range(1, 4):
            script = scripts_dir / f"0{i}-module.sh"
            script.write_text(f"#!/bin/bash\necho 'Module {i}'")
            script.chmod(0o755)

        orchestrator = SentinelSetupOrchestrator(
            config=config,
            scripts_dir=scripts_dir,
            work_dir=tmp_path,
        )

        results = orchestrator.execute_all_modules(strict=False)

        # Should execute all 3 modules despite middle failure
        assert len(results) == 3
        assert mock_run.call_count == 3
        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert results[2]["success"] is True

    def test_workspace_id_shared_between_modules(self, tmp_path):
        """Test that workspace ID from module 2 is available to module 3+."""
        config = SentinelConfig(
            tenant_id="12345678-1234-1234-1234-123456789012",
            subscription_id="87654321-4321-4321-4321-210987654321",
        )

        orchestrator = SentinelSetupOrchestrator(
            config=config,
            work_dir=tmp_path,
        )

        # Simulate module 2 output with workspace ID
        workspace_output = {
            "workspace_id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.OperationalInsights/workspaces/test-workspace",
            "workspace_name": "test-workspace",
        }

        output_file = tmp_path / "workspace_output.json"
        output_file.write_text(json.dumps(workspace_output))

        # Module 3+ should be able to read this file
        orchestrator.set_module_output("create-workspace", workspace_output)
        shared_data = orchestrator.get_shared_data()

        assert "workspace_id" in shared_data
        assert shared_data["workspace_id"] == workspace_output["workspace_id"]
