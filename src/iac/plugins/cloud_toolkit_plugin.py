"""Cloud Toolkit VM replication plugin.

Handles data-plane replication for cloud testing/automation VMs including:
- Cloud CLI tools (Azure CLI, AWS CLI, gcloud, Terraform, kubectl)
- Configuration files (sanitized credentials)
- IaC templates (Terraform, ARM, Bicep, CloudFormation, Ansible)
- Scripts and automation
- Development tools and projects
"""

import asyncio
import json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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


class CloudToolkitReplicationPlugin(ResourceReplicationPlugin):
    """Replication plugin for cloud toolkit/testing environment VMs.

    Discovers and extracts:
    - Cloud CLI tools and versions
    - Configuration files (sanitized)
    - IaC templates and modules
    - Scripts and automation
    - Development environments
    """

    def __init__(
        self,
        ssh_username: Optional[str] = None,
        ssh_password: Optional[str] = None,
        ssh_key_path: Optional[str] = None,
        output_dir: Optional[str] = None,
    ):
        """Initialize Cloud Toolkit plugin.

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
            name="cloud_toolkit",
            version="1.0.0",
            resource_types=["Microsoft.Compute/virtualMachines"],
            description=(
                "Replicates cloud toolkit/testing environment including "
                "CLI tools, IaC templates, scripts, and configurations"
            ),
            requires_ssh=True,
            requires_winrm=False,
            requires_azure_sdk=False,
            supported_os=["linux"],
            dependencies=["asyncssh"],
            complexity="MEDIUM",
            tags=["cloud", "devops", "automation", "iac", "testing"],
        )

    def can_handle(self, resource: Dict[str, Any]) -> bool:
        """Check if this is a cloud toolkit VM.

        Looks for indicators like:
        - VM name contains 'cloud', 'toolkit', 'devops', 'test', 'automation'
        - Tags indicate cloud tooling purpose
        - Computer name patterns (ct, toolkit, devops)

        Args:
            resource: Resource dictionary

        Returns:
            True if this is a cloud toolkit VM
        """
        if resource.get("type") != "Microsoft.Compute/virtualMachines":
            return False

        # Check VM name
        name = resource.get("name", "").lower()
        name_indicators = ["cloud", "toolkit", "devops", "test", "automation", "ct", "cicd", "build"]
        if any(indicator in name for indicator in name_indicators):
            return True

        # Check computer name
        properties = resource.get("properties", {})
        os_profile = properties.get("osProfile", {})
        computer_name = os_profile.get("computerName", "").lower()
        if any(indicator in computer_name for indicator in name_indicators):
            return True

        # Check tags
        tags = resource.get("tags", {})
        purpose = tags.get("purpose", tags.get("Purpose", "")).lower()
        role = tags.get("role", tags.get("Role", "")).lower()
        if any(
            indicator in f"{purpose} {role}"
            for indicator in ["cloud", "toolkit", "devops", "automation", "testing"]
        ):
            return True

        # Check for Linux OS (toolkit VMs are typically Linux)
        storage_profile = properties.get("storageProfile", {})
        image_ref = storage_profile.get("imageReference", {})
        image_ref_str = str(image_ref).lower()
        linux_indicators = ["linux", "ubuntu", "debian", "centos", "rhel"]
        has_linux = any(indicator in image_ref_str for indicator in linux_indicators)

        return has_linux and ("ct" in computer_name or "ct" in name)

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

    async def _run_command(self, conn: Any, command: str) -> Tuple[str, str, int]:
        """Run command on remote host.

        Args:
            conn: SSH connection
            command: Command to run

        Returns:
            Tuple of (stdout, stderr, exit_code)
        """
        result = await conn.run(command, check=False)
        return result.stdout, result.stderr, result.exit_status

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

    def _sanitize_credentials(self, content: str) -> str:
        """Sanitize credentials from configuration files.

        Replaces actual secrets with placeholders while preserving structure.

        Args:
            content: Original file content

        Returns:
            Sanitized content
        """
        # Patterns to sanitize
        patterns = [
            # API keys and tokens (including short values)
            (r'(api[_-]?key|token|secret)["\s:=]+["\']?([a-zA-Z0-9_\-]{6,})["\']?', r'\1="***SANITIZED***"'),
            # Passwords
            (r'(password|passwd)["\s:=]+["\']?([^"\s\n]+)["\']?', r'\1="***SANITIZED***"'),
            # Client secrets
            (r'(client[_-]?secret)["\s:=]+["\']?([a-zA-Z0-9_\-~.]{6,})["\']?', r'\1="***SANITIZED***"'),
            # Access keys
            (r'(access[_-]?key)["\s:=]+["\']?([A-Z0-9]{8,})["\']?', r'\1="***SANITIZED***"'),
            # SSH private keys (replace content between markers)
            (
                r"(-----BEGIN [A-Z ]+PRIVATE KEY-----)(.*?)(-----END [A-Z ]+PRIVATE KEY-----)",
                r"\1\n***SANITIZED***\n\3",
            ),
            # Azure subscription IDs
            (
                r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})",
                r"XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
            ),
            # AWS account numbers
            (r"\b(\d{12})\b", r"XXXXXXXXXXXX"),
        ]

        sanitized = content
        for pattern, replacement in patterns:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE | re.DOTALL)

        return sanitized

    async def analyze_source(self, resource: Dict[str, Any]) -> DataPlaneAnalysis:
        """Analyze cloud toolkit VM to determine what needs replication.

        Args:
            resource: Source VM resource

        Returns:
            DataPlaneAnalysis with discovered elements
        """
        resource_id = resource.get("id", resource.get("name", "unknown"))
        elements: List[DataPlaneElement] = []
        warnings: List[str] = []
        connection_methods = ["SSH"]

        # Define data plane elements to discover
        elements.extend(
            [
                # Cloud CLI Tools
                DataPlaneElement(
                    name="azure_cli",
                    element_type="cloud_cli_tool",
                    description="Azure CLI (az) version and extensions",
                    complexity="LOW",
                    estimated_size_mb=0.1,
                    dependencies=[],
                    metadata={"command": "az version"},
                ),
                DataPlaneElement(
                    name="aws_cli",
                    element_type="cloud_cli_tool",
                    description="AWS CLI version and profiles",
                    complexity="LOW",
                    estimated_size_mb=0.1,
                    dependencies=[],
                    metadata={"command": "aws --version"},
                ),
                DataPlaneElement(
                    name="gcloud_cli",
                    element_type="cloud_cli_tool",
                    description="Google Cloud SDK (gcloud) version",
                    complexity="LOW",
                    estimated_size_mb=0.1,
                    dependencies=[],
                    metadata={"command": "gcloud version"},
                ),
                DataPlaneElement(
                    name="terraform",
                    element_type="iac_tool",
                    description="Terraform version",
                    complexity="LOW",
                    estimated_size_mb=0.1,
                    dependencies=[],
                    metadata={"command": "terraform version"},
                ),
                DataPlaneElement(
                    name="kubectl",
                    element_type="kubernetes_tool",
                    description="Kubernetes kubectl version",
                    complexity="LOW",
                    estimated_size_mb=0.1,
                    dependencies=[],
                    metadata={"command": "kubectl version --client"},
                ),
                DataPlaneElement(
                    name="helm",
                    element_type="kubernetes_tool",
                    description="Helm package manager version",
                    complexity="LOW",
                    estimated_size_mb=0.1,
                    dependencies=[],
                    metadata={"command": "helm version"},
                ),
                # Configuration Files (sanitized)
                DataPlaneElement(
                    name="azure_config",
                    element_type="cloud_config",
                    description="Azure CLI configuration (~/.azure/)",
                    complexity="MEDIUM",
                    estimated_size_mb=1.0,
                    is_sensitive=True,
                    dependencies=["azure_cli"],
                    metadata={"path": "~/.azure/"},
                ),
                DataPlaneElement(
                    name="aws_config",
                    element_type="cloud_config",
                    description="AWS CLI configuration (~/.aws/)",
                    complexity="MEDIUM",
                    estimated_size_mb=1.0,
                    is_sensitive=True,
                    dependencies=["aws_cli"],
                    metadata={"path": "~/.aws/"},
                ),
                DataPlaneElement(
                    name="kube_config",
                    element_type="kubernetes_config",
                    description="Kubernetes configuration (~/.kube/)",
                    complexity="MEDIUM",
                    estimated_size_mb=0.5,
                    is_sensitive=True,
                    dependencies=["kubectl"],
                    metadata={"path": "~/.kube/"},
                ),
                DataPlaneElement(
                    name="terraform_config",
                    element_type="iac_config",
                    description="Terraform configuration (~/.terraform.d/)",
                    complexity="MEDIUM",
                    estimated_size_mb=0.5,
                    dependencies=["terraform"],
                    metadata={"path": "~/.terraform.d/"},
                ),
                # IaC Templates
                DataPlaneElement(
                    name="terraform_modules",
                    element_type="iac_template",
                    description="Terraform modules and state files",
                    complexity="HIGH",
                    estimated_size_mb=10.0,
                    dependencies=["terraform"],
                    metadata={"patterns": ["*.tf", "*.tfvars", "terraform.tfstate"]},
                ),
                DataPlaneElement(
                    name="arm_bicep_templates",
                    element_type="iac_template",
                    description="ARM/Bicep templates",
                    complexity="MEDIUM",
                    estimated_size_mb=5.0,
                    dependencies=[],
                    metadata={"patterns": ["*.bicep", "*.json"]},
                ),
                DataPlaneElement(
                    name="cloudformation_templates",
                    element_type="iac_template",
                    description="CloudFormation templates",
                    complexity="MEDIUM",
                    estimated_size_mb=5.0,
                    dependencies=[],
                    metadata={"patterns": ["*.yaml", "*.yml", "*.json"]},
                ),
                DataPlaneElement(
                    name="ansible_playbooks",
                    element_type="automation_script",
                    description="Ansible playbooks and roles",
                    complexity="HIGH",
                    estimated_size_mb=5.0,
                    dependencies=[],
                    metadata={"patterns": ["*.yml", "*.yaml"]},
                ),
                # Scripts & Automation
                DataPlaneElement(
                    name="deployment_scripts",
                    element_type="automation_script",
                    description="Deployment and automation scripts",
                    complexity="MEDIUM",
                    estimated_size_mb=2.0,
                    dependencies=[],
                    metadata={"patterns": ["*.sh", "*.py", "*.ps1"]},
                ),
                DataPlaneElement(
                    name="cicd_configs",
                    element_type="automation_config",
                    description="CI/CD configurations (GitHub Actions, Azure Pipelines)",
                    complexity="MEDIUM",
                    estimated_size_mb=1.0,
                    dependencies=[],
                    metadata={"paths": [".github/workflows", ".azure-pipelines"]},
                ),
                # Development Tools
                DataPlaneElement(
                    name="git_repositories",
                    element_type="dev_tool",
                    description="Git repositories (list only, not full content)",
                    complexity="LOW",
                    estimated_size_mb=0.5,
                    dependencies=[],
                    metadata={"command": "find ~ -name .git -type d"},
                ),
                DataPlaneElement(
                    name="python_environments",
                    element_type="dev_tool",
                    description="Python virtual environments",
                    complexity="LOW",
                    estimated_size_mb=0.5,
                    dependencies=[],
                    metadata={"patterns": ["venv", ".venv", "env"]},
                ),
                DataPlaneElement(
                    name="docker_images",
                    element_type="dev_tool",
                    description="Docker images inventory",
                    complexity="LOW",
                    estimated_size_mb=0.1,
                    dependencies=[],
                    metadata={"command": "docker images"},
                ),
                # Credentials metadata (NOT actual secrets)
                DataPlaneElement(
                    name="service_principal_metadata",
                    element_type="credentials_metadata",
                    description="Service principal metadata (NOT secrets)",
                    complexity="LOW",
                    estimated_size_mb=0.1,
                    is_sensitive=True,
                    dependencies=["azure_cli"],
                    metadata={"command": "az account list"},
                ),
                DataPlaneElement(
                    name="ssh_key_paths",
                    element_type="credentials_metadata",
                    description="SSH key paths (NOT key contents)",
                    complexity="LOW",
                    estimated_size_mb=0.1,
                    is_sensitive=True,
                    dependencies=[],
                    metadata={"command": "ls ~/.ssh/*.pub"},
                ),
            ]
        )

        # Try to connect and verify accessibility
        hostname = self._extract_hostname(resource)
        if hostname:
            try:
                conn = await self._connect_ssh(hostname)
                stdout, stderr, exit_code = await self._run_command(conn, "uname -a")
                if exit_code == 0:
                    logger.info(f"Connected to cloud toolkit VM {hostname}: {stdout.strip()}")
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
            total_estimated_size_mb=sum(e.estimated_size_mb for e in elements),
            complexity_score=7.0,  # Medium-high complexity
            requires_credentials=True,
            requires_network_access=True,
            connection_methods=connection_methods,
            estimated_extraction_time_minutes=15,
            warnings=warnings,
            metadata={
                "os_type": "linux",
                "plugin_version": self.metadata.version,
                "total_elements": len(elements),
            },
        )

    async def extract_data(
        self, resource: Dict[str, Any], analysis: DataPlaneAnalysis
    ) -> ExtractionResult:
        """Extract data from cloud toolkit VM.

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
            self.output_dir = Path(tempfile.mkdtemp(prefix="cloud_toolkit_extract_"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        extracted_data_items: List[ExtractedData] = []
        warnings: List[str] = []
        errors: List[str] = []
        items_extracted = 0
        items_failed = 0

        try:
            conn = await self._connect_ssh(hostname)

            # Extract Azure CLI version and extensions
            try:
                stdout, stderr, code = await self._run_command(conn, "az version 2>/dev/null || echo 'NOT_INSTALLED'")
                if code == 0 and "NOT_INSTALLED" not in stdout:
                    extracted_data_items.append(
                        ExtractedData(
                            name="azure_cli_version",
                            format=ExtractionFormat.JSON,
                            content=stdout,
                            size_bytes=len(stdout.encode()),
                        )
                    )
                    items_extracted += 1
                else:
                    warnings.append("Azure CLI not installed")
            except Exception as e:
                errors.append(f"Failed to extract Azure CLI version: {e}")
                items_failed += 1

            # Extract AWS CLI version
            try:
                stdout, stderr, code = await self._run_command(
                    conn, "aws --version 2>&1 || echo 'NOT_INSTALLED'"
                )
                if code == 0 and "NOT_INSTALLED" not in stdout:
                    extracted_data_items.append(
                        ExtractedData(
                            name="aws_cli_version",
                            format=ExtractionFormat.JSON,
                            content=stdout.strip(),
                            size_bytes=len(stdout.encode()),
                        )
                    )
                    items_extracted += 1
                else:
                    warnings.append("AWS CLI not installed")
            except Exception as e:
                warnings.append(f"Failed to extract AWS CLI version: {e}")
                items_failed += 1

            # Extract gcloud version
            try:
                stdout, stderr, code = await self._run_command(
                    conn, "gcloud version 2>/dev/null || echo 'NOT_INSTALLED'"
                )
                if code == 0 and "NOT_INSTALLED" not in stdout:
                    extracted_data_items.append(
                        ExtractedData(
                            name="gcloud_version",
                            format=ExtractionFormat.JSON,
                            content=stdout,
                            size_bytes=len(stdout.encode()),
                        )
                    )
                    items_extracted += 1
                else:
                    warnings.append("Google Cloud SDK not installed")
            except Exception as e:
                warnings.append(f"Failed to extract gcloud version: {e}")
                items_failed += 1

            # Extract Terraform version
            try:
                stdout, stderr, code = await self._run_command(
                    conn, "terraform version 2>/dev/null || echo 'NOT_INSTALLED'"
                )
                if code == 0 and "NOT_INSTALLED" not in stdout:
                    extracted_data_items.append(
                        ExtractedData(
                            name="terraform_version",
                            format=ExtractionFormat.JSON,
                            content=stdout.strip(),
                            size_bytes=len(stdout.encode()),
                        )
                    )
                    items_extracted += 1
                else:
                    warnings.append("Terraform not installed")
            except Exception as e:
                warnings.append(f"Failed to extract Terraform version: {e}")
                items_failed += 1

            # Extract kubectl version
            try:
                stdout, stderr, code = await self._run_command(
                    conn, "kubectl version --client 2>/dev/null || echo 'NOT_INSTALLED'"
                )
                if code == 0 and "NOT_INSTALLED" not in stdout:
                    extracted_data_items.append(
                        ExtractedData(
                            name="kubectl_version",
                            format=ExtractionFormat.JSON,
                            content=stdout,
                            size_bytes=len(stdout.encode()),
                        )
                    )
                    items_extracted += 1
                else:
                    warnings.append("kubectl not installed")
            except Exception as e:
                warnings.append(f"Failed to extract kubectl version: {e}")
                items_failed += 1

            # Extract helm version
            try:
                stdout, stderr, code = await self._run_command(
                    conn, "helm version 2>/dev/null || echo 'NOT_INSTALLED'"
                )
                if code == 0 and "NOT_INSTALLED" not in stdout:
                    extracted_data_items.append(
                        ExtractedData(
                            name="helm_version",
                            format=ExtractionFormat.JSON,
                            content=stdout.strip(),
                            size_bytes=len(stdout.encode()),
                        )
                    )
                    items_extracted += 1
                else:
                    warnings.append("Helm not installed")
            except Exception as e:
                warnings.append(f"Failed to extract Helm version: {e}")
                items_failed += 1

            # Extract Azure config (sanitized)
            try:
                stdout, stderr, code = await self._run_command(
                    conn, "az account list 2>/dev/null || echo 'NOT_CONFIGURED'"
                )
                if code == 0 and "NOT_CONFIGURED" not in stdout:
                    sanitized = self._sanitize_credentials(stdout)
                    extracted_data_items.append(
                        ExtractedData(
                            name="azure_accounts",
                            format=ExtractionFormat.JSON,
                            content=sanitized,
                            size_bytes=len(sanitized.encode()),
                            metadata={"sanitized": True},
                        )
                    )
                    items_extracted += 1

                    # Get Azure CLI config
                    stdout, stderr, code = await self._run_command(conn, "az configure --list-defaults 2>/dev/null || echo '{}'")
                    if code == 0:
                        extracted_data_items.append(
                            ExtractedData(
                                name="azure_config",
                                format=ExtractionFormat.JSON,
                                content=stdout,
                                size_bytes=len(stdout.encode()),
                            )
                        )
                        items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to extract Azure config: {e}")
                items_failed += 1

            # Extract AWS config (sanitized)
            try:
                stdout, stderr, code = await self._run_command(
                    conn, "aws configure list 2>/dev/null || echo 'NOT_CONFIGURED'"
                )
                if code == 0 and "NOT_CONFIGURED" not in stdout:
                    sanitized = self._sanitize_credentials(stdout)
                    extracted_data_items.append(
                        ExtractedData(
                            name="aws_config",
                            format=ExtractionFormat.JSON,
                            content=sanitized,
                            size_bytes=len(sanitized.encode()),
                            metadata={"sanitized": True},
                        )
                    )
                    items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to extract AWS config: {e}")
                items_failed += 1

            # Extract kubectl extensions/plugins
            try:
                stdout, stderr, code = await self._run_command(
                    conn, "kubectl plugin list 2>/dev/null || echo 'NOT_CONFIGURED'"
                )
                if code == 0 and "NOT_CONFIGURED" not in stdout:
                    extracted_data_items.append(
                        ExtractedData(
                            name="kubectl_plugins",
                            format=ExtractionFormat.JSON,
                            content=stdout,
                            size_bytes=len(stdout.encode()),
                        )
                    )
                    items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to extract kubectl plugins: {e}")
                items_failed += 1

            # Find Terraform files
            try:
                stdout, stderr, code = await self._run_command(
                    conn,
                    'find ~/ -type f \\( -name "*.tf" -o -name "*.tfvars" \\) 2>/dev/null | head -n 100',
                )
                if code == 0 and stdout.strip():
                    tf_files = stdout.strip().split("\n")
                    extracted_data_items.append(
                        ExtractedData(
                            name="terraform_files_inventory",
                            format=ExtractionFormat.JSON,
                            content=json.dumps({"files": tf_files, "count": len(tf_files)}),
                            size_bytes=len(stdout.encode()),
                            metadata={"file_count": len(tf_files)},
                        )
                    )
                    items_extracted += 1

                    warnings.append(
                        f"Found {len(tf_files)} Terraform files - full extraction requires manual copy"
                    )
            except Exception as e:
                warnings.append(f"Failed to find Terraform files: {e}")
                items_failed += 1

            # Find ARM/Bicep templates
            try:
                stdout, stderr, code = await self._run_command(
                    conn,
                    'find ~/ -type f -name "*.bicep" 2>/dev/null | head -n 100',
                )
                if code == 0 and stdout.strip():
                    bicep_files = stdout.strip().split("\n")
                    extracted_data_items.append(
                        ExtractedData(
                            name="bicep_files_inventory",
                            format=ExtractionFormat.JSON,
                            content=json.dumps({"files": bicep_files, "count": len(bicep_files)}),
                            size_bytes=len(stdout.encode()),
                            metadata={"file_count": len(bicep_files)},
                        )
                    )
                    items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to find Bicep files: {e}")
                items_failed += 1

            # Find Ansible playbooks
            try:
                stdout, stderr, code = await self._run_command(
                    conn,
                    'find ~/ -type f -name "*.yml" -o -name "*.yaml" 2>/dev/null | grep -i ansible | head -n 100',
                )
                if code == 0 and stdout.strip():
                    ansible_files = stdout.strip().split("\n")
                    extracted_data_items.append(
                        ExtractedData(
                            name="ansible_files_inventory",
                            format=ExtractionFormat.JSON,
                            content=json.dumps({"files": ansible_files, "count": len(ansible_files)}),
                            size_bytes=len(stdout.encode()),
                            metadata={"file_count": len(ansible_files)},
                        )
                    )
                    items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to find Ansible files: {e}")
                items_failed += 1

            # Find deployment scripts
            try:
                stdout, stderr, code = await self._run_command(
                    conn,
                    'find ~/ -type f \\( -name "deploy*.sh" -o -name "deploy*.py" \\) 2>/dev/null | head -n 100',
                )
                if code == 0 and stdout.strip():
                    script_files = stdout.strip().split("\n")
                    extracted_data_items.append(
                        ExtractedData(
                            name="deployment_scripts_inventory",
                            format=ExtractionFormat.JSON,
                            content=json.dumps({"files": script_files, "count": len(script_files)}),
                            size_bytes=len(stdout.encode()),
                            metadata={"file_count": len(script_files)},
                        )
                    )
                    items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to find deployment scripts: {e}")
                items_failed += 1

            # Find Git repositories
            try:
                stdout, stderr, code = await self._run_command(
                    conn, 'find ~/ -name .git -type d 2>/dev/null | head -n 50'
                )
                if code == 0 and stdout.strip():
                    git_repos = [line.replace("/.git", "") for line in stdout.strip().split("\n")]
                    extracted_data_items.append(
                        ExtractedData(
                            name="git_repositories_inventory",
                            format=ExtractionFormat.JSON,
                            content=json.dumps({"repositories": git_repos, "count": len(git_repos)}),
                            size_bytes=len(stdout.encode()),
                            metadata={"repo_count": len(git_repos)},
                        )
                    )
                    items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to find Git repositories: {e}")
                items_failed += 1

            # Find Python virtual environments
            try:
                stdout, stderr, code = await self._run_command(
                    conn,
                    'find ~/ -type d \\( -name "venv" -o -name ".venv" -o -name "env" \\) 2>/dev/null | head -n 50',
                )
                if code == 0 and stdout.strip():
                    venvs = stdout.strip().split("\n")
                    extracted_data_items.append(
                        ExtractedData(
                            name="python_venvs_inventory",
                            format=ExtractionFormat.JSON,
                            content=json.dumps({"venvs": venvs, "count": len(venvs)}),
                            size_bytes=len(stdout.encode()),
                            metadata={"venv_count": len(venvs)},
                        )
                    )
                    items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to find Python venvs: {e}")
                items_failed += 1

            # Get Docker images inventory
            try:
                stdout, stderr, code = await self._run_command(
                    conn, "docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null || echo 'NOT_INSTALLED'"
                )
                if code == 0 and "NOT_INSTALLED" not in stdout:
                    images = stdout.strip().split("\n") if stdout.strip() else []
                    extracted_data_items.append(
                        ExtractedData(
                            name="docker_images_inventory",
                            format=ExtractionFormat.JSON,
                            content=json.dumps({"images": images, "count": len(images)}),
                            size_bytes=len(stdout.encode()),
                            metadata={"image_count": len(images)},
                        )
                    )
                    items_extracted += 1
                else:
                    warnings.append("Docker not installed or not accessible")
            except Exception as e:
                warnings.append(f"Failed to get Docker images: {e}")
                items_failed += 1

            # Get SSH public keys (paths only, not content)
            try:
                stdout, stderr, code = await self._run_command(conn, "ls ~/.ssh/*.pub 2>/dev/null || echo 'NONE'")
                if code == 0 and "NONE" not in stdout:
                    ssh_keys = stdout.strip().split("\n")
                    extracted_data_items.append(
                        ExtractedData(
                            name="ssh_key_paths",
                            format=ExtractionFormat.JSON,
                            content=json.dumps({"keys": ssh_keys, "count": len(ssh_keys)}),
                            size_bytes=len(stdout.encode()),
                            metadata={"key_count": len(ssh_keys), "paths_only": True},
                        )
                    )
                    items_extracted += 1
            except Exception as e:
                warnings.append(f"Failed to list SSH keys: {e}")
                items_failed += 1

            await conn.close()

        except ConnectionError as e:
            errors.append(f"Connection failed: {e}")
        except Exception as e:
            errors.append(f"Extraction failed: {e}")

        duration = (datetime.utcnow() - start_time).total_seconds()
        total_size = sum(item.size_bytes for item in extracted_data_items)

        # Write extracted data to files
        extracted_files: List[str] = []
        for item in extracted_data_items:
            filename = f"{item.name}.json"
            file_path = self.output_dir / filename
            file_path.write_text(item.content)
            item.file_path = str(file_path)
            extracted_files.append(str(file_path))

        # Generate summary report
        summary = {
            "resource_id": resource_id,
            "hostname": hostname,
            "extracted_at": datetime.utcnow().isoformat(),
            "items_extracted": items_extracted,
            "items_failed": items_failed,
            "total_size_bytes": total_size,
            "warnings": warnings,
            "errors": errors,
            "extracted_items": [
                {"name": item.name, "format": item.format, "size_bytes": item.size_bytes}
                for item in extracted_data_items
            ],
        }
        summary_path = self.output_dir / "extraction_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2))
        extracted_files.append(str(summary_path))

        status = AnalysisStatus.SUCCESS
        if items_failed > 0:
            status = AnalysisStatus.PARTIAL if items_extracted > 0 else AnalysisStatus.FAILED

        return ExtractionResult(
            resource_id=resource_id,
            status=status,
            extracted_data=extracted_data_items,
            total_size_mb=total_size / (1024 * 1024),
            extraction_duration_seconds=duration,
            items_extracted=items_extracted,
            items_failed=items_failed,
            warnings=warnings,
            errors=errors,
            metadata={
                "hostname": hostname,
                "output_dir": str(self.output_dir),
                "summary_file": str(summary_path),
            },
            extracted_files=extracted_files,
        )

    async def generate_replication_steps(
        self, extraction: ExtractionResult
    ) -> List[ReplicationStep]:
        """Generate replication steps for cloud toolkit VM.

        Creates manual setup instructions since cloud toolkits require
        specific tool installations and credential configuration.

        Args:
            extraction: Previous extraction result

        Returns:
            List of replication steps
        """
        steps: List[ReplicationStep] = []
        output_dir = Path(extraction.metadata.get("output_dir", self.output_dir))

        # Generate setup playbook
        playbook_content = self._generate_setup_playbook(extraction)
        playbook_path = output_dir / "cloud_toolkit_setup.yml"
        playbook_path.write_text(playbook_content)

        # Generate manual setup guide
        manual_guide = self._generate_manual_guide(extraction)
        guide_path = output_dir / "MANUAL_SETUP_GUIDE.md"
        guide_path.write_text(manual_guide)

        # Step 1: Validate target
        steps.append(
            ReplicationStep(
                step_id="validate_target",
                step_type=StepType.VALIDATION,
                description="Validate target VM is accessible via SSH",
                script_content="ssh -o ConnectTimeout=10 {{ target_host }} 'echo Connection successful'",
                script_format=ExtractionFormat.SHELL_SCRIPT,
                depends_on=[],
                estimated_duration_minutes=1,
                is_critical=True,
                can_retry=True,
                max_retries=3,
            )
        )

        # Step 2: Install base tools
        steps.append(
            ReplicationStep(
                step_id="install_base_tools",
                step_type=StepType.PREREQUISITE,
                description="Install base development tools (git, curl, wget, etc.)",
                script_content=playbook_content,
                script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
                depends_on=["validate_target"],
                estimated_duration_minutes=5,
                is_critical=True,
                can_retry=True,
                metadata={"tags": "base_tools", "script_path": str(playbook_path)},
            )
        )

        # Step 3: Install cloud CLI tools
        steps.append(
            ReplicationStep(
                step_id="install_cloud_clis",
                step_type=StepType.PREREQUISITE,
                description="Install cloud CLI tools (az, aws, gcloud)",
                script_content=playbook_content,
                script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
                depends_on=["install_base_tools"],
                estimated_duration_minutes=10,
                is_critical=True,
                can_retry=True,
                metadata={"tags": "cloud_clis", "script_path": str(playbook_path)},
            )
        )

        # Step 4: Install IaC tools
        steps.append(
            ReplicationStep(
                step_id="install_iac_tools",
                step_type=StepType.PREREQUISITE,
                description="Install IaC tools (Terraform, Ansible)",
                script_content=playbook_content,
                script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
                depends_on=["install_base_tools"],
                estimated_duration_minutes=10,
                is_critical=True,
                can_retry=True,
                metadata={"tags": "iac_tools", "script_path": str(playbook_path)},
            )
        )

        # Step 5: Install Kubernetes tools
        steps.append(
            ReplicationStep(
                step_id="install_k8s_tools",
                step_type=StepType.PREREQUISITE,
                description="Install Kubernetes tools (kubectl, helm)",
                script_content=playbook_content,
                script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
                depends_on=["install_base_tools"],
                estimated_duration_minutes=5,
                is_critical=False,
                can_retry=True,
                metadata={"tags": "k8s_tools", "script_path": str(playbook_path)},
            )
        )

        # Step 6: Copy IaC templates
        steps.append(
            ReplicationStep(
                step_id="copy_iac_templates",
                step_type=StepType.DATA_IMPORT,
                description="Copy IaC templates to target (requires manual file transfer)",
                script_content=(
                    "# Manual step: Use scp or rsync to copy files\n"
                    "# See MANUAL_SETUP_GUIDE.md for details\n"
                    f"echo 'See {guide_path} for file copy instructions'"
                ),
                script_format=ExtractionFormat.SHELL_SCRIPT,
                depends_on=["install_iac_tools"],
                estimated_duration_minutes=15,
                is_critical=False,
                can_retry=False,
                metadata={"manual_step": True, "guide_path": str(guide_path)},
            )
        )

        # Step 7: Configure credentials (MANUAL)
        steps.append(
            ReplicationStep(
                step_id="configure_credentials",
                step_type=StepType.CONFIGURATION,
                description="Configure cloud credentials (MANUAL - requires actual secrets)",
                script_content=(
                    "# MANUAL STEP - REQUIRES ACTUAL CREDENTIALS\n"
                    "# 1. Run: az login\n"
                    "# 2. Run: aws configure\n"
                    "# 3. Configure kubectl contexts\n"
                    f"# See {guide_path} for details"
                ),
                script_format=ExtractionFormat.SHELL_SCRIPT,
                depends_on=["install_cloud_clis"],
                estimated_duration_minutes=10,
                is_critical=True,
                can_retry=False,
                metadata={"manual_step": True, "requires_secrets": True, "guide_path": str(guide_path)},
            )
        )

        # Step 8: Verify installation
        steps.append(
            ReplicationStep(
                step_id="verify_installation",
                step_type=StepType.VALIDATION,
                description="Verify all tools are installed and configured",
                script_content=self._generate_verification_script(),
                script_format=ExtractionFormat.SHELL_SCRIPT,
                depends_on=["install_cloud_clis", "install_iac_tools", "install_k8s_tools"],
                estimated_duration_minutes=2,
                is_critical=False,
                can_retry=True,
                validation_script=self._generate_verification_script(),
            )
        )

        return steps

    async def apply_to_target(
        self, steps: List[ReplicationStep], target_resource_id: str
    ) -> ReplicationResult:
        """Apply replication steps to target VM.

        Note: This is largely simulated since cloud toolkit setup requires
        manual credential configuration.

        Args:
            steps: Steps to execute
            target_resource_id: Azure resource ID of target

        Returns:
            ReplicationResult with execution status
        """
        start_time = datetime.utcnow()
        step_results: List[StepResult] = []
        warnings: List[str] = []
        errors: List[str] = []

        warnings.append(
            "Cloud toolkit replication requires manual credential configuration - "
            "see generated MANUAL_SETUP_GUIDE.md"
        )

        # Simulate step execution
        for step in steps:
            step_start = datetime.utcnow()

            # Check if manual step
            is_manual = step.metadata.get("manual_step", False)
            requires_secrets = step.metadata.get("requires_secrets", False)

            if is_manual or requires_secrets:
                status = ReplicationStatus.SKIPPED
                warnings.append(f"Step '{step.step_id}' requires manual execution")
            else:
                status = ReplicationStatus.SUCCESS
                logger.info(f"Would execute step: {step.step_id} - {step.description}")

            step_duration = (datetime.utcnow() - step_start).total_seconds()

            step_results.append(
                StepResult(
                    step_id=step.step_id,
                    status=status,
                    duration_seconds=step_duration,
                    stdout=f"Simulated execution of {step.step_id}",
                    stderr="",
                    exit_code=0 if status == ReplicationStatus.SUCCESS else 1,
                    retry_count=0,
                )
            )

        duration = (datetime.utcnow() - start_time).total_seconds()

        steps_succeeded = sum(1 for r in step_results if r.status == ReplicationStatus.SUCCESS)
        steps_failed = sum(1 for r in step_results if r.status == ReplicationStatus.FAILED)
        steps_skipped = sum(1 for r in step_results if r.status == ReplicationStatus.SKIPPED)

        # Calculate fidelity (automated steps / total steps)
        total_steps = len(steps)
        automated_steps = total_steps - steps_skipped
        fidelity = automated_steps / total_steps if total_steps > 0 else 0.0

        status = ReplicationStatus.PARTIAL_SUCCESS if steps_skipped > 0 else ReplicationStatus.SUCCESS

        return ReplicationResult(
            source_resource_id="source_vm_id",
            target_resource_id=target_resource_id,
            status=status,
            steps_executed=step_results,
            total_duration_seconds=duration,
            steps_succeeded=steps_succeeded,
            steps_failed=steps_failed,
            steps_skipped=steps_skipped,
            fidelity_score=fidelity,
            warnings=warnings,
            errors=errors,
            metadata={
                "total_steps": total_steps,
                "simulated": True,
                "requires_manual_steps": steps_skipped > 0,
            },
        )

    def _generate_setup_playbook(self, extraction: ExtractionResult) -> str:
        """Generate Ansible playbook for setting up cloud toolkit.

        Args:
            extraction: Extraction result with tool inventory

        Returns:
            Ansible playbook as YAML string
        """
        # Extract tool versions from extracted data
        tools_to_install = []
        for item in extraction.extracted_data:
            if "version" in item.name:
                tools_to_install.append(item.name.replace("_version", ""))

        playbook = """---
- name: Setup Cloud Toolkit Environment
  hosts: target
  become: yes
  gather_facts: yes

  tasks:
    - name: Install base development tools
      tags: base_tools
      apt:
        name:
          - git
          - curl
          - wget
          - unzip
          - jq
          - python3
          - python3-pip
        state: present
        update_cache: yes
      when: ansible_os_family == "Debian"

    - name: Install Azure CLI
      tags: cloud_clis
      shell: |
        curl -sL https://aka.ms/InstallAzureCLIDeb | bash
      args:
        creates: /usr/bin/az

    - name: Install AWS CLI
      tags: cloud_clis
      shell: |
        curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
        unzip -q awscliv2.zip
        ./aws/install
        rm -rf aws awscliv2.zip
      args:
        creates: /usr/local/bin/aws

    - name: Install Google Cloud SDK
      tags: cloud_clis
      shell: |
        echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
        curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -
        apt-get update && apt-get install -y google-cloud-sdk
      args:
        creates: /usr/bin/gcloud
      when: ansible_os_family == "Debian"

    - name: Install Terraform
      tags: iac_tools
      shell: |
        wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
        echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/hashicorp.list
        apt-get update && apt-get install -y terraform
      args:
        creates: /usr/bin/terraform
      when: ansible_os_family == "Debian"

    - name: Install Ansible
      tags: iac_tools
      pip:
        name: ansible
        state: present
        executable: pip3

    - name: Install kubectl
      tags: k8s_tools
      shell: |
        curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
        install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
        rm kubectl
      args:
        creates: /usr/local/bin/kubectl

    - name: Install Helm
      tags: k8s_tools
      shell: |
        curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
      args:
        creates: /usr/local/bin/helm

    - name: Create workspace directory
      tags: workspace
      file:
        path: /home/{{ ansible_user }}/workspace
        state: directory
        owner: "{{ ansible_user }}"
        group: "{{ ansible_user }}"
        mode: '0755'

  handlers:
    - name: reload shell
      shell: source ~/.bashrc
      args:
        executable: /bin/bash
"""

        return playbook

    def _generate_manual_guide(self, extraction: ExtractionResult) -> str:
        """Generate manual setup guide.

        Args:
            extraction: Extraction result

        Returns:
            Markdown-formatted manual guide
        """
        guide = """# Cloud Toolkit VM - Manual Setup Guide

This guide provides step-by-step instructions for completing the replication
of your cloud toolkit environment.

## Overview

The automated replication has extracted tool versions, configurations (sanitized),
and file inventories. However, some steps require manual intervention due to:

1. **Credentials**: Actual secrets cannot be automated for security
2. **File Transfer**: Large IaC repositories require manual copying
3. **Custom Configurations**: Tool-specific settings may need adjustment

## Prerequisites

- SSH access to target VM
- Actual cloud credentials (Azure, AWS, GCP)
- Source VM still accessible (for file copying)

## Step 1: Run Automated Setup

The automated Ansible playbook installs all required tools:

```bash
ansible-playbook -i inventory.ini cloud_toolkit_setup.yml
```

This installs:
- Azure CLI
- AWS CLI
- Google Cloud SDK
- Terraform
- kubectl
- Helm
- Ansible

## Step 2: Configure Cloud Credentials

### Azure CLI

```bash
# Login interactively
az login

# Set default subscription (if needed)
az account set --subscription "YOUR_SUBSCRIPTION_ID"

# Verify
az account show
```

### AWS CLI

```bash
# Configure credentials
aws configure

# Provide:
# - AWS Access Key ID
# - AWS Secret Access Key
# - Default region
# - Default output format

# Verify
aws sts get-caller-identity
```

### Google Cloud SDK

```bash
# Login
gcloud auth login

# Set project
gcloud config set project YOUR_PROJECT_ID

# Verify
gcloud config list
```

### Kubernetes

```bash
# Copy kubeconfig from source VM
scp source-vm:~/.kube/config ~/.kube/config

# Verify
kubectl cluster-info
```

## Step 3: Copy IaC Templates and Scripts

"""

        # Add file copy instructions based on extracted inventories
        for item in extraction.extracted_data:
            if "inventory" in item.name:
                try:
                    data = json.loads(item.content)
                    if "files" in data and data.get("count", 0) > 0:
                        guide += f"\n### {item.name.replace('_', ' ').title()}\n\n"
                        guide += f"Found {data['count']} files. Copy using:\n\n"
                        guide += "```bash\n"
                        guide += "# From source VM\n"
                        guide += "# Example for first few files:\n"
                        for file_path in data["files"][:3]:
                            guide += f"scp source-vm:{file_path} target-vm:{file_path}\n"
                        if data["count"] > 3:
                            guide += f"# ... and {data['count'] - 3} more files\n"
                        guide += "```\n"
                except Exception:
                    pass

        guide += """
## Step 4: Configure SSH Keys

If SSH keys are needed for Git or other services:

```bash
# Generate new SSH key
ssh-keygen -t ed25519 -C "your_email@example.com"

# Add to SSH agent
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519

# Copy public key to clipboard
cat ~/.ssh/id_ed25519.pub
# Then add to GitHub/GitLab/etc.
```

## Step 5: Configure Git

```bash
git config --global user.name "Your Name"
git config --global user.email "your_email@example.com"
```

## Step 6: Clone Git Repositories

"""

        # Add git repo clone instructions
        for item in extraction.extracted_data:
            if item.name == "git_repositories_inventory":
                try:
                    data = json.loads(item.content)
                    if "repositories" in data and data.get("count", 0) > 0:
                        guide += f"Found {data['count']} Git repositories:\n\n"
                        guide += "```bash\n"
                        for repo_path in data["repositories"][:5]:
                            repo_name = Path(repo_path).name
                            guide += f"# git clone <repo-url> ~/{repo_name}\n"
                        guide += "```\n"
                except Exception:
                    pass

        guide += """
## Step 7: Verify Installation

Run the verification script:

```bash
./verify_installation.sh
```

This checks:
- All CLI tools are installed
- Credentials are configured
- Basic functionality works

## Security Notes

- **Never** commit actual credentials to version control
- **Use** Azure Key Vault, AWS Secrets Manager, or similar for secrets
- **Rotate** credentials after migration
- **Review** all configuration files for embedded secrets

## Troubleshooting

### Azure CLI issues

```bash
az account clear
az login
```

### AWS CLI issues

```bash
rm -rf ~/.aws/credentials
aws configure
```

### Terraform issues

```bash
# Re-initialize
terraform init

# Check state
terraform state list
```

## Next Steps

1. Test each cloud provider connection
2. Run a test deployment
3. Update any hardcoded paths or configurations
4. Set up CI/CD pipelines if needed

## Support

For issues or questions, refer to:
- Azure CLI: https://docs.microsoft.com/en-us/cli/azure/
- AWS CLI: https://aws.amazon.com/cli/
- Terraform: https://www.terraform.io/docs/
"""

        return guide

    def _generate_verification_script(self) -> str:
        """Generate verification script to check installation.

        Returns:
            Shell script content
        """
        script = """#!/bin/bash
# Cloud Toolkit Installation Verification Script

set -e

echo "=== Cloud Toolkit Verification ==="
echo ""

# Check Azure CLI
echo "Checking Azure CLI..."
if command -v az &> /dev/null; then
    az version | grep "azure-cli" || true
    echo "✓ Azure CLI installed"
else
    echo "✗ Azure CLI not found"
fi
echo ""

# Check AWS CLI
echo "Checking AWS CLI..."
if command -v aws &> /dev/null; then
    aws --version || true
    echo "✓ AWS CLI installed"
else
    echo "✗ AWS CLI not found"
fi
echo ""

# Check Google Cloud SDK
echo "Checking Google Cloud SDK..."
if command -v gcloud &> /dev/null; then
    gcloud version | head -n 1 || true
    echo "✓ Google Cloud SDK installed"
else
    echo "✗ Google Cloud SDK not found"
fi
echo ""

# Check Terraform
echo "Checking Terraform..."
if command -v terraform &> /dev/null; then
    terraform version | head -n 1 || true
    echo "✓ Terraform installed"
else
    echo "✗ Terraform not found"
fi
echo ""

# Check kubectl
echo "Checking kubectl..."
if command -v kubectl &> /dev/null; then
    kubectl version --client --short 2>/dev/null || kubectl version --client || true
    echo "✓ kubectl installed"
else
    echo "✗ kubectl not found"
fi
echo ""

# Check Helm
echo "Checking Helm..."
if command -v helm &> /dev/null; then
    helm version --short || true
    echo "✓ Helm installed"
else
    echo "✗ Helm not found"
fi
echo ""

# Check Ansible
echo "Checking Ansible..."
if command -v ansible &> /dev/null; then
    ansible --version | head -n 1 || true
    echo "✓ Ansible installed"
else
    echo "✗ Ansible not found"
fi
echo ""

echo "=== Verification Complete ==="
echo ""
echo "Note: Tools marked with ✗ may need manual installation."
echo "See MANUAL_SETUP_GUIDE.md for instructions."
"""

        return script
