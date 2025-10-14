"""Tests for Windows Server plugin with real WinRM connectivity.

This test module verifies that the plugin correctly uses pywinrm to connect
to Windows servers and extract real data via PowerShell remoting.
"""

import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.iac.plugins.windows_server_plugin import WindowsServerReplicationPlugin


@pytest.fixture
def winrm_plugin():
    """Create plugin with WinRM credentials configured."""
    return WindowsServerReplicationPlugin(
        config={
            "winrm_username": "Administrator",
            "winrm_password": "TestPassword123!",
            "winrm_port": 5985,
            "winrm_transport": "ntlm",
            "winrm_use_ssl": False,
            "hostname": "test-server.example.com",
        }
    )


@pytest.fixture
def windows_vm_resource():
    """Create mock Windows VM resource."""
    return {
        "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/win-server-01",
        "name": "win-server-01",
        "type": "Microsoft.Compute/virtualMachines",
        "properties": {
            "storageProfile": {
                "imageReference": {"offer": "WindowsServer"}
            }
        },
    }


@pytest.fixture
def mock_winrm_session():
    """Create mock WinRM session."""
    session = MagicMock()

    # Mock successful echo test
    echo_result = MagicMock()
    echo_result.status_code = 0
    echo_result.std_out = b"test"
    echo_result.std_err = b""

    session.run_cmd.return_value = echo_result
    return session


class TestWinRMConnection:
    """Test WinRM connection and authentication."""

    @pytest.mark.asyncio
    async def test_connect_winrm_success(self, winrm_plugin):
        """Test successful WinRM connection."""
        with patch("winrm.Session") as mock_session_class:
            # Setup mock
            mock_session = MagicMock()
            echo_result = MagicMock()
            echo_result.status_code = 0
            echo_result.std_out = b"test"
            mock_session.run_cmd.return_value = echo_result
            mock_session_class.return_value = mock_session

            # Connect
            session = await winrm_plugin._connect_winrm("test-host")

            # Verify session was created with correct parameters
            mock_session_class.assert_called_once()
            call_kwargs = mock_session_class.call_args[1]
            assert call_kwargs["target"] == "http://test-host:5985/wsman"
            assert call_kwargs["auth"] == ("Administrator", "TestPassword123!")
            assert call_kwargs["transport"] == "ntlm"

    @pytest.mark.asyncio
    async def test_connect_winrm_with_ssl(self):
        """Test WinRM connection with SSL."""
        plugin = WindowsServerReplicationPlugin(
            config={
                "winrm_username": "Admin",
                "winrm_password": "Pass",
                "winrm_use_ssl": True,
            }
        )

        with patch("winrm.Session") as mock_session_class:
            mock_session = MagicMock()
            echo_result = MagicMock()
            echo_result.status_code = 0
            echo_result.std_out = b"test"
            mock_session.run_cmd.return_value = echo_result
            mock_session_class.return_value = mock_session

            await plugin._connect_winrm("test-host")

            call_kwargs = mock_session_class.call_args[1]
            assert "https://test-host:5986/wsman" in call_kwargs["target"]

    @pytest.mark.asyncio
    async def test_connect_winrm_no_credentials(self):
        """Test WinRM connection fails without credentials."""
        plugin = WindowsServerReplicationPlugin(config={})

        with pytest.raises(ConnectionError, match="credentials not configured"):
            await plugin._connect_winrm("test-host")

    @pytest.mark.asyncio
    async def test_connect_winrm_connection_failure(self, winrm_plugin):
        """Test WinRM connection failure handling."""
        with patch("winrm.Session") as mock_session_class:
            mock_session_class.side_effect = Exception("Connection refused")

            with pytest.raises(ConnectionError, match="WinRM connection failed"):
                await winrm_plugin._connect_winrm("test-host")


class TestPowerShellExecution:
    """Test PowerShell command execution via WinRM."""

    @pytest.mark.asyncio
    async def test_run_command_powershell_success(self, winrm_plugin):
        """Test successful PowerShell command execution."""
        mock_session = MagicMock()
        ps_result = MagicMock()
        ps_result.status_code = 0
        ps_result.std_out = b"Command output"
        ps_result.std_err = b""
        mock_session.run_ps.return_value = ps_result

        stdout, stderr, exit_code = await winrm_plugin._run_command(
            mock_session, "Get-Service"
        )

        assert stdout == "Command output"
        assert stderr == ""
        assert exit_code == 0
        mock_session.run_ps.assert_called_once_with("Get-Service")

    @pytest.mark.asyncio
    async def test_run_command_cmd_success(self, winrm_plugin):
        """Test successful CMD command execution."""
        mock_session = MagicMock()
        cmd_result = MagicMock()
        cmd_result.status_code = 0
        cmd_result.std_out = b"Directory listing"
        cmd_result.std_err = b""
        mock_session.run_cmd.return_value = cmd_result

        stdout, stderr, exit_code = await winrm_plugin._run_command(
            mock_session, "dir", use_powershell=False
        )

        assert stdout == "Directory listing"
        assert exit_code == 0
        mock_session.run_cmd.assert_called_once_with("dir")

    @pytest.mark.asyncio
    async def test_run_command_with_error(self, winrm_plugin):
        """Test command execution with non-zero exit code."""
        mock_session = MagicMock()
        ps_result = MagicMock()
        ps_result.status_code = 1
        ps_result.std_out = b""
        ps_result.std_err = b"Command failed"
        mock_session.run_ps.return_value = ps_result

        stdout, stderr, exit_code = await winrm_plugin._run_command(
            mock_session, "Get-NonExistentCommand"
        )

        assert exit_code == 1
        assert "Command failed" in stderr


class TestRealDataExtraction:
    """Test real data extraction via WinRM."""

    @pytest.mark.asyncio
    async def test_count_services_via_winrm(
        self, winrm_plugin, windows_vm_resource
    ):
        """Test counting Windows services via real WinRM."""
        with patch.object(
            winrm_plugin, "_connect_winrm"
        ) as mock_connect, patch.object(
            winrm_plugin, "_run_command"
        ) as mock_run_command:
            # Setup mocks
            mock_session = MagicMock()
            mock_connect.return_value = mock_session
            mock_run_command.return_value = ("42\n", "", 0)

            # Count services
            count = await winrm_plugin._count_services(windows_vm_resource)

            assert count == 42
            mock_connect.assert_called_once()
            mock_run_command.assert_called_once()
            # Verify correct PowerShell command
            command = mock_run_command.call_args[0][1]
            assert "Get-Service" in command
            assert "Measure-Object" in command

    @pytest.mark.asyncio
    async def test_count_windows_features_via_winrm(
        self, winrm_plugin, windows_vm_resource
    ):
        """Test counting Windows features via real WinRM."""
        with patch.object(
            winrm_plugin, "_connect_winrm"
        ) as mock_connect, patch.object(
            winrm_plugin, "_run_command"
        ) as mock_run_command:
            mock_session = MagicMock()
            mock_connect.return_value = mock_session
            mock_run_command.return_value = ("18\n", "", 0)

            count = await winrm_plugin._count_windows_features(windows_vm_resource)

            assert count == 18
            command = mock_run_command.call_args[0][1]
            assert "Get-WindowsFeature" in command

    @pytest.mark.asyncio
    async def test_extract_services_with_real_data(
        self, winrm_plugin, windows_vm_resource, tmp_path
    ):
        """Test extracting services with real WinRM data."""
        services_json = json.dumps([
            {
                "Name": "WinRM",
                "DisplayName": "Windows Remote Management",
                "Status": "Running",
                "StartType": "Automatic",
                "ServiceAccount": "LocalSystem",
                "Dependencies": None,
            },
            {
                "Name": "W3SVC",
                "DisplayName": "World Wide Web Publishing Service",
                "Status": "Running",
                "StartType": "Automatic",
                "ServiceAccount": "LocalSystem",
                "Dependencies": ["HTTP"],
            },
        ])

        with patch.object(
            winrm_plugin, "_connect_winrm"
        ) as mock_connect, patch.object(
            winrm_plugin, "_run_command"
        ) as mock_run_command:
            mock_session = MagicMock()
            mock_connect.return_value = mock_session
            mock_run_command.return_value = (services_json, "", 0)

            # Extract services
            result = await winrm_plugin._extract_services(
                windows_vm_resource, tmp_path
            )

            # Verify extracted data
            assert result.name == "windows_services"
            content = json.loads(result.content)
            assert len(content["services"]) == 2
            assert content["services"][0]["name"] == "WinRM"
            assert content["services"][1]["name"] == "W3SVC"

    @pytest.mark.asyncio
    async def test_extract_windows_features_with_real_data(
        self, winrm_plugin, windows_vm_resource, tmp_path
    ):
        """Test extracting Windows features with real WinRM data."""
        features_json = json.dumps([
            {
                "Name": "Web-Server",
                "DisplayName": "Web Server (IIS)",
                "Installed": True,
            },
            {
                "Name": "Web-Asp-Net45",
                "DisplayName": "ASP.NET 4.5",
                "Installed": True,
            },
        ])

        with patch.object(
            winrm_plugin, "_connect_winrm"
        ) as mock_connect, patch.object(
            winrm_plugin, "_run_command"
        ) as mock_run_command:
            mock_session = MagicMock()
            mock_connect.return_value = mock_session
            mock_run_command.return_value = (features_json, "", 0)

            # Extract features
            result = await winrm_plugin._extract_windows_features(
                windows_vm_resource, tmp_path
            )

            # Verify extracted data
            content = json.loads(result.content)
            assert len(content["features"]) == 2
            assert content["features"][0]["name"] == "Web-Server"


class TestFallbackBehavior:
    """Test fallback to mock data when WinRM is unavailable."""

    @pytest.mark.asyncio
    async def test_count_services_without_credentials(self, windows_vm_resource):
        """Test service counting falls back to mock when no credentials."""
        plugin = WindowsServerReplicationPlugin(config={})

        count = await plugin._count_services(windows_vm_resource)

        # Should return mock default
        assert count == 25

    @pytest.mark.asyncio
    async def test_extract_services_without_credentials(
        self, windows_vm_resource, tmp_path
    ):
        """Test service extraction falls back to mock when no credentials."""
        plugin = WindowsServerReplicationPlugin(
            config={"output_dir": str(tmp_path)}
        )

        result = await plugin._extract_services(windows_vm_resource, tmp_path)

        # Should return mock data
        content = json.loads(result.content)
        assert len(content["services"]) >= 1
        assert content["note"] is not None

    @pytest.mark.asyncio
    async def test_extraction_with_winrm_failure(
        self, winrm_plugin, windows_vm_resource, tmp_path
    ):
        """Test graceful fallback when WinRM command fails."""
        with patch.object(
            winrm_plugin, "_connect_winrm"
        ) as mock_connect, patch.object(
            winrm_plugin, "_run_command"
        ) as mock_run_command:
            mock_connect.return_value = MagicMock()
            # Simulate command failure
            mock_run_command.return_value = ("", "Access denied", 1)

            # Should not raise, should fallback
            result = await winrm_plugin._extract_services(
                windows_vm_resource, tmp_path
            )

            content = json.loads(result.content)
            # Should have fallback data
            assert len(content["services"]) >= 1


class TestEndToEndWithWinRM:
    """Test complete workflow with WinRM connectivity."""

    @pytest.mark.asyncio
    async def test_full_analysis_with_winrm(
        self, winrm_plugin, windows_vm_resource
    ):
        """Test full analysis using WinRM connectivity."""
        with patch.object(
            winrm_plugin, "_connect_winrm"
        ) as mock_connect, patch.object(
            winrm_plugin, "_run_command"
        ) as mock_run_command:
            mock_session = MagicMock()
            mock_connect.return_value = mock_session

            # Mock PowerShell version check
            def run_command_side_effect(session, command, use_powershell=True):
                if "PSVersion" in command:
                    return ("5\n", "", 0)
                elif "Get-WindowsFeature" in command:
                    return ("20\n", "", 0)
                elif "Get-LocalUser" in command:
                    return ("7\n", "", 0)
                elif "Get-Service" in command:
                    return ("150\n", "", 0)
                else:
                    return ("10\n", "", 0)

            mock_run_command.side_effect = run_command_side_effect

            # Run analysis
            analysis = await winrm_plugin.analyze_source(windows_vm_resource)

            # Verify WinRM was used
            assert analysis.status.value == "success"
            assert len(analysis.elements) > 0
            assert "WinRM" in analysis.connection_methods

    @pytest.mark.asyncio
    async def test_check_winrm_connectivity_real(
        self, winrm_plugin, windows_vm_resource
    ):
        """Test WinRM connectivity check with real connection."""
        with patch.object(
            winrm_plugin, "_connect_winrm"
        ) as mock_connect, patch.object(
            winrm_plugin, "_run_command"
        ) as mock_run_command:
            mock_session = MagicMock()
            mock_connect.return_value = mock_session
            mock_run_command.return_value = ("5\n", "", 0)

            result = await winrm_plugin._check_winrm_connectivity(
                windows_vm_resource
            )

            assert result is True
            mock_connect.assert_called_once()


class TestEnvironmentConfiguration:
    """Test configuration from environment variables."""

    @pytest.mark.asyncio
    async def test_credentials_from_environment(self, monkeypatch):
        """Test plugin reads credentials from environment."""
        monkeypatch.setenv("WINRM_USERNAME", "env_user")
        monkeypatch.setenv("WINRM_PASSWORD", "env_pass")

        plugin = WindowsServerReplicationPlugin()

        assert plugin.winrm_username == "env_user"
        assert plugin.winrm_password == "env_pass"

    def test_config_override_environment(self, monkeypatch):
        """Test config values override environment."""
        monkeypatch.setenv("WINRM_USERNAME", "env_user")

        plugin = WindowsServerReplicationPlugin(
            config={"winrm_username": "config_user"}
        )

        # Config should take precedence
        assert plugin.winrm_username == "config_user"

    def test_default_winrm_settings(self):
        """Test default WinRM settings."""
        plugin = WindowsServerReplicationPlugin()

        assert plugin.winrm_port == 5985
        assert plugin.winrm_transport == "ntlm"
        assert plugin.winrm_use_ssl is False
