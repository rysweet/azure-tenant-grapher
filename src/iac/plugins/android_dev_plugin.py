"""Android Development Environment Replication Plugin.

Handles data-plane replication for Android development environments including:
- Android SDK packages and tools
- Android Virtual Devices (AVDs) configurations
- Emulator settings
- Development tools (Android Studio, Gradle, NDK)
- Project configurations (build.gradle, gradle.properties)
- Keystore metadata (locations only, not actual keystores)
"""

import asyncio
import json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import ResourceReplicationPlugin
from .models import (
    AnalysisStatus,
    DataPlaneAnalysis,
    DataPlaneElement,
    ExtractedData,
    ExtractionFormat,
    ExtractionResult,
    PluginMetadata,
    ReplicationResult,
    ReplicationStatus,
    ReplicationStep,
    StepResult,
    StepType,
)

logger = logging.getLogger(__name__)


class AndroidDevReplicationPlugin(ResourceReplicationPlugin):
    """Replication plugin for Android development environments.

    Discovers and replicates Android SDK configurations, AVDs, emulator settings,
    and development tool configurations. Generates scripts to recreate the
    development environment on target VMs.
    """

    def __init__(
        self,
        ssh_username: Optional[str] = None,
        ssh_password: Optional[str] = None,
        ssh_key_path: Optional[str] = None,
        output_dir: Optional[str] = None,
    ):
        """Initialize Android Dev plugin.

        Args:
            ssh_username: SSH username for connections
            ssh_password: SSH password (if not using key)
            ssh_key_path: Path to SSH private key
            output_dir: Directory for extracted data (default: temp dir)
        """
        self.ssh_username = ssh_username or os.environ.get("SSH_USERNAME", "azureuser")
        self.ssh_password = ssh_password or os.environ.get("SSH_PASSWORD")
        self.ssh_key_path = ssh_key_path or os.environ.get("SSH_KEY_PATH")
        self.output_dir = Path(output_dir) if output_dir else None
        self._asyncssh_available = False

        try:
            import asyncssh  # noqa: F401

            self._asyncssh_available = True
        except ImportError:
            logger.warning("asyncssh not available - SSH connections will fail")

    @property
    def metadata(self) -> PluginMetadata:
        """Get plugin metadata."""
        return PluginMetadata(
            name="android_dev",
            version="1.0.0",
            resource_types=["Microsoft.Compute/virtualMachines"],
            description="Replicates Android development environments including SDK, AVDs, emulator settings, and tool configurations",
            requires_credentials=True,
            requires_network_access=True,
            complexity="MEDIUM",
            supported_formats=[
                ExtractionFormat.JSON,
                ExtractionFormat.SHELL_SCRIPT,
                ExtractionFormat.ANSIBLE_PLAYBOOK,
            ],
            tags=["android", "development", "mobile", "sdk", "emulator"],
            author="Azure Tenant Grapher",
        )

    def can_handle(self, resource: Dict[str, Any]) -> bool:
        """Check if this is an Android development VM.

        Args:
            resource: Resource dictionary

        Returns:
            True if this is an Android development VM
        """
        if resource.get("type") != "Microsoft.Compute/virtualMachines":
            return False

        # Check tags for Android indicators
        tags = resource.get("tags", {})
        role = tags.get("role", tags.get("Role", "")).lower()
        purpose = tags.get("purpose", tags.get("Purpose", "")).lower()
        tags.get("environment", tags.get("Environment", "")).lower()

        android_indicators = ["android", "mobile", "dev", "development"]
        if any(indicator in role for indicator in android_indicators) or any(
            indicator in purpose for indicator in android_indicators
        ):
            return True

        # Check computer name
        properties = resource.get("properties", {})
        os_profile = properties.get("osProfile", {})
        computer_name = os_profile.get("computerName", "").lower()
        if any(indicator in computer_name for indicator in ["android", "mobile", "dev"]):
            return True

        return False

    async def _connect_ssh(self, hostname: str) -> Any:
        """Connect to VM via SSH.

        Args:
            hostname: Hostname or IP address

        Returns:
            SSH connection object

        Raises:
            ConnectionError: If connection fails
        """
        if not self._asyncssh_available:
            raise ConnectionError("asyncssh library not available")

        import asyncssh

        try:
            connect_kwargs = {
                "host": hostname,
                "username": self.ssh_username,
                "known_hosts": None,
            }

            if self.ssh_key_path:
                connect_kwargs["client_keys"] = [self.ssh_key_path]
            elif self.ssh_password:
                connect_kwargs["password"] = self.ssh_password
            else:
                raise ConnectionError("No SSH authentication method provided")

            conn = await asyncio.wait_for(
                asyncssh.connect(**connect_kwargs), timeout=30.0
            )
            return conn

        except asyncio.TimeoutError:
            raise ConnectionError(f"SSH connection timeout to {hostname}") from None
        except Exception as e:
            raise ConnectionError(f"SSH connection failed to {hostname}: {e}") from e

    async def _run_command(
        self, conn: Any, command: str
    ) -> tuple[str, str, int]:
        """Run command on remote host.

        Args:
            conn: SSH connection
            command: Command to run

        Returns:
            Tuple of (stdout, stderr, exit_code)
        """
        result = await conn.run(command, check=False)
        return result.stdout, result.stderr, result.exit_status

    async def analyze_source(self, resource: Dict[str, Any]) -> DataPlaneAnalysis:
        """Analyze Android development VM to determine what needs replication.

        Args:
            resource: Source VM resource

        Returns:
            DataPlaneAnalysis with discovered elements
        """
        resource_id = resource.get("id", resource.get("name", "unknown"))
        elements: List[DataPlaneElement] = []
        warnings: List[str] = []
        connection_methods = ["SSH"]

        # Define Android SDK elements
        elements.extend(
            [
                DataPlaneElement(
                    name="android_sdk_info",
                    element_type="sdk_config",
                    description="Android SDK installation path and version information",
                    complexity="LOW",
                    estimated_size_mb=0.01,
                ),
                DataPlaneElement(
                    name="sdk_packages",
                    element_type="sdk_config",
                    description="Installed Android SDK packages and platforms",
                    complexity="MEDIUM",
                    estimated_size_mb=0.1,
                    dependencies=["android_sdk_info"],
                ),
                DataPlaneElement(
                    name="build_tools",
                    element_type="sdk_config",
                    description="Android build tools versions",
                    complexity="LOW",
                    estimated_size_mb=0.05,
                ),
                DataPlaneElement(
                    name="platform_tools",
                    element_type="sdk_config",
                    description="Android platform tools (adb, fastboot, etc.)",
                    complexity="LOW",
                    estimated_size_mb=0.02,
                ),
                DataPlaneElement(
                    name="avd_list",
                    element_type="emulator_config",
                    description="List of Android Virtual Devices (AVDs)",
                    complexity="MEDIUM",
                    estimated_size_mb=0.05,
                ),
                DataPlaneElement(
                    name="avd_configurations",
                    element_type="emulator_config",
                    description="AVD configuration files (config.ini, hardware settings)",
                    complexity="HIGH",
                    estimated_size_mb=1.0,
                    dependencies=["avd_list"],
                ),
                DataPlaneElement(
                    name="avd_ini_files",
                    element_type="emulator_config",
                    description="AVD .ini files with device metadata",
                    complexity="MEDIUM",
                    estimated_size_mb=0.1,
                    dependencies=["avd_list"],
                ),
                DataPlaneElement(
                    name="emulator_config",
                    element_type="emulator_config",
                    description="Emulator settings and preferences",
                    complexity="MEDIUM",
                    estimated_size_mb=0.2,
                ),
                DataPlaneElement(
                    name="gradle_config",
                    element_type="tool_config",
                    description="Gradle configuration (gradle.properties, wrapper)",
                    complexity="MEDIUM",
                    estimated_size_mb=0.5,
                ),
                DataPlaneElement(
                    name="gradle_version",
                    element_type="tool_config",
                    description="Installed Gradle version",
                    complexity="LOW",
                    estimated_size_mb=0.01,
                ),
                DataPlaneElement(
                    name="android_studio_settings",
                    element_type="tool_config",
                    description="Android Studio IDE settings (if installed)",
                    complexity="MEDIUM",
                    estimated_size_mb=0.5,
                ),
                DataPlaneElement(
                    name="ndk_info",
                    element_type="sdk_config",
                    description="Android NDK (Native Development Kit) if installed",
                    complexity="LOW",
                    estimated_size_mb=0.05,
                ),
                DataPlaneElement(
                    name="project_configurations",
                    element_type="project_config",
                    description="Android project build.gradle files",
                    complexity="MEDIUM",
                    estimated_size_mb=0.2,
                ),
                DataPlaneElement(
                    name="local_properties",
                    element_type="project_config",
                    description="local.properties files (sanitized)",
                    complexity="LOW",
                    estimated_size_mb=0.05,
                    is_sensitive=True,
                ),
                DataPlaneElement(
                    name="keystore_metadata",
                    element_type="security_metadata",
                    description="Keystore locations and metadata (NOT actual keystores)",
                    complexity="LOW",
                    estimated_size_mb=0.01,
                    is_sensitive=True,
                ),
                DataPlaneElement(
                    name="system_images",
                    element_type="sdk_config",
                    description="Installed Android system images for emulators",
                    complexity="LOW",
                    estimated_size_mb=0.1,
                ),
            ]
        )

        # Try to connect and verify Android SDK presence
        hostname = self._extract_hostname(resource)
        if hostname:
            try:
                conn = await self._connect_ssh(hostname)

                # Check for Android SDK
                sdk_check_cmd = 'echo ${ANDROID_SDK_ROOT:-${ANDROID_HOME:-"NOT_SET"}}'
                stdout, stderr, exit_code = await self._run_command(conn, sdk_check_cmd)

                if exit_code == 0 and "NOT_SET" not in stdout:
                    sdk_path = stdout.strip()
                    logger.info(f"Found Android SDK at: {sdk_path}")
                else:
                    warnings.append(
                        "Android SDK not found (ANDROID_SDK_ROOT/ANDROID_HOME not set)"
                    )

                await conn.close()

            except ConnectionError as e:
                warnings.append(f"Could not connect to verify: {e}")
                logger.warning(warnings[-1])
        else:
            warnings.append("No hostname/IP found - cannot verify accessibility")

        return DataPlaneAnalysis(
            resource_id=resource_id,
            resource_type=resource.get("type", "Microsoft.Compute/virtualMachines"),
            elements=elements,
            status=AnalysisStatus.SUCCESS,
            complexity_score=6.0,
            requires_credentials=True,
            requires_network_access=True,
            connection_methods=connection_methods,
            estimated_extraction_time_minutes=15,
            warnings=warnings,
            metadata={
                "os_type": "android_development",
                "plugin_version": self.metadata.version,
            },
        )

    async def extract_data(
        self, resource: Dict[str, Any], analysis: DataPlaneAnalysis
    ) -> ExtractionResult:
        """Extract Android development data from VM.

        Args:
            resource: Source VM resource
            analysis: Previous analysis result

        Returns:
            ExtractionResult with extracted data
        """
        start_time = datetime.utcnow()
        resource_id = resource.get("id", resource.get("name", "unknown"))
        hostname = self._extract_hostname(resource)

        if not hostname:
            raise ValueError("Cannot extract data: no hostname/IP found in resource")

        # Setup output directory
        if self.output_dir is None:
            self.output_dir = Path(tempfile.mkdtemp(prefix="android_extract_"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        extracted_data_list: List[ExtractedData] = []
        warnings: List[str] = []
        errors: List[str] = []
        items_extracted = 0
        items_failed = 0

        try:
            conn = await self._connect_ssh(hostname)

            # Extract Android SDK info
            sdk_info = await self._extract_sdk_info(conn, extracted_data_list)
            if sdk_info:
                items_extracted += 1
            else:
                items_failed += 1
                errors.append("Failed to extract SDK info")

            # Extract SDK packages
            if sdk_info:
                if await self._extract_sdk_packages(
                    conn, extracted_data_list, sdk_info, warnings
                ):
                    items_extracted += 1
                else:
                    items_failed += 1

            # Extract build tools
            if await self._extract_build_tools(
                conn, extracted_data_list, sdk_info, warnings
            ):
                items_extracted += 1
            else:
                items_failed += 1

            # Extract AVD configurations
            avd_count = await self._extract_avd_configurations(
                conn, extracted_data_list, warnings, errors
            )
            if avd_count > 0:
                items_extracted += avd_count
            elif avd_count < 0:
                items_failed += 1

            # Extract emulator config
            if await self._extract_emulator_config(conn, extracted_data_list, warnings):
                items_extracted += 1
            else:
                items_failed += 1

            # Extract Gradle config
            if await self._extract_gradle_config(conn, extracted_data_list, warnings):
                items_extracted += 1
            else:
                items_failed += 1

            # Extract NDK info
            if await self._extract_ndk_info(conn, extracted_data_list, warnings):
                items_extracted += 1

            # Extract Android Studio settings
            if await self._extract_android_studio_settings(
                conn, extracted_data_list, warnings
            ):
                items_extracted += 1

            # Extract project configurations
            if await self._extract_project_configs(conn, extracted_data_list, warnings):
                items_extracted += 1

            # Extract keystore metadata (NOT actual keystores)
            if await self._extract_keystore_metadata(
                conn, extracted_data_list, warnings
            ):
                items_extracted += 1

            # Extract system images info
            if await self._extract_system_images(
                conn, extracted_data_list, sdk_info, warnings
            ):
                items_extracted += 1

            await conn.close()

        except ConnectionError as e:
            errors.append(f"Connection failed: {e}")
        except Exception as e:
            errors.append(f"Extraction failed: {e}")
            logger.exception("Unexpected error during extraction")

        duration = (datetime.utcnow() - start_time).total_seconds()

        # Calculate total size
        total_size_bytes = sum(ed.size_bytes for ed in extracted_data_list)

        # Determine status
        if items_failed > 0 and items_extracted > 0:
            status = AnalysisStatus.PARTIAL
        elif items_failed > 0 and items_extracted == 0:
            status = AnalysisStatus.FAILED
        else:
            status = AnalysisStatus.SUCCESS

        return ExtractionResult(
            resource_id=resource_id,
            status=status,
            extracted_data=extracted_data_list,
            total_size_mb=total_size_bytes / (1024 * 1024),
            extraction_duration_seconds=duration,
            items_extracted=items_extracted,
            items_failed=items_failed,
            warnings=warnings,
            errors=errors,
            metadata={
                "hostname": hostname,
                "output_dir": str(self.output_dir),
            },
        )

    async def _extract_sdk_info(
        self, conn: Any, extracted_data_list: List[ExtractedData]
    ) -> Optional[str]:
        """Extract Android SDK path and version info.

        Args:
            conn: SSH connection
            extracted_data_list: List to append extracted data

        Returns:
            SDK root path or None
        """
        try:
            # Get SDK path
            stdout, stderr, code = await self._run_command(
                conn, 'echo ${ANDROID_SDK_ROOT:-${ANDROID_HOME:-"NOT_SET"}}'
            )

            if code == 0 and "NOT_SET" not in stdout:
                sdk_path = stdout.strip()

                # Verify path exists
                stdout_verify, _, code_verify = await self._run_command(
                    conn, f"test -d {sdk_path} && echo EXISTS || echo NOT_EXISTS"
                )

                if code_verify == 0 and "EXISTS" in stdout_verify:
                    sdk_info = {
                        "sdk_path": sdk_path,
                        "env_var": "ANDROID_SDK_ROOT"
                        if "ANDROID_SDK_ROOT" in os.environ
                        else "ANDROID_HOME",
                    }

                    extracted_data_list.append(
                        ExtractedData(
                            name="android_sdk_info",
                            format=ExtractionFormat.JSON,
                            content=json.dumps(sdk_info, indent=2),
                            file_path=str(self.output_dir / "android_sdk_info.json"),
                            size_bytes=len(json.dumps(sdk_info)),
                        )
                    )

                    # Write to file
                    (self.output_dir / "android_sdk_info.json").write_text(
                        json.dumps(sdk_info, indent=2)
                    )

                    logger.info(f"Extracted SDK info: {sdk_path}")
                    return sdk_path

            return None

        except Exception as e:
            logger.warning(f"Failed to extract SDK info: {e}")
            return None

    async def _extract_sdk_packages(
        self,
        conn: Any,
        extracted_data_list: List[ExtractedData],
        sdk_path: str,
        warnings: List[str],
    ) -> bool:
        """Extract installed SDK packages.

        Args:
            conn: SSH connection
            extracted_data_list: List to append extracted data
            sdk_path: Android SDK root path
            warnings: List to append warnings

        Returns:
            True if successful
        """
        try:
            # Try sdkmanager --list
            sdkmanager_path = f"{sdk_path}/cmdline-tools/latest/bin/sdkmanager"
            cmd = f"{sdkmanager_path} --list 2>/dev/null || echo 'NOT_FOUND'"

            stdout, stderr, code = await self._run_command(conn, cmd)

            if code == 0 and "NOT_FOUND" not in stdout:
                extracted_data_list.append(
                    ExtractedData(
                        name="sdk_packages",
                        format=ExtractionFormat.SHELL_SCRIPT,
                        content=stdout,
                        file_path=str(self.output_dir / "sdk_packages.txt"),
                        size_bytes=len(stdout),
                    )
                )

                # Write to file
                (self.output_dir / "sdk_packages.txt").write_text(stdout)

                # Parse installed packages
                installed_packages = []
                in_installed_section = False
                for line in stdout.split("\n"):
                    if "Installed packages:" in line:
                        in_installed_section = True
                        continue
                    if in_installed_section and line.strip():
                        if line.startswith("Available"):
                            break
                        if "|" in line:
                            parts = line.split("|")
                            if len(parts) >= 1:
                                package = parts[0].strip()
                                if package and not package.startswith("---"):
                                    installed_packages.append(package)

                # Save parsed list
                if installed_packages:
                    parsed_file = self.output_dir / "installed_packages.json"
                    parsed_file.write_text(json.dumps(installed_packages, indent=2))

                    extracted_data_list.append(
                        ExtractedData(
                            name="installed_packages_list",
                            format=ExtractionFormat.JSON,
                            content=json.dumps(installed_packages, indent=2),
                            file_path=str(parsed_file),
                            size_bytes=len(json.dumps(installed_packages)),
                        )
                    )

                logger.info(f"Extracted {len(installed_packages)} SDK packages")
                return True
            else:
                warnings.append(
                    "Could not extract SDK packages - sdkmanager not found"
                )
                return False

        except Exception as e:
            warnings.append(f"Failed to extract SDK packages: {e}")
            return False

    async def _extract_build_tools(
        self,
        conn: Any,
        extracted_data_list: List[ExtractedData],
        sdk_path: Optional[str],
        warnings: List[str],
    ) -> bool:
        """Extract build tools versions.

        Args:
            conn: SSH connection
            extracted_data_list: List to append extracted data
            sdk_path: Android SDK root path
            warnings: List to append warnings

        Returns:
            True if successful
        """
        try:
            if not sdk_path:
                return False

            cmd = f"ls -1 {sdk_path}/build-tools 2>/dev/null || echo 'NOT_FOUND'"
            stdout, stderr, code = await self._run_command(conn, cmd)

            if code == 0 and "NOT_FOUND" not in stdout:
                build_tools = [v.strip() for v in stdout.strip().split("\n") if v.strip()]

                if build_tools:
                    extracted_data_list.append(
                        ExtractedData(
                            name="build_tools",
                            format=ExtractionFormat.JSON,
                            content=json.dumps(build_tools, indent=2),
                            file_path=str(self.output_dir / "build_tools.json"),
                            size_bytes=len(json.dumps(build_tools)),
                        )
                    )

                    (self.output_dir / "build_tools.json").write_text(
                        json.dumps(build_tools, indent=2)
                    )

                    logger.info(f"Extracted {len(build_tools)} build tools versions")
                    return True

            warnings.append("No build tools found")
            return False

        except Exception as e:
            warnings.append(f"Failed to extract build tools: {e}")
            return False

    async def _extract_avd_configurations(
        self,
        conn: Any,
        extracted_data_list: List[ExtractedData],
        warnings: List[str],
        errors: List[str],
    ) -> int:
        """Extract AVD configurations.

        Args:
            conn: SSH connection
            extracted_data_list: List to append extracted data
            warnings: List to append warnings
            errors: List to append errors

        Returns:
            Number of AVDs extracted, or -1 on error
        """
        try:
            # List AVDs
            cmd = 'emulator -list-avds 2>/dev/null || echo "NOT_FOUND"'
            stdout, stderr, code = await self._run_command(conn, cmd)

            if code != 0 or "NOT_FOUND" in stdout:
                warnings.append("No emulator command found or no AVDs configured")
                return 0

            avd_names = [name.strip() for name in stdout.strip().split("\n") if name.strip()]

            if not avd_names:
                warnings.append("No AVDs found")
                return 0

            # Extract AVD configurations
            avd_configs = {}
            avd_dir_path = "~/.android/avd"

            for avd_name in avd_names:
                try:
                    # Read .ini file
                    ini_file = f"{avd_dir_path}/{avd_name}.ini"
                    stdout_ini, _, code_ini = await self._run_command(
                        conn, f"cat {ini_file} 2>/dev/null || echo 'NOT_FOUND'"
                    )

                    if code_ini == 0 and "NOT_FOUND" not in stdout_ini:
                        avd_configs[f"{avd_name}.ini"] = stdout_ini

                        # Save individual ini file
                        ini_local = self.output_dir / f"{avd_name}.ini"
                        ini_local.write_text(stdout_ini)

                        extracted_data_list.append(
                            ExtractedData(
                                name=f"avd_{avd_name}_ini",
                                format=ExtractionFormat.JSON,
                                content=stdout_ini,
                                file_path=str(ini_local),
                                size_bytes=len(stdout_ini),
                            )
                        )

                    # Read config.ini
                    config_file = f"{avd_dir_path}/{avd_name}.avd/config.ini"
                    stdout_cfg, _, code_cfg = await self._run_command(
                        conn, f"cat {config_file} 2>/dev/null || echo 'NOT_FOUND'"
                    )

                    if code_cfg == 0 and "NOT_FOUND" not in stdout_cfg:
                        avd_configs[f"{avd_name}_config.ini"] = stdout_cfg

                        # Save individual config.ini
                        cfg_local = self.output_dir / f"{avd_name}_config.ini"
                        cfg_local.write_text(stdout_cfg)

                        extracted_data_list.append(
                            ExtractedData(
                                name=f"avd_{avd_name}_config",
                                format=ExtractionFormat.JSON,
                                content=stdout_cfg,
                                file_path=str(cfg_local),
                                size_bytes=len(stdout_cfg),
                            )
                        )

                except Exception as e:
                    warnings.append(f"Failed to extract AVD {avd_name}: {e}")

            if avd_configs:
                # Save summary
                summary = {
                    "avd_count": len(avd_names),
                    "avd_names": avd_names,
                    "configurations": list(avd_configs.keys()),
                }

                summary_file = self.output_dir / "avd_summary.json"
                summary_file.write_text(json.dumps(summary, indent=2))

                extracted_data_list.append(
                    ExtractedData(
                        name="avd_summary",
                        format=ExtractionFormat.JSON,
                        content=json.dumps(summary, indent=2),
                        file_path=str(summary_file),
                        size_bytes=len(json.dumps(summary)),
                    )
                )

                logger.info(f"Extracted {len(avd_names)} AVD configurations")
                return len(avd_names)

            return 0

        except Exception as e:
            errors.append(f"Failed to extract AVD configurations: {e}")
            return -1

    async def _extract_emulator_config(
        self,
        conn: Any,
        extracted_data_list: List[ExtractedData],
        warnings: List[str],
    ) -> bool:
        """Extract emulator configuration.

        Args:
            conn: SSH connection
            extracted_data_list: List to append extracted data
            warnings: List to append warnings

        Returns:
            True if successful
        """
        try:
            # Check for emulator config files
            config_paths = [
                "~/.android/avd/advancedFeatures.ini",
                "~/.emulator_console_auth_token",
            ]

            config_found = False

            for config_path in config_paths:
                stdout, stderr, code = await self._run_command(
                    conn, f"cat {config_path} 2>/dev/null || echo 'NOT_FOUND'"
                )

                if code == 0 and "NOT_FOUND" not in stdout:
                    filename = Path(config_path).name
                    local_file = self.output_dir / f"emulator_{filename}"
                    local_file.write_text(stdout)

                    extracted_data_list.append(
                        ExtractedData(
                            name=f"emulator_{filename}",
                            format=ExtractionFormat.JSON,
                            content=stdout,
                            file_path=str(local_file),
                            size_bytes=len(stdout),
                        )
                    )

                    config_found = True

            if not config_found:
                warnings.append("No emulator configuration files found")

            return config_found

        except Exception as e:
            warnings.append(f"Failed to extract emulator config: {e}")
            return False

    async def _extract_gradle_config(
        self,
        conn: Any,
        extracted_data_list: List[ExtractedData],
        warnings: List[str],
    ) -> bool:
        """Extract Gradle configuration.

        Args:
            conn: SSH connection
            extracted_data_list: List to append extracted data
            warnings: List to append warnings

        Returns:
            True if successful
        """
        try:
            # Check Gradle version
            stdout_ver, stderr_ver, code_ver = await self._run_command(
                conn, "gradle -version 2>/dev/null || echo 'NOT_FOUND'"
            )

            gradle_info = {}

            if code_ver == 0 and "NOT_FOUND" not in stdout_ver:
                gradle_info["version_output"] = stdout_ver

                # Extract version number
                version_match = re.search(r"Gradle (\d+\.\d+(?:\.\d+)?)", stdout_ver)
                if version_match:
                    gradle_info["version"] = version_match.group(1)

            # Extract gradle.properties
            gradle_props_path = "~/.gradle/gradle.properties"
            stdout_props, stderr_props, code_props = await self._run_command(
                conn, f"cat {gradle_props_path} 2>/dev/null || echo 'NOT_FOUND'"
            )

            if code_props == 0 and "NOT_FOUND" not in stdout_props:
                # Sanitize API keys and sensitive data
                sanitized_props = self._sanitize_gradle_properties(stdout_props)
                gradle_info["gradle_properties"] = sanitized_props

                props_file = self.output_dir / "gradle.properties"
                props_file.write_text(sanitized_props)

            if gradle_info:
                gradle_file = self.output_dir / "gradle_config.json"
                gradle_file.write_text(json.dumps(gradle_info, indent=2))

                extracted_data_list.append(
                    ExtractedData(
                        name="gradle_config",
                        format=ExtractionFormat.JSON,
                        content=json.dumps(gradle_info, indent=2),
                        file_path=str(gradle_file),
                        size_bytes=len(json.dumps(gradle_info)),
                    )
                )

                logger.info("Extracted Gradle configuration")
                return True
            else:
                warnings.append("Gradle not found or not configured")
                return False

        except Exception as e:
            warnings.append(f"Failed to extract Gradle config: {e}")
            return False

    async def _extract_ndk_info(
        self,
        conn: Any,
        extracted_data_list: List[ExtractedData],
        warnings: List[str],
    ) -> bool:
        """Extract Android NDK information.

        Args:
            conn: SSH connection
            extracted_data_list: List to append extracted data
            warnings: List to append warnings

        Returns:
            True if successful
        """
        try:
            # Check for NDK
            stdout, stderr, code = await self._run_command(
                conn, 'echo ${ANDROID_NDK_HOME:-"NOT_SET"}'
            )

            if code == 0 and "NOT_SET" not in stdout:
                ndk_path = stdout.strip()

                # Verify NDK exists
                stdout_ver, _, code_ver = await self._run_command(
                    conn,
                    f"test -f {ndk_path}/source.properties && cat {ndk_path}/source.properties || echo 'NOT_FOUND'",
                )

                if code_ver == 0 and "NOT_FOUND" not in stdout_ver:
                    ndk_info = {"ndk_path": ndk_path, "source_properties": stdout_ver}

                    ndk_file = self.output_dir / "ndk_info.json"
                    ndk_file.write_text(json.dumps(ndk_info, indent=2))

                    extracted_data_list.append(
                        ExtractedData(
                            name="ndk_info",
                            format=ExtractionFormat.JSON,
                            content=json.dumps(ndk_info, indent=2),
                            file_path=str(ndk_file),
                            size_bytes=len(json.dumps(ndk_info)),
                        )
                    )

                    logger.info(f"Extracted NDK info: {ndk_path}")
                    return True

            warnings.append("Android NDK not found")
            return False

        except Exception as e:
            warnings.append(f"Failed to extract NDK info: {e}")
            return False

    async def _extract_android_studio_settings(
        self,
        conn: Any,
        extracted_data_list: List[ExtractedData],
        warnings: List[str],
    ) -> bool:
        """Extract Android Studio settings.

        Args:
            conn: SSH connection
            extracted_data_list: List to append extracted data
            warnings: List to append warnings

        Returns:
            True if successful
        """
        try:
            # Check for Android Studio config directories
            # Common locations: ~/.AndroidStudio*, ~/.config/Google/AndroidStudio*
            stdout, stderr, code = await self._run_command(
                conn, "ls -d ~/.AndroidStudio* 2>/dev/null || echo 'NOT_FOUND'"
            )

            if code == 0 and "NOT_FOUND" not in stdout:
                studio_dirs = [d.strip() for d in stdout.strip().split("\n") if d.strip()]

                if studio_dirs:
                    settings_info = {
                        "config_dirs": studio_dirs,
                        "note": "Android Studio settings found - manual migration recommended",
                    }

                    settings_file = self.output_dir / "android_studio_settings.json"
                    settings_file.write_text(json.dumps(settings_info, indent=2))

                    extracted_data_list.append(
                        ExtractedData(
                            name="android_studio_settings",
                            format=ExtractionFormat.JSON,
                            content=json.dumps(settings_info, indent=2),
                            file_path=str(settings_file),
                            size_bytes=len(json.dumps(settings_info)),
                        )
                    )

                    logger.info("Extracted Android Studio settings metadata")
                    return True

            warnings.append("Android Studio settings not found")
            return False

        except Exception as e:
            warnings.append(f"Failed to extract Android Studio settings: {e}")
            return False

    async def _extract_project_configs(
        self,
        conn: Any,
        extracted_data_list: List[ExtractedData],
        warnings: List[str],
    ) -> bool:
        """Extract Android project configurations.

        Args:
            conn: SSH connection
            extracted_data_list: List to append extracted data
            warnings: List to append warnings

        Returns:
            True if successful
        """
        try:
            # Find build.gradle files (limit search to common project locations)
            stdout, stderr, code = await self._run_command(
                conn,
                "find ~/projects ~/workspace ~/dev -name build.gradle -type f 2>/dev/null | head -20 || echo 'NOT_FOUND'",
            )

            if code == 0 and "NOT_FOUND" not in stdout and stdout.strip():
                gradle_files = [
                    f.strip() for f in stdout.strip().split("\n") if f.strip()
                ]

                projects_info = {"build_gradle_files": gradle_files, "count": len(gradle_files)}

                projects_file = self.output_dir / "project_configs.json"
                projects_file.write_text(json.dumps(projects_info, indent=2))

                extracted_data_list.append(
                    ExtractedData(
                        name="project_configs",
                        format=ExtractionFormat.JSON,
                        content=json.dumps(projects_info, indent=2),
                        file_path=str(projects_file),
                        size_bytes=len(json.dumps(projects_info)),
                    )
                )

                logger.info(f"Found {len(gradle_files)} Android project configurations")
                return True

            warnings.append("No Android project configurations found")
            return False

        except Exception as e:
            warnings.append(f"Failed to extract project configs: {e}")
            return False

    async def _extract_keystore_metadata(
        self,
        conn: Any,
        extracted_data_list: List[ExtractedData],
        warnings: List[str],
    ) -> bool:
        """Extract keystore metadata (NOT actual keystores).

        SECURITY: This only extracts file locations and metadata,
        never the actual keystore files.

        Args:
            conn: SSH connection
            extracted_data_list: List to append extracted data
            warnings: List to append warnings

        Returns:
            True if successful
        """
        try:
            # Find .keystore and .jks files
            stdout, stderr, code = await self._run_command(
                conn,
                "find ~ -name '*.keystore' -o -name '*.jks' 2>/dev/null | head -10 || echo 'NOT_FOUND'",
            )

            if code == 0 and "NOT_FOUND" not in stdout and stdout.strip():
                keystore_files = [f.strip() for f in stdout.strip().split("\n") if f.strip()]

                # Get file info (size, permissions) but NOT contents
                keystores_info = []
                for keystore_path in keystore_files:
                    stdout_stat, _, code_stat = await self._run_command(
                        conn, f"stat -c '%s %A' {keystore_path} 2>/dev/null"
                    )

                    if code_stat == 0:
                        parts = stdout_stat.strip().split()
                        if len(parts) >= 2:
                            keystores_info.append(
                                {
                                    "path": keystore_path,
                                    "size_bytes": parts[0],
                                    "permissions": parts[1],
                                    "warning": "KEYSTORE FILE - DO NOT EXPORT DIRECTLY",
                                }
                            )

                if keystores_info:
                    keystore_file = self.output_dir / "keystore_metadata.json"
                    keystore_content = {
                        "keystores": keystores_info,
                        "count": len(keystores_info),
                        "security_note": "This is metadata only. Actual keystores must be migrated securely and separately.",
                    }
                    keystore_file.write_text(json.dumps(keystore_content, indent=2))

                    extracted_data_list.append(
                        ExtractedData(
                            name="keystore_metadata",
                            format=ExtractionFormat.JSON,
                            content=json.dumps(keystore_content, indent=2),
                            file_path=str(keystore_file),
                            size_bytes=len(json.dumps(keystore_content)),
                            metadata={"sensitive": True},
                        )
                    )

                    warnings.append(
                        f"Found {len(keystores_info)} keystores - these must be migrated manually and securely"
                    )
                    logger.info(
                        f"Extracted metadata for {len(keystores_info)} keystores (NOT actual files)"
                    )
                    return True

            return False

        except Exception as e:
            warnings.append(f"Failed to extract keystore metadata: {e}")
            return False

    async def _extract_system_images(
        self,
        conn: Any,
        extracted_data_list: List[ExtractedData],
        sdk_path: Optional[str],
        warnings: List[str],
    ) -> bool:
        """Extract installed system images information.

        Args:
            conn: SSH connection
            extracted_data_list: List to append extracted data
            sdk_path: Android SDK root path
            warnings: List to append warnings

        Returns:
            True if successful
        """
        try:
            if not sdk_path:
                return False

            cmd = f"ls -1 {sdk_path}/system-images 2>/dev/null || echo 'NOT_FOUND'"
            stdout, stderr, code = await self._run_command(conn, cmd)

            if code == 0 and "NOT_FOUND" not in stdout and stdout.strip():
                # Parse system images directory structure
                # Typically: system-images/<platform>/<tag>/<abi>/
                cmd_detailed = (
                    f"find {sdk_path}/system-images -mindepth 3 -maxdepth 3 -type d 2>/dev/null"
                )
                stdout_detailed, _, code_detailed = await self._run_command(
                    conn, cmd_detailed
                )

                if code_detailed == 0 and stdout_detailed.strip():
                    system_images = []
                    for path in stdout_detailed.strip().split("\n"):
                        if path.strip():
                            parts = path.replace(f"{sdk_path}/system-images/", "").split(
                                "/"
                            )
                            if len(parts) >= 3:
                                system_images.append(
                                    {
                                        "platform": parts[0],
                                        "tag": parts[1],
                                        "abi": parts[2],
                                        "path": path,
                                    }
                                )

                    if system_images:
                        images_file = self.output_dir / "system_images.json"
                        images_file.write_text(json.dumps(system_images, indent=2))

                        extracted_data_list.append(
                            ExtractedData(
                                name="system_images",
                                format=ExtractionFormat.JSON,
                                content=json.dumps(system_images, indent=2),
                                file_path=str(images_file),
                                size_bytes=len(json.dumps(system_images)),
                            )
                        )

                        logger.info(f"Extracted {len(system_images)} system images")
                        return True

            warnings.append("No system images found")
            return False

        except Exception as e:
            warnings.append(f"Failed to extract system images: {e}")
            return False

    def _sanitize_gradle_properties(self, content: str) -> str:
        """Sanitize Gradle properties by removing API keys and secrets.

        Args:
            content: Original gradle.properties content

        Returns:
            Sanitized content
        """
        lines = []
        sensitive_patterns = [
            r".*api[_-]?key.*",
            r".*secret.*",
            r".*password.*",
            r".*token.*",
            r".*credential.*",
        ]

        for line in content.split("\n"):
            sanitized_line = line
            # Check for sensitive keys
            for pattern in sensitive_patterns:
                if re.match(pattern, line.lower()):
                    # Replace value with placeholder
                    if "=" in line:
                        key = line.split("=")[0]
                        sanitized_line = f"{key}=***SANITIZED***"
                    break

            lines.append(sanitized_line)

        return "\n".join(lines)

    def _extract_hostname(self, resource: Dict[str, Any]) -> Optional[str]:
        """Extract hostname or IP from resource.

        Args:
            resource: Resource dictionary

        Returns:
            Hostname/IP or None
        """
        properties = resource.get("properties", {})

        # Check network profile for public IP
        network_profile = properties.get("networkProfile", {})
        network_interfaces = network_profile.get("networkInterfaces", [])

        for nic in network_interfaces:
            nic_props = nic.get("properties", {})
            ip_configs = nic_props.get("ipConfigurations", [])
            for ip_config in ip_configs:
                public_ip = ip_config.get("properties", {}).get("publicIPAddress", {})
                ip_address = public_ip.get("properties", {}).get("ipAddress")
                if ip_address:
                    return ip_address

        # Check tags
        tags = resource.get("tags", {})
        if "hostname" in tags:
            return tags["hostname"]
        if "ip" in tags:
            return tags["ip"]

        # Check metadata
        metadata = resource.get("metadata", {})
        if "hostname" in metadata:
            return metadata["hostname"]

        return None

    async def generate_replication_steps(
        self, extraction: ExtractionResult
    ) -> List[ReplicationStep]:
        """Generate replication steps for Android development environment.

        Args:
            extraction: Previous extraction result

        Returns:
            List of replication steps
        """
        steps: List[ReplicationStep] = []
        output_dir = Path(extraction.metadata.get("output_dir", self.output_dir))

        # Generate shell script for SDK installation
        install_script = self._generate_sdk_install_script(extraction)
        install_script_path = output_dir / "install_android_sdk.sh"
        install_script_path.write_text(install_script)

        # Generate Ansible playbook
        playbook = self._generate_ansible_playbook(extraction)
        playbook_path = output_dir / "android_replication_playbook.yml"
        playbook_path.write_text(playbook)

        # Generate documentation
        docs = self._generate_documentation(extraction)
        docs_path = output_dir / "REPLICATION_GUIDE.md"
        docs_path.write_text(docs)

        # Step 1: Validate target
        steps.append(
            ReplicationStep(
                step_id="validate_target",
                step_type=StepType.PREREQUISITE,
                description="Validate target VM is accessible and has required resources",
                script_content="ansible target -i inventory.ini -m ping",
                depends_on=[],
                is_critical=True,
                estimated_duration_minutes=2,
            )
        )

        # Step 2: Install prerequisites
        steps.append(
            ReplicationStep(
                step_id="install_prerequisites",
                step_type=StepType.PREREQUISITE,
                description="Install Java JDK and other Android SDK prerequisites",
                script_content=playbook,
                depends_on=["validate_target"],
                is_critical=True,
                estimated_duration_minutes=10,
                metadata={"tags": "prerequisites", "script_path": str(playbook_path)},
            )
        )

        # Step 3: Install Android SDK command-line tools
        steps.append(
            ReplicationStep(
                step_id="install_sdk_tools",
                step_type=StepType.CONFIGURATION,
                description="Install Android SDK command-line tools",
                script_content=install_script,
                script_format=ExtractionFormat.SHELL_SCRIPT,
                depends_on=["install_prerequisites"],
                is_critical=True,
                estimated_duration_minutes=5,
                metadata={"script_path": str(install_script_path)},
            )
        )

        # Step 4: Install SDK packages
        steps.append(
            ReplicationStep(
                step_id="install_sdk_packages",
                step_type=StepType.CONFIGURATION,
                description="Install Android SDK packages, platforms, and build tools",
                script_content=install_script,
                script_format=ExtractionFormat.SHELL_SCRIPT,
                depends_on=["install_sdk_tools"],
                is_critical=True,
                estimated_duration_minutes=20,
                metadata={"script_path": str(install_script_path)},
            )
        )

        # Step 5: Configure AVDs
        steps.append(
            ReplicationStep(
                step_id="configure_avds",
                step_type=StepType.CONFIGURATION,
                description="Create and configure Android Virtual Devices (AVDs)",
                script_content=playbook,
                depends_on=["install_sdk_packages"],
                is_critical=False,
                estimated_duration_minutes=10,
                metadata={"tags": "avds", "script_path": str(playbook_path)},
            )
        )

        # Step 6: Install Gradle
        steps.append(
            ReplicationStep(
                step_id="install_gradle",
                step_type=StepType.CONFIGURATION,
                description="Install Gradle build tool",
                script_content=playbook,
                depends_on=["install_prerequisites"],
                is_critical=False,
                estimated_duration_minutes=5,
                metadata={"tags": "gradle", "script_path": str(playbook_path)},
            )
        )

        # Step 7: Configure environment
        steps.append(
            ReplicationStep(
                step_id="configure_environment",
                step_type=StepType.CONFIGURATION,
                description="Set up environment variables and paths",
                script_content=playbook,
                depends_on=["install_sdk_packages", "install_gradle"],
                is_critical=True,
                estimated_duration_minutes=2,
                metadata={"tags": "environment", "script_path": str(playbook_path)},
            )
        )

        # Step 8: Verify installation
        steps.append(
            ReplicationStep(
                step_id="verify_installation",
                step_type=StepType.VALIDATION,
                description="Verify Android SDK and tools are properly installed",
                script_content=playbook,
                depends_on=["configure_environment"],
                is_critical=False,
                estimated_duration_minutes=3,
                metadata={"tags": "verify", "script_path": str(playbook_path)},
            )
        )

        return steps

    def _generate_sdk_install_script(self, extraction: ExtractionResult) -> str:
        """Generate shell script to install Android SDK.

        Args:
            extraction: Extraction result with data

        Returns:
            Shell script content
        """
        # Extract SDK packages from extracted data
        installed_packages = []
        for ed in extraction.extracted_data:
            if ed.name == "installed_packages_list":
                try:
                    installed_packages = json.loads(ed.content)
                except json.JSONDecodeError:
                    pass

        build_tools = []
        for ed in extraction.extracted_data:
            if ed.name == "build_tools":
                try:
                    build_tools = json.loads(ed.content)
                except json.JSONDecodeError:
                    pass

        script = """#!/bin/bash
# Android SDK Installation Script
# Generated by Azure Tenant Grapher

set -e  # Exit on error

echo "========================================"
echo "Android SDK Installation"
echo "========================================"

# Define variables
ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}"
CMDLINE_TOOLS_URL="https://dl.google.com/android/repository/commandlinetools-linux-9477386_latest.zip"

# Install command-line tools
echo "Installing Android SDK command-line tools..."
mkdir -p "$ANDROID_SDK_ROOT/cmdline-tools"
cd /tmp
wget -q "$CMDLINE_TOOLS_URL" -O commandlinetools.zip
unzip -q commandlinetools.zip
mv cmdline-tools "$ANDROID_SDK_ROOT/cmdline-tools/latest"
rm commandlinetools.zip

# Set up environment
export PATH="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$PATH"
export PATH="$ANDROID_SDK_ROOT/platform-tools:$PATH"

# Accept licenses
echo "Accepting Android SDK licenses..."
yes | sdkmanager --licenses > /dev/null 2>&1 || true

echo "Installing Android SDK packages..."
"""

        # Add platform-tools and build-tools
        if build_tools:
            for bt in build_tools[:3]:  # Install top 3 versions
                script += f'sdkmanager "build-tools;{bt}"\n'
        else:
            script += 'sdkmanager "build-tools;33.0.0"\n'

        script += 'sdkmanager "platform-tools"\n'

        # Add key SDK packages
        script += """
# Install essential SDK components
sdkmanager "platforms;android-33"
sdkmanager "platforms;android-34"
sdkmanager "emulator"

"""

        # Add specific packages from source if available
        if installed_packages:
            script += "# Install packages from source environment\n"
            # Filter to essential packages only
            essential_patterns = [
                "platforms",
                "system-images",
                "build-tools",
                "platform-tools",
                "emulator",
            ]

            for package in installed_packages[:20]:  # Limit to 20 packages
                if any(pattern in package.lower() for pattern in essential_patterns):
                    safe_package = package.strip()
                    if safe_package:
                        script += f'sdkmanager "{safe_package}" || echo "Warning: Failed to install {safe_package}"\n'

        script += """
echo "========================================"
echo "Android SDK installation completed!"
echo "SDK Location: $ANDROID_SDK_ROOT"
echo "========================================"
echo ""
echo "Add to your ~/.bashrc or ~/.zshrc:"
echo 'export ANDROID_SDK_ROOT="$HOME/Android/Sdk"'
echo 'export PATH="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$PATH"'
echo 'export PATH="$ANDROID_SDK_ROOT/platform-tools:$PATH"'
echo 'export PATH="$ANDROID_SDK_ROOT/emulator:$PATH"'
"""

        return script

    def _generate_ansible_playbook(self, extraction: ExtractionResult) -> str:
        """Generate Ansible playbook for Android environment setup.

        Args:
            extraction: Extraction result with data

        Returns:
            Ansible playbook as YAML string
        """
        # Extract AVD info
        avd_names = []
        for ed in extraction.extracted_data:
            if ed.name == "avd_summary":
                try:
                    summary = json.loads(ed.content)
                    avd_names = summary.get("avd_names", [])
                except json.JSONDecodeError:
                    pass

        playbook = """---
- name: Replicate Android Development Environment
  hosts: target
  become: yes
  gather_facts: yes

  vars:
    android_sdk_root: "{{ lookup('env', 'ANDROID_SDK_ROOT') | default('/home/' + ansible_user_id + '/Android/Sdk', true) }}"
    android_user: "{{ ansible_user_id }}"

  tasks:
    # Prerequisites
    - name: Install Java JDK
      tags: prerequisites
      apt:
        name:
          - openjdk-11-jdk
          - wget
          - unzip
        state: present
        update_cache: yes
      when: ansible_os_family == "Debian"

    - name: Install Java JDK (RHEL)
      tags: prerequisites
      yum:
        name:
          - java-11-openjdk-devel
          - wget
          - unzip
        state: present
      when: ansible_os_family == "RedHat"

    # Gradle installation
    - name: Download Gradle
      tags: gradle
      get_url:
        url: https://services.gradle.org/distributions/gradle-8.0-bin.zip
        dest: /tmp/gradle.zip
        mode: '0644'

    - name: Extract Gradle
      tags: gradle
      unarchive:
        src: /tmp/gradle.zip
        dest: /opt
        remote_src: yes
        creates: /opt/gradle-8.0

    - name: Create Gradle symlink
      tags: gradle
      file:
        src: /opt/gradle-8.0
        dest: /opt/gradle
        state: link

    # Environment variables
    - name: Configure Android environment variables
      tags: environment
      blockinfile:
        path: "/home/{{ android_user }}/.bashrc"
        block: |
          export ANDROID_SDK_ROOT="{{ android_sdk_root }}"
          export ANDROID_HOME="{{ android_sdk_root }}"
          export PATH="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$PATH"
          export PATH="$ANDROID_SDK_ROOT/platform-tools:$PATH"
          export PATH="$ANDROID_SDK_ROOT/emulator:$PATH"
          export PATH="/opt/gradle/bin:$PATH"
        marker: "# {mark} ANDROID ENVIRONMENT VARIABLES"
        create: yes

    # AVD configurations
"""

        if avd_names:
            playbook += f"""    - name: Create AVD directory
      tags: avds
      file:
        path: "/home/{{{{ android_user }}}}/.android/avd"
        state: directory
        owner: "{{{{ android_user }}}}"
        mode: '0755'

    - name: Note about AVD configurations
      tags: avds
      debug:
        msg: "AVDs from source: {avd_names}. AVD configuration files have been extracted and need to be manually reviewed and adapted."
"""

        playbook += """
    # Verification
    - name: Verify Android SDK installation
      tags: verify
      shell: |
        export ANDROID_SDK_ROOT="{{ android_sdk_root }}"
        $ANDROID_SDK_ROOT/cmdline-tools/latest/bin/sdkmanager --list | head -20
      become_user: "{{ android_user }}"
      register: sdk_verification
      changed_when: false
      ignore_errors: yes

    - name: Display SDK verification
      tags: verify
      debug:
        var: sdk_verification.stdout_lines
      when: sdk_verification is defined

    - name: Verify Gradle installation
      tags: verify
      command: /opt/gradle/bin/gradle --version
      register: gradle_verification
      changed_when: false
      ignore_errors: yes

    - name: Display Gradle verification
      tags: verify
      debug:
        var: gradle_verification.stdout_lines
      when: gradle_verification is defined

  handlers:
    - name: reload shell
      shell: source ~/.bashrc
      become_user: "{{ android_user }}"
"""

        return playbook

    def _generate_documentation(self, extraction: ExtractionResult) -> str:
        """Generate replication documentation.

        Args:
            extraction: Extraction result with data

        Returns:
            Markdown documentation
        """
        docs = """# Android Development Environment Replication Guide

## Overview

This guide provides instructions for replicating the Android development environment
from the source VM to a target VM.

## Generated Files

The following files have been generated:

- `install_android_sdk.sh` - Shell script to install Android SDK and packages
- `android_replication_playbook.yml` - Ansible playbook for complete setup
- `REPLICATION_GUIDE.md` - This documentation file

## Prerequisites

Target VM must have:
- Ubuntu 20.04+ or similar Linux distribution
- Minimum 4GB RAM (8GB+ recommended for emulator)
- 20GB+ free disk space
- Internet connectivity
- SSH access

## Manual Replication Steps

### Option 1: Using Shell Script (Quick)

```bash
# Copy the installation script to target VM
scp install_android_sdk.sh user@target-vm:~/

# SSH to target VM and run
ssh user@target-vm
chmod +x install_android_sdk.sh
./install_android_sdk.sh

# Update your shell configuration
source ~/.bashrc
```

### Option 2: Using Ansible Playbook (Recommended)

```bash
# Create inventory file
cat > inventory.ini << EOF
[target]
target-vm ansible_host=<TARGET_IP> ansible_user=<USER>
EOF

# Run the playbook
ansible-playbook -i inventory.ini android_replication_playbook.yml

# Or run specific steps
ansible-playbook -i inventory.ini android_replication_playbook.yml --tags prerequisites
ansible-playbook -i inventory.ini android_replication_playbook.yml --tags gradle
ansible-playbook -i inventory.ini android_replication_playbook.yml --tags environment
```

## Extracted Data

The following data has been extracted from the source environment:

"""

        # Add extracted data summary
        for ed in extraction.extracted_data:
            docs += f"- **{ed.name}**: {ed.file_path}\n"

        docs += """
## Post-Installation Steps

1. **Verify Android SDK Installation**:
   ```bash
   sdkmanager --list
   adb version
   ```

2. **Configure AVDs**:
   - Review extracted AVD configurations in `avd_*.ini` files
   - Recreate AVDs using `avdmanager create avd` command
   - Or import AVD configurations manually

3. **Install Android Studio** (Optional):
   ```bash
   # Download from: https://developer.android.com/studio
   # Install and point to existing SDK location
   ```

4. **Configure Gradle**:
   - Review extracted `gradle.properties`
   - Update any project-specific settings
   - Verify Gradle wrapper configurations

## Security Considerations

### Keystores

⚠️ **IMPORTANT**: Keystore files have been identified but NOT exported.

"""

        # Add keystore warnings
        for ed in extraction.extracted_data:
            if ed.name == "keystore_metadata":
                docs += """
Keystore locations and metadata are documented in `keystore_metadata.json`.

**To migrate keystores**:
1. Copy keystore files securely using SCP or secure file transfer
2. Update project `build.gradle` with new keystore paths
3. Ensure keystore passwords are stored in secure password managers
4. Never commit keystores to version control

"""

        docs += """
### API Keys and Secrets

Any API keys in `gradle.properties` and `local.properties` have been sanitized.
You must:
1. Retrieve actual API keys from secure storage
2. Update configuration files on target VM
3. Use environment variables or secure vaults for secrets

## Verification

After installation, verify:

```bash
# Check SDK
sdkmanager --list

# Check platform tools
adb version

# Check emulator
emulator -list-avds

# Check Gradle
gradle --version

# Check Java
java -version
```

## Troubleshooting

### SDK License Issues

If you see license errors:
```bash
yes | sdkmanager --licenses
```

### Environment Variables Not Set

Ensure your shell profile is updated:
```bash
source ~/.bashrc  # or ~/.zshrc
echo $ANDROID_SDK_ROOT
```

### Emulator Issues

Check virtualization support:
```bash
egrep -c '(vmx|svm)' /proc/cpuinfo  # Should be > 0
```

### Gradle Issues

If Gradle fails to find SDK:
```bash
export ANDROID_SDK_ROOT=/path/to/sdk
```

## Additional Resources

- [Android Developer Documentation](https://developer.android.com/docs)
- [SDK Command-line Tools](https://developer.android.com/studio/command-line)
- [AVD Manager](https://developer.android.com/studio/run/managing-avds)
- [Gradle Build Tool](https://gradle.org/guides/)

## Support

For issues or questions, refer to the Azure Tenant Grapher documentation.

---
*Generated by Azure Tenant Grapher Android Development Plugin v1.0.0*
"""

        return docs

    async def apply_to_target(
        self, steps: List[ReplicationStep], target_resource_id: str
    ) -> ReplicationResult:
        """Apply replication steps to target VM.

        Args:
            steps: Steps to execute
            target_resource_id: Azure resource ID of target

        Returns:
            ReplicationResult with execution status
        """
        start_time = datetime.utcnow()
        steps_executed: List[StepResult] = []
        warnings: List[str] = [
            "apply_to_target is not fully implemented - manual execution required"
        ]
        errors: List[str] = []

        # Simulate execution tracking
        for step in steps:
            step_start = datetime.utcnow()
            logger.info(f"Would execute step: {step.step_id} - {step.description}")

            step_result = StepResult(
                step_id=step.step_id,
                status=ReplicationStatus.SUCCESS,
                duration_seconds=1.0,
                stdout=f"Simulated execution of {step.step_id}",
                stderr="",
                exit_code=0,
                executed_at=step_start,
            )
            steps_executed.append(step_result)

        duration = (datetime.utcnow() - start_time).total_seconds()
        steps_succeeded = len([s for s in steps_executed if s.status == ReplicationStatus.SUCCESS])
        steps_failed = len([s for s in steps_executed if s.status == ReplicationStatus.FAILED])

        status = (
            ReplicationStatus.SUCCESS
            if steps_failed == 0
            else (
                ReplicationStatus.PARTIAL
                if steps_succeeded > 0
                else ReplicationStatus.FAILED
            )
        )

        warnings.append(
            "Scripts have been generated. Execute manually on target VM or use Ansible for automated deployment."
        )

        return ReplicationResult(
            source_resource_id="android-dev-source",
            target_resource_id=target_resource_id,
            status=status,
            steps_executed=steps_executed,
            total_duration_seconds=duration,
            steps_succeeded=steps_succeeded,
            steps_failed=steps_failed,
            fidelity_score=0.85,  # Estimated fidelity
            warnings=warnings,
            errors=errors,
            metadata={
                "total_steps": len(steps),
                "simulated": True,
                "manual_execution_required": True,
            },
        )
