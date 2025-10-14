"""Tests for Linux Client Replication Plugin."""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.iac.plugins.linux_client_plugin import LinuxClientReplicationPlugin
from src.iac.plugins.models import (
    DataPlaneAnalysis,
    ExtractionResult,
    ReplicationResult,
)


@pytest.fixture
def plugin():
    """Create plugin instance."""
    return LinuxClientReplicationPlugin(
        ssh_username="testuser",
        ssh_password="testpass",
    )


@pytest.fixture
def linux_vm_resource():
    """Sample Linux VM resource."""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-linux-vm",
        "name": "test-linux-vm",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "properties": {
            "osProfile": {
                "computerName": "testlinuxcl001",
                "adminUsername": "azureuser",
            },
            "storageProfile": {
                "imageReference": {
                    "publisher": "Canonical",
                    "offer": "UbuntuServer",
                    "sku": "18.04-LTS",
                },
            },
            "networkProfile": {
                "networkInterfaces": [
                    {
                        "properties": {
                            "ipConfigurations": [
                                {
                                    "properties": {
                                        "publicIPAddress": {
                                            "properties": {
                                                "ipAddress": "10.0.0.4"
                                            }
                                        }
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        },
        "tags": {
            "os": "linux",
        },
    }


@pytest.fixture
def windows_vm_resource():
    """Sample Windows VM resource."""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-win-vm",
        "name": "test-win-vm",
        "type": "Microsoft.Compute/virtualMachines",
        "properties": {
            "osProfile": {
                "computerName": "testwin001",
            },
            "storageProfile": {
                "imageReference": {
                    "publisher": "MicrosoftWindowsServer",
                    "offer": "WindowsServer",
                },
            },
        },
        "tags": {
            "os": "windows",
        },
    }


class TestPluginMetadata:
    """Test plugin metadata."""

    def test_metadata(self, plugin):
        """Test plugin metadata is correct."""
        metadata = plugin.metadata

        assert metadata.name == "linux_client"
        assert metadata.version == "1.0.0"
        assert "Microsoft.Compute/virtualMachines" in metadata.resource_types
        assert metadata.requires_ssh is True
        assert metadata.requires_winrm is False
        assert "linux" in metadata.supported_os
        assert "asyncssh" in metadata.dependencies

    def test_resource_types(self, plugin):
        """Test resource_types property."""
        assert plugin.resource_types == ["Microsoft.Compute/virtualMachines"]


class TestCanHandle:
    """Test can_handle method."""

    def test_can_handle_linux_vm_by_image(self, plugin):
        """Test can handle Linux VM identified by image."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {
                "storageProfile": {
                    "imageReference": {
                        "offer": "UbuntuServer"
                    }
                }
            },
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_linux_vm_by_computer_name(self, plugin):
        """Test can handle Linux VM identified by computer name."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {
                "osProfile": {
                    "computerName": "testlinuxcl001"
                },
                "storageProfile": {},
            },
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_linux_vm_by_tags(self, plugin):
        """Test can handle Linux VM identified by tags."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {
                "storageProfile": {},
                "osProfile": {},
            },
            "tags": {
                "os": "Linux"
            },
        }
        assert plugin.can_handle(resource) is True

    def test_cannot_handle_windows_vm(self, plugin, windows_vm_resource):
        """Test cannot handle Windows VM."""
        assert plugin.can_handle(windows_vm_resource) is False

    def test_cannot_handle_wrong_resource_type(self, plugin):
        """Test cannot handle non-VM resource."""
        resource = {
            "type": "Microsoft.Storage/storageAccounts",
            "properties": {},
        }
        assert plugin.can_handle(resource) is False


class TestExtractHostname:
    """Test _extract_hostname method."""

    def test_extract_hostname_from_public_ip(self, plugin, linux_vm_resource):
        """Test extracting hostname from public IP."""
        hostname = plugin._extract_hostname(linux_vm_resource)
        assert hostname == "10.0.0.4"

    def test_extract_hostname_from_tags(self, plugin):
        """Test extracting hostname from tags."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {},
            "tags": {
                "hostname": "test.example.com"
            },
        }
        hostname = plugin._extract_hostname(resource)
        assert hostname == "test.example.com"

    def test_extract_hostname_from_metadata(self, plugin):
        """Test extracting hostname from metadata."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {},
            "metadata": {
                "hostname": "meta.example.com"
            },
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


class TestAnalyzeSource:
    """Test analyze_source method."""

    @pytest.mark.asyncio
    async def test_analyze_source_basic(self, plugin, linux_vm_resource):
        """Test basic source analysis."""
        analysis = await plugin.analyze_source(linux_vm_resource)

        assert isinstance(analysis, DataPlaneAnalysis)
        assert analysis.resource_type == "Microsoft.Compute/virtualMachines"
        assert len(analysis.elements) > 0
        assert analysis.requires_credentials is True

        # Check expected elements
        element_names = [e.name for e in analysis.elements]
        assert "users" in element_names
        assert "groups" in element_names
        assert "ssh_keys" in element_names
        assert "packages" in element_names
        assert "sshd_config" in element_names

    @pytest.mark.asyncio
    async def test_analyze_source_prioritizes_elements(self, plugin, linux_vm_resource):
        """Test that analysis prioritizes critical elements."""
        analysis = await plugin.analyze_source(linux_vm_resource)

        critical_elements = [e for e in analysis.elements if e.priority == "critical"]
        assert len(critical_elements) > 0

        # Users and SSH keys should be critical
        critical_names = [e.name for e in critical_elements]
        assert "users" in critical_names
        assert "ssh_keys" in critical_names

    @pytest.mark.asyncio
    async def test_analyze_source_marks_sensitive(self, plugin, linux_vm_resource):
        """Test that sensitive data is marked."""
        analysis = await plugin.analyze_source(linux_vm_resource)

        sensitive_elements = [e for e in analysis.elements if e.is_sensitive]
        assert len(sensitive_elements) > 0

        # Shadow and SSH keys should be sensitive
        sensitive_names = [e.name for e in sensitive_elements]
        assert "shadow" in sensitive_names
        assert "ssh_keys" in sensitive_names

    @pytest.mark.asyncio
    async def test_analyze_source_no_hostname_warning(self, plugin):
        """Test warning when no hostname available."""
        resource = {
            "id": "test-vm",
            "type": "Microsoft.Compute/virtualMachines",
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
            if "getent passwd" in command:
                return "root:x:0:0:root:/root:/bin/bash\ntestuser:x:1000:1000:Test User:/home/testuser:/bin/bash\n", "", 0
            elif "getent group" in command:
                return "root:x:0:\ntestuser:x:1000:\n", "", 0
            elif "shadow" in command:
                return "root:$6$encrypted:18000:0:99999:7:::\ntestuser:$6$encrypted:18000:0:99999:7:::\n", "", 0
            elif "find /home -name authorized_keys" in command:
                return "/home/testuser/.ssh/authorized_keys\n", "", 0
            elif "cat /home/testuser/.ssh/authorized_keys" in command:
                return "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAB test@example.com\n", "", 0
            elif "ls /etc/sudoers.d/" in command:
                return "testuser\n", "", 0
            elif "sudo cat /etc/sudoers.d/testuser" in command:
                return "testuser ALL=(ALL) NOPASSWD: ALL\n", "", 0
            elif "dpkg -l" in command:
                return "ii  vim  2:8.0  Text editor\n", "", 0
            elif "systemctl list-unit-files" in command:
                return "UNIT FILE                    STATE\nsshd.service                 enabled\n", "", 0
            elif "crontab -l" in command:
                return "0 * * * * /usr/bin/backup.sh\n", "", 0
            elif "cat /etc/ssh/sshd_config" in command:
                return "Port 22\nPermitRootLogin no\n", "", 0
            elif "ufw status" in command:
                return "Status: active\n", "", 0
            elif "uname -a" in command:
                return "Linux testhost 5.4.0 #1 SMP x86_64 GNU/Linux\n", "", 0
            elif "cat /etc/os-release" in command:
                return "NAME=\"Ubuntu\"\nVERSION=\"20.04\"\n", "", 0
            else:
                return "", "", 0

        return _run_command

    @pytest.mark.asyncio
    async def test_extract_data_success(
        self, plugin, linux_vm_resource, mock_ssh_connection, mock_run_command
    ):
        """Test successful data extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command):
                    result = await plugin.extract_data(linux_vm_resource, Mock())

        assert isinstance(result, ExtractionResult)
        assert len(result.extracted_files) > 0
        assert len(result.extracted_data) > 0
        assert result.size_bytes > 0
        assert result.extraction_duration_seconds >= 0

        # Check specific data was extracted
        assert "users" in result.extracted_data
        assert "groups" in result.extracted_data
        assert "root" in result.extracted_data["users"]
        assert "testuser" in result.extracted_data["users"]

    @pytest.mark.asyncio
    async def test_extract_data_sanitizes_shadow(
        self, plugin, linux_vm_resource, mock_ssh_connection, mock_run_command
    ):
        """Test that shadow file is sanitized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command):
                    result = await plugin.extract_data(linux_vm_resource, Mock())

            # Check shadow file was created
            shadow_files = [f for f in result.extracted_files if "shadow" in f]
            assert len(shadow_files) > 0

            # Verify sanitization
            shadow_content = Path(shadow_files[0]).read_text()
            assert "***SANITIZED***" in shadow_content
            assert "$6$encrypted" not in shadow_content

    @pytest.mark.asyncio
    async def test_extract_data_no_hostname_raises(self, plugin):
        """Test extraction fails without hostname."""
        resource = {
            "id": "test-vm",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {},
        }

        with pytest.raises(ValueError, match="no hostname"):
            await plugin.extract_data(resource, Mock())

    @pytest.mark.asyncio
    async def test_extract_data_handles_connection_error(self, plugin, linux_vm_resource):
        """Test extraction handles connection errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", side_effect=ConnectionError("Connection failed")):
                result = await plugin.extract_data(linux_vm_resource, Mock())

        assert isinstance(result, ExtractionResult)
        assert len(result.errors) > 0
        assert any("connection failed" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_extract_data_continues_on_partial_failure(
        self, plugin, linux_vm_resource, mock_ssh_connection
    ):
        """Test extraction continues when some commands fail."""

        async def partial_run_command(conn, command):
            if "getent passwd" in command:
                return "root:x:0:0:root:/root:/bin/bash\n", "", 0
            elif "shadow" in command:
                raise Exception("Permission denied")
            else:
                return "", "", 1

        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=partial_run_command):
                    result = await plugin.extract_data(linux_vm_resource, Mock())

        # Should have extracted some data despite failures
        assert len(result.extracted_data) > 0
        assert len(result.warnings) > 0 or len(result.errors) > 0


class TestGenerateReplicationSteps:
    """Test generate_replication_steps method."""

    @pytest.fixture
    def extraction_result(self, tmp_path):
        """Sample extraction result."""
        return ExtractionResult(
            resource_id="test-vm",
            extracted_files=[],
            extracted_data={
                "users": ["root", "testuser"],
                "groups": ["root", "testuser"],
            },
            scripts_generated=[],
            metadata={"output_dir": str(tmp_path)},
        )

    @pytest.mark.asyncio
    async def test_generate_steps(self, plugin, extraction_result):
        """Test step generation."""
        steps = await plugin.generate_replication_steps(extraction_result)

        assert len(steps) > 0
        assert len(extraction_result.scripts_generated) > 0

        # Check playbook was generated
        playbook_files = [f for f in extraction_result.scripts_generated if "playbook" in f]
        assert len(playbook_files) > 0

        # Verify playbook exists
        playbook_path = Path(playbook_files[0])
        assert playbook_path.exists()
        assert playbook_path.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_generate_steps_correct_order(self, plugin, extraction_result):
        """Test steps are in correct dependency order."""
        steps = await plugin.generate_replication_steps(extraction_result)

        step_ids = [s.step_id for s in steps]

        # validate_target should be first
        assert step_ids[0] == "validate_target"

        # Find indices
        step_ids.index("validate_target")
        users_idx = step_ids.index("replicate_users")
        ssh_keys_idx = step_ids.index("replicate_ssh_keys")

        # Users should depend on validate
        users_step = steps[users_idx]
        assert "validate_target" in users_step.depends_on

        # SSH keys should depend on users
        ssh_keys_step = steps[ssh_keys_idx]
        assert "replicate_users" in ssh_keys_step.depends_on

    @pytest.mark.asyncio
    async def test_generate_steps_marks_critical(self, plugin, extraction_result):
        """Test critical steps are marked."""
        steps = await plugin.generate_replication_steps(extraction_result)

        critical_steps = [s for s in steps if s.is_critical]
        assert len(critical_steps) > 0

        # Validate, users, and SSH keys should be critical
        critical_ids = [s.step_id for s in critical_steps]
        assert "validate_target" in critical_ids
        assert "replicate_users" in critical_ids
        assert "replicate_ssh_keys" in critical_ids

    @pytest.mark.asyncio
    async def test_generate_playbook_valid_yaml(self, plugin, extraction_result):
        """Test generated playbook is valid YAML."""
        await plugin.generate_replication_steps(extraction_result)

        playbook_files = [f for f in extraction_result.scripts_generated if "playbook" in f]
        playbook_path = Path(playbook_files[0])

        # Try to parse as YAML
        import yaml

        with open(playbook_path) as f:
            playbook = yaml.safe_load(f)

        assert isinstance(playbook, list)
        assert len(playbook) > 0
        assert "tasks" in playbook[0]


class TestApplyToTarget:
    """Test apply_to_target method."""

    @pytest.mark.asyncio
    async def test_apply_to_target_simulated(self, plugin):
        """Test application to target using ExecutionEngine."""
        from src.iac.plugins.models import ReplicationStep, StepType, ExtractionFormat, StepResult, ReplicationStatus

        steps = [
            ReplicationStep(
                step_id="step1",
                step_type=StepType.VALIDATION,
                description="Test step 1",
                script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
                depends_on=[],
                is_critical=False,
            ),
            ReplicationStep(
                step_id="step2",
                step_type=StepType.CONFIGURATION,
                description="Test step 2",
                script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
                depends_on=["step1"],
                is_critical=False,
            ),
        ]

        # Mock the ExecutionEngine
        with patch("src.iac.execution.engine.ExecutionEngine") as MockEngine:
            mock_engine_instance = MockEngine.return_value
            mock_engine_instance.execute_step = AsyncMock(
                return_value=StepResult(
                    step_id="test",
                    status=ReplicationStatus.SUCCESS,
                    duration_seconds=1.0,
                )
            )

            result = await plugin.apply_to_target(steps, "target-vm-id")

        assert isinstance(result, ReplicationResult)
        assert result.target_resource_id == "target-vm-id"
        assert len(result.steps_executed) == 2
        assert result.steps_failed == 0
        assert result.fidelity_score == 1.0

    @pytest.mark.asyncio
    async def test_apply_to_target_metadata(self, plugin):
        """Test result metadata."""
        from src.iac.plugins.models import ReplicationStep, StepType, ExtractionFormat, StepResult, ReplicationStatus

        steps = [
            ReplicationStep(
                step_id="step1",
                step_type=StepType.VALIDATION,
                description="Test",
                script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
                depends_on=[],
                is_critical=False,
            )
        ]

        # Mock the ExecutionEngine
        with patch("src.iac.execution.engine.ExecutionEngine") as MockEngine:
            mock_engine_instance = MockEngine.return_value
            mock_engine_instance.execute_step = AsyncMock(
                return_value=StepResult(
                    step_id="step1",
                    status=ReplicationStatus.SUCCESS,
                    duration_seconds=1.0,
                )
            )

            result = await plugin.apply_to_target(steps, "target-vm-id")

        assert "total_steps" in result.metadata
        assert "execution_engine" in result.metadata
        assert result.metadata["execution_engine"] == "ansible_runner"


class TestFullReplication:
    """Test full replication workflow."""

    @pytest.mark.asyncio
    async def test_replicate_workflow(self, plugin, linux_vm_resource):
        """Test full replicate() workflow."""
        # Mock all the steps
        mock_analysis = Mock(spec=DataPlaneAnalysis)
        mock_extraction = Mock(spec=ExtractionResult)
        mock_steps = [Mock(step_id="step1")]
        mock_result = Mock(spec=ReplicationResult)

        with patch.object(plugin, "analyze_source", return_value=mock_analysis):
            with patch.object(plugin, "extract_data", return_value=mock_extraction):
                with patch.object(plugin, "generate_replication_steps", return_value=mock_steps):
                    with patch.object(plugin, "apply_to_target", return_value=mock_result):
                        result = await plugin.replicate(linux_vm_resource, "target-vm-id")

        assert result == mock_result


class TestPluginIntegration:
    """Integration tests for plugin."""

    def test_plugin_initialization(self):
        """Test plugin can be initialized."""
        plugin = LinuxClientReplicationPlugin()
        assert plugin is not None
        assert plugin.ssh_username is not None

    def test_plugin_initialization_with_env(self):
        """Test plugin uses environment variables."""
        with patch.dict(os.environ, {"SSH_USERNAME": "envuser", "SSH_PASSWORD": "envpass"}):
            plugin = LinuxClientReplicationPlugin()
            assert plugin.ssh_username == "envuser"
            assert plugin.ssh_password == "envpass"

    def test_plugin_initialization_with_params(self):
        """Test plugin uses provided parameters."""
        plugin = LinuxClientReplicationPlugin(
            ssh_username="paramuser",
            ssh_password="parampass",
            ssh_key_path="/path/to/key",
        )
        assert plugin.ssh_username == "paramuser"
        assert plugin.ssh_password == "parampass"
        assert plugin.ssh_key_path == "/path/to/key"
