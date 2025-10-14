"""Integration tests for Linux Client Plugin with real SSH connectivity.

These tests demonstrate that the plugin has REAL SSH connectivity implemented,
not mocked connections. They can be run against actual VMs when SSH credentials
are provided.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.iac.plugins.linux_client_plugin import LinuxClientReplicationPlugin
from src.iac.plugins.models import DataPlaneAnalysis, ExtractionResult

# Skip these tests by default - only run when SSH_TEST_HOST is set
pytestmark = pytest.mark.skipif(
    not os.environ.get("SSH_TEST_HOST"),
    reason="Real SSH tests require SSH_TEST_HOST environment variable",
)


@pytest.fixture
def real_ssh_plugin():
    """Create plugin with real SSH credentials from environment."""
    return LinuxClientReplicationPlugin(
        ssh_username=os.environ.get("SSH_USERNAME", "azureuser"),
        ssh_password=os.environ.get("SSH_PASSWORD"),
        ssh_key_path=os.environ.get("SSH_KEY_PATH"),
    )


@pytest.fixture
def test_vm_resource():
    """Test VM resource with real hostname from environment."""
    hostname = os.environ["SSH_TEST_HOST"]

    return {
        "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
        "name": "test-vm",
        "type": "Microsoft.Compute/virtualMachines",
        "properties": {
            "osProfile": {
                "computerName": "testvm",
                "adminUsername": "azureuser",
            },
            "storageProfile": {"imageReference": {"offer": "UbuntuServer"}},
            "networkProfile": {
                "networkInterfaces": [
                    {
                        "properties": {
                            "ipConfigurations": [
                                {
                                    "properties": {
                                        "publicIPAddress": {
                                            "properties": {"ipAddress": hostname}
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


class TestRealSSHConnectivity:
    """Test real SSH connectivity (requires SSH_TEST_HOST)."""

    @pytest.mark.asyncio
    async def test_real_ssh_connection(self, real_ssh_plugin, test_vm_resource):
        """Test that plugin can make a real SSH connection."""
        hostname = os.environ["SSH_TEST_HOST"]

        # Test _connect_ssh actually connects
        conn = await real_ssh_plugin._connect_ssh(hostname)
        assert conn is not None

        # Verify we can run commands
        stdout, stderr, exit_code = await real_ssh_plugin._run_command(
            conn, "echo 'test'"
        )
        assert exit_code == 0
        assert "test" in stdout

        await conn.close()

    @pytest.mark.asyncio
    async def test_real_data_extraction(self, real_ssh_plugin, test_vm_resource):
        """Test extracting real data from a Linux VM via SSH."""
        with tempfile.TemporaryDirectory() as tmpdir:
            real_ssh_plugin.output_dir = Path(tmpdir)

            # Perform real extraction
            result = await real_ssh_plugin.extract_data(test_vm_resource, Mock())

            assert isinstance(result, ExtractionResult)
            assert len(result.extracted_files) > 0
            assert len(result.extracted_data) > 0

            # Verify real data was extracted
            assert "users" in result.extracted_data
            assert "groups" in result.extracted_data
            assert len(result.extracted_data["users"]) > 0
            assert len(result.extracted_data["groups"]) > 0

            # Verify system info was extracted
            if "system_info" in result.extracted_data:
                assert "Linux" in result.extracted_data["system_info"]

    @pytest.mark.asyncio
    async def test_real_command_execution(self, real_ssh_plugin):
        """Test that _run_command executes real commands."""
        hostname = os.environ["SSH_TEST_HOST"]

        conn = await real_ssh_plugin._connect_ssh(hostname)

        # Test various real commands
        stdout, stderr, code = await real_ssh_plugin._run_command(conn, "uname -s")
        assert code == 0
        assert "Linux" in stdout

        stdout, stderr, code = await real_ssh_plugin._run_command(conn, "whoami")
        assert code == 0
        assert len(stdout.strip()) > 0

        stdout, stderr, code = await real_ssh_plugin._run_command(conn, "pwd")
        assert code == 0
        assert "/" in stdout

        await conn.close()

    @pytest.mark.asyncio
    async def test_real_analyze_source(self, real_ssh_plugin, test_vm_resource):
        """Test that analyze_source connects to real VM and verifies accessibility."""
        analysis = await real_ssh_plugin.analyze_source(test_vm_resource)

        assert isinstance(analysis, DataPlaneAnalysis)

        # Should have no connection warnings since we have valid credentials
        connection_warnings = [w for w in analysis.warnings if "connect" in w.lower()]

        # If we got connection warnings, the real connection didn't work
        if connection_warnings:
            pytest.fail(f"Real SSH connection failed: {connection_warnings}")


class TestRealSSHAuthentication:
    """Test different SSH authentication methods."""

    @pytest.mark.asyncio
    async def test_ssh_password_auth(self, test_vm_resource):
        """Test SSH password authentication works."""
        if not os.environ.get("SSH_PASSWORD"):
            pytest.skip("SSH_PASSWORD not provided")

        plugin = LinuxClientReplicationPlugin(
            ssh_username=os.environ.get("SSH_USERNAME", "azureuser"),
            ssh_password=os.environ["SSH_PASSWORD"],
        )

        hostname = os.environ["SSH_TEST_HOST"]
        conn = await plugin._connect_ssh(hostname)
        assert conn is not None
        await conn.close()

    @pytest.mark.asyncio
    async def test_ssh_key_auth(self, test_vm_resource):
        """Test SSH key authentication works."""
        if not os.environ.get("SSH_KEY_PATH"):
            pytest.skip("SSH_KEY_PATH not provided")

        plugin = LinuxClientReplicationPlugin(
            ssh_username=os.environ.get("SSH_USERNAME", "azureuser"),
            ssh_key_path=os.environ["SSH_KEY_PATH"],
        )

        hostname = os.environ["SSH_TEST_HOST"]
        conn = await plugin._connect_ssh(hostname)
        assert conn is not None
        await conn.close()


class TestRealSSHErrorHandling:
    """Test error handling with real SSH connections."""

    @pytest.mark.asyncio
    async def test_connection_timeout(self, real_ssh_plugin):
        """Test that connection timeout is enforced."""
        # Use non-routable IP to trigger timeout
        with pytest.raises(ConnectionError, match="timeout"):
            await real_ssh_plugin._connect_ssh("192.0.2.1")  # TEST-NET-1

    @pytest.mark.asyncio
    async def test_connection_refused(self, real_ssh_plugin):
        """Test handling of connection refused."""
        # Try to connect to localhost on a non-SSH port
        with pytest.raises(ConnectionError):
            await real_ssh_plugin._connect_ssh("127.0.0.1:99")

    @pytest.mark.asyncio
    async def test_invalid_credentials(self):
        """Test handling of invalid credentials."""
        plugin = LinuxClientReplicationPlugin(
            ssh_username="nonexistent_user",
            ssh_password="wrong_password",
        )

        hostname = os.environ["SSH_TEST_HOST"]

        # Should fail with authentication error
        with pytest.raises(ConnectionError):
            await plugin._connect_ssh(hostname)


class TestRealDataExtraction:
    """Test extraction of real system data."""

    @pytest.mark.asyncio
    async def test_extract_real_users(self, real_ssh_plugin, test_vm_resource):
        """Verify extraction of real user accounts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            real_ssh_plugin.output_dir = Path(tmpdir)

            result = await real_ssh_plugin.extract_data(test_vm_resource, Mock())

            # Should have extracted real users
            assert "users" in result.extracted_data
            users = result.extracted_data["users"]

            # Standard Linux users should exist
            assert "root" in users

            # Verify passwd file was saved
            passwd_files = [f for f in result.extracted_files if "passwd" in f]
            assert len(passwd_files) > 0

            passwd_content = Path(passwd_files[0]).read_text()
            assert "root:" in passwd_content

    @pytest.mark.asyncio
    async def test_extract_real_packages(self, real_ssh_plugin, test_vm_resource):
        """Verify extraction of real package list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            real_ssh_plugin.output_dir = Path(tmpdir)

            result = await real_ssh_plugin.extract_data(test_vm_resource, Mock())

            # Should have detected package manager
            assert "package_manager" in result.extracted_data
            assert result.extracted_data["package_manager"] in ["dpkg", "rpm"]

            # Should have saved package list
            package_files = [f for f in result.extracted_files if "packages" in f]
            assert len(package_files) > 0

    @pytest.mark.asyncio
    async def test_extract_real_system_info(self, real_ssh_plugin, test_vm_resource):
        """Verify extraction of real system information."""
        with tempfile.TemporaryDirectory() as tmpdir:
            real_ssh_plugin.output_dir = Path(tmpdir)

            result = await real_ssh_plugin.extract_data(test_vm_resource, Mock())

            # Should have system_info
            assert "system_info" in result.extracted_data
            assert "Linux" in result.extracted_data["system_info"]

            # Should have os-release
            os_release_files = [f for f in result.extracted_files if "os_release" in f]
            if os_release_files:
                os_release_content = Path(os_release_files[0]).read_text()
                assert "NAME=" in os_release_content
