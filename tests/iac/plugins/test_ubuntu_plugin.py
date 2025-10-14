"""Tests for Ubuntu Replication Plugin."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.iac.plugins.models import (
    DataPlaneAnalysis,
    ExtractionResult,
)
from src.iac.plugins.ubuntu_plugin import UbuntuReplicationPlugin


@pytest.fixture
def plugin():
    """Create plugin instance."""
    return UbuntuReplicationPlugin(
        ssh_username="testuser",
        ssh_password="testpass",
    )


@pytest.fixture
def ubuntu_vm_resource():
    """Sample Ubuntu VM resource."""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/atevet12ubuntu001",
        "name": "atevet12ubuntu001",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "properties": {
            "osProfile": {
                "computerName": "atevet12ubuntu001",
                "adminUsername": "azureuser",
            },
            "storageProfile": {
                "imageReference": {
                    "publisher": "Canonical",
                    "offer": "0001-com-ubuntu-server-jammy",
                    "sku": "22_04-lts-gen2",
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
                                                "ipAddress": "10.0.0.12"
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
            "os": "ubuntu",
            "distribution": "Ubuntu 22.04",
        },
    }


@pytest.fixture
def centos_vm_resource():
    """Sample CentOS VM resource (should not be handled by Ubuntu plugin)."""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-centos",
        "name": "test-centos",
        "type": "Microsoft.Compute/virtualMachines",
        "properties": {
            "osProfile": {
                "computerName": "testcentos001",
            },
            "storageProfile": {
                "imageReference": {
                    "publisher": "OpenLogic",
                    "offer": "CentOS",
                },
            },
        },
        "tags": {
            "os": "centos",
        },
    }


class TestPluginMetadata:
    """Test plugin metadata."""

    def test_metadata(self, plugin):
        """Test plugin metadata is correct."""
        metadata = plugin.metadata

        assert metadata.name == "ubuntu"
        assert metadata.version == "1.0.0"
        assert "Microsoft.Compute/virtualMachines" in metadata.resource_types
        assert metadata.requires_ssh is True
        assert metadata.requires_winrm is False
        assert "ubuntu" in metadata.supported_os
        assert "asyncssh" in metadata.dependencies
        assert "ansible" in metadata.dependencies

    def test_resource_types(self, plugin):
        """Test resource_types property."""
        assert plugin.resource_types == ["Microsoft.Compute/virtualMachines"]


class TestCanHandle:
    """Test can_handle method."""

    def test_can_handle_ubuntu_by_publisher(self, plugin):
        """Test can handle Ubuntu VM by Canonical publisher."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {
                "storageProfile": {
                    "imageReference": {
                        "publisher": "Canonical"
                    }
                }
            },
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_ubuntu_by_offer(self, plugin):
        """Test can handle Ubuntu VM by image offer."""
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

    def test_can_handle_ubuntu_by_computer_name(self, plugin):
        """Test can handle Ubuntu VM by computer name."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {
                "osProfile": {
                    "computerName": "myubuntu001"
                },
                "storageProfile": {},
            },
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_ubuntu_by_tags(self, plugin):
        """Test can handle Ubuntu VM by tags."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {
                "storageProfile": {},
                "osProfile": {},
            },
            "tags": {
                "os": "Ubuntu"
            },
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_ubuntu_by_distro_tag(self, plugin):
        """Test can handle Ubuntu VM by distribution tag."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {
                "storageProfile": {},
                "osProfile": {},
            },
            "tags": {
                "distribution": "ubuntu"
            },
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_real_ubuntu_resource(self, plugin, ubuntu_vm_resource):
        """Test can handle realistic Ubuntu resource."""
        assert plugin.can_handle(ubuntu_vm_resource) is True

    def test_cannot_handle_centos(self, plugin, centos_vm_resource):
        """Test cannot handle CentOS VM."""
        assert plugin.can_handle(centos_vm_resource) is False

    def test_cannot_handle_wrong_resource_type(self, plugin):
        """Test cannot handle non-VM resource."""
        resource = {
            "type": "Microsoft.Storage/storageAccounts",
            "properties": {},
        }
        assert plugin.can_handle(resource) is False


class TestAnalyzeSource:
    """Test analyze_source method."""

    @pytest.mark.asyncio
    async def test_analyze_source_extends_linux_analysis(self, plugin, ubuntu_vm_resource):
        """Test analysis extends base Linux analysis."""
        analysis = await plugin.analyze_source(ubuntu_vm_resource)

        assert isinstance(analysis, DataPlaneAnalysis)
        assert analysis.resource_type == "Microsoft.Compute/virtualMachines"
        assert len(analysis.elements) > 0
        assert analysis.requires_credentials is True

        # Check base Linux elements are present
        element_names = [e.name for e in analysis.elements]
        assert "users" in element_names
        assert "groups" in element_names
        assert "ssh_keys" in element_names
        assert "packages" in element_names

        # Check Ubuntu-specific elements are present
        assert "snap_packages" in element_names
        assert "snap_connections" in element_names
        assert "docker_containers" in element_names
        assert "docker_images" in element_names
        assert "cloud_init_config" in element_names

    @pytest.mark.asyncio
    async def test_analyze_source_higher_complexity(self, plugin, ubuntu_vm_resource):
        """Test Ubuntu analysis has higher complexity than generic Linux."""
        analysis = await plugin.analyze_source(ubuntu_vm_resource)

        # Ubuntu should have higher complexity than base Linux (6.5 + 1.5 = 8.0)
        assert analysis.complexity_score > 6.5

    @pytest.mark.asyncio
    async def test_analyze_source_metadata(self, plugin, ubuntu_vm_resource):
        """Test metadata is correctly set."""
        analysis = await plugin.analyze_source(ubuntu_vm_resource)

        assert analysis.metadata["os_type"] == "ubuntu"
        assert analysis.metadata["plugin_version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_analyze_source_prioritizes_snap(self, plugin, ubuntu_vm_resource):
        """Test snap packages are high priority."""
        analysis = await plugin.analyze_source(ubuntu_vm_resource)

        snap_element = next(e for e in analysis.elements if e.name == "snap_packages")
        assert snap_element.priority == "high"


class TestExtractData:
    """Test extract_data method."""

    @pytest.fixture
    def mock_ssh_connection(self):
        """Mock SSH connection."""
        conn = AsyncMock()
        conn.close = AsyncMock()
        return conn

    @pytest.fixture
    def mock_run_command_ubuntu(self):
        """Mock command execution for Ubuntu-specific commands."""

        async def _run_command(conn, command):
            # Base Linux commands
            if "getent passwd" in command:
                return "root:x:0:0:root:/root:/bin/bash\nazureuser:x:1000:1000::/home/azureuser:/bin/bash\n", "", 0
            elif "getent group" in command:
                return "root:x:0:\nazureuser:x:1000:\n", "", 0
            elif "shadow" in command:
                return "root:$6$encrypted:18000:0:99999:7:::\n", "", 0
            elif "find /home -name authorized_keys" in command:
                return "/home/azureuser/.ssh/authorized_keys\n", "", 0
            elif "cat /home/azureuser/.ssh/authorized_keys" in command:
                return "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAB test@example.com\n", "", 0
            elif "ls /etc/sudoers.d/" in command:
                return "azureuser\n", "", 0
            elif "sudo cat /etc/sudoers.d/" in command:
                return "azureuser ALL=(ALL) NOPASSWD: ALL\n", "", 0
            elif "dpkg -l" in command:
                return "ii  vim  2:8.2  Text editor\nii  nginx  1.18  Web server\n", "", 0
            elif "systemctl list-unit-files" in command:
                return "sshd.service enabled\n", "", 0
            elif "crontab -l" in command:
                return "NO_CRONTAB", "", 0
            elif "cat /etc/ssh/sshd_config" in command:
                return "Port 22\n", "", 0
            elif "ufw status" in command:
                return "Status: active\n", "", 0
            elif "uname -a" in command:
                return "Linux ubuntu 5.15.0 Ubuntu SMP x86_64 GNU/Linux\n", "", 0
            elif "cat /etc/os-release" in command:
                return 'NAME="Ubuntu"\nVERSION="22.04"\n', "", 0
            # Ubuntu-specific commands
            elif "snap list --all" in command:
                return "Name    Version  Rev  Tracking  Publisher\ncore20  20230308  1828  latest/stable  canonical\nlxd     5.0      24322  latest/stable  canonical\n", "", 0
            elif "snap connections" in command:
                return "Interface  Plug       Slot\nnetwork    lxd:network  :network\n", "", 0
            elif "which docker" in command:
                return "/usr/bin/docker\n", "", 0
            elif "docker ps -a --format" in command:
                container1 = '{"ID": "abc123", "Image": "nginx:latest", "Names": "web-server", "State": "running"}'
                container2 = '{"ID": "def456", "Image": "redis:7", "Names": "cache", "State": "exited"}'
                return f"{container1}\n{container2}\n", "", 0
            elif "docker images --format" in command:
                image1 = '{"Repository": "nginx", "Tag": "latest", "ID": "abc123", "Size": "142MB"}'
                image2 = '{"Repository": "redis", "Tag": "7", "ID": "def456", "Size": "117MB"}'
                return f"{image1}\n{image2}\n", "", 0
            elif "docker volume ls --format" in command:
                volume1 = '{"Name": "web-data", "Driver": "local"}'
                return f"{volume1}\n", "", 0
            elif "ls /etc/cloud/" in command:
                return "cloud.cfg\ncloud.cfg.d\n", "", 0
            elif "cat /etc/cloud/cloud.cfg" in command:
                return "# Cloud-init config\nmanage_etc_hosts: true\n", "", 0
            elif "cat /etc/update-manager/release-upgrades" in command:
                return "[DEFAULT]\nPrompt=lts\n", "", 0
            else:
                return "", "", 0

        return _run_command

    @pytest.mark.asyncio
    async def test_extract_data_includes_base_linux(
        self, plugin, ubuntu_vm_resource, mock_ssh_connection, mock_run_command_ubuntu
    ):
        """Test extraction includes base Linux data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command_ubuntu):
                    result = await plugin.extract_data(ubuntu_vm_resource, Mock())

        assert isinstance(result, ExtractionResult)
        assert len(result.extracted_files) > 0
        assert len(result.extracted_data) > 0

        # Check base Linux data
        assert "users" in result.extracted_data
        assert "groups" in result.extracted_data
        assert "package_manager" in result.extracted_data
        assert result.extracted_data["package_manager"] == "dpkg"

    @pytest.mark.asyncio
    async def test_extract_snap_packages(
        self, plugin, ubuntu_vm_resource, mock_ssh_connection, mock_run_command_ubuntu
    ):
        """Test snap packages are extracted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command_ubuntu):
                    result = await plugin.extract_data(ubuntu_vm_resource, Mock())

        # Check snap data
        assert "snap_packages" in result.extracted_data
        assert "core20" in result.extracted_data["snap_packages"]
        assert "lxd" in result.extracted_data["snap_packages"]

        # Check snap file was created
        snap_files = [f for f in result.extracted_files if "snap_packages" in f]
        assert len(snap_files) > 0

    @pytest.mark.asyncio
    async def test_extract_snap_connections(
        self, plugin, ubuntu_vm_resource, mock_ssh_connection, mock_run_command_ubuntu
    ):
        """Test snap connections are extracted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command_ubuntu):
                    result = await plugin.extract_data(ubuntu_vm_resource, Mock())

        # Check connections file was created
        conn_files = [f for f in result.extracted_files if "snap_connections" in f]
        assert len(conn_files) > 0

    @pytest.mark.asyncio
    async def test_extract_docker_containers(
        self, plugin, ubuntu_vm_resource, mock_ssh_connection, mock_run_command_ubuntu
    ):
        """Test Docker containers are extracted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command_ubuntu):
                    result = await plugin.extract_data(ubuntu_vm_resource, Mock())

        # Check Docker data
        assert result.extracted_data["docker_installed"] is True
        assert "docker_containers" in result.extracted_data
        assert len(result.extracted_data["docker_containers"]) == 2
        assert result.extracted_data["docker_containers"][0]["Names"] == "web-server"

        # Check Docker files were created
        docker_files = [f for f in result.extracted_files if "docker_containers" in f]
        assert len(docker_files) > 0

    @pytest.mark.asyncio
    async def test_extract_docker_images(
        self, plugin, ubuntu_vm_resource, mock_ssh_connection, mock_run_command_ubuntu
    ):
        """Test Docker images are extracted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command_ubuntu):
                    result = await plugin.extract_data(ubuntu_vm_resource, Mock())

        # Check Docker images
        assert "docker_images" in result.extracted_data
        assert len(result.extracted_data["docker_images"]) == 2
        assert result.extracted_data["docker_images"][0]["Repository"] == "nginx"

    @pytest.mark.asyncio
    async def test_extract_docker_volumes(
        self, plugin, ubuntu_vm_resource, mock_ssh_connection, mock_run_command_ubuntu
    ):
        """Test Docker volumes are extracted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command_ubuntu):
                    result = await plugin.extract_data(ubuntu_vm_resource, Mock())

        # Check Docker volumes
        assert "docker_volumes" in result.extracted_data
        assert len(result.extracted_data["docker_volumes"]) == 1
        assert result.extracted_data["docker_volumes"][0]["Name"] == "web-data"

    @pytest.mark.asyncio
    async def test_extract_cloud_init(
        self, plugin, ubuntu_vm_resource, mock_ssh_connection, mock_run_command_ubuntu
    ):
        """Test cloud-init config is extracted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command_ubuntu):
                    result = await plugin.extract_data(ubuntu_vm_resource, Mock())

        # Check cloud-init file was created
        cloud_files = [f for f in result.extracted_files if "cloud_init" in f]
        assert len(cloud_files) > 0

    @pytest.mark.asyncio
    async def test_extract_update_manager(
        self, plugin, ubuntu_vm_resource, mock_ssh_connection, mock_run_command_ubuntu
    ):
        """Test update manager config is extracted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command_ubuntu):
                    result = await plugin.extract_data(ubuntu_vm_resource, Mock())

        # Check update manager file was created
        update_files = [f for f in result.extracted_files if "release_upgrades" in f]
        assert len(update_files) > 0

    @pytest.mark.asyncio
    async def test_extract_handles_no_snap(
        self, plugin, ubuntu_vm_resource, mock_ssh_connection
    ):
        """Test graceful handling when snap is not installed."""

        async def no_snap_command(conn, command):
            if "snap list" in command:
                return "NO_SNAP", "", 0
            return "", "", 0

        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=no_snap_command):
                    result = await plugin.extract_data(ubuntu_vm_resource, Mock())

        # Should have warning about snap
        assert any("snap" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_extract_handles_no_docker(
        self, plugin, ubuntu_vm_resource, mock_ssh_connection
    ):
        """Test graceful handling when Docker is not installed."""

        async def no_docker_command(conn, command):
            if "which docker" in command:
                return "NO_DOCKER", "", 1
            return "", "", 0

        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=no_docker_command):
                    result = await plugin.extract_data(ubuntu_vm_resource, Mock())

        # Should mark Docker as not installed
        assert result.extracted_data.get("docker_installed") is False


class TestGenerateReplicationSteps:
    """Test generate_replication_steps method."""

    @pytest.fixture
    def extraction_result_with_snap(self):
        """Sample extraction result with snap packages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            return ExtractionResult(
                resource_id="test-ubuntu-vm",
                extracted_files=[],
                extracted_data={
                    "users": ["root", "azureuser"],
                    "groups": ["root", "azureuser"],
                    "snap_packages": ["core20", "lxd"],
                    "docker_installed": False,
                },
                scripts_generated=[],
                metadata={"output_dir": tmpdir},
            )

    @pytest.fixture
    def extraction_result_with_docker(self):
        """Sample extraction result with Docker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            return ExtractionResult(
                resource_id="test-ubuntu-vm",
                extracted_files=[],
                extracted_data={
                    "users": ["root", "azureuser"],
                    "groups": ["root", "azureuser"],
                    "snap_packages": [],
                    "docker_installed": True,
                    "docker_containers": [
                        {"Names": "web-server", "Image": "nginx:latest"}
                    ],
                },
                scripts_generated=[],
                metadata={"output_dir": tmpdir},
            )

    @pytest.mark.asyncio
    async def test_generate_steps_includes_base(self, plugin, extraction_result_with_snap):
        """Test step generation includes base Linux steps."""
        steps = await plugin.generate_replication_steps(extraction_result_with_snap)

        assert len(steps) > 0
        step_ids = [s.step_id for s in steps]

        # Check base Linux steps are present
        assert "validate_target" in step_ids
        assert "replicate_users" in step_ids
        assert "replicate_packages" in step_ids

    @pytest.mark.asyncio
    async def test_generate_steps_adds_snap(self, plugin, extraction_result_with_snap):
        """Test snap package step is added."""
        steps = await plugin.generate_replication_steps(extraction_result_with_snap)

        step_ids = [s.step_id for s in steps]
        assert "replicate_snap_packages" in step_ids

        # Snap step should depend on packages
        snap_step = next(s for s in steps if s.step_id == "replicate_snap_packages")
        assert "replicate_packages" in snap_step.depends_on
        assert snap_step.is_critical is False

    @pytest.mark.asyncio
    async def test_generate_steps_adds_docker(self, plugin, extraction_result_with_docker):
        """Test Docker restoration step is added when Docker was present."""
        steps = await plugin.generate_replication_steps(extraction_result_with_docker)

        step_ids = [s.step_id for s in steps]
        assert "replicate_docker_containers" in step_ids

        # Docker step should depend on packages
        docker_step = next(s for s in steps if s.step_id == "replicate_docker_containers")
        assert "replicate_packages" in docker_step.depends_on
        assert "manual review" in docker_step.description.lower()

    @pytest.mark.asyncio
    async def test_generate_steps_order(self, plugin, extraction_result_with_snap):
        """Test snap step is inserted after packages."""
        steps = await plugin.generate_replication_steps(extraction_result_with_snap)

        step_ids = [s.step_id for s in steps]
        packages_idx = step_ids.index("replicate_packages")
        snap_idx = step_ids.index("replicate_snap_packages")

        # Snap should come after packages
        assert snap_idx > packages_idx

    @pytest.mark.asyncio
    async def test_generate_playbook_includes_ubuntu_tasks(
        self, plugin, extraction_result_with_snap
    ):
        """Test generated playbook includes Ubuntu-specific tasks."""
        await plugin.generate_replication_steps(extraction_result_with_snap)

        playbook_files = [f for f in extraction_result_with_snap.scripts_generated if "playbook" in f]
        assert len(playbook_files) > 0

        playbook_path = Path(playbook_files[0])
        playbook_content = playbook_path.read_text()

        # Check Ubuntu-specific tasks are present
        assert "Install snap packages" in playbook_content
        assert "snap:" in playbook_content
        assert "Install Docker" in playbook_content

    @pytest.mark.asyncio
    async def test_generate_playbook_valid_yaml(self, plugin, extraction_result_with_snap):
        """Test generated playbook is valid YAML."""
        await plugin.generate_replication_steps(extraction_result_with_snap)

        playbook_files = [f for f in extraction_result_with_snap.scripts_generated if "playbook" in f]
        playbook_path = Path(playbook_files[0])

        # Try to parse as YAML
        import yaml

        with open(playbook_path) as f:
            playbook = yaml.safe_load(f)

        assert isinstance(playbook, list)
        assert len(playbook) > 0


class TestFullReplication:
    """Test full replication workflow."""

    @pytest.mark.asyncio
    async def test_replicate_workflow(self, plugin, ubuntu_vm_resource):
        """Test full replicate() workflow."""
        # Mock all the steps
        mock_analysis = Mock(spec=DataPlaneAnalysis)
        mock_extraction = Mock(spec=ExtractionResult)
        mock_steps = [Mock(step_id="step1")]
        mock_result = Mock()

        with patch.object(plugin, "analyze_source", return_value=mock_analysis):
            with patch.object(plugin, "extract_data", return_value=mock_extraction):
                with patch.object(plugin, "generate_replication_steps", return_value=mock_steps):
                    with patch.object(plugin, "apply_to_target", return_value=mock_result):
                        result = await plugin.replicate(ubuntu_vm_resource, "target-vm-id")

        assert result == mock_result


class TestPluginIntegration:
    """Integration tests for plugin."""

    def test_plugin_initialization(self):
        """Test plugin can be initialized."""
        plugin = UbuntuReplicationPlugin()
        assert plugin is not None
        assert plugin.ssh_username is not None

    def test_plugin_initialization_with_params(self):
        """Test plugin uses provided parameters."""
        plugin = UbuntuReplicationPlugin(
            ssh_username="ubuntuuser",
            ssh_password="ubuntupass",
            ssh_key_path="/path/to/ubuntu/key",
        )
        assert plugin.ssh_username == "ubuntuuser"
        assert plugin.ssh_password == "ubuntupass"
        assert plugin.ssh_key_path == "/path/to/ubuntu/key"

    def test_plugin_extends_linux_client(self):
        """Test plugin properly extends Linux Client Plugin."""
        from src.iac.plugins.linux_client_plugin import LinuxClientReplicationPlugin

        plugin = UbuntuReplicationPlugin()
        assert isinstance(plugin, LinuxClientReplicationPlugin)

    def test_ubuntu_specific_metadata(self):
        """Test Ubuntu plugin has distinct metadata from Linux Client."""
        from src.iac.plugins.linux_client_plugin import LinuxClientReplicationPlugin

        ubuntu_plugin = UbuntuReplicationPlugin()
        linux_plugin = LinuxClientReplicationPlugin()

        assert ubuntu_plugin.metadata.name == "ubuntu"
        assert linux_plugin.metadata.name == "linux_client"
        assert ubuntu_plugin.metadata.name != linux_plugin.metadata.name


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_handles_json_parse_errors_in_docker(
        self, plugin, ubuntu_vm_resource
    ):
        """Test graceful handling of JSON parse errors in Docker data."""
        mock_conn = AsyncMock()
        mock_conn.close = AsyncMock()

        async def bad_json_command(conn, command):
            if "docker ps -a --format" in command:
                return "not valid json\n{invalid}\n", "", 0
            return "", "", 0

        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_conn):
                with patch.object(plugin, "_run_command", side_effect=bad_json_command):
                    result = await plugin.extract_data(ubuntu_vm_resource, Mock())

        # Should handle errors gracefully
        docker_containers = result.extracted_data.get("docker_containers", [])
        assert isinstance(docker_containers, list)

    @pytest.mark.asyncio
    async def test_handles_connection_errors_gracefully(self, plugin, ubuntu_vm_resource):
        """Test extraction handles connection errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", side_effect=ConnectionError("Connection failed")):
                result = await plugin.extract_data(ubuntu_vm_resource, Mock())

        assert isinstance(result, ExtractionResult)
        # Should have base errors from parent, plus Ubuntu-specific error
        assert len(result.errors) > 0

