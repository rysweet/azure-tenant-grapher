"""Tests for Android Development Replication Plugin."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.iac.plugins.android_dev_plugin import AndroidDevReplicationPlugin
from src.iac.plugins.models import (
    AnalysisStatus,
    DataPlaneAnalysis,
    ExtractionFormat,
    ExtractionResult,
    ReplicationResult,
    ReplicationStatus,
)


@pytest.fixture
def plugin():
    """Create plugin instance."""
    return AndroidDevReplicationPlugin(
        ssh_username="testuser",
        ssh_password="testpass",
    )


@pytest.fixture
def android_dev_vm_resource():
    """Sample Android development VM resource."""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/atevet12android001",
        "name": "atevet12android001",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "properties": {
            "osProfile": {
                "computerName": "atevet12android001",
                "adminUsername": "devuser",
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
                                            "properties": {"ipAddress": "10.0.0.20"}
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
            "role": "android-dev",
            "purpose": "mobile development",
            "environment": "development",
        },
    }


@pytest.fixture
def non_android_vm_resource():
    """Sample non-Android VM resource."""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-web",
        "name": "test-web",
        "type": "Microsoft.Compute/virtualMachines",
        "properties": {
            "osProfile": {
                "computerName": "testweb001",
            },
        },
        "tags": {
            "role": "web-server",
        },
    }


class TestPluginMetadata:
    """Test plugin metadata."""

    def test_metadata(self, plugin):
        """Test plugin metadata is correct."""
        metadata = plugin.metadata

        assert metadata.name == "android_dev"
        assert metadata.version == "1.0.0"
        assert "Microsoft.Compute/virtualMachines" in metadata.resource_types
        assert metadata.requires_credentials is True
        assert metadata.requires_network_access is True
        assert metadata.complexity == "MEDIUM"
        assert "android" in metadata.tags
        assert "mobile" in metadata.tags
        assert ExtractionFormat.JSON in metadata.supported_formats
        assert ExtractionFormat.SHELL_SCRIPT in metadata.supported_formats
        assert ExtractionFormat.ANSIBLE_PLAYBOOK in metadata.supported_formats

    def test_resource_types(self, plugin):
        """Test resource_types property."""
        assert plugin.resource_types == ["Microsoft.Compute/virtualMachines"]


class TestCanHandle:
    """Test can_handle method."""

    def test_can_handle_by_android_role_tag(self, plugin):
        """Test can handle VM with android role tag."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {},
            "tags": {"role": "android-dev"},
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_by_mobile_role_tag(self, plugin):
        """Test can handle VM with mobile role tag."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {},
            "tags": {"role": "mobile-development"},
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_by_purpose_tag(self, plugin):
        """Test can handle VM with android purpose tag."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {},
            "tags": {"purpose": "android development"},
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_by_computer_name(self, plugin):
        """Test can handle VM by computer name containing android."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {
                "osProfile": {"computerName": "android-dev-01"},
            },
            "tags": {},
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_real_android_resource(self, plugin, android_dev_vm_resource):
        """Test can handle realistic Android dev resource."""
        assert plugin.can_handle(android_dev_vm_resource) is True

    def test_cannot_handle_non_android_vm(self, plugin, non_android_vm_resource):
        """Test cannot handle non-Android VM."""
        assert plugin.can_handle(non_android_vm_resource) is False

    def test_cannot_handle_wrong_resource_type(self, plugin):
        """Test cannot handle non-VM resource."""
        resource = {
            "type": "Microsoft.Storage/storageAccounts",
            "properties": {},
            "tags": {"role": "android"},
        }
        assert plugin.can_handle(resource) is False


class TestAnalyzeSource:
    """Test analyze_source method."""

    @pytest.mark.asyncio
    async def test_analyze_source_basic(self, plugin, android_dev_vm_resource):
        """Test basic analysis."""
        analysis = await plugin.analyze_source(android_dev_vm_resource)

        assert isinstance(analysis, DataPlaneAnalysis)
        assert analysis.resource_type == "Microsoft.Compute/virtualMachines"
        assert analysis.status == AnalysisStatus.SUCCESS
        assert len(analysis.elements) > 0
        assert analysis.requires_credentials is True
        assert analysis.requires_network_access is True
        assert "SSH" in analysis.connection_methods

    @pytest.mark.asyncio
    async def test_analyze_source_elements(self, plugin, android_dev_vm_resource):
        """Test all expected elements are discovered."""
        analysis = await plugin.analyze_source(android_dev_vm_resource)

        element_names = [e.name for e in analysis.elements]

        # SDK elements
        assert "android_sdk_info" in element_names
        assert "sdk_packages" in element_names
        assert "build_tools" in element_names
        assert "platform_tools" in element_names
        assert "system_images" in element_names

        # Emulator elements
        assert "avd_list" in element_names
        assert "avd_configurations" in element_names
        assert "avd_ini_files" in element_names
        assert "emulator_config" in element_names

        # Tool elements
        assert "gradle_config" in element_names
        assert "gradle_version" in element_names
        assert "ndk_info" in element_names
        assert "android_studio_settings" in element_names

        # Project elements
        assert "project_configurations" in element_names
        assert "local_properties" in element_names
        assert "keystore_metadata" in element_names

    @pytest.mark.asyncio
    async def test_analyze_source_element_complexity(self, plugin, android_dev_vm_resource):
        """Test element complexity levels."""
        analysis = await plugin.analyze_source(android_dev_vm_resource)

        # Check some specific complexities
        sdk_info = next(e for e in analysis.elements if e.name == "android_sdk_info")
        assert sdk_info.complexity == "LOW"

        avd_configs = next(e for e in analysis.elements if e.name == "avd_configurations")
        assert avd_configs.complexity == "HIGH"

    @pytest.mark.asyncio
    async def test_analyze_source_sensitive_data(self, plugin, android_dev_vm_resource):
        """Test sensitive data is flagged."""
        analysis = await plugin.analyze_source(android_dev_vm_resource)

        local_props = next(e for e in analysis.elements if e.name == "local_properties")
        assert local_props.is_sensitive is True

        keystore = next(e for e in analysis.elements if e.name == "keystore_metadata")
        assert keystore.is_sensitive is True

    @pytest.mark.asyncio
    async def test_analyze_source_dependencies(self, plugin, android_dev_vm_resource):
        """Test element dependencies are set."""
        analysis = await plugin.analyze_source(android_dev_vm_resource)

        sdk_packages = next(e for e in analysis.elements if e.name == "sdk_packages")
        assert "android_sdk_info" in sdk_packages.dependencies

        avd_configs = next(e for e in analysis.elements if e.name == "avd_configurations")
        assert "avd_list" in avd_configs.dependencies

    @pytest.mark.asyncio
    async def test_analyze_source_metadata(self, plugin, android_dev_vm_resource):
        """Test metadata is correctly set."""
        analysis = await plugin.analyze_source(android_dev_vm_resource)

        assert analysis.metadata["os_type"] == "android_development"
        assert analysis.metadata["plugin_version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_analyze_source_with_ssh_connection(
        self, plugin, android_dev_vm_resource
    ):
        """Test analysis with successful SSH connection."""
        mock_conn = AsyncMock()
        mock_conn.close = AsyncMock()

        async def mock_run(command, check=False):
            result = AsyncMock()
            result.stdout = "/home/devuser/Android/Sdk"
            result.stderr = ""
            result.exit_status = 0
            return result

        mock_conn.run = mock_run

        with patch.object(plugin, "_connect_ssh", return_value=mock_conn):
            analysis = await plugin.analyze_source(android_dev_vm_resource)

        assert analysis.status == AnalysisStatus.SUCCESS
        assert len(analysis.warnings) == 0

    @pytest.mark.asyncio
    async def test_analyze_source_without_sdk(self, plugin, android_dev_vm_resource):
        """Test analysis when SDK is not found."""
        mock_conn = AsyncMock()
        mock_conn.close = AsyncMock()

        async def mock_run(command, check=False):
            result = AsyncMock()
            result.stdout = "NOT_SET"
            result.stderr = ""
            result.exit_status = 0
            return result

        mock_conn.run = mock_run

        with patch.object(plugin, "_connect_ssh", return_value=mock_conn):
            analysis = await plugin.analyze_source(android_dev_vm_resource)

        assert any("Android SDK not found" in w for w in analysis.warnings)


class TestExtractData:
    """Test extract_data method."""

    @pytest.fixture
    def mock_ssh_connection(self):
        """Mock SSH connection."""
        conn = AsyncMock()
        conn.close = AsyncMock()
        return conn

    @pytest.fixture
    def mock_run_command_android(self):
        """Mock command execution for Android development environment."""

        async def _run_command(conn, command):
            # SDK info
            if "ANDROID_SDK_ROOT" in command or "ANDROID_HOME" in command:
                return "/home/devuser/Android/Sdk", "", 0
            elif "test -d /home/devuser/Android/Sdk" in command:
                return "EXISTS", "", 0

            # SDK packages
            elif "sdkmanager --list" in command:
                return """Installed packages:
  Path              | Version | Description
  -------           | ------- | -------
  build-tools;33.0.0 | 33.0.0 | Android SDK Build-Tools 33
  platform-tools     | 34.0.0 | Android SDK Platform-Tools
  platforms;android-33 | 2 | Android SDK Platform 33

Available Packages:
  platforms;android-34
""", "", 0

            # Build tools
            elif "ls -1 /home/devuser/Android/Sdk/build-tools" in command:
                return "33.0.0\n33.0.1\n34.0.0\n", "", 0

            # AVD list
            elif "emulator -list-avds" in command:
                return "Pixel_4_API_33\nPixel_6_API_34\n", "", 0

            # AVD .ini files
            elif "cat ~/.android/avd/Pixel_4_API_33.ini" in command:
                return "avd.ini.encoding=UTF-8\npath=/home/devuser/.android/avd/Pixel_4_API_33.avd\n", "", 0
            elif "cat ~/.android/avd/Pixel_6_API_34.ini" in command:
                return "avd.ini.encoding=UTF-8\npath=/home/devuser/.android/avd/Pixel_6_API_34.avd\n", "", 0

            # AVD config.ini files
            elif "cat ~/.android/avd/Pixel_4_API_33.avd/config.ini" in command:
                return "hw.device.name=pixel_4\nhw.ramSize=2048\nhw.keyboard=yes\n", "", 0
            elif "cat ~/.android/avd/Pixel_6_API_34.avd/config.ini" in command:
                return "hw.device.name=pixel_6\nhw.ramSize=4096\nhw.keyboard=yes\n", "", 0

            # Emulator config
            elif "cat ~/.android/avd/advancedFeatures.ini" in command:
                return "Vulkan = on\nGLDirectMem = on\n", "", 0
            elif "cat ~/.emulator_console_auth_token" in command:
                return "test-auth-token\n", "", 0

            # Gradle
            elif "gradle -version" in command:
                return "Gradle 8.0\n\nBuild time:   2023-01-01\nKotlin:       1.8.0\n", "", 0
            elif "cat ~/.gradle/gradle.properties" in command:
                return "org.gradle.jvmargs=-Xmx2048m\nandroid.useAndroidX=true\n", "", 0

            # NDK
            elif "ANDROID_NDK_HOME" in command:
                return "/home/devuser/Android/Sdk/ndk/25.0.8775105", "", 0
            elif "test -f /home/devuser/Android/Sdk/ndk/25.0.8775105/source.properties" in command:
                return "Pkg.Desc = Android NDK\nPkg.Revision = 25.0.8775105\n", "", 0

            # Android Studio
            elif "ls -d ~/.AndroidStudio*" in command:
                return "/home/devuser/.AndroidStudio2022.3\n", "", 0

            # Project configs
            elif "find ~/projects ~/workspace ~/dev -name build.gradle" in command:
                return "/home/devuser/projects/MyApp/build.gradle\n/home/devuser/projects/MyApp/app/build.gradle\n", "", 0

            # Keystores
            elif "find ~ -name '*.keystore' -o -name '*.jks'" in command:
                return "/home/devuser/.android/debug.keystore\n/home/devuser/projects/MyApp/release.keystore\n", "", 0
            elif "stat -c '%s %A' /home/devuser/.android/debug.keystore" in command:
                return "2048 -rw-------\n", "", 0
            elif "stat -c '%s %A' /home/devuser/projects/MyApp/release.keystore" in command:
                return "4096 -rw-------\n", "", 0

            # System images
            elif "ls -1 /home/devuser/Android/Sdk/system-images" in command:
                return "android-33\nandroid-34\n", "", 0
            elif "find /home/devuser/Android/Sdk/system-images -mindepth 3" in command:
                return "/home/devuser/Android/Sdk/system-images/android-33/google_apis/x86_64\n/home/devuser/Android/Sdk/system-images/android-34/google_apis/x86_64\n", "", 0

            else:
                return "", "", 0

        return _run_command

    @pytest.mark.asyncio
    async def test_extract_data_basic(
        self, plugin, android_dev_vm_resource, mock_ssh_connection, mock_run_command_android
    ):
        """Test basic data extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command_android):
                    result = await plugin.extract_data(android_dev_vm_resource, Mock())

        assert isinstance(result, ExtractionResult)
        assert result.status == AnalysisStatus.SUCCESS
        assert len(result.extracted_data) > 0
        assert result.items_extracted > 0

    @pytest.mark.asyncio
    async def test_extract_sdk_info(
        self, plugin, android_dev_vm_resource, mock_ssh_connection, mock_run_command_android
    ):
        """Test SDK info extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command_android):
                    result = await plugin.extract_data(android_dev_vm_resource, Mock())

        # Check SDK info was extracted
        sdk_info_data = next(
            (ed for ed in result.extracted_data if ed.name == "android_sdk_info"), None
        )
        assert sdk_info_data is not None
        assert sdk_info_data.format == ExtractionFormat.JSON

        sdk_info = json.loads(sdk_info_data.content)
        assert "sdk_path" in sdk_info
        assert "/Android/Sdk" in sdk_info["sdk_path"]

    @pytest.mark.asyncio
    async def test_extract_sdk_packages(
        self, plugin, android_dev_vm_resource, mock_ssh_connection, mock_run_command_android
    ):
        """Test SDK packages extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command_android):
                    result = await plugin.extract_data(android_dev_vm_resource, Mock())

        # Check SDK packages were extracted
        packages_data = next(
            (ed for ed in result.extracted_data if ed.name == "sdk_packages"), None
        )
        assert packages_data is not None

        # Check parsed packages list
        parsed_data = next(
            (ed for ed in result.extracted_data if ed.name == "installed_packages_list"),
            None,
        )
        assert parsed_data is not None
        packages = json.loads(parsed_data.content)
        assert "build-tools;33.0.0" in packages
        assert "platform-tools" in packages

    @pytest.mark.asyncio
    async def test_extract_build_tools(
        self, plugin, android_dev_vm_resource, mock_ssh_connection, mock_run_command_android
    ):
        """Test build tools extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command_android):
                    result = await plugin.extract_data(android_dev_vm_resource, Mock())

        build_tools_data = next(
            (ed for ed in result.extracted_data if ed.name == "build_tools"), None
        )
        assert build_tools_data is not None

        build_tools = json.loads(build_tools_data.content)
        assert "33.0.0" in build_tools
        assert "34.0.0" in build_tools

    @pytest.mark.asyncio
    async def test_extract_avd_configurations(
        self, plugin, android_dev_vm_resource, mock_ssh_connection, mock_run_command_android
    ):
        """Test AVD configurations extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command_android):
                    result = await plugin.extract_data(android_dev_vm_resource, Mock())

        # Check AVD summary
        avd_summary_data = next(
            (ed for ed in result.extracted_data if ed.name == "avd_summary"), None
        )
        assert avd_summary_data is not None

        avd_summary = json.loads(avd_summary_data.content)
        assert avd_summary["avd_count"] == 2
        assert "Pixel_4_API_33" in avd_summary["avd_names"]
        assert "Pixel_6_API_34" in avd_summary["avd_names"]

        # Check individual AVD files were extracted
        avd_files = [ed for ed in result.extracted_data if ed.name.startswith("avd_")]
        assert len(avd_files) > 2  # At least 2 .ini + 2 config.ini + summary

    @pytest.mark.asyncio
    async def test_extract_emulator_config(
        self, plugin, android_dev_vm_resource, mock_ssh_connection, mock_run_command_android
    ):
        """Test emulator config extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command_android):
                    result = await plugin.extract_data(android_dev_vm_resource, Mock())

        # Check emulator config files
        emulator_files = [
            ed for ed in result.extracted_data if ed.name.startswith("emulator_")
        ]
        assert len(emulator_files) > 0

    @pytest.mark.asyncio
    async def test_extract_gradle_config(
        self, plugin, android_dev_vm_resource, mock_ssh_connection, mock_run_command_android
    ):
        """Test Gradle config extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command_android):
                    result = await plugin.extract_data(android_dev_vm_resource, Mock())

        gradle_data = next(
            (ed for ed in result.extracted_data if ed.name == "gradle_config"), None
        )
        assert gradle_data is not None

        gradle_config = json.loads(gradle_data.content)
        assert "version_output" in gradle_config
        assert "Gradle 8.0" in gradle_config["version_output"]

    @pytest.mark.asyncio
    async def test_extract_ndk_info(
        self, plugin, android_dev_vm_resource, mock_ssh_connection, mock_run_command_android
    ):
        """Test NDK info extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command_android):
                    result = await plugin.extract_data(android_dev_vm_resource, Mock())

        ndk_data = next(
            (ed for ed in result.extracted_data if ed.name == "ndk_info"), None
        )
        assert ndk_data is not None

        ndk_info = json.loads(ndk_data.content)
        assert "ndk_path" in ndk_info
        assert "ndk" in ndk_info["ndk_path"]

    @pytest.mark.asyncio
    async def test_extract_android_studio_settings(
        self, plugin, android_dev_vm_resource, mock_ssh_connection, mock_run_command_android
    ):
        """Test Android Studio settings extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command_android):
                    result = await plugin.extract_data(android_dev_vm_resource, Mock())

        studio_data = next(
            (ed for ed in result.extracted_data if ed.name == "android_studio_settings"),
            None,
        )
        assert studio_data is not None

        studio_info = json.loads(studio_data.content)
        assert "config_dirs" in studio_info
        assert len(studio_info["config_dirs"]) > 0

    @pytest.mark.asyncio
    async def test_extract_project_configs(
        self, plugin, android_dev_vm_resource, mock_ssh_connection, mock_run_command_android
    ):
        """Test project configurations extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command_android):
                    result = await plugin.extract_data(android_dev_vm_resource, Mock())

        project_data = next(
            (ed for ed in result.extracted_data if ed.name == "project_configs"), None
        )
        assert project_data is not None

        project_info = json.loads(project_data.content)
        assert "build_gradle_files" in project_info
        assert project_info["count"] == 2

    @pytest.mark.asyncio
    async def test_extract_keystore_metadata(
        self, plugin, android_dev_vm_resource, mock_ssh_connection, mock_run_command_android
    ):
        """Test keystore metadata extraction (NOT actual keystores)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command_android):
                    result = await plugin.extract_data(android_dev_vm_resource, Mock())

        keystore_data = next(
            (ed for ed in result.extracted_data if ed.name == "keystore_metadata"), None
        )
        assert keystore_data is not None
        assert keystore_data.metadata.get("sensitive") is True

        keystore_info = json.loads(keystore_data.content)
        assert "keystores" in keystore_info
        assert "security_note" in keystore_info
        assert "metadata only" in keystore_info["security_note"].lower()
        assert len(keystore_info["keystores"]) == 2

        # Verify warning about keystores
        assert any("keystore" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_extract_system_images(
        self, plugin, android_dev_vm_resource, mock_ssh_connection, mock_run_command_android
    ):
        """Test system images extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=mock_run_command_android):
                    result = await plugin.extract_data(android_dev_vm_resource, Mock())

        images_data = next(
            (ed for ed in result.extracted_data if ed.name == "system_images"), None
        )
        assert images_data is not None

        images = json.loads(images_data.content)
        assert len(images) == 2
        assert images[0]["platform"] == "android-33"
        assert images[1]["platform"] == "android-34"

    @pytest.mark.asyncio
    async def test_extract_handles_no_sdk(
        self, plugin, android_dev_vm_resource, mock_ssh_connection
    ):
        """Test extraction when SDK is not present."""

        async def no_sdk_command(conn, command):
            if "ANDROID_SDK_ROOT" in command:
                return "NOT_SET", "", 0
            return "", "", 0

        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=no_sdk_command):
                    result = await plugin.extract_data(android_dev_vm_resource, Mock())

        assert result.status == AnalysisStatus.FAILED or result.status == AnalysisStatus.PARTIAL
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_extract_handles_connection_error(
        self, plugin, android_dev_vm_resource
    ):
        """Test extraction handles connection errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(
                plugin, "_connect_ssh", side_effect=ConnectionError("Connection failed")
            ):
                result = await plugin.extract_data(android_dev_vm_resource, Mock())

        assert isinstance(result, ExtractionResult)
        assert len(result.errors) > 0
        assert any("Connection failed" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_extract_partial_success(
        self, plugin, android_dev_vm_resource, mock_ssh_connection
    ):
        """Test extraction with partial success (some items fail)."""

        async def partial_command(conn, command):
            if "ANDROID_SDK_ROOT" in command:
                return "/home/devuser/Android/Sdk", "", 0
            elif "test -d" in command:
                return "EXISTS", "", 0
            elif "sdkmanager" in command:
                return "", "Error", 1  # Fail SDK packages
            return "", "", 0

        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=partial_command):
                    result = await plugin.extract_data(android_dev_vm_resource, Mock())

        assert result.items_extracted > 0
        assert result.items_failed > 0


class TestSanitizeGradleProperties:
    """Test _sanitize_gradle_properties method."""

    def test_sanitizes_api_keys(self, plugin):
        """Test API keys are sanitized."""
        content = "org.gradle.jvmargs=-Xmx2048m\napi_key=secret123\nother.setting=value"

        sanitized = plugin._sanitize_gradle_properties(content)

        assert "api_key=***SANITIZED***" in sanitized
        assert "secret123" not in sanitized
        assert "other.setting=value" in sanitized

    def test_sanitizes_passwords(self, plugin):
        """Test passwords are sanitized."""
        content = "username=dev\npassword=secret123\ndebug=true"

        sanitized = plugin._sanitize_gradle_properties(content)

        assert "password=***SANITIZED***" in sanitized
        assert "secret123" not in sanitized
        assert "username=dev" in sanitized

    def test_sanitizes_tokens(self, plugin):
        """Test tokens are sanitized."""
        content = "token=abc123\nauth_token=xyz789\nproject.name=MyApp"

        sanitized = plugin._sanitize_gradle_properties(content)

        assert "token=***SANITIZED***" in sanitized
        assert "auth_token=***SANITIZED***" in sanitized
        assert "abc123" not in sanitized
        assert "xyz789" not in sanitized

    def test_preserves_normal_properties(self, plugin):
        """Test normal properties are preserved."""
        content = "org.gradle.jvmargs=-Xmx2048m\nandroid.useAndroidX=true\nkotlin.version=1.8.0"

        sanitized = plugin._sanitize_gradle_properties(content)

        assert content == sanitized


class TestGenerateReplicationSteps:
    """Test generate_replication_steps method."""

    @pytest.fixture
    def extraction_result_android(self):
        """Sample extraction result with Android data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            extracted_data = []

            # Add SDK info
            sdk_info = {"sdk_path": "/home/devuser/Android/Sdk"}
            extracted_data.append(Mock(
                name="android_sdk_info",
                content=json.dumps(sdk_info),
                format=ExtractionFormat.JSON,
            ))

            # Add packages
            packages = ["build-tools;33.0.0", "platforms;android-33"]
            extracted_data.append(Mock(
                name="installed_packages_list",
                content=json.dumps(packages),
                format=ExtractionFormat.JSON,
            ))

            # Add build tools
            build_tools = ["33.0.0", "34.0.0"]
            extracted_data.append(Mock(
                name="build_tools",
                content=json.dumps(build_tools),
                format=ExtractionFormat.JSON,
            ))

            # Add AVD summary
            avd_summary = {
                "avd_count": 2,
                "avd_names": ["Pixel_4_API_33", "Pixel_6_API_34"],
            }
            extracted_data.append(Mock(
                name="avd_summary",
                content=json.dumps(avd_summary),
                format=ExtractionFormat.JSON,
            ))

            return ExtractionResult(
                resource_id="test-android-vm",
                extracted_data=extracted_data,
                metadata={"output_dir": tmpdir},
            )

    @pytest.mark.asyncio
    async def test_generate_steps_basic(self, plugin, extraction_result_android):
        """Test basic step generation."""
        steps = await plugin.generate_replication_steps(extraction_result_android)

        assert len(steps) > 0
        step_ids = [s.step_id for s in steps]

        # Check all expected steps are present
        assert "validate_target" in step_ids
        assert "install_prerequisites" in step_ids
        assert "install_sdk_tools" in step_ids
        assert "install_sdk_packages" in step_ids
        assert "configure_avds" in step_ids
        assert "install_gradle" in step_ids
        assert "configure_environment" in step_ids
        assert "verify_installation" in step_ids

    @pytest.mark.asyncio
    async def test_generate_steps_dependencies(self, plugin, extraction_result_android):
        """Test step dependencies are correct."""
        steps = await plugin.generate_replication_steps(extraction_result_android)

        # Check dependencies
        prereq_step = next(s for s in steps if s.step_id == "install_prerequisites")
        assert prereq_step.depends_on == ["validate_target"]

        sdk_tools_step = next(s for s in steps if s.step_id == "install_sdk_tools")
        assert sdk_tools_step.depends_on == ["install_prerequisites"]

        sdk_packages_step = next(s for s in steps if s.step_id == "install_sdk_packages")
        assert sdk_packages_step.depends_on == ["install_sdk_tools"]

        avd_step = next(s for s in steps if s.step_id == "configure_avds")
        assert avd_step.depends_on == ["install_sdk_packages"]

    @pytest.mark.asyncio
    async def test_generate_steps_criticality(self, plugin, extraction_result_android):
        """Test step criticality flags."""
        steps = await plugin.generate_replication_steps(extraction_result_android)

        # Critical steps
        validate_step = next(s for s in steps if s.step_id == "validate_target")
        assert validate_step.is_critical is True

        prereq_step = next(s for s in steps if s.step_id == "install_prerequisites")
        assert prereq_step.is_critical is True

        # Non-critical steps
        avd_step = next(s for s in steps if s.step_id == "configure_avds")
        assert avd_step.is_critical is False

        verify_step = next(s for s in steps if s.step_id == "verify_installation")
        assert verify_step.is_critical is False

    @pytest.mark.asyncio
    async def test_generate_sdk_install_script(self, plugin, extraction_result_android):
        """Test SDK installation script generation."""
        await plugin.generate_replication_steps(extraction_result_android)

        # Find script file
        output_dir = Path(extraction_result_android.metadata["output_dir"])
        install_script_path = output_dir / "install_android_sdk.sh"

        assert install_script_path.exists()
        script_content = install_script_path.read_text()

        # Check script contains key elements
        assert "#!/bin/bash" in script_content
        assert "ANDROID_SDK_ROOT" in script_content
        assert "sdkmanager" in script_content
        assert "commandlinetools" in script_content
        assert "build-tools;33.0.0" in script_content  # From extracted data

    @pytest.mark.asyncio
    async def test_generate_ansible_playbook(self, plugin, extraction_result_android):
        """Test Ansible playbook generation."""
        await plugin.generate_replication_steps(extraction_result_android)

        # Find playbook file
        output_dir = Path(extraction_result_android.metadata["output_dir"])
        playbook_path = output_dir / "android_replication_playbook.yml"

        assert playbook_path.exists()
        playbook_content = playbook_path.read_text()

        # Check playbook contains key elements
        assert "Replicate Android Development Environment" in playbook_content
        assert "Install Java JDK" in playbook_content
        assert "Download Gradle" in playbook_content
        assert "Configure Android environment variables" in playbook_content
        assert "ANDROID_SDK_ROOT" in playbook_content
        assert "Verify Android SDK installation" in playbook_content

    @pytest.mark.asyncio
    async def test_generate_ansible_playbook_includes_avds(
        self, plugin, extraction_result_android
    ):
        """Test Ansible playbook includes AVD information."""
        await plugin.generate_replication_steps(extraction_result_android)

        output_dir = Path(extraction_result_android.metadata["output_dir"])
        playbook_path = output_dir / "android_replication_playbook.yml"

        playbook_content = playbook_path.read_text()

        # Check AVD references
        assert "AVD" in playbook_content or "avd" in playbook_content
        assert "Pixel_4_API_33" in playbook_content or "AVDs from source" in playbook_content

    @pytest.mark.asyncio
    async def test_generate_documentation(self, plugin, extraction_result_android):
        """Test documentation generation."""
        await plugin.generate_replication_steps(extraction_result_android)

        # Find docs file
        output_dir = Path(extraction_result_android.metadata["output_dir"])
        docs_path = output_dir / "REPLICATION_GUIDE.md"

        assert docs_path.exists()
        docs_content = docs_path.read_text()

        # Check documentation contains key sections
        assert "# Android Development Environment Replication Guide" in docs_content
        assert "## Overview" in docs_content
        assert "## Prerequisites" in docs_content
        assert "## Manual Replication Steps" in docs_content
        assert "### Option 1: Using Shell Script" in docs_content
        assert "### Option 2: Using Ansible Playbook" in docs_content
        assert "## Security Considerations" in docs_content
        assert "### Keystores" in docs_content
        assert "### API Keys and Secrets" in docs_content
        assert "## Troubleshooting" in docs_content


class TestApplyToTarget:
    """Test apply_to_target method."""

    @pytest.mark.asyncio
    async def test_apply_to_target_basic(self, plugin):
        """Test basic apply_to_target execution."""
        mock_steps = [
            Mock(step_id="step1", description="Test step 1"),
            Mock(step_id="step2", description="Test step 2"),
        ]

        result = await plugin.apply_to_target(mock_steps, "target-vm-id")

        assert isinstance(result, ReplicationResult)
        assert result.target_resource_id == "target-vm-id"
        assert len(result.steps_executed) == 2

    @pytest.mark.asyncio
    async def test_apply_to_target_simulated(self, plugin):
        """Test that apply_to_target is simulated."""
        mock_steps = [Mock(step_id="step1", description="Test step 1")]

        result = await plugin.apply_to_target(mock_steps, "target-vm-id")

        # Should have warnings about simulation
        assert any("not fully implemented" in w.lower() for w in result.warnings)
        assert result.metadata["simulated"] is True
        assert result.metadata["manual_execution_required"] is True

    @pytest.mark.asyncio
    async def test_apply_to_target_success_status(self, plugin):
        """Test successful execution status."""
        mock_steps = [
            Mock(step_id="step1", description="Test step 1"),
            Mock(step_id="step2", description="Test step 2"),
        ]

        result = await plugin.apply_to_target(mock_steps, "target-vm-id")

        assert result.status == ReplicationStatus.SUCCESS
        assert result.steps_succeeded == 2
        assert result.steps_failed == 0

    @pytest.mark.asyncio
    async def test_apply_to_target_fidelity_score(self, plugin):
        """Test fidelity score is calculated."""
        mock_steps = [Mock(step_id="step1", description="Test step 1")]

        result = await plugin.apply_to_target(mock_steps, "target-vm-id")

        assert 0.0 <= result.fidelity_score <= 1.0
        assert result.fidelity_score > 0.5  # Should be reasonably high


class TestFullReplication:
    """Test full replication workflow."""

    @pytest.mark.asyncio
    async def test_replicate_workflow(self, plugin, android_dev_vm_resource):
        """Test full replicate() workflow."""
        mock_analysis = Mock(spec=DataPlaneAnalysis)
        mock_extraction = Mock(spec=ExtractionResult)
        mock_steps = [Mock(step_id="step1")]
        mock_result = Mock()

        with patch.object(plugin, "analyze_source", return_value=mock_analysis):
            with patch.object(plugin, "extract_data", return_value=mock_extraction):
                with patch.object(
                    plugin, "generate_replication_steps", return_value=mock_steps
                ):
                    with patch.object(
                        plugin, "apply_to_target", return_value=mock_result
                    ):
                        result = await plugin.replicate(
                            android_dev_vm_resource, "target-vm-id"
                        )

        assert result == mock_result


class TestPluginIntegration:
    """Integration tests for plugin."""

    def test_plugin_initialization(self):
        """Test plugin can be initialized."""
        plugin = AndroidDevReplicationPlugin()
        assert plugin is not None
        assert plugin.ssh_username is not None

    def test_plugin_initialization_with_params(self):
        """Test plugin uses provided parameters."""
        plugin = AndroidDevReplicationPlugin(
            ssh_username="androiduser",
            ssh_password="androidpass",
            ssh_key_path="/path/to/android/key",
        )
        assert plugin.ssh_username == "androiduser"
        assert plugin.ssh_password == "androidpass"
        assert plugin.ssh_key_path == "/path/to/android/key"

    def test_plugin_initialization_with_env_vars(self):
        """Test plugin reads environment variables."""
        with patch.dict(
            "os.environ",
            {
                "SSH_USERNAME": "envuser",
                "SSH_PASSWORD": "envpass",
                "SSH_KEY_PATH": "/env/key",
            },
        ):
            plugin = AndroidDevReplicationPlugin()
            assert plugin.ssh_username == "envuser"
            assert plugin.ssh_password == "envpass"
            assert plugin.ssh_key_path == "/env/key"


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_handles_no_hostname(self, plugin):
        """Test extraction fails gracefully when no hostname found."""
        resource = {
            "id": "test-vm",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {},
            "tags": {"role": "android-dev"},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with pytest.raises(ValueError, match="no hostname/IP found"):
                await plugin.extract_data(resource, Mock())

    @pytest.mark.asyncio
    async def test_handles_missing_avds(
        self, plugin, android_dev_vm_resource, mock_ssh_connection
    ):
        """Test extraction handles missing AVDs gracefully."""

        async def no_avds_command(conn, command):
            if "ANDROID_SDK_ROOT" in command:
                return "/home/devuser/Android/Sdk", "", 0
            elif "test -d" in command:
                return "EXISTS", "", 0
            elif "emulator -list-avds" in command:
                return "NOT_FOUND", "", 1
            return "", "", 0

        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=no_avds_command):
                    result = await plugin.extract_data(android_dev_vm_resource, Mock())

        # Should have warning about no AVDs
        assert any("no avd" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_handles_gradle_not_found(
        self, plugin, android_dev_vm_resource, mock_ssh_connection
    ):
        """Test extraction handles Gradle not found gracefully."""

        async def no_gradle_command(conn, command):
            if "ANDROID_SDK_ROOT" in command:
                return "/home/devuser/Android/Sdk", "", 0
            elif "test -d" in command:
                return "EXISTS", "", 0
            elif "gradle -version" in command:
                return "NOT_FOUND", "", 1
            return "", "", 0

        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=no_gradle_command):
                    result = await plugin.extract_data(android_dev_vm_resource, Mock())

        # Should have warning about Gradle
        assert any("gradle" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_handles_unexpected_exception(
        self, plugin, android_dev_vm_resource, mock_ssh_connection
    ):
        """Test extraction handles unexpected exceptions gracefully."""

        async def exception_command(conn, command):
            raise Exception("Unexpected error")

        with tempfile.TemporaryDirectory() as tmpdir:
            plugin.output_dir = Path(tmpdir)

            with patch.object(plugin, "_connect_ssh", return_value=mock_ssh_connection):
                with patch.object(plugin, "_run_command", side_effect=exception_command):
                    result = await plugin.extract_data(android_dev_vm_resource, Mock())

        assert isinstance(result, ExtractionResult)
        assert len(result.errors) > 0

    def test_extract_hostname_from_network_interface(self, plugin):
        """Test hostname extraction from network interface."""
        resource = {
            "properties": {
                "networkProfile": {
                    "networkInterfaces": [
                        {
                            "properties": {
                                "ipConfigurations": [
                                    {
                                        "properties": {
                                            "publicIPAddress": {
                                                "properties": {"ipAddress": "1.2.3.4"}
                                            }
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        }

        hostname = plugin._extract_hostname(resource)
        assert hostname == "1.2.3.4"

    def test_extract_hostname_from_tags(self, plugin):
        """Test hostname extraction from tags."""
        resource = {"properties": {}, "tags": {"hostname": "android-dev.example.com"}}

        hostname = plugin._extract_hostname(resource)
        assert hostname == "android-dev.example.com"

    def test_extract_hostname_returns_none(self, plugin):
        """Test hostname extraction returns None when not found."""
        resource = {"properties": {}, "tags": {}}

        hostname = plugin._extract_hostname(resource)
        assert hostname is None
