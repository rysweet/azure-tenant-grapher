"""Tests for Cloud Toolkit Replication Plugin."""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.iac.plugins.cloud_toolkit_plugin import CloudToolkitReplicationPlugin
from src.iac.plugins.models import (
    AnalysisStatus,
    DataPlaneAnalysis,
    ExtractionResult,
    ReplicationResult,
    ReplicationStatus,
    StepType,
)


@pytest.fixture
def plugin():
    """Create plugin instance."""
    return CloudToolkitReplicationPlugin(
        ssh_username="testuser",
        ssh_password="testpass",
    )


@pytest.fixture
def cloud_toolkit_vm_resource():
    """Sample cloud toolkit VM resource."""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/atevet12ct001",
        "name": "atevet12ct001",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "properties": {
            "osProfile": {
                "computerName": "atevet12ct001",
                "adminUsername": "azureuser",
            },
            "storageProfile": {
                "imageReference": {
                    "publisher": "Canonical",
                    "offer": "UbuntuServer",
                    "sku": "20.04-LTS",
                },
            },
            "networkProfile": {
                "networkInterfaces": [
                    {
                        "properties": {
                            "ipConfigurations": [
                                {
                                    "properties": {
                                        "publicIPAddress": {"properties": {"ipAddress": "10.0.0.10"}}
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        },
        "tags": {
            "purpose": "cloud-toolkit",
            "role": "devops",
        },
    }


@pytest.fixture
def regular_vm_resource():
    """Sample regular VM resource (not cloud toolkit)."""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/regular-vm",
        "name": "regular-vm",
        "type": "Microsoft.Compute/virtualMachines",
        "properties": {
            "osProfile": {
                "computerName": "regularvm001",
            },
            "storageProfile": {
                "imageReference": {
                    "publisher": "Canonical",
                    "offer": "UbuntuServer",
                },
            },
        },
        "tags": {},
    }


class TestPluginMetadata:
    """Test plugin metadata."""

    def test_metadata(self, plugin):
        """Test plugin metadata is correct."""
        metadata = plugin.metadata

        assert metadata.name == "cloud_toolkit"
        assert metadata.version == "1.0.0"
        assert "Microsoft.Compute/virtualMachines" in metadata.resource_types
        assert metadata.requires_ssh is True
        assert metadata.requires_winrm is False
        assert "linux" in metadata.supported_os
        assert "asyncssh" in metadata.dependencies
        assert metadata.complexity == "MEDIUM"
        assert "cloud" in metadata.tags
        assert "devops" in metadata.tags

    def test_resource_types(self, plugin):
        """Test resource_types property."""
        assert plugin.resource_types == ["Microsoft.Compute/virtualMachines"]


class TestCanHandle:
    """Test can_handle method."""

    def test_can_handle_by_name_cloud(self, plugin):
        """Test can handle VM with 'cloud' in name."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "cloud-toolkit-vm",
            "properties": {
                "storageProfile": {"imageReference": {"offer": "UbuntuServer"}},
                "osProfile": {},
            },
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_by_name_toolkit(self, plugin):
        """Test can handle VM with 'toolkit' in name."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "dev-toolkit-001",
            "properties": {
                "storageProfile": {"imageReference": {"offer": "UbuntuServer"}},
                "osProfile": {},
            },
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_by_name_devops(self, plugin):
        """Test can handle VM with 'devops' in name."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "devops-automation",
            "properties": {
                "storageProfile": {"imageReference": {"offer": "UbuntuServer"}},
                "osProfile": {},
            },
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_by_computer_name_ct(self, plugin):
        """Test can handle VM with 'ct' in computer name."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "atevet12ct001",
            "properties": {
                "storageProfile": {"imageReference": {"offer": "UbuntuServer"}},
                "osProfile": {"computerName": "atevet12ct001"},
            },
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_by_tags_purpose(self, plugin):
        """Test can handle VM with cloud toolkit purpose tag."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "vm-001",
            "properties": {
                "storageProfile": {"imageReference": {"offer": "UbuntuServer"}},
                "osProfile": {},
            },
            "tags": {"purpose": "cloud-toolkit"},
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_by_tags_role(self, plugin):
        """Test can handle VM with devops role tag."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "vm-001",
            "properties": {
                "storageProfile": {"imageReference": {"offer": "UbuntuServer"}},
                "osProfile": {},
            },
            "tags": {"role": "DevOps"},
        }
        assert plugin.can_handle(resource) is True

    def test_cannot_handle_regular_vm(self, plugin, regular_vm_resource):
        """Test cannot handle regular VM."""
        assert plugin.can_handle(regular_vm_resource) is False

    def test_cannot_handle_wrong_resource_type(self, plugin):
        """Test cannot handle non-VM resource."""
        resource = {
            "type": "Microsoft.Storage/storageAccounts",
            "name": "cloud-storage",
            "properties": {},
        }
        assert plugin.can_handle(resource) is False


class TestExtractHostname:
    """Test _extract_hostname method."""

    def test_extract_hostname_from_public_ip(self, plugin, cloud_toolkit_vm_resource):
        """Test extracting hostname from public IP."""
        hostname = plugin._extract_hostname(cloud_toolkit_vm_resource)
        assert hostname == "10.0.0.10"

    def test_extract_hostname_from_tags(self, plugin):
        """Test extracting hostname from tags."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {},
            "tags": {"hostname": "toolkit.example.com"},
        }
        hostname = plugin._extract_hostname(resource)
        assert hostname == "toolkit.example.com"

    def test_extract_hostname_from_metadata(self, plugin):
        """Test extracting hostname from metadata."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {},
            "metadata": {"hostname": "meta.example.com"},
        }
        hostname = plugin._extract_hostname(resource)
        assert hostname == "meta.example.com"

    def test_extract_hostname_returns_none(self, plugin):
        """Test returns None when no hostname found."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {},
        }
        hostname = plugin._extract_hostname(resource)
        assert hostname is None


class TestSanitizeCredentials:
    """Test _sanitize_credentials method."""

    def test_sanitize_api_key(self, plugin):
        """Test sanitizing API key."""
        content = 'api_key="abcd1234567890efghij1234567890"'
        sanitized = plugin._sanitize_credentials(content)
        assert "abcd1234567890efghij1234567890" not in sanitized
        assert "***SANITIZED***" in sanitized

    def test_sanitize_password(self, plugin):
        """Test sanitizing password."""
        content = 'password="MySecretPass123"'
        sanitized = plugin._sanitize_credentials(content)
        assert "MySecretPass123" not in sanitized
        assert "***SANITIZED***" in sanitized

    def test_sanitize_client_secret(self, plugin):
        """Test sanitizing client secret."""
        content = 'client_secret="abc123-def456-ghi789"'
        sanitized = plugin._sanitize_credentials(content)
        assert "abc123-def456-ghi789" not in sanitized
        assert "***SANITIZED***" in sanitized

    def test_sanitize_access_key(self, plugin):
        """Test sanitizing access key."""
        content = 'access_key="AKIAIOSFODNN7EXAMPLE"'
        sanitized = plugin._sanitize_credentials(content)
        assert "AKIAIOSFODNN7EXAMPLE" not in sanitized
        assert "***SANITIZED***" in sanitized

    def test_sanitize_ssh_private_key(self, plugin):
        """Test sanitizing SSH private key."""
        content = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA1234567890abcdefghij
-----END RSA PRIVATE KEY-----"""
        sanitized = plugin._sanitize_credentials(content)
        assert "MIIEpAIBAAKCAQEA1234567890abcdefghij" not in sanitized
        assert "***SANITIZED***" in sanitized
        assert "BEGIN RSA PRIVATE KEY" in sanitized
        assert "END RSA PRIVATE KEY" in sanitized

    def test_sanitize_azure_subscription_id(self, plugin):
        """Test sanitizing Azure subscription ID."""
        content = "subscription_id=12345678-1234-1234-1234-123456789abc"
        sanitized = plugin._sanitize_credentials(content)
        assert "12345678-1234-1234-1234-123456789abc" not in sanitized
        assert "XXXX" in sanitized

    def test_sanitize_aws_account_number(self, plugin):
        """Test sanitizing AWS account number."""
        content = "account: 123456789012"
        sanitized = plugin._sanitize_credentials(content)
        assert "123456789012" not in sanitized
        assert "XXXXXXXXXXXX" in sanitized

    def test_sanitize_preserves_structure(self, plugin):
        """Test that sanitization preserves file structure."""
        content = """
[default]
api_key=secret123
region=us-east-1
output=json
"""
        sanitized = plugin._sanitize_credentials(content)
        assert "region=us-east-1" in sanitized
        assert "output=json" in sanitized
        assert "secret123" not in sanitized


class TestAnalyzeSource:
    """Test analyze_source method."""

    @pytest.mark.asyncio
    async def test_analyze_source_basic(self, plugin, cloud_toolkit_vm_resource):
        """Test basic source analysis."""
        analysis = await plugin.analyze_source(cloud_toolkit_vm_resource)

        assert isinstance(analysis, DataPlaneAnalysis)
        assert analysis.resource_type == "Microsoft.Compute/virtualMachines"
        assert len(analysis.elements) > 0
        assert analysis.requires_credentials is True
        assert analysis.status == AnalysisStatus.SUCCESS
        assert "SSH" in analysis.connection_methods

    @pytest.mark.asyncio
    async def test_analyze_source_discovers_cloud_tools(self, plugin, cloud_toolkit_vm_resource):
        """Test that analysis discovers cloud CLI tools."""
        analysis = await plugin.analyze_source(cloud_toolkit_vm_resource)

        element_names = [e.name for e in analysis.elements]
        assert "azure_cli" in element_names
        assert "aws_cli" in element_names
        assert "gcloud_cli" in element_names
        assert "terraform" in element_names
        assert "kubectl" in element_names
        assert "helm" in element_names

    @pytest.mark.asyncio
    async def test_analyze_source_discovers_configs(self, plugin, cloud_toolkit_vm_resource):
        """Test that analysis discovers configuration files."""
        analysis = await plugin.analyze_source(cloud_toolkit_vm_resource)

        element_names = [e.name for e in analysis.elements]
        assert "azure_config" in element_names
        assert "aws_config" in element_names
        assert "kube_config" in element_names
        assert "terraform_config" in element_names

    @pytest.mark.asyncio
    async def test_analyze_source_discovers_iac_templates(self, plugin, cloud_toolkit_vm_resource):
        """Test that analysis discovers IaC templates."""
        analysis = await plugin.analyze_source(cloud_toolkit_vm_resource)

        element_names = [e.name for e in analysis.elements]
        assert "terraform_modules" in element_names
        assert "arm_bicep_templates" in element_names
        assert "cloudformation_templates" in element_names
        assert "ansible_playbooks" in element_names

    @pytest.mark.asyncio
    async def test_analyze_source_marks_sensitive(self, plugin, cloud_toolkit_vm_resource):
        """Test that sensitive data is marked."""
        analysis = await plugin.analyze_source(cloud_toolkit_vm_resource)

        sensitive_elements = [e for e in analysis.elements if e.is_sensitive]
        assert len(sensitive_elements) > 0

        sensitive_names = [e.name for e in sensitive_elements]
        assert "azure_config" in sensitive_names
        assert "aws_config" in sensitive_names
        assert "kube_config" in sensitive_names

    @pytest.mark.asyncio
    async def test_analyze_source_estimates_complexity(self, plugin, cloud_toolkit_vm_resource):
        """Test complexity scoring."""
        analysis = await plugin.analyze_source(cloud_toolkit_vm_resource)

        assert analysis.complexity_score > 0
        assert analysis.complexity_score <= 10
        assert analysis.total_estimated_size_mb > 0
        assert analysis.estimated_extraction_time_minutes > 0

    @pytest.mark.asyncio
    async def test_analyze_source_no_hostname_warning(self, plugin):
        """Test warning when no hostname available."""
        resource = {
            "id": "test-vm",
            "type": "Microsoft.Compute/virtualMachines",
            "name": "cloud-toolkit-vm",
            "properties": {},
        }

        analysis = await plugin.analyze_source(resource)
        assert len(analysis.warnings) > 0
        assert any("hostname" in w.lower() for w in analysis.warnings)


class TestExtractData:
    """Test extract_data method."""

    @pytest.fixture
    def mock_ssh_connection(self):
        """Mock SSH connection."""
        conn = AsyncMock()
        conn.close = AsyncMock()
        return conn

    @pytest.fixture
    def mock_run_command(self):
        """Mock command execution."""

        async def _run_command(conn, command):
            # Return mock responses based on command
            if "az version" in command:
                return '{"azure-cli": "2.48.0"}', "", 0
            elif "aws --version" in command:
                return "aws-cli/2.11.0 Python/3.11.2", "", 0
            elif "gcloud version" in command:
                return "Google Cloud SDK 420.0.0", "", 0
            elif "terraform version" in command:
                return "Terraform v1.4.2", "", 0
            elif "kubectl version" in command:
                return "Client Version: v1.26.0", "", 0
            elif "helm version" in command:
                return "version.BuildInfo{Version:\"v3.11.0\"}", "", 0
            elif "az account list" in command:
                return '[{"id":"sub-123","name":"Test"}]', "", 0
            elif "az configure --list-defaults" in command:
                return '{"output":"json"}', "", 0
            elif "aws configure list" in command:
                return "access_key ***\nregion us-east-1", "", 0
            elif "kubectl plugin list" in command:
                return "kubectl-plugin1\nkubectl-plugin2", "", 0
            elif 'find ~/ -type f \\( -name "*.tf"' in command:
                return "~/terraform/main.tf\n~/terraform/variables.tf", "", 0
            elif 'find ~/ -type f -name "*.bicep"' in command:
                return "~/iac/template.bicep", "", 0
            elif "grep -i ansible" in command:
                return "~/ansible/playbook.yml", "", 0
            elif 'find ~/ -type f \\( -name "deploy*.sh"' in command:
                return "~/scripts/deploy.sh", "", 0
            elif "find ~/ -name .git" in command:
                return "~/repos/project1/.git\n~/repos/project2/.git", "", 0
            elif 'find ~/ -type d \\( -name "venv"' in command:
                return "~/project1/venv\n~/project2/.venv", "", 0
            elif "docker images" in command:
                return "nginx:latest\nubuntu:20.04", "", 0
            elif "ls ~/.ssh/*.pub" in command:
                return "~/.ssh/id_rsa.pub\n~/.ssh/id_ed25519.pub", "", 0
            elif "uname -a" in command:
                return "Linux toolkit 5.15.0 x86_64 GNU/Linux", "", 0
            else:
                return "", "", 0

        return _run_command

    @pytest.mark.asyncio
    async def test_extract_data_success(
        self, plugin, cloud_toolkit_vm_resource, mock_ssh_connection, mock_run_command
    ):
        """Test successful data extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command):
                    result = await plugin.extract_data(cloud_toolkit_vm_resource, Mock())

        assert isinstance(result, ExtractionResult)
        assert len(result.extracted_data) > 0
        assert len(result.extracted_files) > 0
        assert result.items_extracted > 0
        assert result.extraction_duration_seconds >= 0
        assert result.status == AnalysisStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_extract_data_extracts_tool_versions(
        self, plugin, cloud_toolkit_vm_resource, mock_ssh_connection, mock_run_command
    ):
        """Test that tool versions are extracted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command):
                    result = await plugin.extract_data(cloud_toolkit_vm_resource, Mock())

        extracted_names = [item.name for item in result.extracted_data]
        assert "azure_cli_version" in extracted_names
        assert "aws_cli_version" in extracted_names
        assert "gcloud_version" in extracted_names
        assert "terraform_version" in extracted_names

    @pytest.mark.asyncio
    async def test_extract_data_sanitizes_configs(
        self, plugin, cloud_toolkit_vm_resource, mock_ssh_connection, mock_run_command
    ):
        """Test that extracted configs are sanitized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command):
                    result = await plugin.extract_data(cloud_toolkit_vm_resource, Mock())

        # Find Azure config
        azure_items = [item for item in result.extracted_data if "azure" in item.name.lower()]
        assert len(azure_items) > 0

        # Check metadata indicates sanitization
        for item in azure_items:
            if item.metadata.get("sanitized"):
                assert "***SANITIZED***" in item.content or "XXXX" in item.content

    @pytest.mark.asyncio
    async def test_extract_data_creates_inventories(
        self, plugin, cloud_toolkit_vm_resource, mock_ssh_connection, mock_run_command
    ):
        """Test that file inventories are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command):
                    result = await plugin.extract_data(cloud_toolkit_vm_resource, Mock())

        extracted_names = [item.name for item in result.extracted_data]
        assert "terraform_files_inventory" in extracted_names
        assert "git_repositories_inventory" in extracted_names
        assert "docker_images_inventory" in extracted_names

    @pytest.mark.asyncio
    async def test_extract_data_writes_files(
        self, plugin, cloud_toolkit_vm_resource, mock_ssh_connection, mock_run_command
    ):
        """Test that extracted data is written to files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command):
                    result = await plugin.extract_data(cloud_toolkit_vm_resource, Mock())

        # Check files exist
        for file_path in result.extracted_files:
            assert Path(file_path).exists()
            assert Path(file_path).stat().st_size > 0

        # Check summary file
        summary_files = [f for f in result.extracted_files if "summary" in f]
        assert len(summary_files) > 0

    @pytest.mark.asyncio
    async def test_extract_data_no_hostname_raises(self, plugin):
        """Test extraction fails without hostname."""
        resource = {
            "id": "test-vm",
            "type": "Microsoft.Compute/virtualMachines",
            "name": "cloud-toolkit-vm",
            "properties": {},
        }

        with pytest.raises(ValueError, match="no hostname"):
            await plugin.extract_data(resource, Mock())

    @pytest.mark.asyncio
    async def test_extract_data_handles_connection_error(self, plugin, cloud_toolkit_vm_resource):
        """Test extraction handles connection errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(
                plugin, "_connect_ssh", side_effect=ConnectionError("Connection failed")
            ):
                result = await plugin.extract_data(cloud_toolkit_vm_resource, Mock())

        assert isinstance(result, ExtractionResult)
        assert len(result.errors) > 0
        assert any("connection failed" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_extract_data_continues_on_partial_failure(
        self, plugin, cloud_toolkit_vm_resource, mock_ssh_connection
    ):
        """Test extraction continues when some commands fail."""

        async def partial_run_command(conn, command):
            if "az version" in command:
                return '{"azure-cli": "2.48.0"}', "", 0
            elif "aws --version" in command:
                raise Exception("Command failed")
            else:
                return "", "", 1

        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=partial_run_command):
                    result = await plugin.extract_data(cloud_toolkit_vm_resource, Mock())

        # Should have extracted some data despite failures
        assert result.items_extracted > 0
        assert result.items_failed > 0 or len(result.warnings) > 0
        assert result.status == AnalysisStatus.PARTIAL


class TestGenerateReplicationSteps:
    """Test generate_replication_steps method."""

    @pytest.fixture
    def extraction_result(self, tmp_path):
        """Sample extraction result."""
        return ExtractionResult(
            resource_id="test-vm",
            extracted_data=[
                Mock(name="azure_cli_version", content='{"version": "2.48.0"}'),
                Mock(name="terraform_version", content="Terraform v1.4.2"),
            ],
            items_extracted=10,
            items_failed=0,
            metadata={"output_dir": str(tmp_path)},
        )

    @pytest.mark.asyncio
    async def test_generate_steps(self, plugin, extraction_result):
        """Test step generation."""
        steps = await plugin.generate_replication_steps(extraction_result)

        assert len(steps) > 0
        assert len(steps) >= 8  # Should have at least 8 steps

    @pytest.mark.asyncio
    async def test_generate_steps_creates_playbook(self, plugin, extraction_result):
        """Test that Ansible playbook is created."""
        output_dir = Path(extraction_result.metadata["output_dir"])

        await plugin.generate_replication_steps(extraction_result)

        playbook_path = output_dir / "cloud_toolkit_setup.yml"
        assert playbook_path.exists()
        assert playbook_path.stat().st_size > 0

        # Check playbook content
        content = playbook_path.read_text()
        assert "Setup Cloud Toolkit Environment" in content
        assert "Azure CLI" in content or "azure" in content.lower()

    @pytest.mark.asyncio
    async def test_generate_steps_creates_manual_guide(self, plugin, extraction_result):
        """Test that manual setup guide is created."""
        output_dir = Path(extraction_result.metadata["output_dir"])

        await plugin.generate_replication_steps(extraction_result)

        guide_path = output_dir / "MANUAL_SETUP_GUIDE.md"
        assert guide_path.exists()
        assert guide_path.stat().st_size > 0

        # Check guide content
        content = guide_path.read_text()
        assert "Manual Setup Guide" in content
        assert "credentials" in content.lower()

    @pytest.mark.asyncio
    async def test_generate_steps_correct_types(self, plugin, extraction_result):
        """Test steps have correct types."""
        steps = await plugin.generate_replication_steps(extraction_result)

        # Find steps by type
        validation_steps = [s for s in steps if s.step_type == StepType.VALIDATION]
        prerequisite_steps = [s for s in steps if s.step_type == StepType.PREREQUISITE]
        config_steps = [s for s in steps if s.step_type == StepType.CONFIGURATION]

        assert len(validation_steps) > 0
        assert len(prerequisite_steps) > 0
        assert len(config_steps) > 0

    @pytest.mark.asyncio
    async def test_generate_steps_correct_order(self, plugin, extraction_result):
        """Test steps are in correct dependency order."""
        steps = await plugin.generate_replication_steps(extraction_result)

        step_ids = [s.step_id for s in steps]

        # validate_target should be first
        assert step_ids[0] == "validate_target"

        # Check dependencies
        step_ids.index("validate_target")
        install_base_idx = step_ids.index("install_base_tools")
        install_cloud_idx = step_ids.index("install_cloud_clis")

        # Base tools should depend on validate
        base_tools_step = steps[install_base_idx]
        assert "validate_target" in base_tools_step.depends_on

        # Cloud CLIs should depend on base tools
        cloud_clis_step = steps[install_cloud_idx]
        assert "install_base_tools" in cloud_clis_step.depends_on

    @pytest.mark.asyncio
    async def test_generate_steps_marks_manual(self, plugin, extraction_result):
        """Test manual steps are marked."""
        steps = await plugin.generate_replication_steps(extraction_result)

        manual_steps = [s for s in steps if s.metadata.get("manual_step", False)]
        assert len(manual_steps) > 0

        # Credentials configuration should be manual
        cred_steps = [s for s in manual_steps if "credentials" in s.step_id.lower()]
        assert len(cred_steps) > 0

    @pytest.mark.asyncio
    async def test_generate_steps_includes_verification(self, plugin, extraction_result):
        """Test verification step is included."""
        steps = await plugin.generate_replication_steps(extraction_result)

        verify_steps = [s for s in steps if "verify" in s.step_id.lower()]
        assert len(verify_steps) > 0

        # Check verification script exists
        verify_step = verify_steps[0]
        assert len(verify_step.script_content) > 0


class TestApplyToTarget:
    """Test apply_to_target method."""

    @pytest.mark.asyncio
    async def test_apply_to_target_simulated(self, plugin):
        """Test simulated application to target."""
        steps = [
            Mock(step_id="step1", description="Test step 1", metadata={}),
            Mock(step_id="step2", description="Test step 2", metadata={}),
        ]

        result = await plugin.apply_to_target(steps, "target-vm-id")

        assert isinstance(result, ReplicationResult)
        assert result.target_resource_id == "target-vm-id"
        assert len(result.steps_executed) == 2
        assert result.steps_succeeded >= 0
        assert result.total_duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_apply_to_target_skips_manual_steps(self, plugin):
        """Test that manual steps are skipped."""
        steps = [
            Mock(step_id="auto", description="Automated", metadata={}),
            Mock(step_id="manual", description="Manual", metadata={"manual_step": True}),
        ]

        result = await plugin.apply_to_target(steps, "target-vm-id")

        assert result.steps_skipped > 0
        assert result.status == ReplicationStatus.PARTIAL_SUCCESS

    @pytest.mark.asyncio
    async def test_apply_to_target_includes_warnings(self, plugin):
        """Test result includes warnings about manual steps."""
        steps = [Mock(step_id="step1", description="Test", metadata={"manual_step": True})]

        result = await plugin.apply_to_target(steps, "target-vm-id")

        assert len(result.warnings) > 0
        assert any("manual" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_apply_to_target_calculates_fidelity(self, plugin):
        """Test fidelity score calculation."""
        steps = [
            Mock(step_id="auto1", description="Auto 1", metadata={}),
            Mock(step_id="auto2", description="Auto 2", metadata={}),
            Mock(step_id="manual", description="Manual", metadata={"manual_step": True}),
        ]

        result = await plugin.apply_to_target(steps, "target-vm-id")

        assert 0.0 <= result.fidelity_score <= 1.0
        # 2 out of 3 steps automated = ~0.67 fidelity
        assert result.fidelity_score > 0.5

    @pytest.mark.asyncio
    async def test_apply_to_target_metadata(self, plugin):
        """Test result metadata."""
        steps = [Mock(step_id="step1", description="Test", metadata={})]

        result = await plugin.apply_to_target(steps, "target-vm-id")

        assert "total_steps" in result.metadata
        assert "simulated" in result.metadata
        assert result.metadata["simulated"] is True


class TestFullReplication:
    """Test full replication workflow."""

    @pytest.mark.asyncio
    async def test_replicate_workflow(self, plugin, cloud_toolkit_vm_resource):
        """Test full replicate() workflow."""
        mock_analysis = Mock(spec=DataPlaneAnalysis)
        mock_extraction = Mock(spec=ExtractionResult)
        mock_steps = [Mock(step_id="step1", metadata={})]
        mock_result = Mock(spec=ReplicationResult)

        with patch.object(plugin, "analyze_source", return_value=mock_analysis):
            with patch.object(plugin, "extract_data", return_value=mock_extraction):
                with patch.object(plugin, "generate_replication_steps", return_value=mock_steps):
                    with patch.object(plugin, "apply_to_target", return_value=mock_result):
                        result = await plugin.replicate(cloud_toolkit_vm_resource, "target-vm-id")

        assert result == mock_result


class TestPluginIntegration:
    """Integration tests for plugin."""

    def test_plugin_initialization(self):
        """Test plugin can be initialized."""
        plugin = CloudToolkitReplicationPlugin()
        assert plugin is not None
        assert plugin.ssh_username is not None

    def test_plugin_initialization_with_env(self):
        """Test plugin uses environment variables."""
        with patch.dict(
            os.environ, {"SSH_USERNAME": "envuser", "SSH_PASSWORD": "envpass"}
        ):
            plugin = CloudToolkitReplicationPlugin()
            assert plugin.ssh_username == "envuser"
            assert plugin.ssh_password == "envpass"

    def test_plugin_initialization_with_params(self):
        """Test plugin uses provided parameters."""
        plugin = CloudToolkitReplicationPlugin(
            ssh_username="paramuser",
            ssh_password="parampass",
            ssh_key_path="/path/to/key",
        )
        assert plugin.ssh_username == "paramuser"
        assert plugin.ssh_password == "parampass"
        assert plugin.ssh_key_path == "/path/to/key"

    def test_plugin_output_dir_default(self):
        """Test plugin creates temp output dir by default."""
        plugin = CloudToolkitReplicationPlugin()
        assert plugin.output_dir is None  # Created on first use

    def test_plugin_output_dir_custom(self):
        """Test plugin uses custom output dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin = CloudToolkitReplicationPlugin(output_dir=tmpdir)
            assert plugin.output_dir == Path(tmpdir)


class TestHelperMethods:
    """Test helper methods."""

    def test_generate_setup_playbook(self, plugin):
        """Test playbook generation."""
        extraction = ExtractionResult(
            resource_id="test-vm",
            extracted_data=[],
            items_extracted=0,
            items_failed=0,
            metadata={},
        )

        playbook = plugin._generate_setup_playbook(extraction)

        assert "Setup Cloud Toolkit Environment" in playbook
        assert "Azure CLI" in playbook
        assert "Terraform" in playbook
        assert "kubectl" in playbook

    def test_generate_manual_guide(self, plugin):
        """Test manual guide generation."""
        extraction = ExtractionResult(
            resource_id="test-vm",
            extracted_data=[],
            items_extracted=0,
            items_failed=0,
            metadata={},
        )

        guide = plugin._generate_manual_guide(extraction)

        assert "Manual Setup Guide" in guide
        assert "Azure CLI" in guide or "az login" in guide
        assert "credentials" in guide.lower()

    def test_generate_verification_script(self, plugin):
        """Test verification script generation."""
        script = plugin._generate_verification_script()

        assert "#!/bin/bash" in script
        assert "az version" in script or "Azure CLI" in script
        assert "terraform version" in script or "Terraform" in script
        assert "kubectl version" in script
