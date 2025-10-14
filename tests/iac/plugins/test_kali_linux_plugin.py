"""Tests for Kali Linux Replication Plugin."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.iac.plugins.kali_linux_plugin import KaliLinuxReplicationPlugin
from src.iac.plugins.models import (
    DataPlaneAnalysis,
    ExtractionResult,
    ReplicationResult,
)


@pytest.fixture
def plugin():
    """Create plugin instance."""
    return KaliLinuxReplicationPlugin(
        ssh_username="root",
        ssh_password="testpass",
    )


@pytest.fixture
def kali_vm_resource():
    """Sample Kali Linux VM resource."""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-kali-vm",
        "name": "test-kali-vm",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "properties": {
            "osProfile": {
                "computerName": "atevet12kal001",
                "adminUsername": "root",
            },
            "storageProfile": {
                "imageReference": {
                    "publisher": "KaliLinux",
                    "offer": "KaliLinux",
                    "sku": "2024.1",
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
                                            "properties": {"ipAddress": "10.0.0.5"}
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
            "os": "kali",
            "purpose": "pentest",
        },
    }


@pytest.fixture
def ubuntu_vm_resource():
    """Sample Ubuntu VM resource (not Kali)."""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-ubuntu-vm",
        "name": "test-ubuntu-vm",
        "type": "Microsoft.Compute/virtualMachines",
        "properties": {
            "osProfile": {
                "computerName": "ubuntu001",
            },
            "storageProfile": {
                "imageReference": {
                    "publisher": "Canonical",
                    "offer": "UbuntuServer",
                },
            },
        },
        "tags": {
            "os": "ubuntu",
        },
    }


class TestPluginMetadata:
    """Test plugin metadata."""

    def test_metadata(self, plugin):
        """Test plugin metadata is correct."""
        metadata = plugin.metadata

        assert metadata.name == "kali_linux"
        assert metadata.version == "1.0.0"
        assert "Microsoft.Compute/virtualMachines" in metadata.resource_types
        assert metadata.requires_ssh is True
        assert metadata.requires_winrm is False
        assert "kali" in metadata.supported_os
        assert "asyncssh" in metadata.dependencies
        assert "security" in metadata.tags
        assert "pentesting" in metadata.tags
        assert metadata.complexity == "MEDIUM"

    def test_resource_types(self, plugin):
        """Test resource_types property."""
        assert plugin.resource_types == ["Microsoft.Compute/virtualMachines"]


class TestCanHandle:
    """Test can_handle method."""

    def test_can_handle_kali_by_image(self, plugin):
        """Test can handle Kali VM identified by image."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {
                "storageProfile": {
                    "imageReference": {"publisher": "KaliLinux", "offer": "KaliLinux"}
                }
            },
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_kali_by_computer_name(self, plugin):
        """Test can handle Kali VM identified by computer name."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {
                "osProfile": {"computerName": "atevet12kal001"},
                "storageProfile": {},
            },
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_kali_by_tags_os(self, plugin):
        """Test can handle Kali VM identified by tags."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {
                "storageProfile": {},
                "osProfile": {},
            },
            "tags": {"os": "kali"},
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_kali_by_tags_purpose(self, plugin):
        """Test can handle VM identified by security/pentest purpose."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {
                "storageProfile": {},
                "osProfile": {},
            },
            "tags": {"purpose": "pentest"},
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_by_name(self, plugin):
        """Test can handle VM identified by name."""
        resource = {
            "name": "kali-pentest-vm",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {
                "storageProfile": {},
                "osProfile": {},
            },
        }
        assert plugin.can_handle(resource) is True

    def test_cannot_handle_ubuntu_vm(self, plugin, ubuntu_vm_resource):
        """Test cannot handle Ubuntu VM."""
        assert plugin.can_handle(ubuntu_vm_resource) is False

    def test_cannot_handle_wrong_resource_type(self, plugin):
        """Test cannot handle non-VM resource."""
        resource = {
            "type": "Microsoft.Storage/storageAccounts",
            "properties": {},
        }
        assert plugin.can_handle(resource) is False


class TestExtractHostname:
    """Test _extract_hostname method."""

    def test_extract_hostname_from_public_ip(self, plugin, kali_vm_resource):
        """Test extracting hostname from public IP."""
        hostname = plugin._extract_hostname(kali_vm_resource)
        assert hostname == "10.0.0.5"

    def test_extract_hostname_from_tags(self, plugin):
        """Test extracting hostname from tags."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {},
            "tags": {"hostname": "kali.example.com"},
        }
        hostname = plugin._extract_hostname(resource)
        assert hostname == "kali.example.com"

    def test_extract_hostname_from_metadata(self, plugin):
        """Test extracting hostname from metadata."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {},
            "metadata": {"hostname": "kali-meta.example.com"},
        }
        hostname = plugin._extract_hostname(resource)
        assert hostname == "kali-meta.example.com"

    def test_extract_hostname_returns_none(self, plugin):
        """Test returns None when no hostname found."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {},
        }
        hostname = plugin._extract_hostname(resource)
        assert hostname is None


class TestSanitizeConfig:
    """Test _sanitize_config method."""

    def test_sanitize_password(self, plugin):
        """Test sanitizing password fields."""
        config = "database:\n  password: 'mySecretPass123'\n  host: localhost"
        sanitized = plugin._sanitize_config(config)
        assert "mySecretPass123" not in sanitized
        assert "***SANITIZED***" in sanitized

    def test_sanitize_api_key(self, plugin):
        """Test sanitizing API keys."""
        config = "api_key: sk_test_123456789abcdef"
        sanitized = plugin._sanitize_config(config)
        assert "sk_test_123456789abcdef" not in sanitized
        assert "***SANITIZED***" in sanitized

    def test_sanitize_secret(self, plugin):
        """Test sanitizing secrets."""
        config = "secret: 'my-secret-value'"
        sanitized = plugin._sanitize_config(config)
        assert "my-secret-value" not in sanitized
        assert "***SANITIZED***" in sanitized

    def test_sanitize_preserves_structure(self, plugin):
        """Test that sanitization preserves config structure."""
        config = "host: localhost\nport: 5432\npassword: secret123"
        sanitized = plugin._sanitize_config(config)
        assert "host: localhost" in sanitized
        assert "port: 5432" in sanitized


class TestAnalyzeSource:
    """Test analyze_source method."""

    @pytest.mark.asyncio
    async def test_analyze_source_basic(self, plugin, kali_vm_resource):
        """Test basic source analysis."""
        analysis = await plugin.analyze_source(kali_vm_resource)

        assert isinstance(analysis, DataPlaneAnalysis)
        assert analysis.resource_type == "Microsoft.Compute/virtualMachines"
        assert len(analysis.elements) > 0
        assert analysis.requires_credentials is True
        assert "SSH" in analysis.connection_methods

        # Check security warning
        assert len(analysis.warnings) > 0
        assert any("SECURITY" in w for w in analysis.warnings)

    @pytest.mark.asyncio
    async def test_analyze_source_expected_elements(self, plugin, kali_vm_resource):
        """Test that expected Kali elements are present."""
        analysis = await plugin.analyze_source(kali_vm_resource)

        element_names = [e.name for e in analysis.elements]
        assert "kali_packages" in element_names
        assert "metasploit_database" in element_names
        assert "metasploit_modules" in element_names
        assert "custom_tools" in element_names
        assert "user_scripts" in element_names
        assert "wordlists_index" in element_names
        assert "vpn_configs" in element_names
        assert "proxy_config" in element_names

    @pytest.mark.asyncio
    async def test_analyze_source_marks_sensitive(self, plugin, kali_vm_resource):
        """Test that sensitive data is marked."""
        analysis = await plugin.analyze_source(kali_vm_resource)

        sensitive_elements = [e for e in analysis.elements if e.is_sensitive]
        assert len(sensitive_elements) > 0

        # Check specific sensitive items
        sensitive_names = [e.name for e in sensitive_elements]
        assert "metasploit_database" in sensitive_names
        assert "vpn_configs" in sensitive_names
        assert "tool_configs" in sensitive_names

    @pytest.mark.asyncio
    async def test_analyze_source_prioritizes_critical(self, plugin, kali_vm_resource):
        """Test that critical elements are prioritized."""
        analysis = await plugin.analyze_source(kali_vm_resource)

        critical_elements = [e for e in analysis.elements if e.priority == "critical"]
        assert len(critical_elements) > 0

        # Kali packages and Metasploit should be critical
        critical_names = [e.name for e in critical_elements]
        assert "kali_packages" in critical_names
        assert "metasploit_database" in critical_names

    @pytest.mark.asyncio
    async def test_analyze_source_high_complexity(self, plugin, kali_vm_resource):
        """Test that Kali analysis has high complexity score."""
        analysis = await plugin.analyze_source(kali_vm_resource)
        assert analysis.complexity_score >= 7.0

    @pytest.mark.asyncio
    async def test_analyze_source_no_hostname_warning(self, plugin):
        """Test warning when no hostname available."""
        resource = {
            "id": "test-vm",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {},
            "tags": {"purpose": "kali"},
        }

        analysis = await plugin.analyze_source(resource)
        assert len(analysis.warnings) > 0
        assert any("hostname" in w.lower() for w in analysis.warnings)

    @pytest.mark.asyncio
    async def test_analyze_source_metadata(self, plugin, kali_vm_resource):
        """Test analysis metadata."""
        analysis = await plugin.analyze_source(kali_vm_resource)

        assert analysis.metadata["os_type"] == "kali_linux"
        assert analysis.metadata["security_warning"] is True
        assert "plugin_version" in analysis.metadata


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
            if "dpkg -l" in command and "grep kali" in command:
                return (
                    "ii  kali-tools-top10  2024.1  Top 10 Kali tools\n"
                    "ii  kali-linux-core   2024.1  Core Kali packages\n"
                    "ii  metasploit-framework  6.3.0  Penetration testing framework\n",
                    "",
                    0,
                )
            elif "find /opt -type f -executable" in command:
                return "/opt/custom/scanner.py\n/opt/custom/exploit_helper.sh\n", "", 0
            elif "find /root/scripts" in command:
                return "/root/scripts/recon.sh\n/root/scripts/report.py\n", "", 0
            elif "cat /root/scripts/recon.sh" in command:
                return "#!/bin/bash\necho 'Recon script'\n", "", 0
            elif "cat /root/scripts/report.py" in command:
                return "#!/usr/bin/env python3\nprint('Report')\n", "", 0
            elif "msfdb status" in command:
                return "● postgresql.service - PostgreSQL RDBMS\nActive: active (running)\n", "", 0
            elif "find /root/.msf4/modules" in command:
                return "/root/.msf4/modules/exploits/custom_exploit.rb\n", "", 0
            elif "ls -la /root/.msf4/" in command:
                return "total 24\ndrwx------  6 root root 4096 Jan 1 00:00 .\ndrwx------ 10 root root 4096 Jan 1 00:00 ..\n", "", 0
            elif "cat /root/.msf4/database.yml" in command:
                return (
                    "production:\n  adapter: postgresql\n  database: msf\n"
                    "  username: msf\n  password: secretpass123\n  host: localhost\n",
                    "",
                    0,
                )
            elif "find /usr/share/wordlists" in command and "wc -l" in command:
                return "542\n", "", 0
            elif "find /usr/share/wordlists" in command and "head" in command:
                return "/usr/share/wordlists/rockyou.txt\n/usr/share/wordlists/dirb/common.txt\n", "", 0
            elif "ls -la /usr/share/seclists" in command:
                return "total 4\ndrwxr-xr-x 10 root root 4096 Jan 1 00:00 .\n", "", 0
            elif "ls -la /root/.config" in command:
                return "total 8\ndrwxr-xr-x  5 root root 4096 Jan 1 00:00 .\n", "", 0
            elif "ls /etc/openvpn/*.conf" in command:
                return "/etc/openvpn/client.conf\n", "", 0
            elif "cat /etc/openvpn/client.conf" in command:
                return "remote vpn.example.com 1194\nauth-user-pass\nauth_pass mypassword\n", "", 0
            elif "cat /etc/proxychains.conf" in command or "cat /etc/proxychains4.conf" in command:
                return "[ProxyList]\nsocks5 127.0.0.1 9050\n", "", 0
            elif "uname -a" in command:
                return "Linux kali 6.1.0-kali5-amd64 #1 SMP PREEMPT_DYNAMIC Kali 6.1.20-1kali1 x86_64 GNU/Linux\n", "", 0
            elif "cat /etc/os-release" in command:
                return 'NAME="Kali GNU/Linux"\nVERSION="2024.1"\nID=kali\n', "", 0
            else:
                return "", "", 0

        return _run_command

    @pytest.mark.asyncio
    async def test_extract_data_success(
        self, plugin, kali_vm_resource, mock_ssh_connection, mock_run_command
    ):
        """Test successful data extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(
                    plugin, "_run_command", side_effect=mock_run_command
                ):
                    result = await plugin.extract_data(kali_vm_resource, Mock())

        assert isinstance(result, ExtractionResult)
        assert len(result.extracted_files) > 0
        assert len(result.extracted_data) > 0
        assert result.total_size_mb >= 0
        assert result.extraction_duration_seconds >= 0
        assert result.items_extracted > 0

    @pytest.mark.asyncio
    async def test_extract_data_security_warning(
        self, plugin, kali_vm_resource, mock_ssh_connection, mock_run_command
    ):
        """Test that security warnings are present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(
                    plugin, "_run_command", side_effect=mock_run_command
                ):
                    result = await plugin.extract_data(kali_vm_resource, Mock())

        assert len(result.warnings) > 0
        assert any("SECURITY" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_extract_data_kali_packages(
        self, plugin, kali_vm_resource, mock_ssh_connection, mock_run_command
    ):
        """Test Kali packages extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(
                    plugin, "_run_command", side_effect=mock_run_command
                ):
                    result = await plugin.extract_data(kali_vm_resource, Mock())

        # Check for Kali packages data
        kali_pkg_data = [d for d in result.extracted_data if d.name == "kali_packages"]
        assert len(kali_pkg_data) > 0

        # Verify package list
        packages = json.loads(kali_pkg_data[0].content)
        assert "kali-tools-top10" in packages
        assert "metasploit-framework" in packages

    @pytest.mark.asyncio
    async def test_extract_data_custom_tools(
        self, plugin, kali_vm_resource, mock_ssh_connection, mock_run_command
    ):
        """Test custom tools extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(
                    plugin, "_run_command", side_effect=mock_run_command
                ):
                    result = await plugin.extract_data(kali_vm_resource, Mock())

        # Check for custom tools
        tools_data = [d for d in result.extracted_data if d.name == "custom_tools"]
        assert len(tools_data) > 0

        tools = json.loads(tools_data[0].content)
        assert "/opt/custom/scanner.py" in tools

    @pytest.mark.asyncio
    async def test_extract_data_user_scripts(
        self, plugin, kali_vm_resource, mock_ssh_connection, mock_run_command
    ):
        """Test user scripts extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(
                    plugin, "_run_command", side_effect=mock_run_command
                ):
                    result = await plugin.extract_data(kali_vm_resource, Mock())

        # Check that scripts were extracted
        scripts_data = [d for d in result.extracted_data if d.name == "user_scripts"]
        assert len(scripts_data) > 0

        # Verify script files were created
        scripts_files = [f for f in result.extracted_files if "scripts" in f]
        assert len(scripts_files) > 0

    @pytest.mark.asyncio
    async def test_extract_data_metasploit_status(
        self, plugin, kali_vm_resource, mock_ssh_connection, mock_run_command
    ):
        """Test Metasploit status extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(
                    plugin, "_run_command", side_effect=mock_run_command
                ):
                    result = await plugin.extract_data(kali_vm_resource, Mock())

        msf_data = [d for d in result.extracted_data if d.name == "metasploit_status"]
        assert len(msf_data) > 0

        status = json.loads(msf_data[0].content)
        assert "available" in status

    @pytest.mark.asyncio
    async def test_extract_data_sanitizes_passwords(
        self, plugin, kali_vm_resource, mock_ssh_connection, mock_run_command
    ):
        """Test that passwords are sanitized in configs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(
                    plugin, "_run_command", side_effect=mock_run_command
                ):
                    result = await plugin.extract_data(kali_vm_resource, Mock())

        # Check MSF database config was sanitized
        db_files = [f for f in result.extracted_files if "metasploit_database.yml" in f]
        if db_files:
            content = Path(db_files[0]).read_text()
            assert "secretpass123" not in content
            assert "***SANITIZED***" in content

    @pytest.mark.asyncio
    async def test_extract_data_vpn_config_sanitized(
        self, plugin, kali_vm_resource, mock_ssh_connection, mock_run_command
    ):
        """Test VPN configs are sanitized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(
                    plugin, "_run_command", side_effect=mock_run_command
                ):
                    result = await plugin.extract_data(kali_vm_resource, Mock())

        # Check VPN config was sanitized
        vpn_files = [f for f in result.extracted_files if "vpn_configs" in f]
        if vpn_files:
            content = Path(vpn_files[0]).read_text()
            assert "mypassword" not in content
            assert "***SANITIZED***" in content

    @pytest.mark.asyncio
    async def test_extract_data_wordlists_index(
        self, plugin, kali_vm_resource, mock_ssh_connection, mock_run_command
    ):
        """Test wordlists are indexed, not copied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(
                    plugin, "_run_command", side_effect=mock_run_command
                ):
                    result = await plugin.extract_data(kali_vm_resource, Mock())

        # Should have index, not actual wordlists
        wordlist_data = [
            d for d in result.extracted_data if d.name == "wordlists_index"
        ]
        assert len(wordlist_data) > 0

        data = json.loads(wordlist_data[0].content)
        assert "total_count" in data
        assert data["total_count"] == 542

    @pytest.mark.asyncio
    async def test_extract_data_no_hostname_raises(self, plugin):
        """Test extraction fails without hostname."""
        resource = {
            "id": "test-vm",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {},
            "tags": {"purpose": "kali"},
        }

        with pytest.raises(ValueError, match="no hostname"):
            await plugin.extract_data(resource, Mock())

    @pytest.mark.asyncio
    async def test_extract_data_handles_connection_error(
        self, plugin, kali_vm_resource
    ):
        """Test extraction handles connection errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(
                plugin, "_connect_ssh", side_effect=ConnectionError("Connection failed")
            ):
                result = await plugin.extract_data(kali_vm_resource, Mock())

        assert isinstance(result, ExtractionResult)
        assert len(result.errors) > 0
        assert any("connection failed" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_extract_data_continues_on_partial_failure(
        self, plugin, kali_vm_resource, mock_ssh_connection
    ):
        """Test extraction continues when some commands fail."""

        async def partial_run_command(conn, command):
            if "dpkg -l" in command:
                return "ii  kali-linux-core   2024.1  Core\n", "", 0
            elif "msfdb status" in command:
                raise Exception("Metasploit not available")
            elif "cat /etc/os-release" in command:
                return 'NAME="Kali GNU/Linux"\n', "", 0
            else:
                return "", "", 1

        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(
                    plugin, "_run_command", side_effect=partial_run_command
                ):
                    result = await plugin.extract_data(kali_vm_resource, Mock())

        # Should have extracted some data despite failures
        assert result.items_extracted > 0
        assert result.items_failed > 0
        assert len(result.warnings) > 0 or len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_extract_data_metadata(
        self, plugin, kali_vm_resource, mock_ssh_connection, mock_run_command
    ):
        """Test extraction result metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(
                    plugin, "_run_command", side_effect=mock_run_command
                ):
                    result = await plugin.extract_data(kali_vm_resource, Mock())

        assert "hostname" in result.metadata
        assert "output_dir" in result.metadata
        assert result.metadata["security_sanitized"] is True


class TestGenerateReplicationSteps:
    """Test generate_replication_steps method."""

    @pytest.fixture
    def extraction_result(self, tmp_path):
        """Sample extraction result."""
        from src.iac.plugins.models import ExtractedData, ExtractionFormat

        return ExtractionResult(
            resource_id="test-vm",
            extracted_files=[],
            extracted_data=[
                ExtractedData(
                    name="kali_packages",
                    format=ExtractionFormat.JSON,
                    content=json.dumps(
                        ["kali-linux-core", "metasploit-framework", "nmap"]
                    ),
                )
            ],
            metadata={"output_dir": str(tmp_path)},
        )

    @pytest.mark.asyncio
    async def test_generate_steps(self, plugin, extraction_result):
        """Test step generation."""
        steps = await plugin.generate_replication_steps(extraction_result)

        assert len(steps) > 0

        # Check expected steps exist
        step_ids = [s.step_id for s in steps]
        assert "validate_target" in step_ids
        assert "verify_kali" in step_ids
        assert "install_kali_packages" in step_ids
        assert "configure_metasploit" in step_ids
        assert "deploy_scripts" in step_ids
        assert "configure_networking" in step_ids
        assert "verify_replication" in step_ids

    @pytest.mark.asyncio
    async def test_generate_steps_creates_playbook(self, plugin, extraction_result):
        """Test that playbook is generated."""
        await plugin.generate_replication_steps(extraction_result)

        output_dir = Path(extraction_result.metadata["output_dir"])
        playbook_path = output_dir / "kali_replication_playbook.yml"

        assert playbook_path.exists()
        assert playbook_path.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_generate_steps_creates_inventory(self, plugin, extraction_result):
        """Test that inventory file is generated."""
        await plugin.generate_replication_steps(extraction_result)

        output_dir = Path(extraction_result.metadata["output_dir"])
        inventory_path = output_dir / "inventory.ini"

        assert inventory_path.exists()
        content = inventory_path.read_text()
        assert "kali_targets" in content

    @pytest.mark.asyncio
    async def test_generate_steps_creates_setup_script(
        self, plugin, extraction_result
    ):
        """Test that setup script is generated."""
        await plugin.generate_replication_steps(extraction_result)

        output_dir = Path(extraction_result.metadata["output_dir"])
        setup_path = output_dir / "setup_kali.sh"

        assert setup_path.exists()
        content = setup_path.read_text()
        assert "#!/bin/bash" in content
        assert "SECURITY WARNING" in content

    @pytest.mark.asyncio
    async def test_generate_steps_correct_order(self, plugin, extraction_result):
        """Test steps are in correct dependency order."""
        steps = await plugin.generate_replication_steps(extraction_result)

        step_ids = [s.step_id for s in steps]

        # validate_target should be first
        assert step_ids[0] == "validate_target"

        # Find indices
        validate_idx = step_ids.index("validate_target")
        verify_idx = step_ids.index("verify_kali")
        install_idx = step_ids.index("install_kali_packages")

        # Verify should come after validate
        assert verify_idx > validate_idx

        # Install should come after verify
        assert install_idx > verify_idx

    @pytest.mark.asyncio
    async def test_generate_steps_dependencies(self, plugin, extraction_result):
        """Test step dependencies are correct."""
        steps = await plugin.generate_replication_steps(extraction_result)

        # Find specific steps
        verify_step = next(s for s in steps if s.step_id == "verify_kali")
        install_step = next(s for s in steps if s.step_id == "install_kali_packages")
        msf_step = next(s for s in steps if s.step_id == "configure_metasploit")

        # Check dependencies
        assert "validate_target" in verify_step.depends_on
        assert "verify_kali" in install_step.depends_on
        assert "install_kali_packages" in msf_step.depends_on

    @pytest.mark.asyncio
    async def test_generate_steps_marks_critical(self, plugin, extraction_result):
        """Test critical steps are marked."""
        steps = await plugin.generate_replication_steps(extraction_result)

        critical_steps = [s for s in steps if s.is_critical]
        assert len(critical_steps) > 0

        # These should be critical
        critical_ids = [s.step_id for s in critical_steps]
        assert "validate_target" in critical_ids
        assert "verify_kali" in critical_ids
        assert "install_kali_packages" in critical_ids
        assert "configure_metasploit" in critical_ids

    @pytest.mark.asyncio
    async def test_generate_playbook_valid_yaml(self, plugin, extraction_result):
        """Test generated playbook is valid YAML."""
        await plugin.generate_replication_steps(extraction_result)

        output_dir = Path(extraction_result.metadata["output_dir"])
        playbook_path = output_dir / "kali_replication_playbook.yml"

        # Try to parse as YAML
        import yaml

        with open(playbook_path) as f:
            playbook = yaml.safe_load(f)

        assert isinstance(playbook, list)
        assert len(playbook) > 0
        assert playbook[0]["name"] == "Replicate Kali Linux Environment"
        assert "tasks" in playbook[0]

    @pytest.mark.asyncio
    async def test_generate_playbook_includes_security_warning(
        self, plugin, extraction_result
    ):
        """Test playbook includes security warning."""
        await plugin.generate_replication_steps(extraction_result)

        output_dir = Path(extraction_result.metadata["output_dir"])
        playbook_path = output_dir / "kali_replication_playbook.yml"

        content = playbook_path.read_text()
        assert "Security Warning" in content
        assert "authorization" in content.lower()

    @pytest.mark.asyncio
    async def test_generate_playbook_includes_metasploit(
        self, plugin, extraction_result
    ):
        """Test playbook includes Metasploit setup."""
        await plugin.generate_replication_steps(extraction_result)

        output_dir = Path(extraction_result.metadata["output_dir"])
        playbook_path = output_dir / "kali_replication_playbook.yml"

        content = playbook_path.read_text()
        assert "msfdb" in content
        assert "metasploit" in content.lower()


class TestApplyToTarget:
    """Test apply_to_target method."""

    @pytest.mark.asyncio
    async def test_apply_to_target_simulated(self, plugin):
        """Test simulated application to target."""
        steps = [
            Mock(step_id="step1", description="Test step 1"),
            Mock(step_id="step2", description="Test step 2"),
        ]

        result = await plugin.apply_to_target(steps, "target-vm-id")

        assert isinstance(result, ReplicationResult)
        assert result.target_resource_id == "target-vm-id"
        assert len(result.steps_executed) == 2
        assert result.steps_succeeded == 2
        assert result.steps_failed == 0

    @pytest.mark.asyncio
    async def test_apply_to_target_security_warning(self, plugin):
        """Test security warning is present."""
        steps = [Mock(step_id="step1", description="Test")]

        result = await plugin.apply_to_target(steps, "target-vm-id")

        assert len(result.warnings) > 0
        assert any("SECURITY" in w for w in result.warnings)
        assert any("authorization" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_apply_to_target_metadata(self, plugin):
        """Test result metadata."""
        steps = [Mock(step_id="step1", description="Test")]

        result = await plugin.apply_to_target(steps, "target-vm-id")

        assert "total_steps" in result.metadata
        assert "simulated" in result.metadata
        assert result.metadata["simulated"] is True
        assert result.metadata["kali_specific"] is True

    @pytest.mark.asyncio
    async def test_apply_to_target_fidelity_score(self, plugin):
        """Test fidelity score is appropriate."""
        steps = [Mock(step_id="step1", description="Test")]

        result = await plugin.apply_to_target(steps, "target-vm-id")

        # Should have reasonable fidelity (not 100% due to complexity)
        assert 0.0 <= result.fidelity_score <= 1.0
        assert result.fidelity_score >= 0.8


class TestFullReplication:
    """Test full replication workflow."""

    @pytest.mark.asyncio
    async def test_replicate_workflow(self, plugin, kali_vm_resource):
        """Test full replicate() workflow."""
        # Mock all the steps
        mock_analysis = Mock(spec=DataPlaneAnalysis)
        mock_extraction = Mock(spec=ExtractionResult)
        mock_steps = [Mock(step_id="step1")]
        mock_result = Mock(spec=ReplicationResult)

        with patch.object(plugin, "analyze_source", return_value=mock_analysis):
            with patch.object(plugin, "extract_data", return_value=mock_extraction):
                with patch.object(
                    plugin, "generate_replication_steps", return_value=mock_steps
                ):
                    with patch.object(
                        plugin, "apply_to_target", return_value=mock_result
                    ):
                        result = await plugin.replicate(
                            kali_vm_resource, "target-vm-id"
                        )

        assert result == mock_result


class TestPluginIntegration:
    """Integration tests for plugin."""

    def test_plugin_initialization(self):
        """Test plugin can be initialized."""
        plugin = KaliLinuxReplicationPlugin()
        assert plugin is not None
        assert plugin.ssh_username is not None

    def test_plugin_initialization_with_env(self):
        """Test plugin uses environment variables."""
        with patch.dict(
            os.environ, {"SSH_USERNAME": "kali", "SSH_PASSWORD": "kalipass"}
        ):
            plugin = KaliLinuxReplicationPlugin()
            assert plugin.ssh_username == "kali"
            assert plugin.ssh_password == "kalipass"

    def test_plugin_initialization_with_params(self):
        """Test plugin uses provided parameters."""
        plugin = KaliLinuxReplicationPlugin(
            ssh_username="customuser",
            ssh_password="custompass",
            ssh_key_path="/path/to/key",
            output_dir="/tmp/kali_output",
        )
        assert plugin.ssh_username == "customuser"
        assert plugin.ssh_password == "custompass"
        assert plugin.ssh_key_path == "/path/to/key"
        assert plugin.output_dir == Path("/tmp/kali_output")

    def test_plugin_asyncssh_warning(self):
        """Test plugin warns when asyncssh not available."""
        with patch.dict("sys.modules", {"asyncssh": None}):
            plugin = KaliLinuxReplicationPlugin()
            assert plugin._asyncssh_available is False


class TestSecurityFeatures:
    """Test security-specific features."""

    @pytest.mark.asyncio
    async def test_security_warnings_in_analysis(self, plugin, kali_vm_resource):
        """Test security warnings in analysis phase."""
        analysis = await plugin.analyze_source(kali_vm_resource)
        security_warnings = [w for w in analysis.warnings if "SECURITY" in w]
        assert len(security_warnings) > 0

    @pytest.mark.asyncio
    async def test_sensitive_data_marked(self, plugin, kali_vm_resource):
        """Test sensitive elements are marked."""
        analysis = await plugin.analyze_source(kali_vm_resource)
        sensitive = [e for e in analysis.elements if e.is_sensitive]
        assert len(sensitive) >= 3  # At least MSF DB, VPN, tool configs

    def test_sanitize_all_password_types(self, plugin):
        """Test various password formats are sanitized."""
        configs = [
            "password: mypass",
            "password: 'quoted'",
            'password: "double"',
            "auth_pass secretvalue",
            "secret: mysecret",
            "api_key: sk_123",
        ]

        for config in configs:
            sanitized = plugin._sanitize_config(config)
            # Should not contain original values
            assert "mypass" not in sanitized
            assert "quoted" not in sanitized
            assert "double" not in sanitized
            assert "secretvalue" not in sanitized
            assert "mysecret" not in sanitized
            assert "sk_123" not in sanitized
            # Should contain sanitized marker
            assert "***SANITIZED***" in sanitized
