"""Ubuntu Replication Plugin.

Extends Linux Client Plugin with Ubuntu-specific features:
- Snap package management
- Docker container handling (if installed)
- Ubuntu-specific system configurations
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from .linux_client_plugin import LinuxClientReplicationPlugin
from .models import (
    DataPlaneAnalysis,
    DataPlaneElement,
    ExtractionResult,
    PluginMetadata,
    ReplicationStep,
    StepType,
)

logger = logging.getLogger(__name__)


class UbuntuReplicationPlugin(LinuxClientReplicationPlugin):
    """Replication plugin for Ubuntu VMs.

    Extends Linux Client Plugin with Ubuntu-specific features:
    - Snap package extraction and restoration
    - Docker container support (optional)
    - Ubuntu cloud-init configurations
    """

    @property
    def metadata(self) -> PluginMetadata:
        """Get plugin metadata."""
        return PluginMetadata(
            name="ubuntu",
            version="1.0.0",
            resource_types=["Microsoft.Compute/virtualMachines"],
            description="Replicates Ubuntu VM configurations including snap packages, Docker, and Ubuntu-specific settings",
            requires_ssh=True,
            requires_winrm=False,
            requires_azure_sdk=False,
            supported_os=["ubuntu"],
            dependencies=["asyncssh", "ansible"],
        )

    def can_handle(self, resource: Dict[str, Any]) -> bool:
        """Check if this is an Ubuntu VM.

        Args:
            resource: Resource dictionary

        Returns:
            True if this is an Ubuntu VM
        """
        if resource.get("type") != "Microsoft.Compute/virtualMachines":
            return False

        # Check storage profile for Ubuntu images
        properties = resource.get("properties", {})
        storage_profile = properties.get("storageProfile", {})
        image_ref = storage_profile.get("imageReference", {})

        # Check publisher/offer
        publisher = image_ref.get("publisher", "").lower()
        offer = image_ref.get("offer", "").lower()
        if "canonical" in publisher or "ubuntu" in offer:
            return True

        # Check OS profile for Ubuntu computer name patterns
        os_profile = properties.get("osProfile", {})
        computer_name = os_profile.get("computerName", "").lower()
        if "ubuntu" in computer_name:
            return True

        # Check tags
        tags = resource.get("tags", {})
        os_type = tags.get("os", tags.get("OS", tags.get("osType", ""))).lower()
        distribution = tags.get("distribution", tags.get("distro", "")).lower()
        if "ubuntu" in os_type or "ubuntu" in distribution:
            return True

        return False

    async def analyze_source(self, resource: Dict[str, Any]) -> DataPlaneAnalysis:
        """Analyze Ubuntu VM to determine what needs replication.

        Extends parent class analysis with Ubuntu-specific elements.

        Args:
            resource: Source VM resource

        Returns:
            DataPlaneAnalysis with discovered elements
        """
        # Get base Linux analysis
        analysis = await super().analyze_source(resource)

        # Add Ubuntu-specific elements
        ubuntu_elements = [
            DataPlaneElement(
                name="snap_packages",
                element_type="system_config",
                description="Snap packages installed on the system",
                priority="high",
                extraction_method="snap list --all",
            ),
            DataPlaneElement(
                name="snap_connections",
                element_type="system_config",
                description="Snap interface connections and plugs",
                priority="medium",
                extraction_method="snap connections",
            ),
            DataPlaneElement(
                name="docker_containers",
                element_type="application_config",
                description="Docker containers (if Docker is installed)",
                priority="medium",
                extraction_method="docker ps -a",
            ),
            DataPlaneElement(
                name="docker_images",
                element_type="application_config",
                description="Docker images (if Docker is installed)",
                priority="medium",
                extraction_method="docker images",
            ),
            DataPlaneElement(
                name="docker_volumes",
                element_type="application_config",
                description="Docker volumes (if Docker is installed)",
                priority="low",
                extraction_method="docker volume ls",
            ),
            DataPlaneElement(
                name="cloud_init_config",
                element_type="system_config",
                description="Cloud-init configuration (if present)",
                priority="medium",
                extraction_method="ls /etc/cloud/",
            ),
            DataPlaneElement(
                name="update_manager",
                element_type="system_config",
                description="Ubuntu update manager configuration",
                priority="low",
                extraction_method="cat /etc/update-manager/release-upgrades",
            ),
        ]

        analysis.elements.extend(ubuntu_elements)
        analysis.complexity_score += 1.5  # Slightly more complex than generic Linux
        analysis.metadata["os_type"] = "ubuntu"
        analysis.metadata["plugin_version"] = self.metadata.version

        return analysis

    async def extract_data(
        self, resource: Dict[str, Any], analysis: DataPlaneAnalysis
    ) -> ExtractionResult:
        """Extract data from Ubuntu VM.

        Extends parent class extraction with Ubuntu-specific data.

        Args:
            resource: Source VM resource
            analysis: Previous analysis result

        Returns:
            ExtractionResult with extracted data
        """
        # Get base Linux extraction
        result = await super().extract_data(resource, analysis)
        hostname = self._extract_hostname(resource)

        if not hostname:
            # Parent already raised, but just in case
            return result

        # Extract Ubuntu-specific data
        try:
            conn = await self._connect_ssh(hostname)

            # Extract snap packages
            await self._extract_snap_packages(conn, result)

            # Extract snap connections
            await self._extract_snap_connections(conn, result)

            # Extract Docker data (if Docker is installed)
            await self._extract_docker_data(conn, result)

            # Extract cloud-init configuration
            await self._extract_cloud_init_config(conn, result)

            # Extract update manager config
            await self._extract_update_manager_config(conn, result)

            await conn.close()

        except ConnectionError as e:
            result.errors.append(f"Ubuntu-specific extraction failed: {e}")
        except Exception as e:
            result.warnings.append(f"Some Ubuntu features could not be extracted: {e}")

        return result

    async def _extract_snap_packages(self, conn: Any, result: ExtractionResult) -> None:
        """Extract snap packages.

        Args:
            conn: SSH connection
            result: ExtractionResult to update
        """
        try:
            stdout, stderr, code = await self._run_command(
                conn, "snap list --all 2>/dev/null || echo 'NO_SNAP'"
            )
            if code == 0 and "NO_SNAP" not in stdout:
                snap_file = self.output_dir / "snap_packages.txt"
                snap_file.write_text(stdout)
                result.extracted_files.append(str(snap_file))

                # Parse snap list output
                snap_packages = []
                for line in stdout.strip().split("\n")[1:]:  # Skip header
                    if line and not line.startswith("Name"):
                        parts = line.split()
                        if parts:
                            snap_packages.append(parts[0])

                result.extracted_data["snap_packages"] = snap_packages
                logger.info(f"Extracted {len(snap_packages)} snap packages")
            else:
                result.warnings.append("Snap is not installed or not accessible")
        except Exception as e:
            result.warnings.append(f"Failed to extract snap packages: {e}")

    async def _extract_snap_connections(self, conn: Any, result: ExtractionResult) -> None:
        """Extract snap interface connections.

        Args:
            conn: SSH connection
            result: ExtractionResult to update
        """
        try:
            stdout, stderr, code = await self._run_command(
                conn, "snap connections 2>/dev/null || echo 'NO_SNAP'"
            )
            if code == 0 and "NO_SNAP" not in stdout:
                connections_file = self.output_dir / "snap_connections.txt"
                connections_file.write_text(stdout)
                result.extracted_files.append(str(connections_file))
                logger.info("Extracted snap connections")
        except Exception as e:
            result.warnings.append(f"Failed to extract snap connections: {e}")

    async def _extract_docker_data(self, conn: Any, result: ExtractionResult) -> None:
        """Extract Docker containers, images, and volumes.

        Args:
            conn: SSH connection
            result: ExtractionResult to update
        """
        try:
            # Check if Docker is installed
            stdout, stderr, code = await self._run_command(
                conn, "which docker 2>/dev/null || echo 'NO_DOCKER'"
            )
            if code != 0 or "NO_DOCKER" in stdout:
                result.extracted_data["docker_installed"] = False
                return

            result.extracted_data["docker_installed"] = True

            # Extract running and stopped containers
            stdout, stderr, code = await self._run_command(
                conn, "docker ps -a --format '{{json .}}' 2>/dev/null"
            )
            if code == 0 and stdout.strip():
                containers_file = self.output_dir / "docker_containers.json"
                # Parse each JSON line
                containers = []
                for line in stdout.strip().split("\n"):
                    if line:
                        try:
                            containers.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass

                containers_file.write_text(json.dumps(containers, indent=2))
                result.extracted_files.append(str(containers_file))
                result.extracted_data["docker_containers"] = containers
                logger.info(f"Extracted {len(containers)} Docker containers")

            # Extract Docker images
            stdout, stderr, code = await self._run_command(
                conn, "docker images --format '{{json .}}' 2>/dev/null"
            )
            if code == 0 and stdout.strip():
                images_file = self.output_dir / "docker_images.json"
                images = []
                for line in stdout.strip().split("\n"):
                    if line:
                        try:
                            images.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass

                images_file.write_text(json.dumps(images, indent=2))
                result.extracted_files.append(str(images_file))
                result.extracted_data["docker_images"] = images
                logger.info(f"Extracted {len(images)} Docker images")

            # Extract Docker volumes
            stdout, stderr, code = await self._run_command(
                conn, "docker volume ls --format '{{json .}}' 2>/dev/null"
            )
            if code == 0 and stdout.strip():
                volumes_file = self.output_dir / "docker_volumes.json"
                volumes = []
                for line in stdout.strip().split("\n"):
                    if line:
                        try:
                            volumes.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass

                volumes_file.write_text(json.dumps(volumes, indent=2))
                result.extracted_files.append(str(volumes_file))
                result.extracted_data["docker_volumes"] = volumes
                logger.info(f"Extracted {len(volumes)} Docker volumes")

        except Exception as e:
            result.warnings.append(f"Failed to extract Docker data: {e}")

    async def _extract_cloud_init_config(self, conn: Any, result: ExtractionResult) -> None:
        """Extract cloud-init configuration.

        Args:
            conn: SSH connection
            result: ExtractionResult to update
        """
        try:
            stdout, stderr, code = await self._run_command(
                conn, "ls /etc/cloud/ 2>/dev/null || echo 'NO_CLOUD_INIT'"
            )
            if code == 0 and "NO_CLOUD_INIT" not in stdout:
                # Extract cloud.cfg
                stdout, stderr, code = await self._run_command(
                    conn, "cat /etc/cloud/cloud.cfg 2>/dev/null"
                )
                if code == 0:
                    cloud_cfg_file = self.output_dir / "cloud_init.cfg"
                    cloud_cfg_file.write_text(stdout)
                    result.extracted_files.append(str(cloud_cfg_file))
                    logger.info("Extracted cloud-init configuration")
        except Exception as e:
            result.warnings.append(f"Failed to extract cloud-init config: {e}")

    async def _extract_update_manager_config(self, conn: Any, result: ExtractionResult) -> None:
        """Extract Ubuntu update manager configuration.

        Args:
            conn: SSH connection
            result: ExtractionResult to update
        """
        try:
            stdout, stderr, code = await self._run_command(
                conn, "cat /etc/update-manager/release-upgrades 2>/dev/null || echo 'NO_CONFIG'"
            )
            if code == 0 and "NO_CONFIG" not in stdout:
                update_mgr_file = self.output_dir / "release_upgrades.cfg"
                update_mgr_file.write_text(stdout)
                result.extracted_files.append(str(update_mgr_file))
                logger.info("Extracted update manager configuration")
        except Exception as e:
            result.warnings.append(f"Failed to extract update manager config: {e}")

    async def generate_replication_steps(
        self, extraction: ExtractionResult
    ) -> List[ReplicationStep]:
        """Generate Ansible playbook for Ubuntu VM replication.

        Extends parent class with Ubuntu-specific steps.

        Args:
            extraction: Previous extraction result

        Returns:
            List of replication steps
        """
        # Get base Linux steps
        steps = await super().generate_replication_steps(extraction)

        # Add Ubuntu-specific steps after package installation
        output_dir = Path(extraction.metadata.get("output_dir", self.output_dir))
        playbook_path = output_dir / "replication_playbook.yml"

        # Regenerate playbook with Ubuntu-specific tasks
        playbook_content = self._generate_ansible_playbook(extraction)
        playbook_path.write_text(playbook_content)

        # Insert snap package installation step after replicate_packages
        packages_idx = next(
            (i for i, s in enumerate(steps) if s.step_id == "replicate_packages"),
            None
        )

        if packages_idx is not None and "snap_packages" in extraction.extracted_data:
            snap_step = ReplicationStep(
                step_id="replicate_snap_packages",
                step_type=StepType.CONFIGURATION,
                description="Install snap packages",
                script_content=playbook_content,
                depends_on=["replicate_packages"],
                is_critical=False,
                metadata={"tags": "snap", "script_path": str(playbook_path)},
            )
            steps.insert(packages_idx + 1, snap_step)

        # Add Docker restoration step if Docker was present
        if extraction.extracted_data.get("docker_installed"):
            docker_step = ReplicationStep(
                step_id="replicate_docker_containers",
                step_type=StepType.CONFIGURATION,
                description="Restore Docker containers (manual review required)",
                script_content=playbook_content,
                depends_on=["replicate_packages"],
                is_critical=False,
                metadata={"tags": "docker", "script_path": str(playbook_path)},
            )
            steps.append(docker_step)

        return steps

    def _generate_ansible_playbook(self, extraction: ExtractionResult) -> str:
        """Generate Ansible playbook for Ubuntu replication.

        Extends parent class playbook with Ubuntu-specific tasks.

        Args:
            extraction: Extraction result with data

        Returns:
            Ansible playbook as YAML string
        """
        # Get base playbook
        base_playbook = super()._generate_ansible_playbook(extraction)

        # Add Ubuntu-specific tasks
        snap_packages = extraction.extracted_data.get("snap_packages", [])
        extraction.extracted_data.get("docker_containers", [])
        docker_installed = extraction.extracted_data.get("docker_installed", False)

        ubuntu_tasks = """
    - name: Install snap packages
      tags: snap
      snap:
        name: "{{ item }}"
        state: present
      loop: {{ snap_packages | to_json }}
      when: snap_packages is defined
      ignore_errors: yes

    - name: Install Docker (if was present on source)
      tags: docker
      apt:
        name: docker.io
        state: present
        update_cache: yes
      when: docker_installed | default(false)

    - name: Ensure Docker service is running
      tags: docker
      service:
        name: docker
        state: started
        enabled: yes
      when: docker_installed | default(false)

    - name: Note about Docker containers
      tags: docker
      debug:
        msg: "Docker containers from source VM have been documented. Manual review required for restoration due to data volumes and configurations."
      when: docker_containers is defined
"""

        # Substitute variables
        ubuntu_tasks = ubuntu_tasks.replace(
            "{{ snap_packages | to_json }}", json.dumps(snap_packages)
        )
        ubuntu_tasks = ubuntu_tasks.replace(
            "{{ docker_installed | default(false) }}",
            str(docker_installed).lower()
        )

        # Insert before handlers section
        if "handlers:" in base_playbook:
            parts = base_playbook.split("  handlers:")
            return parts[0] + ubuntu_tasks + "\n  handlers:" + parts[1]
        else:
            return base_playbook + ubuntu_tasks

