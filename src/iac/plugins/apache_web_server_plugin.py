"""Apache Web Server replication plugin.

Handles data-plane replication for Apache HTTP Server including:
- Apache configuration files (httpd.conf, apache2.conf)
- Virtual host configurations
- SSL/TLS certificates and keys
- Module configurations
- Web content structure
- Access control (.htaccess, .htpasswd)
- Log configurations
"""

import asyncio
import hashlib
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


class ApacheWebServerReplicationPlugin(ResourceReplicationPlugin):
    """Replication plugin for Apache HTTP Server.

    Supports both httpd (RHEL/CentOS) and apache2 (Debian/Ubuntu) variants.
    Extracts configurations, SSL certificates, virtual hosts, and web content metadata.
    """

    def __init__(
        self,
        ssh_username: Optional[str] = None,
        ssh_password: Optional[str] = None,
        ssh_key_path: Optional[str] = None,
        output_dir: Optional[str] = None,
    ):
        """Initialize Apache Web Server plugin.

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
            name="apache_web_server",
            version="1.0.0",
            resource_types=["Microsoft.Compute/virtualMachines"],
            description="Replicates Apache HTTP Server configurations, virtual hosts, SSL certs, and web content",
            author="Azure Tenant Grapher",
            supported_formats=[
                ExtractionFormat.ANSIBLE_PLAYBOOK,
                ExtractionFormat.SHELL_SCRIPT,
                ExtractionFormat.JSON,
            ],
            requires_credentials=True,
            requires_network_access=True,
            complexity="MEDIUM",
            estimated_effort_weeks=1.5,
            tags=["web_server", "apache", "httpd", "ssl", "virtual_hosts"],
            supported_os=["linux"],
            dependencies=["asyncssh", "ansible"],
        )

    def can_handle(self, resource: Dict[str, Any]) -> bool:
        """Check if this is a VM with Apache installed.

        Args:
            resource: Resource dictionary

        Returns:
            True if this is a Linux VM potentially running Apache
        """
        if resource.get("type") != "Microsoft.Compute/virtualMachines":
            return False

        # Check if it's a Linux VM
        properties = resource.get("properties", {})
        storage_profile = properties.get("storageProfile", {})
        os_profile = properties.get("osProfile", {})

        # Check for Linux in storage profile
        image_ref = storage_profile.get("imageReference", {})
        image_ref_str = str(image_ref).lower()
        linux_indicators = ["linux", "ubuntu", "debian", "centos", "rhel", "redhat"]

        is_linux = any(indicator in image_ref_str for indicator in linux_indicators)
        if not is_linux:
            return False

        # Check for Apache-specific indicators in VM name or tags
        vm_name = resource.get("name", "").lower()
        tags = resource.get("tags", {})

        # Check for Apache/web server indicators
        apache_indicators = ["apache", "httpd", "web", "www"]
        for indicator in apache_indicators:
            if indicator in vm_name:
                return True
            for tag_value in tags.values():
                if indicator in str(tag_value).lower():
                    return True

        # Check computer name for Apache patterns
        computer_name = os_profile.get("computerName", "").lower()
        for indicator in apache_indicators:
            if indicator in computer_name:
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
            # Build connection parameters
            connect_kwargs = {
                "host": hostname,
                "username": self.ssh_username,
                "known_hosts": None,  # Skip host key verification for demo
            }

            if self.ssh_key_path:
                connect_kwargs["client_keys"] = [self.ssh_key_path]
            elif self.ssh_password:
                connect_kwargs["password"] = self.ssh_password
            else:
                raise ConnectionError("No SSH authentication method provided")

            conn = await asyncio.wait_for(asyncssh.connect(**connect_kwargs), timeout=30.0)
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

    async def _detect_apache_variant(self, conn: Any) -> Optional[str]:
        """Detect which Apache variant is installed.

        Args:
            conn: SSH connection

        Returns:
            'httpd', 'apache2', or None
        """
        # Try httpd first (RHEL/CentOS)
        stdout, _, code = await self._run_command(conn, "which httpd 2>/dev/null || echo ''")
        if code == 0 and stdout.strip():
            return "httpd"

        # Try apache2 (Debian/Ubuntu)
        stdout, _, code = await self._run_command(conn, "which apache2 2>/dev/null || echo ''")
        if code == 0 and stdout.strip():
            return "apache2"

        # Try systemctl status
        stdout, _, code = await self._run_command(
            conn, "systemctl status httpd 2>/dev/null || echo ''"
        )
        if code == 0 or "httpd" in stdout:
            return "httpd"

        stdout, _, code = await self._run_command(
            conn, "systemctl status apache2 2>/dev/null || echo ''"
        )
        if code == 0 or "apache2" in stdout:
            return "apache2"

        return None

    async def _get_apache_config_paths(self, variant: str) -> Dict[str, str]:
        """Get Apache configuration paths for the variant.

        Args:
            variant: 'httpd' or 'apache2'

        Returns:
            Dictionary of config paths
        """
        if variant == "httpd":
            return {
                "main_config": "/etc/httpd/conf/httpd.conf",
                "conf_dir": "/etc/httpd/conf.d",
                "ssl_dir": "/etc/pki/tls",
                "log_dir": "/var/log/httpd",
                "web_root": "/var/www/html",
                "modules_dir": "/etc/httpd/modules",
            }
        else:  # apache2
            return {
                "main_config": "/etc/apache2/apache2.conf",
                "conf_dir": "/etc/apache2/conf-available",
                "conf_enabled": "/etc/apache2/conf-enabled",
                "sites_available": "/etc/apache2/sites-available",
                "sites_enabled": "/etc/apache2/sites-enabled",
                "mods_available": "/etc/apache2/mods-available",
                "mods_enabled": "/etc/apache2/mods-enabled",
                "ssl_dir": "/etc/ssl",
                "log_dir": "/var/log/apache2",
                "web_root": "/var/www/html",
                "ports_config": "/etc/apache2/ports.conf",
            }

    async def analyze_source(self, resource: Dict[str, Any]) -> DataPlaneAnalysis:
        """Analyze Apache server to determine what needs replication.

        Args:
            resource: Source VM resource

        Returns:
            DataPlaneAnalysis with discovered elements
        """
        resource_id = resource.get("id", resource.get("name", "unknown"))
        elements: List[DataPlaneElement] = []
        warnings: List[str] = []
        errors: List[str] = []
        metadata: Dict[str, Any] = {}

        hostname = self._extract_hostname(resource)
        if not hostname:
            warnings.append("No hostname/IP found - analysis limited to static configuration")
            # Return static analysis
            elements.extend(self._get_static_elements())
            return DataPlaneAnalysis(
                resource_id=resource_id,
                resource_type=resource.get("type", "Microsoft.Compute/virtualMachines"),
                elements=elements,
                status=AnalysisStatus.PARTIAL,
                complexity_score=7.0,
                requires_credentials=True,
                connection_methods=["SSH"],
                estimated_extraction_time_minutes=15,
                warnings=warnings,
                metadata={"plugin_version": self.metadata.version},
            )

        # Connect and analyze
        try:
            conn = await self._connect_ssh(hostname)

            # Detect Apache variant
            variant = await self._detect_apache_variant(conn)
            if not variant:
                errors.append("Apache HTTP Server not detected on this VM")
                await conn.close()
                return DataPlaneAnalysis(
                    resource_id=resource_id,
                    resource_type=resource.get("type", "Microsoft.Compute/virtualMachines"),
                    elements=[],
                    status=AnalysisStatus.NOT_APPLICABLE,
                    complexity_score=0.0,
                    warnings=warnings,
                    errors=errors,
                )

            metadata["apache_variant"] = variant
            config_paths = await self._get_apache_config_paths(variant)
            metadata["config_paths"] = config_paths

            # Get Apache version
            version_cmd = f"{variant} -v" if variant == "httpd" else "apache2 -v"
            stdout, _, code = await self._run_command(conn, version_cmd)
            if code == 0:
                metadata["apache_version"] = stdout.split("\n")[0] if stdout else "unknown"

            # Check if configs exist
            main_config_exists = False
            stdout, _, code = await self._run_command(
                conn, f"test -f {config_paths['main_config']} && echo 'EXISTS' || echo 'MISSING'"
            )
            if "EXISTS" in stdout:
                main_config_exists = True
                elements.append(
                    DataPlaneElement(
                        name="main_config",
                        element_type="configuration",
                        description=f"Main Apache configuration ({config_paths['main_config']})",
                        complexity="MEDIUM",
                        estimated_size_mb=0.01,
                        dependencies=[],
                    )
                )

            # Check for virtual hosts
            if variant == "apache2":
                stdout, _, code = await self._run_command(
                    conn, f"ls {config_paths['sites_available']} 2>/dev/null | wc -l"
                )
                vhost_count = int(stdout.strip()) if code == 0 and stdout.strip().isdigit() else 0
                if vhost_count > 0:
                    metadata["vhost_count"] = vhost_count
                    elements.append(
                        DataPlaneElement(
                            name="virtual_hosts",
                            element_type="configuration",
                            description=f"Virtual host configurations ({vhost_count} files)",
                            complexity="MEDIUM",
                            estimated_size_mb=0.05 * vhost_count,
                            dependencies=["main_config"],
                        )
                    )
            else:  # httpd
                stdout, _, code = await self._run_command(
                    conn, f"ls {config_paths['conf_dir']}/*.conf 2>/dev/null | wc -l"
                )
                conf_count = int(stdout.strip()) if code == 0 and stdout.strip().isdigit() else 0
                if conf_count > 0:
                    metadata["conf_count"] = conf_count
                    elements.append(
                        DataPlaneElement(
                            name="conf_d_configs",
                            element_type="configuration",
                            description=f"Configuration files in conf.d ({conf_count} files)",
                            complexity="MEDIUM",
                            estimated_size_mb=0.02 * conf_count,
                            dependencies=["main_config"],
                        )
                    )

            # Check for SSL certificates
            if variant == "apache2":
                stdout, _, code = await self._run_command(
                    conn,
                    f"find {config_paths['ssl_dir']}/certs -name '*.crt' -o -name '*.pem' 2>/dev/null | wc -l",
                )
            else:
                stdout, _, code = await self._run_command(
                    conn,
                    f"find {config_paths['ssl_dir']}/certs -name '*.crt' -o -name '*.pem' 2>/dev/null | wc -l",
                )

            cert_count = int(stdout.strip()) if code == 0 and stdout.strip().isdigit() else 0
            if cert_count > 0:
                metadata["ssl_cert_count"] = cert_count
                elements.append(
                    DataPlaneElement(
                        name="ssl_certificates",
                        element_type="security",
                        description=f"SSL/TLS certificates ({cert_count} files)",
                        complexity="MEDIUM",
                        estimated_size_mb=0.01 * cert_count,
                        is_sensitive=True,
                        dependencies=[],
                    )
                )

            # Check for private keys
            if variant == "apache2":
                stdout, _, code = await self._run_command(
                    conn,
                    f"sudo find {config_paths['ssl_dir']}/private -name '*.key' 2>/dev/null | wc -l",
                )
            else:
                stdout, _, code = await self._run_command(
                    conn,
                    f"sudo find {config_paths['ssl_dir']}/private -name '*.key' 2>/dev/null | wc -l",
                )

            key_count = int(stdout.strip()) if code == 0 and stdout.strip().isdigit() else 0
            if key_count > 0:
                metadata["ssl_key_count"] = key_count
                elements.append(
                    DataPlaneElement(
                        name="ssl_private_keys",
                        element_type="security",
                        description=f"SSL/TLS private keys ({key_count} files)",
                        complexity="HIGH",
                        estimated_size_mb=0.005 * key_count,
                        is_sensitive=True,
                        dependencies=[],
                    )
                )
                warnings.append(
                    "SSL private keys detected - ensure secure transfer and consider certificate renewal"
                )

            # Check for enabled modules
            if variant == "apache2":
                stdout, _, code = await self._run_command(
                    conn, f"ls {config_paths['mods_enabled']} 2>/dev/null | wc -l"
                )
                mod_count = int(stdout.strip()) if code == 0 and stdout.strip().isdigit() else 0
                if mod_count > 0:
                    metadata["enabled_modules_count"] = mod_count
                    elements.append(
                        DataPlaneElement(
                            name="enabled_modules",
                            element_type="configuration",
                            description=f"Enabled Apache modules ({mod_count} modules)",
                            complexity="LOW",
                            estimated_size_mb=0.01,
                            dependencies=[],
                        )
                    )

            # Check web content
            stdout, _, code = await self._run_command(
                conn, f"du -sm {config_paths['web_root']} 2>/dev/null | cut -f1"
            )
            if code == 0 and stdout.strip().isdigit():
                web_content_mb = int(stdout.strip())
                metadata["web_content_size_mb"] = web_content_mb
                elements.append(
                    DataPlaneElement(
                        name="web_content",
                        element_type="application_data",
                        description=f"Web content in {config_paths['web_root']} ({web_content_mb} MB)",
                        complexity="MEDIUM",
                        estimated_size_mb=web_content_mb,
                        dependencies=[],
                    )
                )
                if web_content_mb > 1000:
                    warnings.append(
                        f"Large web content detected ({web_content_mb} MB) - consider selective extraction"
                    )

            # Check for .htaccess files
            stdout, _, code = await self._run_command(
                conn,
                f"find {config_paths['web_root']} -name '.htaccess' 2>/dev/null | wc -l",
            )
            htaccess_count = int(stdout.strip()) if code == 0 and stdout.strip().isdigit() else 0
            if htaccess_count > 0:
                metadata["htaccess_count"] = htaccess_count
                elements.append(
                    DataPlaneElement(
                        name="htaccess_files",
                        element_type="configuration",
                        description=f".htaccess access control files ({htaccess_count} files)",
                        complexity="LOW",
                        estimated_size_mb=0.001 * htaccess_count,
                        dependencies=["web_content"],
                    )
                )

            # Check for .htpasswd files
            stdout, _, code = await self._run_command(
                conn, f"find {config_paths['web_root']} -name '.htpasswd' 2>/dev/null | wc -l"
            )
            htpasswd_count = int(stdout.strip()) if code == 0 and stdout.strip().isdigit() else 0
            if htpasswd_count > 0:
                metadata["htpasswd_count"] = htpasswd_count
                elements.append(
                    DataPlaneElement(
                        name="htpasswd_files",
                        element_type="security",
                        description=f".htpasswd authentication files ({htpasswd_count} files)",
                        complexity="LOW",
                        estimated_size_mb=0.001 * htpasswd_count,
                        is_sensitive=True,
                        dependencies=["web_content"],
                    )
                )
                warnings.append(
                    ".htpasswd files will be sanitized - hashes preserved, passwords not recoverable"
                )

            # Check log configuration
            if main_config_exists:
                elements.append(
                    DataPlaneElement(
                        name="log_configuration",
                        element_type="configuration",
                        description="Apache logging configuration (CustomLog, ErrorLog)",
                        complexity="LOW",
                        estimated_size_mb=0.001,
                        dependencies=["main_config"],
                    )
                )

            await conn.close()

        except ConnectionError as e:
            errors.append(f"Connection failed: {e}")
            elements.extend(self._get_static_elements())
            return DataPlaneAnalysis(
                resource_id=resource_id,
                resource_type=resource.get("type", "Microsoft.Compute/virtualMachines"),
                elements=elements,
                status=AnalysisStatus.PARTIAL,
                complexity_score=7.0,
                requires_credentials=True,
                warnings=warnings,
                errors=errors,
                metadata=metadata,
            )

        # Calculate complexity
        complexity_score = self._calculate_complexity(elements, metadata)

        return DataPlaneAnalysis(
            resource_id=resource_id,
            resource_type=resource.get("type", "Microsoft.Compute/virtualMachines"),
            elements=elements,
            status=AnalysisStatus.SUCCESS,
            total_estimated_size_mb=sum(e.estimated_size_mb for e in elements),
            complexity_score=complexity_score,
            requires_credentials=True,
            requires_network_access=True,
            connection_methods=["SSH"],
            estimated_extraction_time_minutes=max(10, int(len(elements) * 2)),
            warnings=warnings,
            errors=errors,
            metadata=metadata,
        )

    def _get_static_elements(self) -> List[DataPlaneElement]:
        """Get static list of elements when connection is unavailable.

        Returns:
            List of typical Apache elements
        """
        return [
            DataPlaneElement(
                name="main_config",
                element_type="configuration",
                description="Main Apache configuration file",
                complexity="MEDIUM",
                estimated_size_mb=0.01,
            ),
            DataPlaneElement(
                name="virtual_hosts",
                element_type="configuration",
                description="Virtual host configurations",
                complexity="MEDIUM",
                estimated_size_mb=0.1,
            ),
            DataPlaneElement(
                name="ssl_certificates",
                element_type="security",
                description="SSL/TLS certificates",
                complexity="MEDIUM",
                estimated_size_mb=0.05,
                is_sensitive=True,
            ),
            DataPlaneElement(
                name="enabled_modules",
                element_type="configuration",
                description="Enabled Apache modules",
                complexity="LOW",
                estimated_size_mb=0.01,
            ),
            DataPlaneElement(
                name="web_content",
                element_type="application_data",
                description="Web content and applications",
                complexity="MEDIUM",
                estimated_size_mb=100.0,
            ),
        ]

    def _calculate_complexity(
        self, elements: List[DataPlaneElement], metadata: Dict[str, Any]
    ) -> float:
        """Calculate complexity score based on elements.

        Args:
            elements: List of discovered elements
            metadata: Analysis metadata

        Returns:
            Complexity score (1.0-10.0)
        """
        base_score = 5.0

        # Add for virtual hosts
        vhost_count = metadata.get("vhost_count", 0)
        base_score += min(vhost_count * 0.5, 2.0)

        # Add for SSL
        if metadata.get("ssl_cert_count", 0) > 0:
            base_score += 1.0

        # Add for large web content
        web_size = metadata.get("web_content_size_mb", 0)
        if web_size > 100:
            base_score += 1.0
        if web_size > 1000:
            base_score += 1.0

        # Add for complex access control
        if metadata.get("htaccess_count", 0) > 5:
            base_score += 0.5

        return min(base_score, 10.0)

    async def extract_data(
        self, resource: Dict[str, Any], analysis: DataPlaneAnalysis
    ) -> ExtractionResult:
        """Extract data from Apache server.

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
            self.output_dir = Path(tempfile.mkdtemp(prefix="apache_extract_"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        extracted_data: List[ExtractedData] = []
        warnings: List[str] = []
        errors: List[str] = []
        items_extracted = 0
        items_failed = 0

        variant = analysis.metadata.get("apache_variant")
        if not variant:
            raise ValueError("Apache variant not determined in analysis")

        config_paths = await self._get_apache_config_paths(variant)

        try:
            conn = await self._connect_ssh(hostname)

            # Extract main configuration
            try:
                stdout, _, code = await self._run_command(
                    conn, f"cat {config_paths['main_config']}"
                )
                if code == 0:
                    config_file = self.output_dir / f"{variant}.conf"
                    config_file.write_text(stdout)
                    extracted_data.append(
                        ExtractedData(
                            name="main_config",
                            format=ExtractionFormat.SHELL_SCRIPT,
                            content=stdout,
                            file_path=str(config_file),
                            size_bytes=len(stdout.encode()),
                            checksum=hashlib.sha256(stdout.encode()).hexdigest(),
                        )
                    )
                    items_extracted += 1
            except Exception as e:
                errors.append(f"Failed to extract main config: {e}")
                items_failed += 1

            # Extract virtual hosts or conf.d configs
            if variant == "apache2":
                # Extract sites-available
                sites_dir = self.output_dir / "sites-available"
                sites_dir.mkdir(exist_ok=True)
                try:
                    stdout, _, code = await self._run_command(
                        conn, f"ls {config_paths['sites_available']} 2>/dev/null"
                    )
                    if code == 0 and stdout.strip():
                        for site_file in stdout.strip().split("\n"):
                            if site_file:
                                content, _, code = await self._run_command(
                                    conn, f"cat {config_paths['sites_available']}/{site_file}"
                                )
                                if code == 0:
                                    local_file = sites_dir / site_file
                                    local_file.write_text(content)
                                    extracted_data.append(
                                        ExtractedData(
                                            name=f"vhost_{site_file}",
                                            format=ExtractionFormat.SHELL_SCRIPT,
                                            content=content,
                                            file_path=str(local_file),
                                            size_bytes=len(content.encode()),
                                        )
                                    )
                                    items_extracted += 1
                except Exception as e:
                    warnings.append(f"Failed to extract virtual hosts: {e}")

                # Extract enabled sites symlinks
                try:
                    stdout, _, code = await self._run_command(
                        conn, f"ls -la {config_paths['sites_enabled']} 2>/dev/null"
                    )
                    if code == 0:
                        enabled_file = self.output_dir / "sites-enabled.txt"
                        enabled_file.write_text(stdout)
                        extracted_data.append(
                            ExtractedData(
                                name="sites_enabled",
                                format=ExtractionFormat.SHELL_SCRIPT,
                                content=stdout,
                                file_path=str(enabled_file),
                                size_bytes=len(stdout.encode()),
                            )
                        )
                        items_extracted += 1
                except Exception as e:
                    warnings.append(f"Failed to list enabled sites: {e}")

                # Extract ports.conf
                try:
                    stdout, _, code = await self._run_command(
                        conn, f"cat {config_paths['ports_config']} 2>/dev/null || echo ''"
                    )
                    if code == 0 and stdout.strip():
                        ports_file = self.output_dir / "ports.conf"
                        ports_file.write_text(stdout)
                        extracted_data.append(
                            ExtractedData(
                                name="ports_config",
                                format=ExtractionFormat.SHELL_SCRIPT,
                                content=stdout,
                                file_path=str(ports_file),
                                size_bytes=len(stdout.encode()),
                            )
                        )
                        items_extracted += 1
                except Exception as e:
                    warnings.append(f"Failed to extract ports.conf: {e}")

                # Extract enabled modules
                mods_dir = self.output_dir / "mods-enabled"
                mods_dir.mkdir(exist_ok=True)
                try:
                    stdout, _, code = await self._run_command(
                        conn, f"ls {config_paths['mods_enabled']} 2>/dev/null"
                    )
                    if code == 0 and stdout.strip():
                        mods_list_file = mods_dir / "modules_list.txt"
                        mods_list_file.write_text(stdout)
                        extracted_data.append(
                            ExtractedData(
                                name="enabled_modules_list",
                                format=ExtractionFormat.SHELL_SCRIPT,
                                content=stdout,
                                file_path=str(mods_list_file),
                                size_bytes=len(stdout.encode()),
                            )
                        )
                        items_extracted += 1
                except Exception as e:
                    warnings.append(f"Failed to list enabled modules: {e}")

            else:  # httpd variant
                # Extract conf.d configs
                conf_d_dir = self.output_dir / "conf.d"
                conf_d_dir.mkdir(exist_ok=True)
                try:
                    stdout, _, code = await self._run_command(
                        conn, f"ls {config_paths['conf_dir']}/*.conf 2>/dev/null"
                    )
                    if code == 0 and stdout.strip():
                        for conf_file in stdout.strip().split("\n"):
                            if conf_file:
                                basename = os.path.basename(conf_file)
                                content, _, code = await self._run_command(conn, f"cat {conf_file}")
                                if code == 0:
                                    local_file = conf_d_dir / basename
                                    local_file.write_text(content)
                                    extracted_data.append(
                                        ExtractedData(
                                            name=f"conf_d_{basename}",
                                            format=ExtractionFormat.SHELL_SCRIPT,
                                            content=content,
                                            file_path=str(local_file),
                                            size_bytes=len(content.encode()),
                                        )
                                    )
                                    items_extracted += 1
                except Exception as e:
                    warnings.append(f"Failed to extract conf.d configs: {e}")

            # Extract SSL certificates
            ssl_dir = self.output_dir / "ssl_certs"
            ssl_dir.mkdir(exist_ok=True)
            try:
                if variant == "apache2":
                    cert_search_path = f"{config_paths['ssl_dir']}/certs"
                else:
                    cert_search_path = f"{config_paths['ssl_dir']}/certs"

                stdout, _, code = await self._run_command(
                    conn,
                    f"find {cert_search_path} -name '*.crt' -o -name '*.pem' 2>/dev/null",
                )
                if code == 0 and stdout.strip():
                    for cert_path in stdout.strip().split("\n"):
                        if cert_path:
                            basename = os.path.basename(cert_path)
                            content, _, code = await self._run_command(conn, f"cat {cert_path}")
                            if code == 0:
                                local_file = ssl_dir / basename
                                local_file.write_text(content)
                                extracted_data.append(
                                    ExtractedData(
                                        name=f"ssl_cert_{basename}",
                                        format=ExtractionFormat.BINARY,
                                        content=content,
                                        file_path=str(local_file),
                                        size_bytes=len(content.encode()),
                                        metadata={"is_sensitive": False},
                                    )
                                )
                                items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to extract SSL certificates: {e}")

            # Extract SSL private keys (with warning)
            ssl_keys_dir = self.output_dir / "ssl_keys"
            ssl_keys_dir.mkdir(exist_ok=True)
            try:
                if variant == "apache2":
                    key_search_path = f"{config_paths['ssl_dir']}/private"
                else:
                    key_search_path = f"{config_paths['ssl_dir']}/private"

                stdout, _, code = await self._run_command(
                    conn, f"sudo find {key_search_path} -name '*.key' 2>/dev/null"
                )
                if code == 0 and stdout.strip():
                    for key_path in stdout.strip().split("\n"):
                        if key_path:
                            basename = os.path.basename(key_path)
                            content, _, code = await self._run_command(
                                conn, f"sudo cat {key_path}"
                            )
                            if code == 0:
                                local_file = ssl_keys_dir / basename
                                local_file.write_text(content)
                                extracted_data.append(
                                    ExtractedData(
                                        name=f"ssl_key_{basename}",
                                        format=ExtractionFormat.BINARY,
                                        content=content,
                                        file_path=str(local_file),
                                        size_bytes=len(content.encode()),
                                        metadata={"is_sensitive": True, "secure_transfer_required": True},
                                    )
                                )
                                items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to extract SSL private keys: {e}")

            # Extract .htaccess files
            htaccess_dir = self.output_dir / "htaccess"
            htaccess_dir.mkdir(exist_ok=True)
            try:
                stdout, _, code = await self._run_command(
                    conn,
                    f"find {config_paths['web_root']} -name '.htaccess' 2>/dev/null",
                )
                if code == 0 and stdout.strip():
                    for htaccess_path in stdout.strip().split("\n")[:20]:  # Limit to 20
                        if htaccess_path:
                            # Create safe filename from path
                            safe_name = htaccess_path.replace("/", "_").replace(".", "")
                            content, _, code = await self._run_command(
                                conn, f"cat {htaccess_path}"
                            )
                            if code == 0:
                                local_file = htaccess_dir / f"{safe_name}_htaccess"
                                local_file.write_text(content)
                                extracted_data.append(
                                    ExtractedData(
                                        name=f"htaccess_{safe_name}",
                                        format=ExtractionFormat.SHELL_SCRIPT,
                                        content=content,
                                        file_path=str(local_file),
                                        size_bytes=len(content.encode()),
                                        metadata={"original_path": htaccess_path},
                                    )
                                )
                                items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to extract .htaccess files: {e}")

            # Extract .htpasswd files (sanitized)
            htpasswd_dir = self.output_dir / "htpasswd"
            htpasswd_dir.mkdir(exist_ok=True)
            try:
                stdout, _, code = await self._run_command(
                    conn,
                    f"find {config_paths['web_root']} -name '.htpasswd' 2>/dev/null",
                )
                if code == 0 and stdout.strip():
                    for htpasswd_path in stdout.strip().split("\n")[:10]:  # Limit to 10
                        if htpasswd_path:
                            safe_name = htpasswd_path.replace("/", "_").replace(".", "")
                            content, _, code = await self._run_command(
                                conn, f"cat {htpasswd_path}"
                            )
                            if code == 0:
                                # Keep hash format but mark as sanitized
                                sanitized_content = f"# Original file: {htpasswd_path}\n"
                                sanitized_content += "# Hashes preserved for format reference\n"
                                sanitized_content += content
                                local_file = htpasswd_dir / f"{safe_name}_htpasswd"
                                local_file.write_text(sanitized_content)
                                extracted_data.append(
                                    ExtractedData(
                                        name=f"htpasswd_{safe_name}",
                                        format=ExtractionFormat.SHELL_SCRIPT,
                                        content=sanitized_content,
                                        file_path=str(local_file),
                                        size_bytes=len(sanitized_content.encode()),
                                        metadata={
                                            "original_path": htpasswd_path,
                                            "is_sensitive": True,
                                        },
                                    )
                                )
                                items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to extract .htpasswd files: {e}")

            # Extract web content structure (metadata only, not full content)
            try:
                stdout, _, code = await self._run_command(
                    conn,
                    f"find {config_paths['web_root']} -type f | head -100 2>/dev/null",
                )
                if code == 0 and stdout.strip():
                    structure_file = self.output_dir / "web_content_structure.txt"
                    structure_file.write_text(stdout)
                    extracted_data.append(
                        ExtractedData(
                            name="web_content_structure",
                            format=ExtractionFormat.SHELL_SCRIPT,
                            content=stdout,
                            file_path=str(structure_file),
                            size_bytes=len(stdout.encode()),
                            metadata={"note": "Sample of files, not complete listing"},
                        )
                    )
                    items_extracted += 1

                # Get directory sizes
                stdout, _, code = await self._run_command(
                    conn, f"du -sh {config_paths['web_root']}/* 2>/dev/null"
                )
                if code == 0:
                    sizes_file = self.output_dir / "web_content_sizes.txt"
                    sizes_file.write_text(stdout)
                    extracted_data.append(
                        ExtractedData(
                            name="web_content_sizes",
                            format=ExtractionFormat.SHELL_SCRIPT,
                            content=stdout,
                            file_path=str(sizes_file),
                            size_bytes=len(stdout.encode()),
                        )
                    )
                    items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to extract web content metadata: {e}")

            # Get Apache module list
            try:
                module_cmd = f"{variant} -M" if variant == "httpd" else "apache2 -M"
                stdout, _, code = await self._run_command(conn, module_cmd)
                if code == 0:
                    modules_file = self.output_dir / "loaded_modules.txt"
                    modules_file.write_text(stdout)
                    extracted_data.append(
                        ExtractedData(
                            name="loaded_modules",
                            format=ExtractionFormat.SHELL_SCRIPT,
                            content=stdout,
                            file_path=str(modules_file),
                            size_bytes=len(stdout.encode()),
                        )
                    )
                    items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to extract module list: {e}")

            # Create extraction summary
            summary = {
                "apache_variant": variant,
                "config_paths": config_paths,
                "items_extracted": items_extracted,
                "items_failed": items_failed,
                "extraction_timestamp": datetime.utcnow().isoformat(),
                "hostname": hostname,
            }
            summary_file = self.output_dir / "extraction_summary.json"
            summary_file.write_text(json.dumps(summary, indent=2))

            await conn.close()

        except ConnectionError as e:
            errors.append(f"Connection failed: {e}")
        except Exception as e:
            errors.append(f"Extraction failed: {e}")

        duration = (datetime.utcnow() - start_time).total_seconds()
        total_size = sum(d.size_bytes for d in extracted_data)

        status = AnalysisStatus.SUCCESS
        if items_failed > 0 and items_extracted > 0:
            status = AnalysisStatus.PARTIAL
        elif items_failed > 0 and items_extracted == 0:
            status = AnalysisStatus.FAILED

        return ExtractionResult(
            resource_id=resource_id,
            status=status,
            extracted_data=extracted_data,
            total_size_mb=total_size / (1024 * 1024),
            extraction_duration_seconds=duration,
            items_extracted=items_extracted,
            items_failed=items_failed,
            warnings=warnings,
            errors=errors,
            metadata={
                "hostname": hostname,
                "output_dir": str(self.output_dir),
                "apache_variant": variant,
            },
        )

    async def generate_replication_steps(
        self, extraction: ExtractionResult
    ) -> List[ReplicationStep]:
        """Generate Ansible playbook and shell scripts for replication.

        Args:
            extraction: Previous extraction result

        Returns:
            List of replication steps
        """
        steps: List[ReplicationStep] = []
        output_dir = Path(extraction.metadata.get("output_dir", self.output_dir))
        variant = extraction.metadata.get("apache_variant", "apache2")

        # Generate Ansible playbook
        playbook_content = self._generate_ansible_playbook(extraction, variant)
        playbook_path = output_dir / "apache_replication_playbook.yml"
        playbook_path.write_text(playbook_content)

        # Generate inventory template
        inventory_content = """[apache_target]
target_host ansible_user={{ ansible_user }} ansible_become=yes

[apache_target:vars]
apache_variant={{ apache_variant }}
"""
        inventory_path = output_dir / "inventory.ini"
        inventory_path.write_text(inventory_content)

        # Generate shell script for manual execution
        shell_script = self._generate_shell_script(extraction, variant)
        shell_path = output_dir / "manual_replication.sh"
        shell_path.write_text(shell_script)
        shell_path.chmod(0o755)

        # Generate README with instructions
        readme_content = self._generate_readme(extraction, variant)
        readme_path = output_dir / "REPLICATION_README.md"
        readme_path.write_text(readme_content)

        # Define replication steps
        steps.append(
            ReplicationStep(
                step_id="prerequisite_check",
                step_type=StepType.PREREQUISITE,
                description="Verify target VM is accessible and Apache is installed",
                script_content=f"ansible target_host -i {inventory_path} -m ping && ansible target_host -i {inventory_path} -m shell -a 'which {variant}'",
                script_format=ExtractionFormat.SHELL_SCRIPT,
                depends_on=[],
                estimated_duration_minutes=2,
                is_critical=True,
            )
        )

        steps.append(
            ReplicationStep(
                step_id="install_apache",
                step_type=StepType.PREREQUISITE,
                description=f"Ensure Apache ({variant}) is installed on target",
                script_content=f"ansible-playbook {playbook_path} --tags install",
                script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
                depends_on=["prerequisite_check"],
                estimated_duration_minutes=5,
                is_critical=True,
                can_retry=True,
            )
        )

        steps.append(
            ReplicationStep(
                step_id="deploy_configs",
                step_type=StepType.CONFIGURATION,
                description="Deploy Apache configuration files",
                script_content=f"ansible-playbook {playbook_path} --tags configs",
                script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
                depends_on=["install_apache"],
                estimated_duration_minutes=5,
                is_critical=True,
            )
        )

        steps.append(
            ReplicationStep(
                step_id="deploy_ssl_certs",
                step_type=StepType.CONFIGURATION,
                description="Deploy SSL certificates and keys",
                script_content=f"ansible-playbook {playbook_path} --tags ssl",
                script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
                depends_on=["deploy_configs"],
                estimated_duration_minutes=3,
                is_critical=False,
                metadata={"security_warning": "Ensure secure transfer of private keys"},
            )
        )

        steps.append(
            ReplicationStep(
                step_id="deploy_vhosts",
                step_type=StepType.CONFIGURATION,
                description="Deploy virtual host configurations",
                script_content=f"ansible-playbook {playbook_path} --tags vhosts",
                script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
                depends_on=["deploy_configs"],
                estimated_duration_minutes=3,
                is_critical=True,
            )
        )

        steps.append(
            ReplicationStep(
                step_id="enable_modules",
                step_type=StepType.CONFIGURATION,
                description="Enable required Apache modules",
                script_content=f"ansible-playbook {playbook_path} --tags modules",
                script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
                depends_on=["install_apache"],
                estimated_duration_minutes=2,
                is_critical=False,
            )
        )

        steps.append(
            ReplicationStep(
                step_id="deploy_htaccess",
                step_type=StepType.CONFIGURATION,
                description="Deploy .htaccess and .htpasswd files",
                script_content=f"ansible-playbook {playbook_path} --tags access_control",
                script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
                depends_on=["deploy_vhosts"],
                estimated_duration_minutes=2,
                is_critical=False,
            )
        )

        steps.append(
            ReplicationStep(
                step_id="validate_config",
                step_type=StepType.VALIDATION,
                description="Validate Apache configuration syntax",
                script_content=f"ansible target_host -i {inventory_path} -m shell -a '{variant} -t'",
                script_format=ExtractionFormat.SHELL_SCRIPT,
                depends_on=["deploy_vhosts", "deploy_configs"],
                estimated_duration_minutes=1,
                is_critical=True,
            )
        )

        steps.append(
            ReplicationStep(
                step_id="restart_apache",
                step_type=StepType.POST_CONFIG,
                description="Restart Apache service",
                script_content=f"ansible target_host -i {inventory_path} -m service -a 'name={variant} state=restarted'",
                script_format=ExtractionFormat.SHELL_SCRIPT,
                depends_on=["validate_config"],
                estimated_duration_minutes=1,
                is_critical=True,
            )
        )

        steps.append(
            ReplicationStep(
                step_id="verify_service",
                step_type=StepType.VALIDATION,
                description="Verify Apache is running and responding",
                script_content=f"ansible target_host -i {inventory_path} -m shell -a 'systemctl status {variant} && curl -I http://localhost/'",
                script_format=ExtractionFormat.SHELL_SCRIPT,
                depends_on=["restart_apache"],
                estimated_duration_minutes=1,
                is_critical=True,
            )
        )

        return steps

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
        steps_executed: List[str] = []
        warnings: List[str] = []
        errors: List[str] = []

        # In a real implementation, this would:
        # 1. Resolve target_resource_id to hostname/IP
        # 2. Execute each step via ansible-playbook or SSH
        # 3. Handle failures and retries based on can_retry flag
        # 4. Verify success after each critical step
        # 5. Roll back on critical failures

        # For now, simulate execution
        warnings.append(
            "apply_to_target is not fully implemented - requires target VM hostname and Ansible setup"
        )
        warnings.append("Generated playbooks and scripts are ready for manual execution")

        for step in steps:
            logger.info(f"Would execute step: {step.step_id} - {step.description}")
            steps_executed.append(step.step_id)

        duration = (datetime.utcnow() - start_time).total_seconds()

        return ReplicationResult(
            source_resource_id="source_apache_vm",
            target_resource_id=target_resource_id,
            status=ReplicationStatus.PARTIAL,
            steps_executed=steps_executed,
            total_duration_seconds=duration,
            steps_succeeded=len(steps_executed),
            steps_failed=0,
            steps_skipped=0,
            fidelity_score=0.0,  # Would be calculated after real execution
            warnings=warnings,
            errors=errors,
            metadata={
                "total_steps": len(steps),
                "simulated": True,
                "manual_execution_required": True,
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

    def _generate_ansible_playbook(self, extraction: ExtractionResult, variant: str) -> str:
        """Generate Ansible playbook for Apache replication.

        Args:
            extraction: Extraction result with data
            variant: 'httpd' or 'apache2'

        Returns:
            Ansible playbook as YAML string
        """
        output_dir = Path(extraction.metadata.get("output_dir"))

        playbook = f"""---
# Apache Web Server Replication Playbook
# Generated by Azure Tenant Grapher
# Variant: {variant}

- name: Replicate Apache Configuration
  hosts: apache_target
  become: yes
  gather_facts: yes

  vars:
    apache_variant: "{variant}"
    apache_service: "{variant}"
    apache_config_dir: "{'/etc/httpd' if variant == 'httpd' else '/etc/apache2'}"
    apache_web_root: "/var/www/html"
    source_files_dir: "{output_dir}"

  tasks:
    # Installation
    - name: Install Apache (Debian/Ubuntu)
      tags: install
      apt:
        name: apache2
        state: present
        update_cache: yes
      when: ansible_os_family == "Debian" and apache_variant == "apache2"

    - name: Install Apache (RHEL/CentOS)
      tags: install
      yum:
        name: httpd
        state: present
      when: ansible_os_family == "RedHat" and apache_variant == "httpd"

    # Main Configuration
    - name: Deploy main Apache configuration
      tags: configs
      copy:
        src: "{{{{ source_files_dir }}}}/{variant}.conf"
        dest: "{{{{ apache_config_dir }}}}/conf/{{{{ apache_variant }}}}.conf"
        owner: root
        group: root
        mode: '0644'
        backup: yes
      notify: validate and restart apache

"""

        # Add virtual hosts configuration for apache2
        if variant == "apache2":
            playbook += """    # Virtual Hosts (apache2)
    - name: Deploy sites-available configurations
      tags: [configs, vhosts]
      copy:
        src: "{{ source_files_dir }}/sites-available/"
        dest: "{{ apache_config_dir }}/sites-available/"
        owner: root
        group: root
        mode: '0644'
      when: apache_variant == "apache2"

    - name: Enable sites (based on source)
      tags: [configs, vhosts]
      shell: |
        # Parse sites-enabled.txt and enable sites
        # This is a placeholder - actual implementation would parse the file
        a2ensite default-ssl || true
      when: apache_variant == "apache2"
      notify: validate and restart apache

    - name: Deploy ports.conf
      tags: configs
      copy:
        src: "{{ source_files_dir }}/ports.conf"
        dest: "{{ apache_config_dir }}/ports.conf"
        owner: root
        group: root
        mode: '0644'
      when: apache_variant == "apache2"
      notify: validate and restart apache

"""
        else:  # httpd
            playbook += """    # Configuration includes (httpd)
    - name: Deploy conf.d configurations
      tags: [configs, vhosts]
      copy:
        src: "{{ source_files_dir }}/conf.d/"
        dest: "{{ apache_config_dir }}/conf.d/"
        owner: root
        group: root
        mode: '0644'
      when: apache_variant == "httpd"
      notify: validate and restart apache

"""

        # Add SSL configuration
        playbook += """    # SSL Certificates
    - name: Create SSL directories
      tags: ssl
      file:
        path: "{{ item }}"
        state: directory
        owner: root
        group: root
        mode: '0755'
      loop:
        - /etc/ssl/certs
        - /etc/ssl/private

    - name: Deploy SSL certificates
      tags: ssl
      copy:
        src: "{{ source_files_dir }}/ssl_certs/"
        dest: "/etc/ssl/certs/"
        owner: root
        group: root
        mode: '0644'

    - name: Deploy SSL private keys
      tags: ssl
      copy:
        src: "{{ source_files_dir }}/ssl_keys/"
        dest: "/etc/ssl/private/"
        owner: root
        group: root
        mode: '0600'
      no_log: yes  # Don't log private key content

"""

        # Add module management
        if variant == "apache2":
            playbook += """    # Apache Modules (apache2)
    - name: Enable required modules
      tags: modules
      apache2_module:
        name: "{{ item }}"
        state: present
      loop:
        - ssl
        - rewrite
        - headers
        - proxy
        - proxy_http
      when: apache_variant == "apache2"
      notify: validate and restart apache

"""
        else:  # httpd
            playbook += """    # Apache Modules (httpd)
    - name: Ensure required modules are loaded
      tags: modules
      lineinfile:
        path: "{{ apache_config_dir }}/conf/httpd.conf"
        regexp: "^#?LoadModule {{ item }}_module"
        line: "LoadModule {{ item }}_module modules/mod_{{ item }}.so"
      loop:
        - ssl
        - rewrite
        - headers
        - proxy
        - proxy_http
      when: apache_variant == "httpd"
      notify: validate and restart apache

"""

        # Add access control
        playbook += """    # Access Control
    - name: Deploy .htaccess files
      tags: access_control
      copy:
        src: "{{ source_files_dir }}/htaccess/"
        dest: "{{ apache_web_root }}/"
        owner: www-data
        group: www-data
        mode: '0644'
      when: apache_variant == "apache2"

    - name: Deploy .htpasswd files
      tags: access_control
      copy:
        src: "{{ source_files_dir }}/htpasswd/"
        dest: "{{ apache_web_root }}/"
        owner: www-data
        group: www-data
        mode: '0640'
      when: apache_variant == "apache2"
      no_log: yes

    # Service Management
    - name: Enable Apache service
      tags: post_config
      service:
        name: "{{ apache_service }}"
        enabled: yes

  handlers:
    - name: validate and restart apache
      block:
        - name: Validate Apache configuration
          command: "{{ apache_variant }} -t"
          register: apache_config_test
          failed_when: apache_config_test.rc != 0

        - name: Restart Apache
          service:
            name: "{{ apache_service }}"
            state: restarted
          when: apache_config_test.rc == 0
"""

        return playbook

    def _generate_shell_script(self, extraction: ExtractionResult, variant: str) -> str:
        """Generate shell script for manual replication.

        Args:
            extraction: Extraction result
            variant: Apache variant

        Returns:
            Shell script content
        """
        output_dir = Path(extraction.metadata.get("output_dir"))

        script = f"""#!/bin/bash
# Apache Web Server Manual Replication Script
# Generated by Azure Tenant Grapher
# Variant: {variant}

set -e  # Exit on error

TARGET_HOST="${{1:-localhost}}"
APACHE_VARIANT="{variant}"
SOURCE_DIR="{output_dir}"

echo "=== Apache Replication Script ==="
echo "Target: $TARGET_HOST"
echo "Variant: $APACHE_VARIANT"
echo "Source: $SOURCE_DIR"
echo ""

# Check if running locally or remotely
if [ "$TARGET_HOST" = "localhost" ]; then
    SSH_CMD=""
    SCP_CMD="cp"
else
    SSH_CMD="ssh $TARGET_HOST"
    SCP_CMD="scp"
fi

# Install Apache
echo "Step 1: Installing Apache..."
if [ "$APACHE_VARIANT" = "apache2" ]; then
    $SSH_CMD sudo apt-get update
    $SSH_CMD sudo apt-get install -y apache2
else
    $SSH_CMD sudo yum install -y httpd
fi

# Deploy main configuration
echo "Step 2: Deploying main configuration..."
if [ "$TARGET_HOST" = "localhost" ]; then
    sudo cp "$SOURCE_DIR/{variant}.conf" /etc/$APACHE_VARIANT/conf/$APACHE_VARIANT.conf.new
else
    $SCP_CMD "$SOURCE_DIR/{variant}.conf" "$TARGET_HOST:/tmp/{variant}.conf"
    $SSH_CMD sudo mv /tmp/{variant}.conf /etc/$APACHE_VARIANT/conf/$APACHE_VARIANT.conf.new
fi

# Deploy virtual hosts or conf.d
echo "Step 3: Deploying site configurations..."
"""

        if variant == "apache2":
            script += """if [ "$TARGET_HOST" = "localhost" ]; then
    sudo cp -r "$SOURCE_DIR/sites-available/"* /etc/apache2/sites-available/
else
    $SCP_CMD -r "$SOURCE_DIR/sites-available/" "$TARGET_HOST:/tmp/"
    $SSH_CMD sudo cp -r /tmp/sites-available/* /etc/apache2/sites-available/
fi
"""
        else:
            script += """if [ "$TARGET_HOST" = "localhost" ]; then
    sudo cp -r "$SOURCE_DIR/conf.d/"* /etc/httpd/conf.d/
else
    $SCP_CMD -r "$SOURCE_DIR/conf.d/" "$TARGET_HOST:/tmp/"
    $SSH_CMD sudo cp -r /tmp/conf.d/* /etc/httpd/conf.d/
fi
"""

        script += """
# Deploy SSL certificates
echo "Step 4: Deploying SSL certificates..."
if [ -d "$SOURCE_DIR/ssl_certs" ]; then
    if [ "$TARGET_HOST" = "localhost" ]; then
        sudo cp -r "$SOURCE_DIR/ssl_certs/"* /etc/ssl/certs/
    else
        $SCP_CMD -r "$SOURCE_DIR/ssl_certs/" "$TARGET_HOST:/tmp/"
        $SSH_CMD sudo cp -r /tmp/ssl_certs/* /etc/ssl/certs/
    fi
fi

# Deploy SSL private keys (SECURE!)
echo "Step 5: Deploying SSL private keys (secure transfer)..."
if [ -d "$SOURCE_DIR/ssl_keys" ]; then
    echo "WARNING: Transferring private keys - ensure secure connection!"
    if [ "$TARGET_HOST" = "localhost" ]; then
        sudo cp -r "$SOURCE_DIR/ssl_keys/"* /etc/ssl/private/
        sudo chmod 600 /etc/ssl/private/*.key
    else
        $SCP_CMD -r "$SOURCE_DIR/ssl_keys/" "$TARGET_HOST:/tmp/"
        $SSH_CMD sudo cp -r /tmp/ssl_keys/* /etc/ssl/private/
        $SSH_CMD sudo chmod 600 /etc/ssl/private/*.key
    fi
fi

# Validate configuration
echo "Step 6: Validating Apache configuration..."
$SSH_CMD sudo $APACHE_VARIANT -t

# Restart Apache
echo "Step 7: Restarting Apache..."
$SSH_CMD sudo systemctl restart $APACHE_VARIANT

# Verify
echo "Step 8: Verifying Apache is running..."
$SSH_CMD sudo systemctl status $APACHE_VARIANT

echo ""
echo "=== Replication Complete ==="
echo "Please verify web sites are accessible"
echo "Check SSL certificates are valid and not expired"
"""

        return script

    def _generate_readme(self, extraction: ExtractionResult, variant: str) -> str:
        """Generate README with replication instructions.

        Args:
            extraction: Extraction result
            variant: Apache variant

        Returns:
            README content
        """
        output_dir = Path(extraction.metadata.get("output_dir"))

        readme = f"""# Apache Web Server Replication Guide

This directory contains extracted Apache configuration and replication scripts.

## Extraction Summary

- **Apache Variant**: {variant}
- **Extracted Items**: {extraction.items_extracted}
- **Output Directory**: {output_dir}
- **Extraction Date**: {extraction.extracted_at.isoformat()}

## Contents

- `{variant}.conf` - Main Apache configuration
- `sites-available/` or `conf.d/` - Virtual host/site configurations
- `ssl_certs/` - SSL certificates (public)
- `ssl_keys/` - SSL private keys (**SENSITIVE**)
- `htaccess/` - .htaccess access control files
- `htpasswd/` - .htpasswd authentication files (**SENSITIVE**)
- `apache_replication_playbook.yml` - Ansible playbook for automated replication
- `manual_replication.sh` - Shell script for manual replication
- `extraction_summary.json` - Detailed extraction metadata

## Replication Methods

### Method 1: Ansible Playbook (Recommended)

1. Install Ansible on your control machine
2. Edit `inventory.ini` and set target host details
3. Run the playbook:

```bash
ansible-playbook -i inventory.ini apache_replication_playbook.yml
```

For specific steps only:
```bash
# Install Apache only
ansible-playbook -i inventory.ini apache_replication_playbook.yml --tags install

# Deploy configs only
ansible-playbook -i inventory.ini apache_replication_playbook.yml --tags configs

# Deploy SSL only
ansible-playbook -i inventory.ini apache_replication_playbook.yml --tags ssl
```

### Method 2: Manual Shell Script

1. Make the script executable: `chmod +x manual_replication.sh`
2. Run for local installation: `./manual_replication.sh localhost`
3. Run for remote host: `./manual_replication.sh user@target-host`

## Security Considerations

### SSL Private Keys
- Private keys in `ssl_keys/` are **HIGHLY SENSITIVE**
- Transfer only over secure channels (SSH, encrypted volumes)
- Consider regenerating certificates instead of copying keys
- Verify key file permissions are 0600 after transfer

### .htpasswd Files
- Password hashes are preserved but passwords are not recoverable
- Consider regenerating passwords on target system
- Update users and passwords as needed

### Certificate Validity
- Check certificate expiration dates: `openssl x509 -in cert.crt -noout -dates`
- Update certificates before expiration
- Verify certificate chain and trust

## Post-Replication Tasks

1. **Verify Configuration**
   ```bash
   {variant} -t
   ```

2. **Check Service Status**
   ```bash
   systemctl status {variant}
   ```

3. **Test Web Access**
   ```bash
   curl -I http://localhost/
   curl -I https://localhost/  # If SSL configured
   ```

4. **Review Logs**
   ```bash
   tail -f /var/log/{variant}/error.log
   tail -f /var/log/{variant}/access.log
   ```

5. **Update DNS/Firewall**
   - Point DNS records to new server
   - Configure firewall rules (ports 80, 443)
   - Update Azure NSG rules if applicable

## Troubleshooting

### Configuration Errors
If `{variant} -t` fails:
- Check main config file syntax
- Verify all referenced files exist
- Check SSL certificate paths
- Review module dependencies

### Service Won't Start
- Check `systemctl status {variant}` for errors
- Review `/var/log/{variant}/error.log`
- Verify port 80/443 are not already in use
- Check SELinux/AppArmor policies (RHEL/CentOS)

### SSL Issues
- Verify certificate and key match:
  ```bash
  openssl x509 -noout -modulus -in cert.crt | openssl md5
  openssl rsa -noout -modulus -in key.key | openssl md5
  ```
- Check certificate chain is complete
- Verify SNI configuration for multiple SSL sites

## Warnings

"""

        for warning in extraction.warnings:
            readme += f"- ⚠️  {warning}\n"

        if extraction.errors:
            readme += "\n## Errors During Extraction\n\n"
            for error in extraction.errors:
                readme += f"- ❌ {error}\n"

        readme += """
## Additional Resources

- Apache Documentation: https://httpd.apache.org/docs/
- SSL/TLS Best Practices: https://wiki.mozilla.org/Security/Server_Side_TLS
- Let's Encrypt (Free SSL): https://letsencrypt.org/

---
Generated by Azure Tenant Grapher - Apache Web Server Replication Plugin v1.0.0
"""

        return readme
