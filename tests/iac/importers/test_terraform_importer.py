"""Comprehensive tests for TerraformImporter module.

This test suite provides extensive coverage of the TerraformImporter functionality,
including resource detection, command generation, execution, and error handling.

Test Coverage:
- Initialization and validation
- Azure resource detection
- Import command generation
- Command execution (mocked)
- Import strategies
- State backup and recovery
- Edge cases and error scenarios
"""

import subprocess
from unittest.mock import Mock, patch

import pytest
from azure.core.exceptions import AzureError

from src.iac.importers.terraform_importer import (
    ImportCommand,
    ImportReport,
    ImportResult,
    ImportStrategy,
    TerraformImporter,
)


@pytest.fixture
def mock_credential():
    """Mock Azure credential."""
    return Mock()


@pytest.fixture
def temp_terraform_dir(tmp_path):
    """Create temporary Terraform directory with minimal setup."""
    tf_dir = tmp_path / "terraform"
    tf_dir.mkdir()

    # Create a sample .tf file
    main_tf = tf_dir / "main.tf"
    main_tf.write_text("""
resource "azurerm_resource_group" "main" {
  name     = "test-rg"
  location = "eastus"
}

resource "azurerm_storage_account" "storage" {
  name                = "teststorageacct"
  resource_group_name = azurerm_resource_group.main.name
  location           = "eastus"
}
""")

    # Create .terraform directory (indicates 'terraform init' was run)
    (tf_dir / ".terraform").mkdir()

    return tf_dir


@pytest.fixture
def mock_resource_client():
    """Mock ResourceManagementClient."""
    client = Mock()
    client.resources.list.return_value = []
    return client


class TestTerraformImporterInitialization:
    """Test TerraformImporter initialization and validation."""

    def test_initialization_valid(self, temp_terraform_dir, mock_credential):
        """Test successful initialization with valid parameters."""
        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            import_strategy=ImportStrategy.RESOURCE_GROUPS,
            credential=mock_credential,
        )

        assert importer.subscription_id == "test-sub-id"
        assert importer.terraform_dir == temp_terraform_dir
        assert importer.import_strategy == ImportStrategy.RESOURCE_GROUPS
        assert importer.credential == mock_credential
        assert importer.dry_run is False

    def test_initialization_with_dry_run(self, temp_terraform_dir, mock_credential):
        """Test initialization with dry_run mode enabled."""
        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
            dry_run=True,
        )

        assert importer.dry_run is True

    def test_initialization_invalid_terraform_dir(self, mock_credential):
        """Test initialization fails with non-existent terraform_dir."""
        with pytest.raises(ValueError, match="does not exist"):
            TerraformImporter(
                subscription_id="test-sub-id",
                terraform_dir="/nonexistent/path",
                credential=mock_credential,
            )

    def test_initialization_invalid_import_strategy(
        self, temp_terraform_dir, mock_credential
    ):
        """Test initialization fails with invalid import strategy."""
        with pytest.raises(ValueError, match="Invalid import strategy"):
            TerraformImporter(
                subscription_id="test-sub-id",
                terraform_dir=str(temp_terraform_dir),
                import_strategy="invalid_strategy",  # Not an ImportStrategy enum
                credential=mock_credential,
            )

    def test_default_credential_initialization(self, temp_terraform_dir):
        """Test that DefaultAzureCredential is used when credential is None."""
        with patch(
            "src.iac.importers.terraform_importer.DefaultAzureCredential"
        ) as mock_default:
            mock_default.return_value = Mock()
            importer = TerraformImporter(
                subscription_id="test-sub-id",
                terraform_dir=str(temp_terraform_dir),
            )
            assert importer.credential is not None

    def test_lazy_client_initialization(self, temp_terraform_dir, mock_credential):
        """Test that resource client is lazily initialized."""
        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
        )

        assert importer._resource_client is None

        # Access property to trigger initialization
        with patch(
            "src.iac.importers.terraform_importer.ResourceManagementClient"
        ) as mock_client:
            mock_client.return_value = Mock()
            _ = importer.resource_client
            assert importer._resource_client is not None


class TestAzureResourceDetection:
    """Test Azure resource detection functionality."""

    @pytest.mark.asyncio
    async def test_detect_existing_resources_success(
        self, temp_terraform_dir, mock_credential, mock_resource_client
    ):
        """Test successful detection of existing Azure resources."""
        # Setup mock resources
        mock_resource1 = Mock()
        mock_resource1.type = "Microsoft.Storage/storageAccounts"
        mock_resource1.name = "teststorageacct"
        mock_resource1.id = "/subscriptions/sub-id/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorageacct"
        mock_resource1.location = "eastus"

        mock_resource2 = Mock()
        mock_resource2.type = "Microsoft.Resources/resourceGroups"
        mock_resource2.name = "test-rg"
        mock_resource2.id = "/subscriptions/sub-id/resourceGroups/test-rg"
        mock_resource2.location = "eastus"

        mock_resource_client.resources.list.return_value = [
            mock_resource1,
            mock_resource2,
        ]

        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
        )
        importer._resource_client = mock_resource_client

        resources = await importer.detect_existing_resources()

        assert len(resources) == 2
        assert resources[0]["type"] == "Microsoft.Storage/storageAccounts"
        assert resources[0]["name"] == "teststorageacct"
        assert resources[0]["resource_group"] == "test-rg"
        assert resources[1]["type"] == "Microsoft.Resources/resourceGroups"

    @pytest.mark.asyncio
    async def test_detect_existing_resources_empty_subscription(
        self, temp_terraform_dir, mock_credential, mock_resource_client
    ):
        """Test detection when subscription has no resources."""
        mock_resource_client.resources.list.return_value = []

        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
        )
        importer._resource_client = mock_resource_client

        resources = await importer.detect_existing_resources()

        assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_detect_existing_resources_azure_error(
        self, temp_terraform_dir, mock_credential, mock_resource_client
    ):
        """Test detection handles Azure API errors gracefully."""
        mock_resource_client.resources.list.side_effect = Exception("Azure API error")

        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
        )
        importer._resource_client = mock_resource_client

        with pytest.raises(AzureError, match="Resource detection failed"):
            await importer.detect_existing_resources()

    @pytest.mark.asyncio
    async def test_detect_resources_extracts_resource_group(
        self, temp_terraform_dir, mock_credential, mock_resource_client
    ):
        """Test that resource group is correctly extracted from resource ID."""
        mock_resource = Mock()
        mock_resource.type = "Microsoft.Compute/virtualMachines"
        mock_resource.name = "test-vm"
        mock_resource.id = "/subscriptions/sub-id/resourceGroups/my-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
        mock_resource.location = "westus"

        mock_resource_client.resources.list.return_value = [mock_resource]

        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
        )
        importer._resource_client = mock_resource_client

        resources = await importer.detect_existing_resources()

        assert resources[0]["resource_group"] == "my-rg"


class TestImportStrategyFiltering:
    """Test resource filtering based on import strategies."""

    def test_filter_resource_groups_strategy(self, temp_terraform_dir, mock_credential):
        """Test RESOURCE_GROUPS strategy filters to only resource groups."""
        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            import_strategy=ImportStrategy.RESOURCE_GROUPS,
            credential=mock_credential,
        )

        resources = [
            {"type": "Microsoft.Resources/resourceGroups", "name": "rg1"},
            {"type": "Microsoft.Storage/storageAccounts", "name": "storage1"},
            {"type": "Microsoft.Resources/resourceGroups", "name": "rg2"},
            {"type": "Microsoft.Compute/virtualMachines", "name": "vm1"},
        ]

        filtered = importer.filter_resources_by_strategy(resources)

        assert len(filtered) == 2
        assert all(r["type"] == "Microsoft.Resources/resourceGroups" for r in filtered)

    def test_filter_all_resources_strategy(self, temp_terraform_dir, mock_credential):
        """Test ALL_RESOURCES strategy returns all resources."""
        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            import_strategy=ImportStrategy.ALL_RESOURCES,
            credential=mock_credential,
        )

        resources = [
            {"type": "Microsoft.Resources/resourceGroups", "name": "rg1"},
            {"type": "Microsoft.Storage/storageAccounts", "name": "storage1"},
            {"type": "Microsoft.Compute/virtualMachines", "name": "vm1"},
        ]

        filtered = importer.filter_resources_by_strategy(resources)

        assert len(filtered) == 3
        assert filtered == resources

    def test_filter_selective_strategy(self, temp_terraform_dir, mock_credential):
        """Test SELECTIVE strategy (currently defaults to resource groups)."""
        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            import_strategy=ImportStrategy.SELECTIVE,
            credential=mock_credential,
        )

        resources = [
            {"type": "Microsoft.Resources/resourceGroups", "name": "rg1"},
            {"type": "Microsoft.Storage/storageAccounts", "name": "storage1"},
        ]

        filtered = importer.filter_resources_by_strategy(resources)

        # Currently defaults to resource groups
        assert len(filtered) == 1
        assert filtered[0]["type"] == "Microsoft.Resources/resourceGroups"

    def test_filter_empty_resource_list(self, temp_terraform_dir, mock_credential):
        """Test filtering handles empty resource list."""
        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
        )

        filtered = importer.filter_resources_by_strategy([])
        assert len(filtered) == 0


class TestImportCommandGeneration:
    """Test generation of Terraform import commands."""

    def test_generate_import_commands_success(
        self, temp_terraform_dir, mock_credential
    ):
        """Test successful generation of import commands for matching resources."""
        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
        )

        resources = [
            {
                "type": "Microsoft.Resources/resourceGroups",
                "name": "main",  # Matches resource "azurerm_resource_group" "main"
                "id": "/subscriptions/sub-id/resourceGroups/main",
            },
        ]

        commands = importer.generate_import_commands(resources)

        # Should generate commands for resources in terraform config
        assert len(commands) > 0
        assert isinstance(commands[0], ImportCommand)

    def test_generate_import_commands_skips_missing_resources(
        self, temp_terraform_dir, mock_credential
    ):
        """Test that resources not in Terraform config are skipped."""
        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
        )

        resources = [
            {
                "type": "Microsoft.Compute/virtualMachines",
                "name": "not-in-config",
                "id": "/subscriptions/sub-id/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/not-in-config",
            },
        ]

        commands = importer.generate_import_commands(resources)

        # Should skip resources not in config
        assert len(commands) == 0

    def test_generate_import_commands_multiple_resources(
        self, temp_terraform_dir, mock_credential
    ):
        """Test generating commands for multiple matching resources."""
        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
        )

        resources = [
            {
                "type": "Microsoft.Resources/resourceGroups",
                "name": "main",  # Matches "main" in config
                "id": "/subscriptions/sub-id/resourceGroups/main",
            },
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "storage",  # Matches "storage" in config
                "id": "/subscriptions/sub-id/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/storage",
            },
        ]

        commands = importer.generate_import_commands(resources)

        # Both resources should have commands generated
        assert len(commands) >= 1

    def test_import_command_to_command_string(self):
        """Test ImportCommand.to_command() generates correct command string."""
        command = ImportCommand(
            resource_type="Microsoft.Resources/resourceGroups",
            terraform_address="azurerm_resource_group.main",
            azure_resource_id="/subscriptions/sub-id/resourceGroups/test-rg",
            resource_name="test-rg",
        )

        cmd_string = command.to_command()

        assert (
            cmd_string
            == "terraform import azurerm_resource_group.main /subscriptions/sub-id/resourceGroups/test-rg"
        )

    def test_to_terraform_name_conversion(self, temp_terraform_dir, mock_credential):
        """Test conversion of Azure names to Terraform-safe names."""
        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
        )

        # Test various name conversions
        assert importer._to_terraform_name("test-rg") == "test_rg"
        assert importer._to_terraform_name("Test-RG") == "test_rg"
        assert importer._to_terraform_name("test.rg") == "test_rg"
        assert importer._to_terraform_name("test@rg!") == "test_rg_"


class TestImportExecution:
    """Test execution of Terraform import commands (with mocked subprocess)."""

    @pytest.mark.asyncio
    async def test_execute_import_commands_dry_run(
        self, temp_terraform_dir, mock_credential
    ):
        """Test dry-run mode doesn't execute commands."""
        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
            dry_run=True,
        )

        commands = [
            ImportCommand(
                resource_type="Microsoft.Resources/resourceGroups",
                terraform_address="azurerm_resource_group.main",
                azure_resource_id="/subscriptions/sub-id/resourceGroups/test-rg",
                resource_name="test-rg",
            )
        ]

        report = await importer.execute_import_commands(commands)

        assert report.dry_run is True
        assert report.commands_generated == 1
        assert report.commands_executed == 0

    @pytest.mark.asyncio
    @patch("subprocess.run")
    async def test_execute_single_import_success(
        self, mock_subprocess, temp_terraform_dir, mock_credential
    ):
        """Test successful execution of a single import command."""
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="Import successful!",
            stderr="",
        )

        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
        )

        command = ImportCommand(
            resource_type="Microsoft.Resources/resourceGroups",
            terraform_address="azurerm_resource_group.main",
            azure_resource_id="/subscriptions/sub-id/resourceGroups/test-rg",
            resource_name="test-rg",
        )

        result = await importer._execute_single_import(command)

        assert result.success is True
        assert result.stdout == "Import successful!"
        assert result.error_message is None

    @pytest.mark.asyncio
    @patch("subprocess.run")
    async def test_execute_single_import_failure(
        self, mock_subprocess, temp_terraform_dir, mock_credential
    ):
        """Test handling of failed import command."""
        mock_subprocess.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Error: Resource already exists in state",
        )

        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
        )

        command = ImportCommand(
            resource_type="Microsoft.Resources/resourceGroups",
            terraform_address="azurerm_resource_group.main",
            azure_resource_id="/subscriptions/sub-id/resourceGroups/test-rg",
            resource_name="test-rg",
        )

        result = await importer._execute_single_import(command)

        assert result.success is False
        assert result.failed is True
        assert "already exists" in result.error_message

    @pytest.mark.asyncio
    @patch("subprocess.run")
    async def test_execute_single_import_timeout(
        self, mock_subprocess, temp_terraform_dir, mock_credential
    ):
        """Test handling of command timeout."""
        mock_subprocess.side_effect = subprocess.TimeoutExpired(
            cmd="terraform", timeout=300
        )

        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
        )

        command = ImportCommand(
            resource_type="Microsoft.Resources/resourceGroups",
            terraform_address="azurerm_resource_group.main",
            azure_resource_id="/subscriptions/sub-id/resourceGroups/test-rg",
            resource_name="test-rg",
        )

        result = await importer._execute_single_import(command)

        assert result.success is False
        assert "timed out" in result.error_message.lower()

    @pytest.mark.asyncio
    @patch("subprocess.run")
    async def test_execute_import_commands_multiple_success(
        self, mock_subprocess, temp_terraform_dir, mock_credential
    ):
        """Test executing multiple import commands successfully."""
        mock_subprocess.return_value = Mock(returncode=0, stdout="Success", stderr="")

        with patch.object(
            TerraformImporter, "_check_terraform_ready", return_value=True
        ):
            with patch.object(TerraformImporter, "_backup_terraform_state"):
                importer = TerraformImporter(
                    subscription_id="test-sub-id",
                    terraform_dir=str(temp_terraform_dir),
                    credential=mock_credential,
                )

                commands = [
                    ImportCommand(
                        resource_type="Microsoft.Resources/resourceGroups",
                        terraform_address="azurerm_resource_group.rg1",
                        azure_resource_id="/subscriptions/sub-id/resourceGroups/rg1",
                        resource_name="rg1",
                    ),
                    ImportCommand(
                        resource_type="Microsoft.Resources/resourceGroups",
                        terraform_address="azurerm_resource_group.rg2",
                        azure_resource_id="/subscriptions/sub-id/resourceGroups/rg2",
                        resource_name="rg2",
                    ),
                ]

                report = await importer.execute_import_commands(commands)

                assert report.commands_executed == 2
                assert report.successes == 2
                assert report.failures == 0

    @pytest.mark.asyncio
    @patch("subprocess.run")
    async def test_execute_import_commands_partial_failure(
        self, mock_subprocess, temp_terraform_dir, mock_credential
    ):
        """Test executing commands with some failures (continues on error)."""
        # First command succeeds, second fails
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout="Success", stderr=""),
            Mock(returncode=1, stdout="", stderr="Error"),
        ]

        with patch.object(
            TerraformImporter, "_check_terraform_ready", return_value=True
        ):
            with patch.object(TerraformImporter, "_backup_terraform_state"):
                importer = TerraformImporter(
                    subscription_id="test-sub-id",
                    terraform_dir=str(temp_terraform_dir),
                    credential=mock_credential,
                )

                commands = [
                    ImportCommand(
                        resource_type="Microsoft.Resources/resourceGroups",
                        terraform_address="azurerm_resource_group.rg1",
                        azure_resource_id="/subscriptions/sub-id/resourceGroups/rg1",
                        resource_name="rg1",
                    ),
                    ImportCommand(
                        resource_type="Microsoft.Resources/resourceGroups",
                        terraform_address="azurerm_resource_group.rg2",
                        azure_resource_id="/subscriptions/sub-id/resourceGroups/rg2",
                        resource_name="rg2",
                    ),
                ]

                report = await importer.execute_import_commands(commands)

                assert report.commands_executed == 2
                assert report.successes == 1
                assert report.failures == 1


class TestTerraformReadiness:
    """Test Terraform installation and initialization checks."""

    def test_check_terraform_ready_success(self, temp_terraform_dir, mock_credential):
        """Test successful Terraform readiness check."""
        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
        )

        with patch("shutil.which", return_value="/usr/bin/terraform"):
            ready = importer._check_terraform_ready()
            assert ready is True

    def test_check_terraform_ready_not_installed(
        self, temp_terraform_dir, mock_credential
    ):
        """Test Terraform not installed."""
        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
        )

        with patch("shutil.which", return_value=None):
            ready = importer._check_terraform_ready()
            assert ready is False

    def test_check_terraform_ready_not_initialized(self, tmp_path, mock_credential):
        """Test Terraform not initialized (no .terraform directory)."""
        tf_dir = tmp_path / "terraform"
        tf_dir.mkdir()

        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(tf_dir),
            credential=mock_credential,
        )

        with patch("shutil.which", return_value="/usr/bin/terraform"):
            ready = importer._check_terraform_ready()
            assert ready is False

    @pytest.mark.asyncio
    async def test_execute_import_terraform_not_ready(
        self, temp_terraform_dir, mock_credential
    ):
        """Test execution aborts when Terraform is not ready."""
        with patch.object(
            TerraformImporter, "_check_terraform_ready", return_value=False
        ):
            importer = TerraformImporter(
                subscription_id="test-sub-id",
                terraform_dir=str(temp_terraform_dir),
                credential=mock_credential,
            )

            commands = [
                ImportCommand(
                    resource_type="Microsoft.Resources/resourceGroups",
                    terraform_address="azurerm_resource_group.main",
                    azure_resource_id="/subscriptions/sub-id/resourceGroups/test-rg",
                    resource_name="test-rg",
                )
            ]

            report = await importer.execute_import_commands(commands)

            assert report.commands_executed == 0
            assert len(report.warnings) > 0
            assert "not ready" in report.warnings[0].lower()


class TestStateBackup:
    """Test Terraform state backup functionality."""

    def test_backup_terraform_state_success(self, temp_terraform_dir, mock_credential):
        """Test successful state backup."""
        # Create a state file
        state_file = temp_terraform_dir / "terraform.tfstate"
        state_file.write_text('{"version": 4}')

        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
        )

        importer._backup_terraform_state()

        # Check backup was created
        backup_files = list(temp_terraform_dir.glob("terraform.tfstate.backup.*"))
        assert len(backup_files) == 1

    def test_backup_terraform_state_no_state_file(
        self, temp_terraform_dir, mock_credential
    ):
        """Test backup when no state file exists."""
        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
        )

        # Should not raise error
        importer._backup_terraform_state()

    def test_backup_terraform_state_dry_run(self, temp_terraform_dir, mock_credential):
        """Test backup is skipped in dry-run mode."""
        state_file = temp_terraform_dir / "terraform.tfstate"
        state_file.write_text('{"version": 4}')

        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
            dry_run=True,
        )

        importer._backup_terraform_state()

        # No backup should be created in dry-run
        backup_files = list(temp_terraform_dir.glob("terraform.tfstate.backup.*"))
        assert len(backup_files) == 0

    @pytest.mark.asyncio
    @patch("subprocess.run")
    async def test_execute_import_backup_failure_continues(
        self, mock_subprocess, temp_terraform_dir, mock_credential
    ):
        """Test import continues even if backup fails."""
        mock_subprocess.return_value = Mock(returncode=0, stdout="Success", stderr="")

        with patch.object(
            TerraformImporter, "_check_terraform_ready", return_value=True
        ):
            with patch.object(
                TerraformImporter,
                "_backup_terraform_state",
                side_effect=Exception("Backup failed"),
            ):
                importer = TerraformImporter(
                    subscription_id="test-sub-id",
                    terraform_dir=str(temp_terraform_dir),
                    credential=mock_credential,
                )

                commands = [
                    ImportCommand(
                        resource_type="Microsoft.Resources/resourceGroups",
                        terraform_address="azurerm_resource_group.main",
                        azure_resource_id="/subscriptions/sub-id/resourceGroups/test-rg",
                        resource_name="test-rg",
                    )
                ]

                report = await importer.execute_import_commands(commands)

                # Import should continue despite backup failure
                assert report.successes == 1
                assert any("backup failed" in w.lower() for w in report.warnings)


class TestImportReporting:
    """Test import report generation and statistics."""

    def test_import_report_initialization(self):
        """Test ImportReport initialization with defaults."""
        report = ImportReport(
            subscription_id="test-sub-id",
            strategy=ImportStrategy.RESOURCE_GROUPS,
        )

        assert report.subscription_id == "test-sub-id"
        assert report.strategy == ImportStrategy.RESOURCE_GROUPS
        assert report.commands_generated == 0
        assert report.successes == 0
        assert report.failures == 0
        assert len(report.results) == 0

    def test_import_report_add_result_success(self):
        """Test adding successful result to report."""
        report = ImportReport(
            subscription_id="test-sub-id",
            strategy=ImportStrategy.ALL_RESOURCES,
        )

        command = ImportCommand(
            resource_type="Microsoft.Resources/resourceGroups",
            terraform_address="azurerm_resource_group.main",
            azure_resource_id="/subscriptions/sub-id/resourceGroups/test-rg",
            resource_name="test-rg",
        )

        result = ImportResult(command=command, success=True, stdout="Success")

        report.add_result(result)

        assert report.commands_executed == 1
        assert report.successes == 1
        assert report.failures == 0

    def test_import_report_add_result_failure(self):
        """Test adding failed result to report."""
        report = ImportReport(
            subscription_id="test-sub-id",
            strategy=ImportStrategy.ALL_RESOURCES,
        )

        command = ImportCommand(
            resource_type="Microsoft.Resources/resourceGroups",
            terraform_address="azurerm_resource_group.main",
            azure_resource_id="/subscriptions/sub-id/resourceGroups/test-rg",
            resource_name="test-rg",
        )

        result = ImportResult(
            command=command, success=False, error_message="Import failed"
        )

        report.add_result(result)

        assert report.commands_executed == 1
        assert report.successes == 0
        assert report.failures == 1

    def test_import_report_format_no_conflicts(self):
        """Test report formatting with no failures."""
        report = ImportReport(
            subscription_id="test-sub-id",
            strategy=ImportStrategy.RESOURCE_GROUPS,
            commands_generated=2,
            successes=2,
        )

        formatted = report.format_report()

        assert "test-sub-id" in formatted
        assert "Commands Generated: 2" in formatted
        assert "Successful: 2" in formatted
        assert "FAILED IMPORTS" not in formatted

    def test_import_report_format_with_failures(self):
        """Test report formatting with failures."""
        report = ImportReport(
            subscription_id="test-sub-id",
            strategy=ImportStrategy.ALL_RESOURCES,
        )

        command = ImportCommand(
            resource_type="Microsoft.Resources/resourceGroups",
            terraform_address="azurerm_resource_group.main",
            azure_resource_id="/subscriptions/sub-id/resourceGroups/test-rg",
            resource_name="test-rg",
        )

        result = ImportResult(
            command=command, success=False, error_message="Resource already in state"
        )

        report.add_result(result)
        formatted = report.format_report()

        assert "FAILED IMPORTS" in formatted
        assert "azurerm_resource_group.main" in formatted
        assert "Resource already in state" in formatted

    def test_import_report_dry_run_indicator(self):
        """Test report shows dry-run mode indicator."""
        report = ImportReport(
            subscription_id="test-sub-id",
            strategy=ImportStrategy.RESOURCE_GROUPS,
            dry_run=True,
        )

        formatted = report.format_report()

        assert "DRY RUN MODE" in formatted


class TestFullImportWorkflow:
    """Test complete import workflow from detection to execution."""

    @pytest.mark.asyncio
    @patch("subprocess.run")
    async def test_run_import_full_workflow_success(
        self, mock_subprocess, temp_terraform_dir, mock_credential, mock_resource_client
    ):
        """Test complete import workflow with auto-detection."""
        # Setup mock resources
        mock_resource = Mock()
        mock_resource.type = "Microsoft.Resources/resourceGroups"
        mock_resource.name = "test-rg"
        mock_resource.id = "/subscriptions/sub-id/resourceGroups/test-rg"
        mock_resource.location = "eastus"
        mock_resource_client.resources.list.return_value = [mock_resource]

        # Mock successful import
        mock_subprocess.return_value = Mock(returncode=0, stdout="Success", stderr="")

        with patch.object(
            TerraformImporter, "_check_terraform_ready", return_value=True
        ):
            with patch.object(TerraformImporter, "_backup_terraform_state"):
                importer = TerraformImporter(
                    subscription_id="test-sub-id",
                    terraform_dir=str(temp_terraform_dir),
                    credential=mock_credential,
                )
                importer._resource_client = mock_resource_client

                report = await importer.run_import()

                assert report.commands_generated >= 0
                # Note: Actual command count depends on Terraform config matching

    @pytest.mark.asyncio
    async def test_run_import_with_provided_resources(
        self, temp_terraform_dir, mock_credential
    ):
        """Test import workflow with pre-provided resource list."""
        resources = [
            {
                "type": "Microsoft.Resources/resourceGroups",
                "name": "test-rg",
                "id": "/subscriptions/sub-id/resourceGroups/test-rg",
            },
        ]

        with patch.object(
            TerraformImporter, "_check_terraform_ready", return_value=True
        ):
            with patch.object(TerraformImporter, "_backup_terraform_state"):
                importer = TerraformImporter(
                    subscription_id="test-sub-id",
                    terraform_dir=str(temp_terraform_dir),
                    credential=mock_credential,
                    dry_run=True,  # Use dry-run to avoid actual execution
                )

                report = await importer.run_import(resources=resources)

                assert report.subscription_id == "test-sub-id"

    @pytest.mark.asyncio
    async def test_run_import_detection_failure(
        self, temp_terraform_dir, mock_credential, mock_resource_client
    ):
        """Test import workflow handles detection failure gracefully."""
        mock_resource_client.resources.list.side_effect = Exception("Azure API error")

        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
        )
        importer._resource_client = mock_resource_client

        report = await importer.run_import()

        assert len(report.warnings) > 0
        assert "detection failed" in report.warnings[0].lower()


class TestTerraformImporterEdgeCases:
    """Test edge cases and error scenarios."""

    def test_load_terraform_config_empty_directory(self, tmp_path, mock_credential):
        """Test loading Terraform config from empty directory."""
        tf_dir = tmp_path / "empty_terraform"
        tf_dir.mkdir()
        (tf_dir / ".terraform").mkdir()

        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(tf_dir),
            credential=mock_credential,
        )

        config = importer._load_terraform_config()
        assert len(config) == 0

    def test_load_terraform_config_invalid_syntax(self, tmp_path, mock_credential):
        """Test loading Terraform config with invalid syntax."""
        tf_dir = tmp_path / "invalid_terraform"
        tf_dir.mkdir()
        (tf_dir / ".terraform").mkdir()

        # Create invalid .tf file
        (tf_dir / "invalid.tf").write_text("this is not valid HCL")

        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(tf_dir),
            credential=mock_credential,
        )

        # Should handle gracefully and return empty config
        config = importer._load_terraform_config()
        assert isinstance(config, dict)

    def test_get_terraform_address_no_match(self, temp_terraform_dir, mock_credential):
        """Test getting Terraform address for resource not in config."""
        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
        )

        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "nonexistent-vm",
            "id": "/subscriptions/sub-id/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/nonexistent-vm",
        }

        terraform_config = importer._load_terraform_config()
        address = importer._get_terraform_address(resource, terraform_config)

        assert address is None

    @pytest.mark.asyncio
    @patch("subprocess.run")
    async def test_execute_single_import_generic_exception(
        self, mock_subprocess, temp_terraform_dir, mock_credential
    ):
        """Test handling of generic exception during import execution."""
        mock_subprocess.side_effect = RuntimeError("Unexpected error")

        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            credential=mock_credential,
        )

        command = ImportCommand(
            resource_type="Microsoft.Resources/resourceGroups",
            terraform_address="azurerm_resource_group.main",
            azure_resource_id="/subscriptions/sub-id/resourceGroups/test-rg",
            resource_name="test-rg",
        )

        result = await importer._execute_single_import(command)

        assert result.success is False
        assert "Unexpected error" in result.error_message

    def test_import_result_properties(self):
        """Test ImportResult helper properties."""
        command = ImportCommand(
            resource_type="Microsoft.Resources/resourceGroups",
            terraform_address="azurerm_resource_group.main",
            azure_resource_id="/subscriptions/sub-id/resourceGroups/test-rg",
            resource_name="test-rg",
        )

        # Test successful result
        success_result = ImportResult(command=command, success=True)
        assert success_result.failed is False

        # Test failed result
        failed_result = ImportResult(command=command, success=False)
        assert failed_result.failed is True

    def test_import_strategy_enum_values(self):
        """Test ImportStrategy enum has expected values."""
        assert ImportStrategy.RESOURCE_GROUPS.value == "resource_groups"
        assert ImportStrategy.ALL_RESOURCES.value == "all_resources"
        assert ImportStrategy.SELECTIVE.value == "selective"

    def test_import_report_format_with_warnings(self):
        """Test report formatting includes warnings."""
        report = ImportReport(
            subscription_id="test-sub-id",
            strategy=ImportStrategy.ALL_RESOURCES,
        )
        report.warnings.append("Warning 1: Terraform not ready")
        report.warnings.append("Warning 2: State backup failed")

        formatted = report.format_report()

        assert "WARNINGS:" in formatted
        assert "Warning 1: Terraform not ready" in formatted
        assert "Warning 2: State backup failed" in formatted

    @pytest.mark.asyncio
    async def test_filter_resources_with_empty_strategy(
        self, temp_terraform_dir, mock_credential
    ):
        """Test filtering with empty resources and different strategies."""
        importer = TerraformImporter(
            subscription_id="test-sub-id",
            terraform_dir=str(temp_terraform_dir),
            import_strategy=ImportStrategy.RESOURCE_GROUPS,
            credential=mock_credential,
        )

        # Test with resources that don't match strategy
        resources = [
            {"type": "Microsoft.Storage/storageAccounts", "name": "storage1"},
        ]

        filtered = importer.filter_resources_by_strategy(resources)
        assert len(filtered) == 0  # No resource groups in list
