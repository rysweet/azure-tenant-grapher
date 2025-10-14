"""Kali Linux Security Plugin for replication.

Handles data-plane replication for Kali Linux penetration testing VMs including:
- Kali-specific packages and tools
- Metasploit Framework configuration
- Custom security tools and scripts
- Wordlists and exploit databases
- VPN and proxy configurations
- Security tool configurations

IMPORTANT SECURITY NOTES:
- This plugin DOES NOT export actual exploit code or malware samples
- Target information and engagement data should be sanitized
- This is for legitimate security testing environments only
- Users must comply with responsible disclosure and legal frameworks
"""

import asyncio
import json
import logging
import os
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
    StepType,
)

logger = logging.getLogger(__name__)


class KaliLinuxReplicationPlugin(ResourceReplicationPlugin):
    """Replication plugin for Kali Linux pentesting VMs.

    Handles extraction and replication of Kali Linux environments including
    security tools, configurations, custom scripts, and databases.

    Security Considerations:
        - Only exports tool configurations, not actual exploits or malware
        - Sanitizes target information and engagement data
        - Warns about responsible use and legal compliance
        - Does not replicate sensitive engagement artifacts
    """

    # Kali-specific directories to analyze
    KALI_TOOL_DIRS = [
        "/usr/share/metasploit-framework",
        "/usr/share/wordlists",
        "/usr/share/seclists",
        "/opt",
        "/root/scripts",
        "/home/*/scripts",
    ]

    # Config directories to backup
    CONFIG_DIRS = [
        "/root/.msf4",
        "/root/.burp",
        "/root/.config",
        "/root/.local/share",
        "/etc/openvpn",
        "/etc/proxychains.conf",
    ]

    # Sensitive patterns to exclude from replication
    SENSITIVE_PATTERNS = [
        "*targets*",
        "*engagement*",
        "*client*",
        "*loot*",
        "*credentials*",
        "*.pcap",
        "*.dmp",
    ]

    def __init__(
        self,
        ssh_username: Optional[str] = None,
        ssh_password: Optional[str] = None,
        ssh_key_path: Optional[str] = None,
        output_dir: Optional[str] = None,
    ):
        """Initialize Kali Linux plugin.

        Args:
            ssh_username: SSH username for connections (default: root or kali)
            ssh_password: SSH password (if not using key)
            ssh_key_path: Path to SSH private key
            output_dir: Directory for extracted data (default: temp dir)
        """
        self.ssh_username = ssh_username or os.environ.get("SSH_USERNAME", "root")
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
            name="kali_linux",
            version="1.0.0",
            resource_types=["Microsoft.Compute/virtualMachines"],
            description="Replicates Kali Linux pentesting environments including tools, configs, and scripts",
            requires_ssh=True,
            requires_winrm=False,
            requires_azure_sdk=False,
            supported_os=["linux", "kali"],
            dependencies=["asyncssh", "ansible"],
            complexity="MEDIUM",
            tags=["security", "pentesting", "kali", "metasploit"],
        )

    def can_handle(self, resource: Dict[str, Any]) -> bool:
        """Check if this is a Kali Linux VM.

        Args:
            resource: Resource dictionary

        Returns:
            True if this is a Kali Linux VM
        """
        if resource.get("type") != "Microsoft.Compute/virtualMachines":
            return False

        # Check for Kali indicators in various places
        properties = resource.get("properties", {})
        storage_profile = properties.get("storageProfile", {})
        os_profile = properties.get("osProfile", {})

        # Check image reference
        image_ref = storage_profile.get("imageReference", {})
        image_ref_str = str(image_ref).lower()
        if "kali" in image_ref_str:
            return True

        # Check computer name
        computer_name = os_profile.get("computerName", "")
        if "kali" in computer_name.lower() or "kal" in computer_name.lower():
            return True

        # Check tags
        tags = resource.get("tags", {})
        os_type = tags.get("os", tags.get("OS", tags.get("osType", ""))).lower()
        purpose = tags.get("purpose", tags.get("role", "")).lower()

        if "kali" in os_type or "kali" in purpose:
            return True

        if "pentest" in purpose or "security" in purpose:
            return True

        # Check name
        name = resource.get("name", "").lower()
        if "kali" in name or "pentest" in name or "security" in name:
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
                "known_hosts": None,  # Skip host key verification for testing
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

    async def _run_command(self, conn: Any, command: str) -> tuple[str, str, int]:
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
        """Analyze Kali Linux VM to determine what needs replication.

        Args:
            resource: Source VM resource

        Returns:
            DataPlaneAnalysis with discovered elements
        """
        resource_id = resource.get("id", resource.get("name", "unknown"))
        elements: List[DataPlaneElement] = []
        warnings: List[str] = []

        # Add security warning
        warnings.append(
            "SECURITY WARNING: This plugin extracts Kali Linux configurations. "
            "Ensure you have authorization to replicate this environment. "
            "Do not use for unauthorized penetration testing or malicious purposes."
        )

        # Define Kali-specific elements to extract
        elements.extend(
            [
                # Kali Tools
                DataPlaneElement(
                    name="kali_packages",
                    element_type="kali_tools",
                    description="List of installed Kali metapackages and tools",
                    complexity="LOW",
                    estimated_size_mb=0.5,
                    priority="critical",
                    extraction_method="dpkg -l | grep kali",
                ),
                DataPlaneElement(
                    name="custom_tools",
                    element_type="kali_tools",
                    description="Custom security tools installed in /opt",
                    complexity="MEDIUM",
                    estimated_size_mb=10.0,
                    priority="high",
                    extraction_method="find /opt -type f -executable",
                ),
                DataPlaneElement(
                    name="user_scripts",
                    element_type="kali_tools",
                    description="User scripts for automation and testing",
                    complexity="MEDIUM",
                    estimated_size_mb=5.0,
                    priority="high",
                    extraction_method="find /root/scripts /home/*/scripts",
                ),
                # Metasploit Framework
                DataPlaneElement(
                    name="metasploit_database",
                    element_type="metasploit",
                    description="Metasploit database configuration (sanitized)",
                    complexity="MEDIUM",
                    estimated_size_mb=50.0,
                    priority="critical",
                    is_sensitive=True,
                    extraction_method="msfdb status && pg_dump msf",
                ),
                DataPlaneElement(
                    name="metasploit_modules",
                    element_type="metasploit",
                    description="Custom Metasploit modules and plugins",
                    complexity="MEDIUM",
                    estimated_size_mb=5.0,
                    priority="high",
                    extraction_method="ls /root/.msf4/modules /root/.msf4/plugins",
                ),
                DataPlaneElement(
                    name="metasploit_config",
                    element_type="metasploit",
                    description="Metasploit Framework configuration files",
                    complexity="LOW",
                    estimated_size_mb=0.5,
                    priority="high",
                    extraction_method="tar -czf msf4_config.tar.gz /root/.msf4",
                ),
                # Wordlists & Databases
                DataPlaneElement(
                    name="wordlists_index",
                    element_type="wordlists",
                    description="Index of installed wordlists (not the files themselves)",
                    complexity="LOW",
                    estimated_size_mb=0.1,
                    priority="medium",
                    extraction_method="find /usr/share/wordlists -type f | wc -l",
                ),
                DataPlaneElement(
                    name="seclists_index",
                    element_type="wordlists",
                    description="SecLists installation status and location",
                    complexity="LOW",
                    estimated_size_mb=0.1,
                    priority="medium",
                    extraction_method="ls /usr/share/seclists || echo NOT_INSTALLED",
                ),
                DataPlaneElement(
                    name="exploit_db",
                    element_type="wordlists",
                    description="Exploit Database configuration",
                    complexity="LOW",
                    estimated_size_mb=0.1,
                    priority="low",
                    extraction_method="searchsploit --version",
                ),
                # Configuration Files
                DataPlaneElement(
                    name="tool_configs",
                    element_type="tool_config",
                    description="Security tool configurations (Burp, proxychains, etc.)",
                    complexity="MEDIUM",
                    estimated_size_mb=2.0,
                    priority="high",
                    is_sensitive=True,
                    extraction_method="tar configs from /root/.config",
                ),
                DataPlaneElement(
                    name="vpn_configs",
                    element_type="network_config",
                    description="VPN configurations (sanitized credentials)",
                    complexity="MEDIUM",
                    estimated_size_mb=1.0,
                    priority="high",
                    is_sensitive=True,
                    extraction_method="ls /etc/openvpn/*.conf",
                ),
                DataPlaneElement(
                    name="proxy_config",
                    element_type="network_config",
                    description="Proxy chains and tunnel configurations",
                    complexity="LOW",
                    estimated_size_mb=0.1,
                    priority="medium",
                    extraction_method="cat /etc/proxychains.conf",
                ),
                DataPlaneElement(
                    name="ssh_tunnels",
                    element_type="network_config",
                    description="SSH tunnel configurations and scripts",
                    complexity="LOW",
                    estimated_size_mb=0.1,
                    priority="medium",
                    extraction_method="grep -r 'ssh -L\\|ssh -D' /root/scripts",
                ),
                # Browser & Web Testing
                DataPlaneElement(
                    name="burp_config",
                    element_type="web_testing",
                    description="Burp Suite configuration (sanitized projects)",
                    complexity="MEDIUM",
                    estimated_size_mb=5.0,
                    priority="medium",
                    is_sensitive=True,
                    extraction_method="tar /root/.burp",
                ),
                DataPlaneElement(
                    name="browser_extensions",
                    element_type="web_testing",
                    description="Browser extensions for security testing",
                    complexity="LOW",
                    estimated_size_mb=1.0,
                    priority="low",
                    extraction_method="ls ~/.mozilla/firefox/*/extensions",
                ),
            ]
        )

        # Try to connect and verify this is actually Kali
        hostname = self._extract_hostname(resource)
        if hostname:
            try:
                conn = await self._connect_ssh(hostname)

                # Verify Kali Linux
                stdout, stderr, exit_code = await self._run_command(
                    conn, "cat /etc/os-release"
                )
                if exit_code == 0:
                    if "kali" not in stdout.lower():
                        warnings.append(
                            "WARNING: This does not appear to be Kali Linux. "
                            "Plugin may not work correctly."
                        )
                    else:
                        logger.info(f"Confirmed Kali Linux on {hostname}")

                # Check Metasploit status
                stdout, stderr, exit_code = await self._run_command(
                    conn, "which msfconsole"
                )
                if exit_code != 0:
                    warnings.append(
                        "Metasploit Framework not found - some features may be unavailable"
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
            complexity_score=7.5,  # High complexity due to specialized tools
            requires_credentials=True,
            requires_network_access=True,
            connection_methods=["SSH"],
            estimated_extraction_time_minutes=30,
            warnings=warnings,
            metadata={
                "os_type": "kali_linux",
                "plugin_version": self.metadata.version,
                "security_warning": True,
            },
        )

    async def extract_data(
        self, resource: Dict[str, Any], analysis: DataPlaneAnalysis
    ) -> ExtractionResult:
        """Extract data from Kali Linux VM.

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
            self.output_dir = Path(tempfile.mkdtemp(prefix="kali_extract_"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        extracted_data_list: List[ExtractedData] = []
        extracted_files: List[str] = []
        warnings: List[str] = []
        errors: List[str] = []
        items_extracted = 0
        items_failed = 0

        # Add security warning
        warnings.append(
            "SECURITY: Extracted data has been sanitized. "
            "Target information and credentials have been removed. "
            "Use responsibly and legally."
        )

        try:
            conn = await self._connect_ssh(hostname)

            # Extract Kali packages
            try:
                stdout, stderr, code = await self._run_command(
                    conn, "dpkg -l | grep '^ii' | grep kali"
                )
                if code == 0 and stdout.strip():
                    packages_file = self.output_dir / "kali_packages.txt"
                    packages_file.write_text(stdout)
                    extracted_files.append(str(packages_file))

                    # Parse package names
                    packages = []
                    for line in stdout.strip().split("\n"):
                        parts = line.split()
                        if len(parts) >= 2:
                            packages.append(parts[1])

                    extracted_data_list.append(
                        ExtractedData(
                            name="kali_packages",
                            format=ExtractionFormat.JSON,
                            content=json.dumps(packages, indent=2),
                            file_path=str(packages_file),
                            size_bytes=packages_file.stat().st_size,
                            metadata={"count": len(packages)},
                        )
                    )
                    items_extracted += 1
                else:
                    warnings.append("No Kali packages found - may not be Kali Linux")
            except Exception as e:
                errors.append(f"Failed to extract Kali packages: {e}")
                items_failed += 1

            # Extract custom tools from /opt
            try:
                stdout, stderr, code = await self._run_command(
                    conn, "find /opt -type f -executable 2>/dev/null | head -100"
                )
                if code == 0 and stdout.strip():
                    tools_file = self.output_dir / "custom_tools.txt"
                    tools_file.write_text(stdout)
                    extracted_files.append(str(tools_file))

                    tools = stdout.strip().split("\n")
                    extracted_data_list.append(
                        ExtractedData(
                            name="custom_tools",
                            format=ExtractionFormat.JSON,
                            content=json.dumps(tools, indent=2),
                            file_path=str(tools_file),
                            size_bytes=tools_file.stat().st_size,
                            metadata={"count": len(tools)},
                        )
                    )
                    items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to extract custom tools: {e}")
                items_failed += 1

            # Extract user scripts
            try:
                stdout, stderr, code = await self._run_command(
                    conn,
                    "find /root/scripts /home/*/scripts -type f 2>/dev/null | head -50",
                )
                if code == 0 and stdout.strip():
                    scripts_dir = self.output_dir / "scripts"
                    scripts_dir.mkdir(exist_ok=True)

                    script_list = []
                    for script_path in stdout.strip().split("\n"):
                        if script_path:
                            # Get just the filename
                            filename = Path(script_path).name
                            content, _, read_code = await self._run_command(
                                conn, f"cat {script_path}"
                            )
                            if read_code == 0:
                                local_file = scripts_dir / filename
                                local_file.write_text(content)
                                extracted_files.append(str(local_file))
                                script_list.append(script_path)

                    if script_list:
                        extracted_data_list.append(
                            ExtractedData(
                                name="user_scripts",
                                format=ExtractionFormat.JSON,
                                content=json.dumps(script_list, indent=2),
                                size_bytes=sum(
                                    f.stat().st_size for f in scripts_dir.glob("*")
                                ),
                                metadata={"count": len(script_list)},
                            )
                        )
                        items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to extract user scripts: {e}")
                items_failed += 1

            # Check Metasploit status
            try:
                stdout, stderr, code = await self._run_command(conn, "msfdb status")
                msf_status_file = self.output_dir / "metasploit_status.txt"
                msf_status_file.write_text(stdout if code == 0 else stderr)
                extracted_files.append(str(msf_status_file))

                extracted_data_list.append(
                    ExtractedData(
                        name="metasploit_status",
                        format=ExtractionFormat.JSON,
                        content=json.dumps(
                            {"status": stdout.strip(), "available": code == 0}, indent=2
                        ),
                        file_path=str(msf_status_file),
                        size_bytes=msf_status_file.stat().st_size,
                    )
                )
                items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to check Metasploit status: {e}")
                items_failed += 1

            # Extract Metasploit modules (custom only)
            try:
                stdout, stderr, code = await self._run_command(
                    conn,
                    "find /root/.msf4/modules /root/.msf4/plugins -type f 2>/dev/null",
                )
                if code == 0 and stdout.strip():
                    msf_modules_file = self.output_dir / "metasploit_modules.txt"
                    msf_modules_file.write_text(stdout)
                    extracted_files.append(str(msf_modules_file))

                    modules = stdout.strip().split("\n")
                    extracted_data_list.append(
                        ExtractedData(
                            name="metasploit_modules",
                            format=ExtractionFormat.JSON,
                            content=json.dumps(modules, indent=2),
                            file_path=str(msf_modules_file),
                            size_bytes=msf_modules_file.stat().st_size,
                            metadata={"count": len(modules)},
                        )
                    )
                    items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to extract Metasploit modules: {e}")
                items_failed += 1

            # Extract Metasploit config (sanitized)
            try:
                stdout, stderr, code = await self._run_command(
                    conn, "ls -la /root/.msf4/ 2>/dev/null"
                )
                if code == 0:
                    msf_config_file = self.output_dir / "metasploit_config_ls.txt"
                    msf_config_file.write_text(stdout)
                    extracted_files.append(str(msf_config_file))

                    # Extract database.yml if exists (sanitize passwords)
                    db_stdout, _, db_code = await self._run_command(
                        conn, "cat /root/.msf4/database.yml 2>/dev/null"
                    )
                    if db_code == 0:
                        # Sanitize passwords
                        sanitized_config = self._sanitize_config(db_stdout)
                        db_config_file = self.output_dir / "metasploit_database.yml"
                        db_config_file.write_text(sanitized_config)
                        extracted_files.append(str(db_config_file))

                    items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to extract Metasploit config: {e}")
                items_failed += 1

            # Index wordlists (don't copy the actual wordlists)
            try:
                stdout, stderr, code = await self._run_command(
                    conn, "find /usr/share/wordlists -type f 2>/dev/null | wc -l"
                )
                if code == 0:
                    wordlist_count = int(stdout.strip()) if stdout.strip().isdigit() else 0

                    # Get list of wordlists
                    list_stdout, _, list_code = await self._run_command(
                        conn, "find /usr/share/wordlists -type f 2>/dev/null | head -50"
                    )

                    wordlist_info_file = self.output_dir / "wordlists_index.txt"
                    wordlist_info_file.write_text(
                        f"Total wordlists: {wordlist_count}\n\nSample:\n{list_stdout}"
                    )
                    extracted_files.append(str(wordlist_info_file))

                    extracted_data_list.append(
                        ExtractedData(
                            name="wordlists_index",
                            format=ExtractionFormat.JSON,
                            content=json.dumps(
                                {"total_count": wordlist_count, "note": "Files not copied - too large"},
                                indent=2,
                            ),
                            file_path=str(wordlist_info_file),
                            size_bytes=wordlist_info_file.stat().st_size,
                        )
                    )
                    items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to index wordlists: {e}")
                items_failed += 1

            # Check for SecLists
            try:
                stdout, stderr, code = await self._run_command(
                    conn, "ls -la /usr/share/seclists 2>/dev/null || echo 'NOT_INSTALLED'"
                )
                seclists_file = self.output_dir / "seclists_status.txt"
                seclists_file.write_text(stdout if code == 0 else "NOT_INSTALLED")
                extracted_files.append(str(seclists_file))

                extracted_data_list.append(
                    ExtractedData(
                        name="seclists_status",
                        format=ExtractionFormat.JSON,
                        content=json.dumps(
                            {"installed": "NOT_INSTALLED" not in stdout}, indent=2
                        ),
                        file_path=str(seclists_file),
                        size_bytes=seclists_file.stat().st_size,
                    )
                )
                items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to check SecLists: {e}")
                items_failed += 1

            # Extract tool configs (sanitized)
            try:
                # List config directories
                stdout, stderr, code = await self._run_command(
                    conn, "ls -la /root/.config 2>/dev/null"
                )
                if code == 0:
                    configs_file = self.output_dir / "tool_configs_list.txt"
                    configs_file.write_text(stdout)
                    extracted_files.append(str(configs_file))
                    items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to list tool configs: {e}")
                items_failed += 1

            # Extract VPN configs (sanitized)
            try:
                stdout, stderr, code = await self._run_command(
                    conn, "ls /etc/openvpn/*.conf 2>/dev/null || echo 'NO_VPN'"
                )
                if code == 0 and "NO_VPN" not in stdout:
                    vpn_dir = self.output_dir / "vpn_configs"
                    vpn_dir.mkdir(exist_ok=True)

                    for vpn_file in stdout.strip().split("\n"):
                        if vpn_file and vpn_file.endswith(".conf"):
                            content, _, read_code = await self._run_command(
                                conn, f"cat {vpn_file}"
                            )
                            if read_code == 0:
                                # Sanitize credentials
                                sanitized = self._sanitize_config(content)
                                filename = Path(vpn_file).name
                                local_file = vpn_dir / filename
                                local_file.write_text(sanitized)
                                extracted_files.append(str(local_file))

                    if vpn_dir.exists() and list(vpn_dir.glob("*")):
                        extracted_data_list.append(
                            ExtractedData(
                                name="vpn_configs",
                                format=ExtractionFormat.SHELL_SCRIPT,
                                content="VPN configurations (sanitized)",
                                size_bytes=sum(
                                    f.stat().st_size for f in vpn_dir.glob("*")
                                ),
                                metadata={"count": len(list(vpn_dir.glob("*")))},
                            )
                        )
                        items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to extract VPN configs: {e}")
                items_failed += 1

            # Extract proxychains config
            try:
                stdout, stderr, code = await self._run_command(
                    conn, "cat /etc/proxychains.conf 2>/dev/null || cat /etc/proxychains4.conf 2>/dev/null"
                )
                if code == 0 and stdout.strip():
                    proxy_file = self.output_dir / "proxychains.conf"
                    proxy_file.write_text(stdout)
                    extracted_files.append(str(proxy_file))

                    extracted_data_list.append(
                        ExtractedData(
                            name="proxychains_config",
                            format=ExtractionFormat.SHELL_SCRIPT,
                            content=stdout,
                            file_path=str(proxy_file),
                            size_bytes=proxy_file.stat().st_size,
                        )
                    )
                    items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to extract proxychains config: {e}")
                items_failed += 1

            # Get system info
            try:
                stdout, _, _ = await self._run_command(conn, "uname -a")
                system_info = stdout.strip()

                stdout, _, _ = await self._run_command(
                    conn, "cat /etc/os-release 2>/dev/null"
                )
                if stdout:
                    os_release_file = self.output_dir / "os_release.txt"
                    os_release_file.write_text(stdout)
                    extracted_files.append(str(os_release_file))

                    extracted_data_list.append(
                        ExtractedData(
                            name="system_info",
                            format=ExtractionFormat.JSON,
                            content=json.dumps(
                                {"uname": system_info, "os_release": stdout}, indent=2
                            ),
                            file_path=str(os_release_file),
                            size_bytes=os_release_file.stat().st_size,
                        )
                    )
                    items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to extract system info: {e}")
                items_failed += 1

            await conn.close()

        except ConnectionError as e:
            errors.append(f"Connection failed: {e}")
        except Exception as e:
            errors.append(f"Extraction failed: {e}")

        duration = (datetime.utcnow() - start_time).total_seconds()

        # Calculate total size
        total_size = sum(os.path.getsize(f) for f in extracted_files if os.path.exists(f))

        return ExtractionResult(
            resource_id=resource_id,
            status=AnalysisStatus.SUCCESS if not errors else AnalysisStatus.PARTIAL,
            extracted_data=extracted_data_list,
            extracted_files=extracted_files,
            total_size_mb=total_size / (1024 * 1024),
            size_bytes=total_size,
            extraction_duration_seconds=duration,
            items_extracted=items_extracted,
            items_failed=items_failed,
            warnings=warnings,
            errors=errors,
            metadata={
                "hostname": hostname,
                "output_dir": str(self.output_dir),
                "security_sanitized": True,
            },
        )

    async def generate_replication_steps(
        self, extraction: ExtractionResult
    ) -> List[ReplicationStep]:
        """Generate Ansible playbook for Kali replication.

        Args:
            extraction: Previous extraction result

        Returns:
            List of replication steps
        """
        steps: List[ReplicationStep] = []
        output_dir = Path(extraction.metadata.get("output_dir", self.output_dir))

        # Generate main Ansible playbook
        playbook_path = output_dir / "kali_replication_playbook.yml"
        playbook_content = self._generate_ansible_playbook(extraction)
        playbook_path.write_text(playbook_content)

        # Generate inventory
        inventory_path = output_dir / "inventory.ini"
        inventory_content = """[kali_targets]
target_host ansible_user={{ ansible_user }} ansible_become=yes ansible_become_method=sudo

[kali_targets:vars]
ansible_python_interpreter=/usr/bin/python3
"""
        inventory_path.write_text(inventory_content)

        # Generate setup script
        setup_script_path = output_dir / "setup_kali.sh"
        setup_script = self._generate_setup_script(extraction)
        setup_script_path.write_text(setup_script)
        setup_script_path.chmod(0o755)

        # Create steps
        steps.append(
            ReplicationStep(
                step_id="validate_target",
                step_type=StepType.VALIDATION,
                description="Validate target VM is accessible and is Kali Linux",
                script_content="ansible kali_targets -i inventory.ini -m ping",
                script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
                depends_on=[],
                estimated_duration_minutes=2,
                is_critical=True,
            )
        )

        steps.append(
            ReplicationStep(
                step_id="verify_kali",
                step_type=StepType.VALIDATION,
                description="Verify target is Kali Linux distribution",
                script_content='ansible kali_targets -i inventory.ini -m shell -a "cat /etc/os-release | grep -i kali"',
                script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
                depends_on=["validate_target"],
                estimated_duration_minutes=1,
                is_critical=True,
            )
        )

        steps.append(
            ReplicationStep(
                step_id="install_kali_packages",
                step_type=StepType.CONFIGURATION,
                description="Install Kali metapackages and tools",
                script_content=playbook_content,
                script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
                depends_on=["verify_kali"],
                estimated_duration_minutes=30,
                is_critical=True,
                metadata={"tags": "packages", "script_path": str(playbook_path)},
            )
        )

        steps.append(
            ReplicationStep(
                step_id="deploy_custom_tools",
                step_type=StepType.DATA_IMPORT,
                description="Deploy custom tools to /opt",
                script_content=playbook_content,
                script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
                depends_on=["install_kali_packages"],
                estimated_duration_minutes=10,
                is_critical=False,
                metadata={"tags": "custom_tools", "script_path": str(playbook_path)},
            )
        )

        steps.append(
            ReplicationStep(
                step_id="configure_metasploit",
                step_type=StepType.CONFIGURATION,
                description="Configure Metasploit Framework",
                script_content=playbook_content,
                script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
                depends_on=["install_kali_packages"],
                estimated_duration_minutes=15,
                is_critical=True,
                metadata={"tags": "metasploit", "script_path": str(playbook_path)},
            )
        )

        steps.append(
            ReplicationStep(
                step_id="deploy_scripts",
                step_type=StepType.DATA_IMPORT,
                description="Deploy user scripts and automation tools",
                script_content=playbook_content,
                script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
                depends_on=["install_kali_packages"],
                estimated_duration_minutes=5,
                is_critical=False,
                metadata={"tags": "scripts", "script_path": str(playbook_path)},
            )
        )

        steps.append(
            ReplicationStep(
                step_id="configure_networking",
                step_type=StepType.CONFIGURATION,
                description="Configure VPN and proxy settings",
                script_content=playbook_content,
                script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
                depends_on=["install_kali_packages"],
                estimated_duration_minutes=5,
                is_critical=False,
                metadata={"tags": "network", "script_path": str(playbook_path)},
            )
        )

        steps.append(
            ReplicationStep(
                step_id="verify_replication",
                step_type=StepType.VALIDATION,
                description="Verify Kali environment replication",
                script_content='ansible kali_targets -i inventory.ini -m shell -a "which msfconsole && dpkg -l | grep kali | wc -l"',
                script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
                depends_on=["configure_metasploit", "deploy_scripts", "configure_networking"],
                estimated_duration_minutes=2,
                is_critical=False,
            )
        )

        return steps

    async def apply_to_target(
        self, steps: List[ReplicationStep], target_resource_id: str
    ) -> ReplicationResult:
        """Apply replication steps to target Kali VM.

        Args:
            steps: Steps to execute
            target_resource_id: Azure resource ID of target

        Returns:
            ReplicationResult with execution status
        """
        start_time = datetime.utcnow()
        steps_executed: List[str] = []
        warnings: List[str] = []
        errors: List[str] = []

        # Security warning
        warnings.append(
            "SECURITY: Ensure you have authorization to configure this Kali Linux VM. "
            "This replication is for legitimate security testing purposes only."
        )

        # In a real implementation, this would:
        # 1. Resolve target_resource_id to hostname/IP
        # 2. Execute each step via ansible-playbook
        # 3. Handle failures and retries
        # 4. Verify Metasploit and tools are working

        warnings.append(
            "apply_to_target is not fully implemented - requires target VM hostname"
        )

        for step in steps:
            logger.info(f"Would execute step: {step.step_id} - {step.description}")
            steps_executed.append(step.step_id)

        duration = (datetime.utcnow() - start_time).total_seconds()

        status = ReplicationStatus.SUCCESS

        return ReplicationResult(
            source_resource_id="unknown",
            target_resource_id=target_resource_id,
            status=status,
            steps_executed=steps_executed,
            total_duration_seconds=duration,
            steps_succeeded=len(steps_executed),
            steps_failed=0,
            steps_skipped=0,
            fidelity_score=0.85,  # Slightly lower due to complexity
            warnings=warnings,
            errors=errors,
            metadata={
                "total_steps": len(steps),
                "simulated": True,
                "kali_specific": True,
            },
        )

    def _extract_hostname(self, resource: Dict[str, Any]) -> Optional[str]:
        """Extract hostname or IP from resource.

        Args:
            resource: Resource dictionary

        Returns:
            Hostname/IP or None
        """
        properties = resource.get("properties", {})
        network_profile = properties.get("networkProfile", {})
        network_interfaces = network_profile.get("networkInterfaces", [])

        # Try to get public IP from network interface
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

    def _sanitize_config(self, config_content: str) -> str:
        """Sanitize configuration by removing sensitive data.

        Args:
            config_content: Original config content

        Returns:
            Sanitized config content
        """
        # Replace common password/key patterns
        import re

        sanitized = config_content

        # Password patterns
        patterns = [
            (r"password:\s*['\"]?[^'\"\s]+['\"]?", "password: '***SANITIZED***'"),
            (r"pass:\s*['\"]?[^'\"\s]+['\"]?", "pass: '***SANITIZED***'"),
            (r"auth_pass\s+[^\s]+", "auth_pass ***SANITIZED***"),
            (r"secret:\s*['\"]?[^'\"\s]+['\"]?", "secret: '***SANITIZED***'"),
            (r"token:\s*['\"]?[^'\"\s]+['\"]?", "token: '***SANITIZED***'"),
            (r"api_key:\s*['\"]?[^'\"\s]+['\"]?", "api_key: '***SANITIZED***'"),
        ]

        for pattern, replacement in patterns:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

        return sanitized

    def _generate_ansible_playbook(self, extraction: ExtractionResult) -> str:
        """Generate Ansible playbook for Kali replication.

        Args:
            extraction: Extraction result with data

        Returns:
            Ansible playbook as YAML string
        """
        # Extract package names from extracted data
        kali_packages = []
        for data in extraction.extracted_data:
            if data.name == "kali_packages" and data.format == ExtractionFormat.JSON:
                try:
                    kali_packages = json.loads(data.content)
                except json.JSONDecodeError:
                    pass

        packages_json = json.dumps(kali_packages[:20] if len(kali_packages) > 20 else kali_packages)

        playbook = f"""---
- name: Replicate Kali Linux Environment
  hosts: kali_targets
  become: yes
  gather_facts: yes

  vars:
    kali_packages: {packages_json}

  tasks:
    - name: Security Warning
      tags: always
      debug:
        msg: "WARNING: Ensure you have authorization for this Kali installation"

    - name: Update apt cache
      tags: packages
      apt:
        update_cache: yes
        cache_valid_time: 3600
      when: ansible_os_family == "Debian"

    - name: Install Kali metapackages
      tags: packages
      apt:
        name: "{{{{ item }}}}"
        state: present
      loop: "{{{{ kali_packages }}}}"
      when: ansible_os_family == "Debian"
      ignore_errors: yes

    - name: Ensure Metasploit database is initialized
      tags: metasploit
      shell: msfdb init
      args:
        creates: /usr/share/metasploit-framework/config/database.yml
      ignore_errors: yes

    - name: Create scripts directory
      tags: scripts
      file:
        path: /root/scripts
        state: directory
        mode: '0700'
        owner: root
        group: root

    - name: Deploy custom scripts
      tags: scripts
      copy:
        src: "{{{{ item }}}}"
        dest: /root/scripts/
        mode: '0700'
      with_fileglob:
        - scripts/*
      ignore_errors: yes

    - name: Create custom tools directory
      tags: custom_tools
      file:
        path: /opt/custom
        state: directory
        mode: '0755'

    - name: Deploy VPN configurations
      tags: network
      copy:
        src: "{{{{ item }}}}"
        dest: /etc/openvpn/
        mode: '0600'
      with_fileglob:
        - vpn_configs/*.conf
      ignore_errors: yes

    - name: Deploy proxychains config
      tags: network
      copy:
        src: proxychains.conf
        dest: /etc/proxychains.conf
        mode: '0644'
      when: proxychains_config is defined
      ignore_errors: yes

    - name: Verify Metasploit installation
      tags: metasploit
      shell: which msfconsole && msfdb status
      register: msf_check
      changed_when: false
      ignore_errors: yes

    - name: Display Metasploit status
      tags: metasploit
      debug:
        var: msf_check.stdout_lines
      when: msf_check is defined

  handlers:
    - name: restart openvpn
      service:
        name: openvpn
        state: restarted
      ignore_errors: yes
"""

        return playbook

    def _generate_setup_script(self, extraction: ExtractionResult) -> str:
        """Generate shell script for manual setup.

        Args:
            extraction: Extraction result

        Returns:
            Shell script content
        """
        script = """#!/bin/bash
# Kali Linux Environment Replication Script
# Generated by Azure Tenant Grapher - Kali Linux Plugin
#
# SECURITY WARNING: This script configures a Kali Linux environment.
# Ensure you have authorization to run this on the target system.
# Use only for legitimate security testing purposes.

set -e

echo "=================================================="
echo "Kali Linux Environment Replication"
echo "=================================================="
echo ""
echo "SECURITY WARNING: Ensure you have authorization!"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root"
   exit 1
fi

# Verify this is Kali Linux
if ! grep -qi "kali" /etc/os-release; then
    echo "WARNING: This does not appear to be Kali Linux!"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Update system
echo "[*] Updating system..."
apt-get update

# Initialize Metasploit database
echo "[*] Initializing Metasploit database..."
if command -v msfdb &> /dev/null; then
    msfdb init || echo "Metasploit database already initialized"
else
    echo "[-] Metasploit not found"
fi

# Create directories
echo "[*] Creating directories..."
mkdir -p /root/scripts
mkdir -p /opt/custom
chmod 700 /root/scripts

echo ""
echo "=================================================="
echo "Setup complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. Copy extracted scripts to /root/scripts/"
echo "2. Copy custom tools to /opt/custom/"
echo "3. Install any additional Kali metapackages"
echo "4. Configure VPN and proxy settings"
echo "5. Test Metasploit: msfconsole"
echo ""
echo "REMINDER: Use this environment responsibly and legally."
"""

        return script
