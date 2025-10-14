"""Tests for Apache Web Server replication plugin."""

import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.iac.plugins.apache_web_server_plugin import ApacheWebServerReplicationPlugin
from src.iac.plugins.models import (
    AnalysisStatus,
    ExtractionFormat,
    ReplicationStatus,
    StepType,
)


@pytest.fixture
def apache_plugin():
    """Create Apache plugin instance for testing."""
    return ApacheWebServerReplicationPlugin(
        ssh_username="testuser",
        ssh_password="testpass",
        output_dir="/tmp/test_apache_output",
    )


@pytest.fixture
def mock_vm_resource():
    """Mock Apache VM resource."""
    return {
        "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/apache-vm",
        "name": "apache-vm",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "properties": {
            "storageProfile": {
                "imageReference": {
                    "publisher": "Canonical",
                    "offer": "UbuntuServer",
                    "sku": "20.04-LTS",
                    "version": "latest",
                }
            },
            "osProfile": {"computerName": "atevet12apache001"},
            "networkProfile": {
                "networkInterfaces": [
                    {
                        "properties": {
                            "ipConfigurations": [
                                {
                                    "properties": {
                                        "publicIPAddress": {
                                            "properties": {"ipAddress": "10.0.1.100"}
                                        }
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        },
        "tags": {"role": "web_server", "application": "apache"},
    }


@pytest.fixture
def mock_ssh_connection():
    """Create mock SSH connection."""
    conn = AsyncMock()
    conn.close = AsyncMock()
    return conn


@pytest.fixture
def mock_ssh_result():
    """Create mock SSH command result."""

    def create_result(stdout="", stderr="", exit_status=0):
        result = Mock()
        result.stdout = stdout
        result.stderr = stderr
        result.exit_status = exit_status
        return result

    return create_result


class TestPluginMetadata:
    """Tests for plugin metadata and configuration."""

    def test_metadata(self, apache_plugin):
        """Test plugin metadata."""
        metadata = apache_plugin.metadata

        assert metadata.name == "apache_web_server"
        assert metadata.version == "1.0.0"
        assert "Microsoft.Compute/virtualMachines" in metadata.resource_types
        assert metadata.complexity == "MEDIUM"
        assert "apache" in metadata.tags
        assert "ssl" in metadata.tags
        assert "virtual_hosts" in metadata.tags

    def test_resource_types(self, apache_plugin):
        """Test resource types property."""
        resource_types = apache_plugin.resource_types
        assert isinstance(resource_types, list)
        assert "Microsoft.Compute/virtualMachines" in resource_types

    def test_supported_formats(self, apache_plugin):
        """Test supported formats."""
        metadata = apache_plugin.metadata
        assert ExtractionFormat.ANSIBLE_PLAYBOOK in metadata.supported_formats
        assert ExtractionFormat.SHELL_SCRIPT in metadata.supported_formats
        assert ExtractionFormat.JSON in metadata.supported_formats


class TestCanHandle:
    """Tests for resource filtering logic."""

    def test_can_handle_apache_vm(self, apache_plugin, mock_vm_resource):
        """Test plugin recognizes Apache VM."""
        assert apache_plugin.can_handle(mock_vm_resource) is True

    def test_can_handle_non_vm(self, apache_plugin):
        """Test plugin rejects non-VM resources."""
        resource = {"type": "Microsoft.Storage/storageAccounts", "name": "storage1"}
        assert apache_plugin.can_handle(resource) is False

    def test_can_handle_windows_vm(self, apache_plugin):
        """Test plugin rejects Windows VMs."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {
                "storageProfile": {
                    "imageReference": {"publisher": "MicrosoftWindowsServer"}
                }
            },
        }
        assert apache_plugin.can_handle(resource) is False

    def test_can_handle_vm_with_apache_name(self, apache_plugin):
        """Test plugin recognizes VM with Apache in name."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "my-apache-server",
            "properties": {
                "storageProfile": {"imageReference": {"offer": "UbuntuServer"}},
                "osProfile": {"computerName": "apache-web"},
            },
            "tags": {},
        }
        assert apache_plugin.can_handle(resource) is True

    def test_can_handle_vm_with_web_tag(self, apache_plugin):
        """Test plugin recognizes VM with web server tag."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "vm1",
            "properties": {
                "storageProfile": {"imageReference": {"offer": "UbuntuServer"}},
                "osProfile": {"computerName": "server1"},
            },
            "tags": {"role": "web"},
        }
        assert apache_plugin.can_handle(resource) is True

    def test_can_handle_vm_with_httpd_tag(self, apache_plugin):
        """Test plugin recognizes VM with httpd tag."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "vm1",
            "properties": {
                "storageProfile": {"imageReference": {"offer": "CentOS"}},
                "osProfile": {"computerName": "httpd-server"},
            },
            "tags": {},
        }
        assert apache_plugin.can_handle(resource) is True


class TestSSHConnection:
    """Tests for SSH connection handling."""

    @pytest.mark.asyncio
    async def test_connect_ssh_with_key(self, apache_plugin):
        """Test SSH connection with key authentication."""
        apache_plugin._asyncssh_available = True

        with patch("src.iac.plugins.apache_web_server_plugin.asyncssh") as mock_asyncssh:
            mock_conn = AsyncMock()
            mock_asyncssh.connect = AsyncMock(return_value=mock_conn)

            apache_plugin.ssh_key_path = "/path/to/key"
            apache_plugin.ssh_password = None

            result = await apache_plugin._connect_ssh("10.0.1.100")

            assert result == mock_conn
            mock_asyncssh.connect.assert_called_once()
            call_kwargs = mock_asyncssh.connect.call_args[1]
            assert call_kwargs["host"] == "10.0.1.100"
            assert call_kwargs["username"] == "testuser"
            assert call_kwargs["client_keys"] == ["/path/to/key"]

    @pytest.mark.asyncio
    async def test_connect_ssh_with_password(self, apache_plugin):
        """Test SSH connection with password authentication."""
        apache_plugin._asyncssh_available = True

        with patch("src.iac.plugins.apache_web_server_plugin.asyncssh") as mock_asyncssh:
            mock_conn = AsyncMock()
            mock_asyncssh.connect = AsyncMock(return_value=mock_conn)

            apache_plugin.ssh_key_path = None
            apache_plugin.ssh_password = "testpass"

            result = await apache_plugin._connect_ssh("10.0.1.100")

            assert result == mock_conn
            call_kwargs = mock_asyncssh.connect.call_args[1]
            assert call_kwargs["password"] == "testpass"

    @pytest.mark.asyncio
    async def test_connect_ssh_timeout(self, apache_plugin):
        """Test SSH connection timeout handling."""
        apache_plugin._asyncssh_available = True

        with patch("src.iac.plugins.apache_web_server_plugin.asyncssh") as mock_asyncssh:
            import asyncio

            mock_asyncssh.connect = AsyncMock(side_effect=asyncio.TimeoutError)

            apache_plugin.ssh_password = "testpass"

            with pytest.raises(ConnectionError, match="timeout"):
                await apache_plugin._connect_ssh("10.0.1.100")

    @pytest.mark.asyncio
    async def test_connect_ssh_no_auth(self, apache_plugin):
        """Test SSH connection with no authentication method."""
        apache_plugin._asyncssh_available = True
        apache_plugin.ssh_key_path = None
        apache_plugin.ssh_password = None

        with pytest.raises(ConnectionError, match="No SSH authentication"):
            await apache_plugin._connect_ssh("10.0.1.100")

    @pytest.mark.asyncio
    async def test_connect_ssh_library_unavailable(self, apache_plugin):
        """Test SSH connection when asyncssh is unavailable."""
        apache_plugin._asyncssh_available = False

        with pytest.raises(ConnectionError, match="asyncssh library not available"):
            await apache_plugin._connect_ssh("10.0.1.100")


class TestApacheDetection:
    """Tests for Apache variant detection."""

    @pytest.mark.asyncio
    async def test_detect_apache2(self, apache_plugin, mock_ssh_connection, mock_ssh_result):
        """Test detection of apache2 variant."""
        mock_ssh_connection.run = AsyncMock(
            side_effect=[
                mock_ssh_result("", "", 1),  # httpd not found
                mock_ssh_result("/usr/sbin/apache2", "", 0),  # apache2 found
            ]
        )

        variant = await apache_plugin._detect_apache_variant(mock_ssh_connection)
        assert variant == "apache2"

    @pytest.mark.asyncio
    async def test_detect_httpd(self, apache_plugin, mock_ssh_connection, mock_ssh_result):
        """Test detection of httpd variant."""
        mock_ssh_connection.run = AsyncMock(
            return_value=mock_ssh_result("/usr/sbin/httpd", "", 0)
        )

        variant = await apache_plugin._detect_apache_variant(mock_ssh_connection)
        assert variant == "httpd"

    @pytest.mark.asyncio
    async def test_detect_no_apache(self, apache_plugin, mock_ssh_connection, mock_ssh_result):
        """Test when Apache is not installed."""
        mock_ssh_connection.run = AsyncMock(
            return_value=mock_ssh_result("", "", 1)  # Not found
        )

        variant = await apache_plugin._detect_apache_variant(mock_ssh_connection)
        assert variant is None

    @pytest.mark.asyncio
    async def test_get_apache_config_paths_httpd(self, apache_plugin):
        """Test config paths for httpd variant."""
        paths = await apache_plugin._get_apache_config_paths("httpd")

        assert paths["main_config"] == "/etc/httpd/conf/httpd.conf"
        assert paths["conf_dir"] == "/etc/httpd/conf.d"
        assert paths["web_root"] == "/var/www/html"

    @pytest.mark.asyncio
    async def test_get_apache_config_paths_apache2(self, apache_plugin):
        """Test config paths for apache2 variant."""
        paths = await apache_plugin._get_apache_config_paths("apache2")

        assert paths["main_config"] == "/etc/apache2/apache2.conf"
        assert paths["sites_available"] == "/etc/apache2/sites-available"
        assert paths["mods_enabled"] == "/etc/apache2/mods-enabled"
        assert paths["ports_config"] == "/etc/apache2/ports.conf"


class TestAnalyzeSource:
    """Tests for source resource analysis."""

    @pytest.mark.asyncio
    async def test_analyze_source_no_hostname(self, apache_plugin, mock_vm_resource):
        """Test analysis when hostname cannot be determined."""
        # Remove network profile to simulate missing hostname
        mock_vm_resource["properties"]["networkProfile"] = {}

        analysis = await apache_plugin.analyze_source(mock_vm_resource)

        assert analysis.status == AnalysisStatus.PARTIAL
        assert len(analysis.warnings) > 0
        assert any("No hostname" in w for w in analysis.warnings)
        assert len(analysis.elements) > 0  # Should return static elements

    @pytest.mark.asyncio
    async def test_analyze_source_apache2_success(
        self, apache_plugin, mock_vm_resource, mock_ssh_result
    ):
        """Test successful analysis of apache2 server."""
        apache_plugin._asyncssh_available = True

        with patch.object(apache_plugin, "_connect_ssh") as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            # Mock command results
            mock_conn.run = AsyncMock(
                side_effect=[
                    mock_ssh_result("Linux apache 5.4.0", "", 0),  # uname -a
                    mock_ssh_result("", "", 1),  # which httpd (not found)
                    mock_ssh_result("/usr/sbin/apache2", "", 0),  # which apache2
                    mock_ssh_result("Apache/2.4.41 (Ubuntu)", "", 0),  # apache2 -v
                    mock_ssh_result("EXISTS", "", 0),  # main config exists
                    mock_ssh_result("5", "", 0),  # vhost count
                    mock_ssh_result("3", "", 0),  # SSL cert count
                    mock_ssh_result("2", "", 0),  # SSL key count
                    mock_ssh_result("15", "", 0),  # enabled modules count
                    mock_ssh_result("150", "", 0),  # web content size (MB)
                    mock_ssh_result("8", "", 0),  # .htaccess count
                    mock_ssh_result("2", "", 0),  # .htpasswd count
                ]
            )
            mock_conn.close = AsyncMock()

            analysis = await apache_plugin.analyze_source(mock_vm_resource)

            assert analysis.status == AnalysisStatus.SUCCESS
            assert analysis.metadata["apache_variant"] == "apache2"
            assert analysis.metadata["vhost_count"] == 5
            assert analysis.metadata["ssl_cert_count"] == 3
            assert analysis.metadata["ssl_key_count"] == 2
            assert len(analysis.elements) > 5
            assert any(e.name == "main_config" for e in analysis.elements)
            assert any(e.name == "virtual_hosts" for e in analysis.elements)
            assert any(e.name == "ssl_certificates" for e in analysis.elements)
            assert any(e.is_sensitive for e in analysis.elements)
            assert len(analysis.warnings) > 0  # Should warn about SSL keys

    @pytest.mark.asyncio
    async def test_analyze_source_httpd_variant(
        self, apache_plugin, mock_vm_resource, mock_ssh_result
    ):
        """Test analysis of httpd (RHEL) server."""
        apache_plugin._asyncssh_available = True

        with patch.object(apache_plugin, "_connect_ssh") as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            mock_conn.run = AsyncMock(
                side_effect=[
                    mock_ssh_result("Linux", "", 0),  # uname
                    mock_ssh_result("/usr/sbin/httpd", "", 0),  # which httpd
                    mock_ssh_result("Apache/2.4.6 (CentOS)", "", 0),  # httpd -v
                    mock_ssh_result("EXISTS", "", 0),  # main config
                    mock_ssh_result("10", "", 0),  # conf.d count
                    mock_ssh_result("1", "", 0),  # SSL certs
                    mock_ssh_result("0", "", 0),  # SSL keys
                    mock_ssh_result("50", "", 0),  # web content
                    mock_ssh_result("3", "", 0),  # .htaccess
                    mock_ssh_result("1", "", 0),  # .htpasswd
                ]
            )
            mock_conn.close = AsyncMock()

            analysis = await apache_plugin.analyze_source(mock_vm_resource)

            assert analysis.status == AnalysisStatus.SUCCESS
            assert analysis.metadata["apache_variant"] == "httpd"
            assert any(e.name == "conf_d_configs" for e in analysis.elements)

    @pytest.mark.asyncio
    async def test_analyze_source_no_apache(
        self, apache_plugin, mock_vm_resource, mock_ssh_result
    ):
        """Test analysis when Apache is not installed."""
        apache_plugin._asyncssh_available = True

        with patch.object(apache_plugin, "_connect_ssh") as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            # All detection methods fail
            mock_conn.run = AsyncMock(
                side_effect=[
                    mock_ssh_result("", "", 1),  # which httpd
                    mock_ssh_result("", "", 1),  # which apache2
                    mock_ssh_result("", "", 1),  # systemctl httpd
                    mock_ssh_result("", "", 1),  # systemctl apache2
                ]
            )
            mock_conn.close = AsyncMock()

            analysis = await apache_plugin.analyze_source(mock_vm_resource)

            assert analysis.status == AnalysisStatus.NOT_APPLICABLE
            assert len(analysis.errors) > 0
            assert any("not detected" in e for e in analysis.errors)

    @pytest.mark.asyncio
    async def test_analyze_source_connection_failure(self, apache_plugin, mock_vm_resource):
        """Test analysis with connection failure."""
        apache_plugin._asyncssh_available = True

        with patch.object(
            apache_plugin, "_connect_ssh", side_effect=ConnectionError("Connection refused")
        ):
            analysis = await apache_plugin.analyze_source(mock_vm_resource)

            assert analysis.status == AnalysisStatus.PARTIAL
            assert len(analysis.errors) > 0
            assert any("Connection failed" in e for e in analysis.errors)


class TestExtractData:
    """Tests for data extraction."""

    @pytest.mark.asyncio
    async def test_extract_data_no_hostname(self, apache_plugin, mock_vm_resource):
        """Test extraction fails without hostname."""
        mock_vm_resource["properties"]["networkProfile"] = {}

        analysis = MagicMock()
        analysis.metadata = {"apache_variant": "apache2"}

        with pytest.raises(ValueError, match="no hostname"):
            await apache_plugin.extract_data(mock_vm_resource, analysis)

    @pytest.mark.asyncio
    async def test_extract_data_apache2(self, apache_plugin, mock_vm_resource, mock_ssh_result, tmp_path):
        """Test data extraction from apache2 server."""
        apache_plugin._asyncssh_available = True
        apache_plugin.output_dir = tmp_path

        analysis = MagicMock()
        analysis.metadata = {"apache_variant": "apache2"}

        with patch.object(apache_plugin, "_connect_ssh") as mock_connect, patch.object(
            apache_plugin, "_get_apache_config_paths"
        ) as mock_paths:

            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            mock_paths.return_value = {
                "main_config": "/etc/apache2/apache2.conf",
                "sites_available": "/etc/apache2/sites-available",
                "sites_enabled": "/etc/apache2/sites-enabled",
                "mods_enabled": "/etc/apache2/mods-enabled",
                "ssl_dir": "/etc/ssl",
                "web_root": "/var/www/html",
                "ports_config": "/etc/apache2/ports.conf",
            }

            # Mock various command results
            mock_conn.run = AsyncMock(
                side_effect=[
                    # Main config
                    mock_ssh_result("ServerRoot /etc/apache2\nListen 80", "", 0),
                    # List sites
                    mock_ssh_result("000-default.conf\ndefault-ssl.conf", "", 0),
                    # Site 1 content
                    mock_ssh_result("<VirtualHost *:80>\nServerName example.com\n</VirtualHost>", "", 0),
                    # Site 2 content
                    mock_ssh_result("<VirtualHost *:443>\nServerName example.com\n</VirtualHost>", "", 0),
                    # Sites enabled listing
                    mock_ssh_result("lrwxrwxrwx 000-default.conf -> ../sites-available/", "", 0),
                    # Ports.conf
                    mock_ssh_result("Listen 80\nListen 443", "", 0),
                    # Mods list
                    mock_ssh_result("ssl.load\nrewrite.load", "", 0),
                    # SSL certs
                    mock_ssh_result("/etc/ssl/certs/server.crt", "", 0),
                    # SSL cert content
                    mock_ssh_result("-----BEGIN CERTIFICATE-----\nMIIC...\n", "", 0),
                    # SSL keys
                    mock_ssh_result("/etc/ssl/private/server.key", "", 0),
                    # SSL key content
                    mock_ssh_result("-----BEGIN PRIVATE KEY-----\nMIIE...\n", "", 0),
                    # .htaccess find
                    mock_ssh_result("/var/www/html/.htaccess", "", 0),
                    # .htaccess content
                    mock_ssh_result("RewriteEngine On\nRewriteRule ^(.*)$ index.php", "", 0),
                    # .htpasswd find
                    mock_ssh_result("/var/www/html/.htpasswd", "", 0),
                    # .htpasswd content
                    mock_ssh_result("user1:$apr1$abcd1234$xyz\n", "", 0),
                    # Web content structure
                    mock_ssh_result("/var/www/html/index.html\n/var/www/html/style.css", "", 0),
                    # Web content sizes
                    mock_ssh_result("100M\t/var/www/html/uploads", "", 0),
                    # Loaded modules
                    mock_ssh_result("Loaded Modules:\n ssl_module\n rewrite_module", "", 0),
                ]
            )
            mock_conn.close = AsyncMock()

            result = await apache_plugin.extract_data(mock_vm_resource, analysis)

            assert result.status == AnalysisStatus.SUCCESS
            assert result.items_extracted > 0
            assert len(result.extracted_data) > 0

            # Check that files were created
            assert (tmp_path / "apache2.conf").exists()
            assert (tmp_path / "sites-available").exists()
            assert (tmp_path / "ssl_certs").exists()
            assert (tmp_path / "extraction_summary.json").exists()

            # Verify summary
            summary_file = tmp_path / "extraction_summary.json"
            summary = json.loads(summary_file.read_text())
            assert summary["apache_variant"] == "apache2"

    @pytest.mark.asyncio
    async def test_extract_data_httpd(self, apache_plugin, mock_vm_resource, mock_ssh_result, tmp_path):
        """Test data extraction from httpd server."""
        apache_plugin._asyncssh_available = True
        apache_plugin.output_dir = tmp_path

        analysis = MagicMock()
        analysis.metadata = {"apache_variant": "httpd"}

        with patch.object(apache_plugin, "_connect_ssh") as mock_connect, patch.object(
            apache_plugin, "_get_apache_config_paths"
        ) as mock_paths:

            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            mock_paths.return_value = {
                "main_config": "/etc/httpd/conf/httpd.conf",
                "conf_dir": "/etc/httpd/conf.d",
                "ssl_dir": "/etc/pki/tls",
                "web_root": "/var/www/html",
            }

            mock_conn.run = AsyncMock(
                side_effect=[
                    # Main config
                    mock_ssh_result("ServerRoot /etc/httpd", "", 0),
                    # conf.d list
                    mock_ssh_result("/etc/httpd/conf.d/ssl.conf", "", 0),
                    # conf.d content
                    mock_ssh_result("SSLEngine on", "", 0),
                    # SSL certs (none)
                    mock_ssh_result("", "", 0),
                    # SSL keys (none)
                    mock_ssh_result("", "", 0),
                    # .htaccess (none)
                    mock_ssh_result("", "", 0),
                    # .htpasswd (none)
                    mock_ssh_result("", "", 0),
                    # Web content
                    mock_ssh_result("/var/www/html/index.html", "", 0),
                    # Sizes
                    mock_ssh_result("10M\t/var/www/html", "", 0),
                    # Modules
                    mock_ssh_result("ssl_module (shared)", "", 0),
                ]
            )
            mock_conn.close = AsyncMock()

            result = await apache_plugin.extract_data(mock_vm_resource, analysis)

            assert result.status == AnalysisStatus.SUCCESS
            assert (tmp_path / "httpd.conf").exists()
            assert (tmp_path / "conf.d").exists()


class TestGenerateReplicationSteps:
    """Tests for replication step generation."""

    @pytest.mark.asyncio
    async def test_generate_replication_steps_apache2(self, apache_plugin, tmp_path):
        """Test step generation for apache2."""
        apache_plugin.output_dir = tmp_path

        extraction = MagicMock()
        extraction.metadata = {"output_dir": str(tmp_path), "apache_variant": "apache2"}
        extraction.extracted_data = []

        steps = await apache_plugin.generate_replication_steps(extraction)

        assert len(steps) > 0
        assert any(s.step_id == "prerequisite_check" for s in steps)
        assert any(s.step_id == "install_apache" for s in steps)
        assert any(s.step_id == "deploy_configs" for s in steps)
        assert any(s.step_id == "deploy_vhosts" for s in steps)
        assert any(s.step_id == "deploy_ssl_certs" for s in steps)
        assert any(s.step_id == "validate_config" for s in steps)
        assert any(s.step_id == "restart_apache" for s in steps)

        # Check step types
        prereq_step = next(s for s in steps if s.step_id == "prerequisite_check")
        assert prereq_step.step_type == StepType.PREREQUISITE

        config_step = next(s for s in steps if s.step_id == "deploy_configs")
        assert config_step.step_type == StepType.CONFIGURATION

        validate_step = next(s for s in steps if s.step_id == "validate_config")
        assert validate_step.step_type == StepType.VALIDATION

        # Check dependencies
        install_step = next(s for s in steps if s.step_id == "install_apache")
        assert "prerequisite_check" in install_step.depends_on

        deploy_step = next(s for s in steps if s.step_id == "deploy_configs")
        assert "install_apache" in deploy_step.depends_on

        # Check files were created
        assert (tmp_path / "apache_replication_playbook.yml").exists()
        assert (tmp_path / "inventory.ini").exists()
        assert (tmp_path / "manual_replication.sh").exists()
        assert (tmp_path / "REPLICATION_README.md").exists()

    @pytest.mark.asyncio
    async def test_generate_replication_steps_httpd(self, apache_plugin, tmp_path):
        """Test step generation for httpd."""
        apache_plugin.output_dir = tmp_path

        extraction = MagicMock()
        extraction.metadata = {"output_dir": str(tmp_path), "apache_variant": "httpd"}
        extraction.extracted_data = []

        steps = await apache_plugin.generate_replication_steps(extraction)

        assert len(steps) > 0

        # Verify playbook content
        playbook_file = tmp_path / "apache_replication_playbook.yml"
        assert playbook_file.exists()
        playbook_content = playbook_file.read_text()
        assert "httpd" in playbook_content
        assert "Install Apache (RHEL/CentOS)" in playbook_content

    @pytest.mark.asyncio
    async def test_playbook_contains_ssl_tasks(self, apache_plugin, tmp_path):
        """Test playbook includes SSL deployment tasks."""
        apache_plugin.output_dir = tmp_path

        extraction = MagicMock()
        extraction.metadata = {"output_dir": str(tmp_path), "apache_variant": "apache2"}
        extraction.extracted_data = []

        await apache_plugin.generate_replication_steps(extraction)

        playbook_file = tmp_path / "apache_replication_playbook.yml"
        playbook_content = playbook_file.read_text()

        assert "Deploy SSL certificates" in playbook_content
        assert "Deploy SSL private keys" in playbook_content
        assert "no_log: yes" in playbook_content  # Sensitive data handling

    @pytest.mark.asyncio
    async def test_shell_script_executable(self, apache_plugin, tmp_path):
        """Test shell script is created with executable permissions."""
        apache_plugin.output_dir = tmp_path

        extraction = MagicMock()
        extraction.metadata = {"output_dir": str(tmp_path), "apache_variant": "apache2"}
        extraction.extracted_data = []

        await apache_plugin.generate_replication_steps(extraction)

        shell_script = tmp_path / "manual_replication.sh"
        assert shell_script.exists()
        assert shell_script.stat().st_mode & 0o111  # Executable bits set

    @pytest.mark.asyncio
    async def test_readme_includes_warnings(self, apache_plugin, tmp_path):
        """Test README includes warnings from extraction."""
        apache_plugin.output_dir = tmp_path

        extraction = MagicMock()
        extraction.metadata = {"output_dir": str(tmp_path), "apache_variant": "apache2"}
        extraction.extracted_data = []
        extraction.warnings = ["SSL private keys detected", "Large web content (2GB)"]
        extraction.errors = []
        extraction.items_extracted = 15
        extraction.extracted_at = MagicMock()
        extraction.extracted_at.isoformat.return_value = "2025-10-11T10:00:00"

        await apache_plugin.generate_replication_steps(extraction)

        readme_file = tmp_path / "REPLICATION_README.md"
        readme_content = readme_file.read_text()

        assert "SSL private keys detected" in readme_content
        assert "Large web content (2GB)" in readme_content
        assert "Security Considerations" in readme_content


class TestApplyToTarget:
    """Tests for applying replication to target."""

    @pytest.mark.asyncio
    async def test_apply_to_target_simulation(self, apache_plugin):
        """Test apply_to_target in simulation mode."""
        steps = [
            MagicMock(step_id="step1", description="Test step 1"),
            MagicMock(step_id="step2", description="Test step 2"),
        ]

        result = await apache_plugin.apply_to_target(steps, "target-resource-id")

        assert result.status == ReplicationStatus.PARTIAL
        assert len(result.warnings) > 0
        assert any("not fully implemented" in w for w in result.warnings)
        assert result.metadata["simulated"] is True

    @pytest.mark.asyncio
    async def test_apply_to_target_tracks_steps(self, apache_plugin):
        """Test that all steps are tracked."""
        steps = [
            MagicMock(step_id=f"step{i}", description=f"Test step {i}") for i in range(5)
        ]

        result = await apache_plugin.apply_to_target(steps, "target-resource-id")

        assert len(result.steps_executed) == 5
        assert all(f"step{i}" in result.steps_executed for i in range(5))


class TestUtilityMethods:
    """Tests for utility methods."""

    def test_extract_hostname_from_network_profile(self, apache_plugin, mock_vm_resource):
        """Test extracting hostname from network profile."""
        hostname = apache_plugin._extract_hostname(mock_vm_resource)
        assert hostname == "10.0.1.100"

    def test_extract_hostname_from_tags(self, apache_plugin):
        """Test extracting hostname from tags."""
        resource = {
            "properties": {},
            "tags": {"hostname": "web-server.example.com"},
        }
        hostname = apache_plugin._extract_hostname(resource)
        assert hostname == "web-server.example.com"

    def test_extract_hostname_from_ip_tag(self, apache_plugin):
        """Test extracting IP from tags."""
        resource = {"properties": {}, "tags": {"ip": "192.168.1.100"}}
        hostname = apache_plugin._extract_hostname(resource)
        assert hostname == "192.168.1.100"

    def test_extract_hostname_none(self, apache_plugin):
        """Test when hostname cannot be found."""
        resource = {"properties": {}}
        hostname = apache_plugin._extract_hostname(resource)
        assert hostname is None

    def test_calculate_complexity_basic(self, apache_plugin):
        """Test complexity calculation with basic setup."""
        elements = []
        metadata = {"vhost_count": 1, "ssl_cert_count": 0, "web_content_size_mb": 10}

        complexity = apache_plugin._calculate_complexity(elements, metadata)
        assert 5.0 <= complexity <= 7.0

    def test_calculate_complexity_high(self, apache_plugin):
        """Test complexity calculation with complex setup."""
        elements = []
        metadata = {
            "vhost_count": 10,
            "ssl_cert_count": 5,
            "web_content_size_mb": 2000,
            "htaccess_count": 20,
        }

        complexity = apache_plugin._calculate_complexity(elements, metadata)
        assert complexity >= 8.0
        assert complexity <= 10.0  # Capped at 10

    def test_get_static_elements(self, apache_plugin):
        """Test static elements generation."""
        elements = apache_plugin._get_static_elements()

        assert len(elements) > 0
        assert any(e.name == "main_config" for e in elements)
        assert any(e.name == "virtual_hosts" for e in elements)
        assert any(e.name == "ssl_certificates" for e in elements)
        assert any(e.is_sensitive for e in elements)


class TestIntegration:
    """Integration tests for full workflow."""

    @pytest.mark.asyncio
    async def test_full_workflow_apache2(self, apache_plugin, mock_vm_resource, tmp_path):
        """Test complete workflow from analysis to step generation."""
        apache_plugin._asyncssh_available = True
        apache_plugin.output_dir = tmp_path

        def mock_ssh_result(stdout="", stderr="", exit_status=0):
            result = Mock()
            result.stdout = stdout
            result.stderr = stderr
            result.exit_status = exit_status
            return result

        with patch.object(apache_plugin, "_connect_ssh") as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            # Analysis phase
            mock_conn.run = AsyncMock(
                side_effect=[
                    # Analysis commands
                    mock_ssh_result("Linux", "", 0),  # uname
                    mock_ssh_result("", "", 1),  # httpd
                    mock_ssh_result("/usr/sbin/apache2", "", 0),  # apache2
                    mock_ssh_result("Apache/2.4", "", 0),  # version
                    mock_ssh_result("EXISTS", "", 0),  # main config
                    mock_ssh_result("3", "", 0),  # vhosts
                    mock_ssh_result("1", "", 0),  # certs
                    mock_ssh_result("1", "", 0),  # keys
                    mock_ssh_result("10", "", 0),  # modules
                    mock_ssh_result("50", "", 0),  # web size
                    mock_ssh_result("2", "", 0),  # htaccess
                    mock_ssh_result("1", "", 0),  # htpasswd
                ]
            )
            mock_conn.close = AsyncMock()

            # Step 1: Analyze
            analysis = await apache_plugin.analyze_source(mock_vm_resource)
            assert analysis.status == AnalysisStatus.SUCCESS

            # Step 2: Extract (reset mock for extraction)
            mock_conn.run = AsyncMock(
                side_effect=[
                    mock_ssh_result("ServerRoot /etc/apache2", "", 0),  # main config
                    mock_ssh_result("default.conf", "", 0),  # sites list
                    mock_ssh_result("<VirtualHost>", "", 0),  # site content
                    mock_ssh_result("lrwx", "", 0),  # enabled sites
                    mock_ssh_result("Listen 80", "", 0),  # ports.conf
                    mock_ssh_result("ssl.load", "", 0),  # mods list
                    mock_ssh_result("/etc/ssl/certs/cert.crt", "", 0),  # cert find
                    mock_ssh_result("-----BEGIN CERT", "", 0),  # cert content
                    mock_ssh_result("/etc/ssl/private/key.key", "", 0),  # key find
                    mock_ssh_result("-----BEGIN KEY", "", 0),  # key content
                    mock_ssh_result("/var/www/.htaccess", "", 0),  # htaccess
                    mock_ssh_result("RewriteEngine", "", 0),  # htaccess content
                    mock_ssh_result("/var/www/.htpasswd", "", 0),  # htpasswd
                    mock_ssh_result("user:hash", "", 0),  # htpasswd content
                    mock_ssh_result("/var/www/index.html", "", 0),  # web content
                    mock_ssh_result("50M\t/var/www", "", 0),  # sizes
                    mock_ssh_result("ssl_module", "", 0),  # modules
                ]
            )

            extraction = await apache_plugin.extract_data(mock_vm_resource, analysis)
            assert extraction.status == AnalysisStatus.SUCCESS
            assert extraction.items_extracted > 0

            # Step 3: Generate steps
            steps = await apache_plugin.generate_replication_steps(extraction)
            assert len(steps) > 5

            # Step 4: Apply (simulation)
            result = await apache_plugin.apply_to_target(steps, "target-id")
            assert result.status == ReplicationStatus.PARTIAL
            assert len(result.steps_executed) == len(steps)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_large_vhost_count(self, apache_plugin, mock_vm_resource, mock_ssh_result):
        """Test handling of large number of virtual hosts."""
        apache_plugin._asyncssh_available = True

        with patch.object(apache_plugin, "_connect_ssh") as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            mock_conn.run = AsyncMock(
                side_effect=[
                    mock_ssh_result("", "", 1),  # which httpd (not found)
                    mock_ssh_result("/usr/sbin/apache2", "", 0),  # which apache2
                    mock_ssh_result("Apache/2.4", "", 0),  # apache2 -v
                    mock_ssh_result("EXISTS", "", 0),  # main config exists
                    mock_ssh_result("100", "", 0),  # 100 vhosts
                    mock_ssh_result("0", "", 0),  # SSL certs
                    mock_ssh_result("0", "", 0),  # SSL keys
                    mock_ssh_result("0", "", 0),  # enabled modules
                    mock_ssh_result("10", "", 0),  # web content size
                    mock_ssh_result("0", "", 0),  # .htaccess count
                    mock_ssh_result("0", "", 0),  # .htpasswd count
                ]
            )
            mock_conn.close = AsyncMock()

            analysis = await apache_plugin.analyze_source(mock_vm_resource)
            assert analysis.metadata["vhost_count"] == 100
            assert analysis.complexity_score >= 7.0  # 5.0 base + 2.0 max for vhosts

    @pytest.mark.asyncio
    async def test_very_large_web_content(self, apache_plugin, mock_vm_resource, mock_ssh_result):
        """Test handling of very large web content."""
        apache_plugin._asyncssh_available = True

        with patch.object(apache_plugin, "_connect_ssh") as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            mock_conn.run = AsyncMock(
                side_effect=[
                    mock_ssh_result("", "", 1),  # which httpd (not found)
                    mock_ssh_result("/usr/sbin/apache2", "", 0),  # which apache2
                    mock_ssh_result("Apache/2.4", "", 0),  # apache2 -v
                    mock_ssh_result("EXISTS", "", 0),  # main config exists
                    mock_ssh_result("1", "", 0),  # vhost count
                    mock_ssh_result("0", "", 0),  # SSL certs
                    mock_ssh_result("0", "", 0),  # SSL keys
                    mock_ssh_result("0", "", 0),  # enabled modules
                    mock_ssh_result("5000", "", 0),  # 5GB web content
                    mock_ssh_result("0", "", 0),  # .htaccess count
                    mock_ssh_result("0", "", 0),  # .htpasswd count
                ]
            )
            mock_conn.close = AsyncMock()

            analysis = await apache_plugin.analyze_source(mock_vm_resource)
            assert any("Large web content" in w for w in analysis.warnings)

    @pytest.mark.asyncio
    async def test_missing_ssl_cert_but_key_present(
        self, apache_plugin, mock_vm_resource, mock_ssh_result, tmp_path
    ):
        """Test extraction when SSL key exists but cert is missing."""
        apache_plugin._asyncssh_available = True
        apache_plugin.output_dir = tmp_path

        analysis = MagicMock()
        analysis.metadata = {"apache_variant": "apache2"}

        with patch.object(apache_plugin, "_connect_ssh") as mock_connect, patch.object(
            apache_plugin, "_get_apache_config_paths"
        ) as mock_paths:

            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            mock_paths.return_value = {
                "main_config": "/etc/apache2/apache2.conf",
                "sites_available": "/etc/apache2/sites-available",
                "sites_enabled": "/etc/apache2/sites-enabled",
                "mods_enabled": "/etc/apache2/mods-enabled",
                "ssl_dir": "/etc/ssl",
                "web_root": "/var/www/html",
                "ports_config": "/etc/apache2/ports.conf",
            }

            mock_conn.run = AsyncMock(
                side_effect=[
                    mock_ssh_result("ServerRoot", "", 0),  # main config
                    mock_ssh_result("", "", 0),  # no sites
                    mock_ssh_result("", "", 0),  # sites enabled
                    mock_ssh_result("", "", 0),  # ports
                    mock_ssh_result("", "", 0),  # mods
                    mock_ssh_result("", "", 0),  # no certs
                    mock_ssh_result("/etc/ssl/private/key.key", "", 0),  # key found
                    mock_ssh_result("-----BEGIN KEY", "", 0),  # key content
                    mock_ssh_result("", "", 0),  # no htaccess
                    mock_ssh_result("", "", 0),  # no htpasswd
                    mock_ssh_result("", "", 0),  # no web content
                    mock_ssh_result("", "", 0),  # no sizes
                    mock_ssh_result("", "", 0),  # modules
                ]
            )
            mock_conn.close = AsyncMock()

            result = await apache_plugin.extract_data(mock_vm_resource, analysis)
            # Should succeed even with missing cert
            assert result.status in [AnalysisStatus.SUCCESS, AnalysisStatus.PARTIAL]
