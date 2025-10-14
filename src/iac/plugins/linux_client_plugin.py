"""Linux Client VM replication plugin.

Handles data-plane replication for Linux virtual machines including:
- User and group management
- SSH keys and configurations
- System configurations (packages, services, cron)
- Application configurations
- Firewall rules
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
    DataPlaneAnalysis,
    DataPlaneElement,
    ExtractionResult,
    PluginMetadata,
    ReplicationResult,
    ReplicationStatus,
    ReplicationStep,
    StepType,
)

logger = logging.getLogger(__name__)


class LinuxClientReplicationPlugin(ResourceReplicationPlugin):
    """Replication plugin for Linux VMs.

    Supports Ubuntu, CentOS, RHEL, and other major Linux distributions.
    Extracts system configurations and generates Ansible playbooks for replication.
    """

    def __init__(self, ssh_username: Optional[str] = None, ssh_password: Optional[str] = None,
                 ssh_key_path: Optional[str] = None, output_dir: Optional[str] = None):
        """Initialize Linux Client plugin.

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
            name="linux_client",
            version="1.0.0",
            resource_types=["Microsoft.Compute/virtualMachines"],
            description="Replicates Linux VM configurations including users, SSH, packages, and services",
            requires_ssh=True,
            requires_winrm=False,
            requires_azure_sdk=False,
            supported_os=["linux"],
            dependencies=["asyncssh", "ansible"],
        )

    def can_handle(self, resource: Dict[str, Any]) -> bool:
        """Check if this is a Linux VM.

        Args:
            resource: Resource dictionary

        Returns:
            True if this is a Linux VM
        """
        if resource.get("type") != "Microsoft.Compute/virtualMachines":
            return False

        # Check OS type in properties
        properties = resource.get("properties", {})
        storage_profile = properties.get("storageProfile", {})
        os_profile = properties.get("osProfile", {})

        # Check for Linux in storage profile
        image_ref = storage_profile.get("imageReference", {})
        image_ref_str = str(image_ref).lower()
        linux_indicators = ["linux", "ubuntu", "debian", "centos", "rhel", "redhat", "suse", "fedora", "oracle"]
        if any(indicator in image_ref_str for indicator in linux_indicators):
            return True

        # Check OS profile for Linux computer name patterns
        computer_name = os_profile.get("computerName", "")
        if "linux" in computer_name.lower() or computer_name.endswith("cl"):
            return True

        # Check tags
        tags = resource.get("tags", {})
        os_type = tags.get("os", tags.get("OS", tags.get("osType", "")))
        if "linux" in os_type.lower():
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

            conn = await asyncio.wait_for(
                asyncssh.connect(**connect_kwargs),
                timeout=30.0
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
        """Analyze Linux VM to determine what needs replication.

        Args:
            resource: Source VM resource

        Returns:
            DataPlaneAnalysis with discovered elements
        """
        resource_id = resource.get("id", resource.get("name", "unknown"))
        elements: List[DataPlaneElement] = []
        warnings: List[str] = []

        # Define what we want to extract
        elements.extend([
            # User & Group Management
            DataPlaneElement(
                name="users",
                element_type="user_management",
                description="User accounts from /etc/passwd",
                priority="critical",
                extraction_method="getent passwd",
            ),
            DataPlaneElement(
                name="groups",
                element_type="user_management",
                description="Group definitions from /etc/group",
                priority="critical",
                extraction_method="getent group",
            ),
            DataPlaneElement(
                name="shadow",
                element_type="user_management",
                description="Password hashes from /etc/shadow (sanitized)",
                priority="high",
                is_sensitive=True,
                extraction_method="sudo cat /etc/shadow",
            ),
            DataPlaneElement(
                name="ssh_keys",
                element_type="security",
                description="SSH authorized keys for all users",
                priority="critical",
                is_sensitive=True,
                extraction_method="find /home -name authorized_keys",
            ),
            DataPlaneElement(
                name="sudoers",
                element_type="security",
                description="Sudo permissions from /etc/sudoers.d/",
                priority="high",
                extraction_method="ls /etc/sudoers.d/",
            ),
            # System Configuration
            DataPlaneElement(
                name="packages",
                element_type="system_config",
                description="Installed packages",
                priority="high",
                extraction_method="dpkg -l / rpm -qa",
            ),
            DataPlaneElement(
                name="systemd_services",
                element_type="system_config",
                description="Systemd service units",
                priority="medium",
                extraction_method="systemctl list-unit-files",
            ),
            DataPlaneElement(
                name="cron_jobs",
                element_type="system_config",
                description="Cron jobs and schedules",
                priority="medium",
                extraction_method="crontab -l / ls /etc/cron*",
            ),
            DataPlaneElement(
                name="network_config",
                element_type="system_config",
                description="Network configuration files",
                priority="medium",
                extraction_method="cat /etc/netplan/* / cat /etc/network/interfaces",
            ),
            # Application Configuration
            DataPlaneElement(
                name="etc_configs",
                element_type="application_config",
                description="Critical configuration files from /etc",
                priority="medium",
                extraction_method="tar configs",
            ),
            DataPlaneElement(
                name="environment",
                element_type="application_config",
                description="Environment variables",
                priority="low",
                extraction_method="env / cat /etc/environment",
            ),
            # SSH & Security
            DataPlaneElement(
                name="sshd_config",
                element_type="security",
                description="SSH daemon configuration",
                priority="high",
                extraction_method="cat /etc/ssh/sshd_config",
            ),
            DataPlaneElement(
                name="firewall",
                element_type="security",
                description="Firewall rules (iptables/ufw)",
                priority="medium",
                extraction_method="iptables -L / ufw status",
            ),
        ])

        # Try to connect and verify accessibility (if hostname provided)
        hostname = self._extract_hostname(resource)
        if hostname:
            try:
                conn = await self._connect_ssh(hostname)
                # Quick check - get OS info
                stdout, stderr, exit_code = await self._run_command(conn, "uname -a")
                if exit_code == 0:
                    logger.info(f"Connected to {hostname}: {stdout.strip()}")
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
            complexity_score=6.5,  # Medium-high complexity
            requires_credentials=True,
            warnings=warnings,
            metadata={
                "os_type": "linux",
                "plugin_version": self.metadata.version,
            },
        )

    async def extract_data(
        self, resource: Dict[str, Any], analysis: DataPlaneAnalysis
    ) -> ExtractionResult:
        """Extract data from Linux VM.

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
            self.output_dir = Path(tempfile.mkdtemp(prefix="linux_extract_"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        extracted_files: List[str] = []
        extracted_data: Dict[str, Any] = {}
        warnings: List[str] = []
        errors: List[str] = []

        try:
            conn = await self._connect_ssh(hostname)

            # Extract users
            try:
                stdout, stderr, code = await self._run_command(conn, "getent passwd")
                if code == 0:
                    users_file = self.output_dir / "passwd.txt"
                    users_file.write_text(stdout)
                    extracted_files.append(str(users_file))
                    extracted_data["users"] = [line.split(":")[0] for line in stdout.strip().split("\n")]
            except Exception as e:
                errors.append(f"Failed to extract users: {e}")

            # Extract groups
            try:
                stdout, stderr, code = await self._run_command(conn, "getent group")
                if code == 0:
                    groups_file = self.output_dir / "group.txt"
                    groups_file.write_text(stdout)
                    extracted_files.append(str(groups_file))
                    extracted_data["groups"] = [line.split(":")[0] for line in stdout.strip().split("\n")]
            except Exception as e:
                errors.append(f"Failed to extract groups: {e}")

            # Extract shadow (sanitized - hashes replaced with placeholder)
            try:
                stdout, stderr, code = await self._run_command(conn, "sudo cat /etc/shadow 2>/dev/null || echo 'PERMISSION_DENIED'")
                if code == 0 and "PERMISSION_DENIED" not in stdout:
                    # Sanitize password hashes
                    sanitized_lines = []
                    for line in stdout.strip().split("\n"):
                        if line and not line.startswith("#"):
                            parts = line.split(":")
                            if len(parts) >= 2:
                                parts[1] = "***SANITIZED***"
                            sanitized_lines.append(":".join(parts))

                    shadow_file = self.output_dir / "shadow_sanitized.txt"
                    shadow_file.write_text("\n".join(sanitized_lines))
                    extracted_files.append(str(shadow_file))
                else:
                    warnings.append("Could not extract /etc/shadow - insufficient permissions")
            except Exception as e:
                warnings.append(f"Failed to extract shadow: {e}")

            # Extract SSH keys
            try:
                stdout, stderr, code = await self._run_command(
                    conn, "find /home -name authorized_keys 2>/dev/null"
                )
                if code == 0 and stdout.strip():
                    ssh_keys_dir = self.output_dir / "ssh_keys"
                    ssh_keys_dir.mkdir(exist_ok=True)

                    for key_path in stdout.strip().split("\n"):
                        if key_path:
                            content, _, code = await self._run_command(conn, f"cat {key_path}")
                            if code == 0:
                                # Extract username from path
                                username = key_path.split("/")[2] if len(key_path.split("/")) > 2 else "unknown"
                                safe_filename = f"{username}_authorized_keys.txt"
                                local_file = ssh_keys_dir / safe_filename
                                local_file.write_text(content)
                                extracted_files.append(str(local_file))

                    extracted_data["ssh_keys_found"] = len(list(ssh_keys_dir.glob("*")))
            except Exception as e:
                warnings.append(f"Failed to extract SSH keys: {e}")

            # Extract sudoers
            try:
                stdout, stderr, code = await self._run_command(
                    conn, "ls /etc/sudoers.d/ 2>/dev/null || echo 'NOT_FOUND'"
                )
                if code == 0 and "NOT_FOUND" not in stdout:
                    sudoers_dir = self.output_dir / "sudoers.d"
                    sudoers_dir.mkdir(exist_ok=True)

                    for filename in stdout.strip().split("\n"):
                        if filename:
                            content, _, code = await self._run_command(conn, f"sudo cat /etc/sudoers.d/{filename}")
                            if code == 0:
                                local_file = sudoers_dir / filename
                                local_file.write_text(content)
                                extracted_files.append(str(local_file))
            except Exception as e:
                warnings.append(f"Failed to extract sudoers: {e}")

            # Extract installed packages
            try:
                # Try dpkg first (Debian/Ubuntu)
                stdout, stderr, code = await self._run_command(conn, "dpkg -l 2>/dev/null || echo 'NOT_DEBIAN'")
                if code == 0 and "NOT_DEBIAN" not in stdout:
                    packages_file = self.output_dir / "packages_dpkg.txt"
                    packages_file.write_text(stdout)
                    extracted_files.append(str(packages_file))
                    extracted_data["package_manager"] = "dpkg"
                else:
                    # Try rpm (RHEL/CentOS)
                    stdout, stderr, code = await self._run_command(conn, "rpm -qa")
                    if code == 0:
                        packages_file = self.output_dir / "packages_rpm.txt"
                        packages_file.write_text(stdout)
                        extracted_files.append(str(packages_file))
                        extracted_data["package_manager"] = "rpm"
            except Exception as e:
                errors.append(f"Failed to extract packages: {e}")

            # Extract systemd services
            try:
                stdout, stderr, code = await self._run_command(conn, "systemctl list-unit-files --type=service")
                if code == 0:
                    services_file = self.output_dir / "systemd_services.txt"
                    services_file.write_text(stdout)
                    extracted_files.append(str(services_file))
            except Exception as e:
                warnings.append(f"Failed to extract services: {e}")

            # Extract cron jobs
            try:
                stdout, stderr, code = await self._run_command(conn, "crontab -l 2>/dev/null || echo 'NO_CRONTAB'")
                if code == 0 and "NO_CRONTAB" not in stdout:
                    cron_file = self.output_dir / "crontab.txt"
                    cron_file.write_text(stdout)
                    extracted_files.append(str(cron_file))
            except Exception as e:
                warnings.append(f"Failed to extract crontab: {e}")

            # Extract SSH daemon config
            try:
                stdout, stderr, code = await self._run_command(conn, "cat /etc/ssh/sshd_config")
                if code == 0:
                    sshd_file = self.output_dir / "sshd_config.txt"
                    sshd_file.write_text(stdout)
                    extracted_files.append(str(sshd_file))
            except Exception as e:
                warnings.append(f"Failed to extract sshd_config: {e}")

            # Extract firewall rules
            try:
                # Try ufw first
                stdout, stderr, code = await self._run_command(conn, "sudo ufw status verbose 2>/dev/null || echo 'NO_UFW'")
                if code == 0 and "NO_UFW" not in stdout:
                    fw_file = self.output_dir / "firewall_ufw.txt"
                    fw_file.write_text(stdout)
                    extracted_files.append(str(fw_file))
                else:
                    # Try iptables
                    stdout, stderr, code = await self._run_command(conn, "sudo iptables -L -n -v")
                    if code == 0:
                        fw_file = self.output_dir / "firewall_iptables.txt"
                        fw_file.write_text(stdout)
                        extracted_files.append(str(fw_file))
            except Exception as e:
                warnings.append(f"Failed to extract firewall rules: {e}")

            # Get system info
            try:
                stdout, _, _ = await self._run_command(conn, "uname -a")
                extracted_data["system_info"] = stdout.strip()

                stdout, _, _ = await self._run_command(conn, "cat /etc/os-release 2>/dev/null || echo 'N/A'")
                if "N/A" not in stdout:
                    os_release_file = self.output_dir / "os_release.txt"
                    os_release_file.write_text(stdout)
                    extracted_files.append(str(os_release_file))
            except Exception as e:
                warnings.append(f"Failed to extract system info: {e}")

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
            extracted_files=extracted_files,
            extracted_data=extracted_data,
            scripts_generated=[],  # Will be populated in generate_replication_steps
            size_bytes=total_size,
            extraction_duration_seconds=duration,
            warnings=warnings,
            errors=errors,
            metadata={
                "hostname": hostname,
                "output_dir": str(self.output_dir),
            },
        )

    async def generate_replication_steps(
        self, extraction: ExtractionResult
    ) -> List[ReplicationStep]:
        """Generate Ansible playbook for replication.

        Args:
            extraction: Previous extraction result

        Returns:
            List of replication steps
        """
        steps: List[ReplicationStep] = []
        output_dir = Path(extraction.metadata.get("output_dir", self.output_dir))

        # Generate Ansible playbook
        playbook_path = output_dir / "replication_playbook.yml"
        playbook_content = self._generate_ansible_playbook(extraction)
        playbook_path.write_text(playbook_content)

        extraction.scripts_generated.append(str(playbook_path))

        # Generate inventory file
        inventory_path = output_dir / "inventory.ini"
        inventory_content = "[target]\ntarget_host ansible_user={{ ansible_user }}\n"
        inventory_path.write_text(inventory_content)

        extraction.scripts_generated.append(str(inventory_path))

        # Create steps
        steps.append(
            ReplicationStep(
                step_id="validate_target",
                step_type=StepType.VALIDATION,
                description="Validate target VM is accessible",
                script_content="ansible target -i inventory.ini -m ping",
                depends_on=[],
                is_critical=True,
            )
        )

        steps.append(
            ReplicationStep(
                step_id="replicate_users",
                step_type=StepType.DATA_IMPORT,
                description="Create user accounts on target",
                script_content=playbook_content,
                depends_on=["validate_target"],
                is_critical=True,
                metadata={"tags": "users", "script_path": str(playbook_path)},
            )
        )

        steps.append(
            ReplicationStep(
                step_id="replicate_ssh_keys",
                step_type=StepType.CONFIGURATION,
                description="Deploy SSH authorized keys",
                script_content=playbook_content,
                depends_on=["replicate_users"],
                is_critical=True,
                metadata={"tags": "ssh_keys", "script_path": str(playbook_path)},
            )
        )

        steps.append(
            ReplicationStep(
                step_id="replicate_packages",
                step_type=StepType.CONFIGURATION,
                description="Install required packages",
                script_content=playbook_content,
                depends_on=["validate_target"],
                is_critical=False,
                metadata={"tags": "packages", "script_path": str(playbook_path)},
            )
        )

        steps.append(
            ReplicationStep(
                step_id="replicate_configs",
                step_type=StepType.CONFIGURATION,
                description="Deploy configuration files",
                script_content=playbook_content,
                depends_on=["replicate_packages"],
                is_critical=False,
                metadata={"tags": "configs", "script_path": str(playbook_path)},
            )
        )

        steps.append(
            ReplicationStep(
                step_id="verify_replication",
                step_type=StepType.VALIDATION,
                description="Verify replication completed successfully",
                script_content="ansible target -i inventory.ini -m setup",
                depends_on=["replicate_configs"],
                is_critical=False,
            )
        )

        return steps

    async def apply_to_target(
        self,
        steps: List[ReplicationStep],
        target_resource_id: str,
        dry_run: bool = False,
    ) -> ReplicationResult:
        """Apply replication steps to target resource using execution engine.

        Args:
            steps: Replication steps to execute
            target_resource_id: Target resource ID
            dry_run: If True, simulate without making changes

        Returns:
            ReplicationResult with execution results
        """
        # Import here to avoid circular dependency
        from ..execution.engine import ExecutionEngine
        from ..execution.models import ExecutionConfig

        start_time = datetime.utcnow()

        # Initialize execution engine
        engine = ExecutionEngine(
            ExecutionConfig(
                working_dir=Path(self.output_dir) if self.output_dir else Path.cwd(),
                timeout_seconds=1800,  # 30 minutes
                dry_run=dry_run,
                retry_count=2,
                log_file=Path(self.output_dir) / "execution.log" if self.output_dir else None,
            )
        )

        step_results = []
        completed_steps = set()

        for step in steps:
            # Check dependencies
            if step.depends_on:
                unmet_deps = set(step.depends_on) - completed_steps
                if unmet_deps:
                    step_results.append({
                        "step_id": step.step_id,
                        "status": "skipped",
                        "message": f"Unmet dependencies: {unmet_deps}",
                    })
                    continue

            try:
                # Execute step via engine
                result = await engine.execute_step(
                    step=step,
                    context={
                        "target_resource_id": target_resource_id,
                        "output_dir": str(self.output_dir) if self.output_dir else ".",
                        "plugin_name": self.metadata.name,
                    },
                )

                if result.status == ReplicationStatus.SUCCESS:
                    completed_steps.add(step.step_id)
                    step_results.append({
                        "step_id": step.step_id,
                        "status": "success",
                        "duration": result.duration_seconds,
                    })
                else:
                    step_results.append({
                        "step_id": step.step_id,
                        "status": "failed",
                        "error": result.stderr,
                        "duration": result.duration_seconds,
                    })

                    if step.is_critical:
                        logger.error(f"Critical step {step.step_id} failed, stopping execution")
                        break  # Stop on critical failure

            except Exception as e:
                step_results.append({
                    "step_id": step.step_id,
                    "status": "error",
                    "error": str(e),
                })

                if step.is_critical:
                    logger.error(f"Critical step {step.step_id} raised exception, stopping execution")
                    break

        # Calculate metrics
        total_steps = len(steps)
        successful_steps = sum(1 for r in step_results if r.get("status") == "success")
        failed_steps = sum(1 for r in step_results if r.get("status") in ["failed", "error"])
        skipped_steps = sum(1 for r in step_results if r.get("status") == "skipped")

        fidelity_score = successful_steps / total_steps if total_steps > 0 else 0.0

        # Determine overall status
        if successful_steps == total_steps and failed_steps == 0:
            status = ReplicationStatus.SUCCESS
        elif failed_steps > 0 and successful_steps == 0:
            status = ReplicationStatus.FAILED
        elif failed_steps > 0:
            status = ReplicationStatus.PARTIAL
        else:
            status = ReplicationStatus.FAILED

        duration = (datetime.utcnow() - start_time).total_seconds()

        return ReplicationResult(
            status=status,
            target_resource_id=target_resource_id,
            steps_executed=step_results,
            steps_succeeded=successful_steps,
            steps_failed=failed_steps,
            steps_skipped=skipped_steps,
            fidelity_score=fidelity_score,
            total_duration_seconds=duration,
            metadata={
                "execution_engine": "ansible_runner",
                "dry_run": dry_run,
                "total_steps": total_steps,
            },
            warnings=[] if not dry_run else ["Executed in dry-run mode"],
        )

    def _extract_hostname(self, resource: Dict[str, Any]) -> Optional[str]:
        """Extract hostname or IP from resource.

        Args:
            resource: Resource dictionary

        Returns:
            Hostname/IP or None
        """
        # Try common locations
        properties = resource.get("properties", {})

        # Check network profile for public IP
        network_profile = properties.get("networkProfile", {})
        network_interfaces = network_profile.get("networkInterfaces", [])

        # Try to get from network interface (simplified)
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

    def _generate_ansible_playbook(self, extraction: ExtractionResult) -> str:
        """Generate Ansible playbook for replication.

        Args:
            extraction: Extraction result with data

        Returns:
            Ansible playbook as YAML string
        """
        playbook = """---
- name: Replicate Linux VM Configuration
  hosts: target
  become: yes
  gather_facts: yes

  tasks:
    - name: Create user accounts
      tags: users
      user:
        name: "{{ item }}"
        state: present
        create_home: yes
        shell: /bin/bash
      loop: {{ users | to_json }}
      when: users is defined

    - name: Create groups
      tags: users
      group:
        name: "{{ item }}"
        state: present
      loop: {{ groups | to_json }}
      when: groups is defined

    - name: Deploy SSH authorized keys
      tags: ssh_keys
      authorized_key:
        user: "{{ item.user }}"
        key: "{{ item.key }}"
        state: present
      loop: "{{ ssh_keys }}"
      when: ssh_keys is defined

    - name: Install packages (dpkg)
      tags: packages
      apt:
        name: "{{ item }}"
        state: present
      loop: "{{ dpkg_packages }}"
      when: dpkg_packages is defined and ansible_os_family == "Debian"

    - name: Install packages (rpm)
      tags: packages
      yum:
        name: "{{ item }}"
        state: present
      loop: "{{ rpm_packages }}"
      when: rpm_packages is defined and ansible_os_family == "RedHat"

    - name: Deploy SSH daemon config
      tags: configs
      copy:
        src: "{{ sshd_config_src }}"
        dest: /etc/ssh/sshd_config
        owner: root
        group: root
        mode: '0644'
      when: sshd_config_src is defined
      notify: restart sshd

    - name: Deploy cron jobs
      tags: configs
      copy:
        content: "{{ crontab_content }}"
        dest: "/var/spool/cron/{{ crontab_user }}"
        owner: "{{ crontab_user }}"
        mode: '0600'
      when: crontab_content is defined

  handlers:
    - name: restart sshd
      service:
        name: sshd
        state: restarted
"""

        # Substitute extracted data
        users = extraction.extracted_data.get("users", [])
        groups = extraction.extracted_data.get("groups", [])

        playbook = playbook.replace("{{ users | to_json }}", json.dumps(users))
        playbook = playbook.replace("{{ groups | to_json }}", json.dumps(groups))

        return playbook
