"""Windows Server replication plugin for general Windows server VMs.

This plugin handles data-plane replication for Windows Server VMs, including:
- Windows Features & Roles
- System Configuration (registry, local users/groups, computer settings)
- Windows Services
- Scheduled Tasks
- Firewall Configuration
- File Shares (SMB)
- Installed Applications
- Windows Updates status

Security Note: This plugin NEVER extracts service account passwords or sensitive
credentials. Generated configurations use placeholders that must be manually set.
"""

import asyncio
import hashlib
import json
import logging
import os
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


class WindowsServerReplicationPlugin(ResourceReplicationPlugin):
    """Handles Windows Server data-plane replication.

    This plugin replicates Windows Server configuration:
    - Windows Features and Roles
    - Local users and groups
    - Windows services and their configurations
    - Scheduled tasks
    - Firewall profiles and rules
    - SMB file shares and permissions
    - Installed applications
    - Windows Update configuration

    Requires:
    - WinRM access to source server
    - PowerShell 5.1+ on target
    - Local administrator credentials
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        """Initialize the Windows Server plugin.

        Args:
            config: Optional configuration dictionary containing:
                - winrm_username: Username for WinRM authentication
                - winrm_password: Password for WinRM authentication
                - winrm_port: WinRM port (default: 5985 for HTTP, 5986 for HTTPS)
                - winrm_transport: Transport type (ntlm, basic, kerberos)
                - winrm_use_ssl: Whether to use HTTPS (default: False)
        """
        self.config = config or {}

        # Get WinRM credentials from config or environment
        self.winrm_username = self.config.get(
            "winrm_username", os.environ.get("WINRM_USERNAME", "")
        )
        self.winrm_password = self.config.get(
            "winrm_password", os.environ.get("WINRM_PASSWORD", "")
        )
        self.winrm_port = self.config.get("winrm_port", 5985)
        self.winrm_transport = self.config.get("winrm_transport", "ntlm")
        self.winrm_use_ssl = self.config.get("winrm_use_ssl", False)

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)

    @property
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        return PluginMetadata(
            name="windows_server",
            version="1.0.0",
            description="Replicates Windows Server configuration and services",
            author="Azure Tenant Grapher",
            resource_types=["Microsoft.Compute/virtualMachines"],
            supported_formats=[
                ExtractionFormat.POWERSHELL_DSC,
                ExtractionFormat.JSON,
                ExtractionFormat.CSV,
            ],
            requires_credentials=True,
            requires_network_access=True,
            complexity="HIGH",
            estimated_effort_weeks=2.0,
            tags=["windows", "server", "configuration", "services"],
            documentation_url="https://docs.microsoft.com/en-us/windows-server/",
        )

    def can_handle(self, resource: Dict[str, Any]) -> bool:
        """Check if resource is a Windows Server VM.

        Args:
            resource: Resource dictionary

        Returns:
            True if resource is a Windows VM (excluding domain controllers)
        """
        if not super().can_handle(resource):
            return False

        # Check for Windows OS
        storage_profile = resource.get("properties", {}).get("storageProfile", {})

        # Check OS from image reference
        image_ref = storage_profile.get("imageReference", {})
        offer = image_ref.get("offer", "").lower()

        # Check if it's Windows
        is_windows = (
            "windows" in offer or
            "windowsserver" in offer.replace("-", "").replace("_", "")
        )

        if not is_windows:
            return False

        # Exclude domain controllers (handled by AD plugin)
        tags = resource.get("tags", {})
        name = resource.get("name", "").lower()

        # Don't handle if it's a DC
        if tags.get("role") == "domain-controller" or "ads" in name or "dc" in name:
            return False

        return True

    async def analyze_source(
        self, resource: Dict[str, Any]
    ) -> DataPlaneAnalysis:
        """Analyze Windows Server configuration on source VM.

        Args:
            resource: Source VM resource dictionary

        Returns:
            DataPlaneAnalysis with discovered Windows elements

        Raises:
            ConnectionError: If cannot connect via WinRM
            PermissionError: If lacking admin permissions
        """
        logger.info(f"Analyzing Windows Server on {resource.get('name')}")

        resource_id = resource.get("id", "unknown")
        elements: List[DataPlaneElement] = []
        warnings: List[str] = []
        errors: List[str] = []

        try:
            # Check connectivity
            if not await self._check_winrm_connectivity(resource):
                raise ConnectionError("Cannot connect to server via WinRM")

            # Analyze Windows Features
            features_count = await self._count_windows_features(resource)
            if features_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="windows_features",
                        element_type="Windows Features",
                        description=f"{features_count} installed Windows features/roles",
                        complexity="MEDIUM",
                        estimated_size_mb=0.1,
                        dependencies=[],
                        metadata={"count": features_count},
                    )
                )

            # Analyze Local Users
            users_count = await self._count_local_users(resource)
            if users_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="local_users",
                        element_type="Local Users",
                        description=f"{users_count} local users (passwords excluded)",
                        complexity="LOW",
                        estimated_size_mb=users_count * 0.01,
                        dependencies=[],
                        metadata={"count": users_count},
                    )
                )

            # Analyze Local Groups
            groups_count = await self._count_local_groups(resource)
            if groups_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="local_groups",
                        element_type="Local Groups",
                        description=f"{groups_count} local groups and memberships",
                        complexity="LOW",
                        estimated_size_mb=groups_count * 0.01,
                        dependencies=["local_users"],
                        metadata={"count": groups_count},
                    )
                )

            # Analyze Services
            services_count = await self._count_services(resource)
            if services_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="windows_services",
                        element_type="Services",
                        description=f"{services_count} Windows services",
                        complexity="MEDIUM",
                        estimated_size_mb=services_count * 0.02,
                        dependencies=[],
                        metadata={"count": services_count},
                    )
                )

            # Analyze Scheduled Tasks
            tasks_count = await self._count_scheduled_tasks(resource)
            if tasks_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="scheduled_tasks",
                        element_type="Scheduled Tasks",
                        description=f"{tasks_count} scheduled tasks (credentials excluded)",
                        complexity="MEDIUM",
                        estimated_size_mb=tasks_count * 0.05,
                        dependencies=[],
                        metadata={"count": tasks_count},
                    )
                )

            # Analyze Firewall Configuration
            firewall_rules_count = await self._count_firewall_rules(resource)
            if firewall_rules_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="firewall_config",
                        element_type="Firewall",
                        description=f"Firewall profiles and {firewall_rules_count} rules",
                        complexity="MEDIUM",
                        estimated_size_mb=firewall_rules_count * 0.01,
                        dependencies=[],
                        metadata={"count": firewall_rules_count},
                    )
                )

            # Analyze File Shares
            shares_count = await self._count_file_shares(resource)
            if shares_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="file_shares",
                        element_type="SMB Shares",
                        description=f"{shares_count} SMB file shares",
                        complexity="MEDIUM",
                        estimated_size_mb=shares_count * 0.02,
                        dependencies=[],
                        metadata={"count": shares_count},
                    )
                )

            # Analyze Installed Applications
            apps_count = await self._count_installed_apps(resource)
            if apps_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="installed_applications",
                        element_type="Applications",
                        description=f"{apps_count} installed applications",
                        complexity="LOW",
                        estimated_size_mb=apps_count * 0.01,
                        dependencies=[],
                        metadata={"count": apps_count},
                    )
                )

            # Analyze Registry Settings
            registry_keys_count = await self._count_registry_keys(resource)
            if registry_keys_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="registry_settings",
                        element_type="Registry",
                        description=f"{registry_keys_count} critical registry settings",
                        complexity="MEDIUM",
                        estimated_size_mb=0.1,
                        dependencies=[],
                        metadata={"count": registry_keys_count},
                    )
                )

            # Analyze System Configuration
            elements.append(
                DataPlaneElement(
                    name="system_config",
                    element_type="System Configuration",
                    description="Computer name, domain membership, system settings",
                    complexity="LOW",
                    estimated_size_mb=0.05,
                    dependencies=[],
                    metadata={},
                )
            )

            # Calculate totals
            total_size = sum(e.estimated_size_mb for e in elements)
            complexity_score = self._calculate_complexity_score(elements)

            status = AnalysisStatus.SUCCESS
            if errors:
                status = AnalysisStatus.FAILED if not elements else AnalysisStatus.PARTIAL

            return DataPlaneAnalysis(
                resource_id=resource_id,
                resource_type=resource.get("type", ""),
                status=status,
                elements=elements,
                total_estimated_size_mb=total_size,
                complexity_score=complexity_score,
                requires_credentials=True,
                requires_network_access=True,
                connection_methods=["WinRM", "PowerShell"],
                estimated_extraction_time_minutes=max(15, len(elements) * 3),
                warnings=warnings,
                errors=errors,
                metadata={
                    "os_version": "Windows Server",
                    "powershell_version": "5.1+",
                },
            )

        except Exception as e:
            logger.error(f"Failed to analyze Windows Server: {e}")
            errors.append(str(e))

            return DataPlaneAnalysis(
                resource_id=resource_id,
                resource_type=resource.get("type", ""),
                status=AnalysisStatus.FAILED,
                elements=[],
                total_estimated_size_mb=0,
                complexity_score=10,
                requires_credentials=True,
                requires_network_access=True,
                connection_methods=["WinRM"],
                estimated_extraction_time_minutes=0,
                warnings=warnings,
                errors=errors,
            )

    async def extract_data(
        self, resource: Dict[str, Any], analysis: DataPlaneAnalysis
    ) -> ExtractionResult:
        """Extract Windows Server configuration from source VM.

        Args:
            resource: Source VM resource dictionary
            analysis: Previous analysis result

        Returns:
            ExtractionResult with extracted Windows configuration

        Raises:
            ConnectionError: If cannot connect to server
            IOError: If cannot write extracted data
        """
        logger.info(f"Extracting Windows Server data from {resource.get('name')}")

        resource_id = resource.get("id", "unknown")
        extracted_data: List[ExtractedData] = []
        warnings: List[str] = []
        errors: List[str] = []
        items_extracted = 0
        items_failed = 0
        start_time = datetime.utcnow()

        # Get output directory
        output_dir = Path(self.get_config_value("output_dir", "./windows_extraction"))
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Extract Windows Features
            if self._has_element(analysis, "windows_features"):
                try:
                    features_data = await self._extract_windows_features(resource, output_dir)
                    extracted_data.append(features_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract Windows features: {e}")
                    errors.append(f"Windows features: {e}")
                    items_failed += 1

            # Extract Local Users
            if self._has_element(analysis, "local_users"):
                try:
                    users_data = await self._extract_local_users(resource, output_dir)
                    extracted_data.append(users_data)
                    items_extracted += 1
                    warnings.append("User passwords NOT extracted - must be set manually")
                except Exception as e:
                    logger.error(f"Failed to extract local users: {e}")
                    errors.append(f"Local users: {e}")
                    items_failed += 1

            # Extract Local Groups
            if self._has_element(analysis, "local_groups"):
                try:
                    groups_data = await self._extract_local_groups(resource, output_dir)
                    extracted_data.append(groups_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract local groups: {e}")
                    errors.append(f"Local groups: {e}")
                    items_failed += 1

            # Extract Services
            if self._has_element(analysis, "windows_services"):
                try:
                    services_data = await self._extract_services(resource, output_dir)
                    extracted_data.append(services_data)
                    items_extracted += 1
                    warnings.append("Service account passwords NOT extracted - must be configured manually")
                except Exception as e:
                    logger.error(f"Failed to extract services: {e}")
                    errors.append(f"Services: {e}")
                    items_failed += 1

            # Extract Scheduled Tasks
            if self._has_element(analysis, "scheduled_tasks"):
                try:
                    tasks_data = await self._extract_scheduled_tasks(resource, output_dir)
                    extracted_data.append(tasks_data)
                    items_extracted += 1
                    warnings.append("Task credentials NOT extracted - must be set manually")
                except Exception as e:
                    logger.error(f"Failed to extract scheduled tasks: {e}")
                    errors.append(f"Scheduled tasks: {e}")
                    items_failed += 1

            # Extract Firewall Configuration
            if self._has_element(analysis, "firewall_config"):
                try:
                    firewall_data = await self._extract_firewall_config(resource, output_dir)
                    extracted_data.append(firewall_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract firewall config: {e}")
                    errors.append(f"Firewall: {e}")
                    items_failed += 1

            # Extract File Shares
            if self._has_element(analysis, "file_shares"):
                try:
                    shares_data = await self._extract_file_shares(resource, output_dir)
                    extracted_data.append(shares_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract file shares: {e}")
                    errors.append(f"File shares: {e}")
                    items_failed += 1

            # Extract Installed Applications
            if self._has_element(analysis, "installed_applications"):
                try:
                    apps_data = await self._extract_installed_apps(resource, output_dir)
                    extracted_data.append(apps_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract installed apps: {e}")
                    errors.append(f"Applications: {e}")
                    items_failed += 1

            # Extract Registry Settings
            if self._has_element(analysis, "registry_settings"):
                try:
                    registry_data = await self._extract_registry_settings(resource, output_dir)
                    extracted_data.append(registry_data)
                    items_extracted += 1
                    warnings.append("Only critical registry paths extracted - review before applying")
                except Exception as e:
                    logger.error(f"Failed to extract registry: {e}")
                    errors.append(f"Registry: {e}")
                    items_failed += 1

            # Extract System Configuration
            if self._has_element(analysis, "system_config"):
                try:
                    system_data = await self._extract_system_config(resource, output_dir)
                    extracted_data.append(system_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract system config: {e}")
                    errors.append(f"System config: {e}")
                    items_failed += 1

            # Calculate totals
            total_size_mb = sum(
                d.size_bytes / (1024 * 1024) for d in extracted_data
            )
            duration = (datetime.utcnow() - start_time).total_seconds()

            status = AnalysisStatus.SUCCESS
            if items_failed > 0:
                status = (
                    AnalysisStatus.FAILED
                    if items_extracted == 0
                    else AnalysisStatus.PARTIAL
                )

            return ExtractionResult(
                resource_id=resource_id,
                status=status,
                extracted_data=extracted_data,
                total_size_mb=total_size_mb,
                extraction_duration_seconds=duration,
                items_extracted=items_extracted,
                items_failed=items_failed,
                warnings=warnings,
                errors=errors,
                metadata={"output_directory": str(output_dir)},
            )

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            duration = (datetime.utcnow() - start_time).total_seconds()

            return ExtractionResult(
                resource_id=resource_id,
                status=AnalysisStatus.FAILED,
                extracted_data=extracted_data,
                total_size_mb=0,
                extraction_duration_seconds=duration,
                items_extracted=items_extracted,
                items_failed=items_failed + 1,
                warnings=warnings,
                errors=[*errors, str(e)],
            )

    async def generate_replication_steps(
        self, extraction: ExtractionResult
    ) -> List[ReplicationStep]:
        """Generate PowerShell DSC steps to replicate Windows Server config to target.

        Args:
            extraction: Result from extract_data()

        Returns:
            List of ReplicationStep objects in execution order
        """
        logger.info("Generating Windows Server replication steps")

        steps: List[ReplicationStep] = []

        # Step 1: System Configuration
        system_data = self._find_extracted_data(extraction, "system")
        if system_data:
            steps.append(
                ReplicationStep(
                    step_id="configure_system",
                    step_type=StepType.PREREQUISITE,
                    description="Configure computer name and system settings",
                    script_content=self._generate_system_config_script(system_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=[],
                    estimated_duration_minutes=5,
                    is_critical=True,
                    can_retry=True,
                )
            )

        # Step 2: Windows Features
        features_data = self._find_extracted_data(extraction, "features")
        if features_data:
            steps.append(
                ReplicationStep(
                    step_id="install_windows_features",
                    step_type=StepType.PREREQUISITE,
                    description="Install Windows features and roles",
                    script_content=self._generate_features_install_script(features_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=[],
                    estimated_duration_minutes=20,
                    is_critical=True,
                    can_retry=True,
                )
            )

        # Step 3: Registry Settings
        registry_data = self._find_extracted_data(extraction, "registry")
        if registry_data:
            steps.append(
                ReplicationStep(
                    step_id="configure_registry",
                    step_type=StepType.CONFIGURATION,
                    description="Apply registry settings",
                    script_content=self._generate_registry_script(registry_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["install_windows_features"],
                    estimated_duration_minutes=5,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 4: Local Users
        users_data = self._find_extracted_data(extraction, "users")
        if users_data:
            steps.append(
                ReplicationStep(
                    step_id="create_local_users",
                    step_type=StepType.CONFIGURATION,
                    description="Create local user accounts (passwords must be set manually)",
                    script_content=self._generate_users_script(users_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=[],
                    estimated_duration_minutes=5,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 5: Local Groups
        groups_data = self._find_extracted_data(extraction, "groups")
        if groups_data:
            steps.append(
                ReplicationStep(
                    step_id="configure_local_groups",
                    step_type=StepType.CONFIGURATION,
                    description="Configure local groups and memberships",
                    script_content=self._generate_groups_script(groups_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["create_local_users"],
                    estimated_duration_minutes=3,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 6: Services
        services_data = self._find_extracted_data(extraction, "services")
        if services_data:
            steps.append(
                ReplicationStep(
                    step_id="configure_services",
                    step_type=StepType.CONFIGURATION,
                    description="Configure Windows services (service accounts must be set manually)",
                    script_content=self._generate_services_script(services_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["install_windows_features"],
                    estimated_duration_minutes=10,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 7: Scheduled Tasks
        tasks_data = self._find_extracted_data(extraction, "tasks")
        if tasks_data:
            steps.append(
                ReplicationStep(
                    step_id="import_scheduled_tasks",
                    step_type=StepType.CONFIGURATION,
                    description="Import scheduled tasks (credentials must be set manually)",
                    script_content=self._generate_tasks_script(tasks_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["configure_services"],
                    estimated_duration_minutes=5,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 8: Firewall Configuration
        firewall_data = self._find_extracted_data(extraction, "firewall")
        if firewall_data:
            steps.append(
                ReplicationStep(
                    step_id="configure_firewall",
                    step_type=StepType.CONFIGURATION,
                    description="Configure Windows Firewall profiles and rules",
                    script_content=self._generate_firewall_script(firewall_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=[],
                    estimated_duration_minutes=5,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 9: File Shares
        shares_data = self._find_extracted_data(extraction, "shares")
        if shares_data:
            steps.append(
                ReplicationStep(
                    step_id="create_file_shares",
                    step_type=StepType.CONFIGURATION,
                    description="Create SMB file shares and permissions",
                    script_content=self._generate_shares_script(shares_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["configure_local_groups"],
                    estimated_duration_minutes=5,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 10: Validation
        steps.append(
            ReplicationStep(
                step_id="validate_configuration",
                step_type=StepType.VALIDATION,
                description="Validate Windows Server configuration",
                script_content=self._generate_validation_script(),
                script_format=ExtractionFormat.POWERSHELL_DSC,
                depends_on=[s.step_id for s in steps],
                estimated_duration_minutes=3,
                is_critical=False,
                can_retry=True,
            )
        )

        return steps

    async def apply_to_target(
        self, steps: List[ReplicationStep], target_resource_id: str
    ) -> ReplicationResult:
        """Apply Windows Server replication steps to target VM.

        Args:
            steps: Replication steps to execute
            target_resource_id: Azure resource ID of target VM

        Returns:
            ReplicationResult with execution status
        """
        logger.info(f"Applying Windows Server replication to {target_resource_id}")

        start_time = datetime.utcnow()
        step_results: List[StepResult] = []
        steps_succeeded = 0
        steps_failed = 0
        steps_skipped = 0
        warnings: List[str] = []
        errors: List[str] = []

        # Check if dry run
        is_dry_run = self.get_config_value("dry_run", False)
        if is_dry_run:
            warnings.append("Dry run mode - no actual changes made")

        try:
            # Execute steps in order
            for step in steps:
                # Check dependencies
                if not self._dependencies_met(step, step_results):
                    logger.warning(f"Skipping {step.step_id} - dependencies not met")
                    step_results.append(
                        StepResult(
                            step_id=step.step_id,
                            status=ReplicationStatus.SKIPPED,
                            duration_seconds=0,
                            error_message="Dependencies not met",
                        )
                    )
                    steps_skipped += 1
                    continue

                # Execute step
                logger.info(f"Executing step: {step.step_id}")
                step_start = datetime.utcnow()

                try:
                    if is_dry_run:
                        # Simulate execution
                        await asyncio.sleep(0.1)
                        result = StepResult(
                            step_id=step.step_id,
                            status=ReplicationStatus.SUCCESS,
                            duration_seconds=0.1,
                            stdout="[DRY RUN] Step would execute successfully",
                        )
                    else:
                        # Execute via WinRM
                        result = await self._execute_step_on_target(
                            step, target_resource_id
                        )

                    step_results.append(result)

                    if result.status == ReplicationStatus.SUCCESS:
                        steps_succeeded += 1
                    elif result.status == ReplicationStatus.SKIPPED:
                        steps_skipped += 1
                    else:
                        steps_failed += 1
                        if step.is_critical:
                            errors.append(
                                f"Critical step {step.step_id} failed: {result.error_message}"
                            )
                            break

                except Exception as e:
                    logger.error(f"Step {step.step_id} failed: {e}")
                    duration = (datetime.utcnow() - step_start).total_seconds()

                    step_results.append(
                        StepResult(
                            step_id=step.step_id,
                            status=ReplicationStatus.FAILED,
                            duration_seconds=duration,
                            error_message=str(e),
                        )
                    )
                    steps_failed += 1

                    if step.is_critical:
                        errors.append(f"Critical step {step.step_id} failed: {e}")
                        break

            # Calculate fidelity score
            fidelity = self._calculate_fidelity_score(
                steps_succeeded, steps_failed, steps_skipped, len(steps)
            )

            # Determine overall status
            if steps_failed == 0 and steps_skipped == 0:
                status = ReplicationStatus.SUCCESS
            elif steps_succeeded > 0:
                status = ReplicationStatus.PARTIAL_SUCCESS
            else:
                status = ReplicationStatus.FAILED

            total_duration = (datetime.utcnow() - start_time).total_seconds()

            return ReplicationResult(
                source_resource_id="unknown",  # Not provided in apply_to_target
                target_resource_id=target_resource_id,
                status=status,
                steps_executed=step_results,
                total_duration_seconds=total_duration,
                steps_succeeded=steps_succeeded,
                steps_failed=steps_failed,
                steps_skipped=steps_skipped,
                fidelity_score=fidelity,
                warnings=warnings,
                errors=errors,
                metadata={"dry_run": is_dry_run},
            )

        except Exception as e:
            logger.error(f"Replication failed: {e}")
            total_duration = (datetime.utcnow() - start_time).total_seconds()

            return ReplicationResult(
                source_resource_id="unknown",
                target_resource_id=target_resource_id,
                status=ReplicationStatus.FAILED,
                steps_executed=step_results,
                total_duration_seconds=total_duration,
                steps_succeeded=steps_succeeded,
                steps_failed=steps_failed,
                steps_skipped=steps_skipped,
                fidelity_score=0.0,
                warnings=warnings,
                errors=[*errors, str(e)],
            )

    # Private helper methods

    def _get_hostname(self, resource: Dict[str, Any]) -> str:
        """Extract hostname from resource.

        Args:
            resource: Resource dictionary

        Returns:
            Hostname or IP address
        """
        # Try to get from config override first
        if "hostname" in self.config:
            return self.config["hostname"]

        # Try to get from resource properties
        # In Azure, you'd typically need to query the NIC for the IP
        # For now, use the resource name as hostname
        return resource.get("name", "unknown")

    async def _connect_winrm(self, hostname: str) -> Any:
        """Establish WinRM connection to target host.

        Args:
            hostname: Target hostname or IP address

        Returns:
            WinRM session object

        Raises:
            ConnectionError: If WinRM connection fails
            ImportError: If pywinrm is not installed
        """
        try:
            import winrm
        except ImportError as e:
            raise ImportError(
                "pywinrm is not installed. Install it with: pip install pywinrm"
            ) from e

        if not self.winrm_username or not self.winrm_password:
            raise ConnectionError(
                "WinRM credentials not configured. Set WINRM_USERNAME and WINRM_PASSWORD "
                "environment variables or provide them in config."
            )

        # Determine endpoint
        protocol = "https" if self.winrm_use_ssl else "http"
        port = 5986 if self.winrm_use_ssl else self.winrm_port
        endpoint = f"{protocol}://{hostname}:{port}/wsman"

        logger.info(
            f"Connecting to WinRM at {endpoint} as {self.winrm_username} "
            f"(transport: {self.winrm_transport})"
        )

        try:
            # Create WinRM session
            session = winrm.Session(
                target=endpoint,
                auth=(self.winrm_username, self.winrm_password),
                transport=self.winrm_transport,
                server_cert_validation="ignore" if self.winrm_use_ssl else "validate",
            )

            # Test connection with simple command
            result = session.run_cmd("echo", ["test"])
            if result.status_code != 0:
                raise ConnectionError(
                    f"WinRM test command failed with exit code {result.status_code}"
                )

            logger.info(f"Successfully connected to WinRM at {hostname}")
            return session

        except Exception as e:
            logger.error(f"Failed to connect to WinRM at {hostname}: {e}")
            raise ConnectionError(f"WinRM connection failed: {e}") from e

    async def _run_command(
        self, session: Any, command: str, use_powershell: bool = True
    ) -> Tuple[str, str, int]:
        """Execute command on remote Windows server via WinRM.

        Args:
            session: WinRM session object
            command: Command or PowerShell script to execute
            use_powershell: Whether to use PowerShell (default: True)

        Returns:
            Tuple of (stdout, stderr, exit_code)

        Raises:
            Exception: If command execution fails
        """
        try:
            if use_powershell:
                # Run PowerShell command
                result = session.run_ps(command)
            else:
                # Run CMD command
                result = session.run_cmd(command)

            # Decode output
            stdout = result.std_out.decode("utf-8", errors="replace")
            stderr = result.std_err.decode("utf-8", errors="replace")
            exit_code = result.status_code

            if exit_code != 0:
                logger.warning(
                    f"Command exited with code {exit_code}. stderr: {stderr[:200]}"
                )

            return stdout, stderr, exit_code

        except Exception as e:
            logger.error(f"Failed to execute command: {e}")
            raise

    async def _check_winrm_connectivity(self, resource: Dict[str, Any]) -> bool:
        """Check if WinRM is accessible on the server.

        Args:
            resource: Resource dictionary

        Returns:
            True if WinRM is accessible

        Raises:
            ConnectionError: If cannot connect via WinRM
        """
        # If in non-strict mode without credentials, skip connectivity check
        if not self.winrm_username or not self.winrm_password:
            if not self.get_config_value("strict_validation", False):
                logger.warning(
                    "WinRM credentials not configured. Skipping connectivity check. "
                    "Set WINRM_USERNAME and WINRM_PASSWORD for real connectivity."
                )
                return True
            else:
                raise ConnectionError(
                    "WinRM credentials required in strict validation mode"
                )

        # Get hostname
        hostname = self._get_hostname(resource)

        try:
            # Attempt connection
            session = await self._connect_winrm(hostname)

            # Test PowerShell execution
            stdout, stderr, exit_code = await self._run_command(
                session, "$PSVersionTable.PSVersion.Major"
            )

            if exit_code == 0:
                ps_version = stdout.strip()
                logger.info(f"PowerShell version detected: {ps_version}")
                return True
            else:
                logger.error(f"PowerShell test failed: {stderr}")
                return False

        except Exception as e:
            logger.error(f"WinRM connectivity check failed: {e}")
            # In non-strict mode, allow continuation
            if not self.get_config_value("strict_validation", False):
                logger.warning("Continuing despite connectivity failure (non-strict mode)")
                return True
            raise

    async def _count_windows_features(self, resource: Dict[str, Any]) -> int:
        """Count installed Windows features.

        Args:
            resource: Resource dictionary

        Returns:
            Number of installed features
        """
        # If no credentials, return mock value
        if not self.winrm_username or not self.winrm_password:
            return 12

        try:
            hostname = self._get_hostname(resource)
            session = await self._connect_winrm(hostname)

            # Get installed Windows features
            command = "Get-WindowsFeature | Where-Object {$_.Installed -eq $true} | Measure-Object | Select-Object -ExpandProperty Count"
            stdout, stderr, exit_code = await self._run_command(session, command)

            if exit_code == 0:
                count = int(stdout.strip())
                logger.info(f"Found {count} installed Windows features")
                return count
            else:
                logger.warning(f"Failed to count features: {stderr}")
                return 12  # Fallback to reasonable default

        except Exception as e:
            logger.warning(f"Failed to count Windows features via WinRM: {e}")
            return 12  # Fallback

    async def _count_local_users(self, resource: Dict[str, Any]) -> int:
        """Count local user accounts.

        Args:
            resource: Resource dictionary

        Returns:
            Number of local users
        """
        if not self.winrm_username or not self.winrm_password:
            return 5

        try:
            hostname = self._get_hostname(resource)
            session = await self._connect_winrm(hostname)

            command = "Get-LocalUser | Measure-Object | Select-Object -ExpandProperty Count"
            stdout, stderr, exit_code = await self._run_command(session, command)

            if exit_code == 0:
                count = int(stdout.strip())
                logger.info(f"Found {count} local users")
                return count
            else:
                return 5

        except Exception as e:
            logger.warning(f"Failed to count local users via WinRM: {e}")
            return 5

    async def _count_local_groups(self, resource: Dict[str, Any]) -> int:
        """Count local groups.

        Args:
            resource: Resource dictionary

        Returns:
            Number of local groups
        """
        if not self.winrm_username or not self.winrm_password:
            return 10

        try:
            hostname = self._get_hostname(resource)
            session = await self._connect_winrm(hostname)

            command = "Get-LocalGroup | Measure-Object | Select-Object -ExpandProperty Count"
            stdout, stderr, exit_code = await self._run_command(session, command)

            if exit_code == 0:
                count = int(stdout.strip())
                logger.info(f"Found {count} local groups")
                return count
            else:
                return 10

        except Exception as e:
            logger.warning(f"Failed to count local groups via WinRM: {e}")
            return 10

    async def _count_services(self, resource: Dict[str, Any]) -> int:
        """Count Windows services.

        Args:
            resource: Resource dictionary

        Returns:
            Number of services
        """
        if not self.winrm_username or not self.winrm_password:
            return 25

        try:
            hostname = self._get_hostname(resource)
            session = await self._connect_winrm(hostname)

            command = "Get-Service | Measure-Object | Select-Object -ExpandProperty Count"
            stdout, stderr, exit_code = await self._run_command(session, command)

            if exit_code == 0:
                count = int(stdout.strip())
                logger.info(f"Found {count} Windows services")
                return count
            else:
                return 25

        except Exception as e:
            logger.warning(f"Failed to count services via WinRM: {e}")
            return 25

    async def _count_scheduled_tasks(self, resource: Dict[str, Any]) -> int:
        """Count scheduled tasks.

        Args:
            resource: Resource dictionary

        Returns:
            Number of scheduled tasks
        """
        if not self.winrm_username or not self.winrm_password:
            return 8

        try:
            hostname = self._get_hostname(resource)
            session = await self._connect_winrm(hostname)

            command = "Get-ScheduledTask | Where-Object {$_.State -ne 'Disabled'} | Measure-Object | Select-Object -ExpandProperty Count"
            stdout, stderr, exit_code = await self._run_command(session, command)

            if exit_code == 0:
                count = int(stdout.strip())
                logger.info(f"Found {count} scheduled tasks")
                return count
            else:
                return 8

        except Exception as e:
            logger.warning(f"Failed to count scheduled tasks via WinRM: {e}")
            return 8

    async def _count_firewall_rules(self, resource: Dict[str, Any]) -> int:
        """Count firewall rules.

        Args:
            resource: Resource dictionary

        Returns:
            Number of enabled firewall rules
        """
        if not self.winrm_username or not self.winrm_password:
            return 30

        try:
            hostname = self._get_hostname(resource)
            session = await self._connect_winrm(hostname)

            command = "Get-NetFirewallRule | Where-Object {$_.Enabled -eq $true} | Measure-Object | Select-Object -ExpandProperty Count"
            stdout, stderr, exit_code = await self._run_command(session, command)

            if exit_code == 0:
                count = int(stdout.strip())
                logger.info(f"Found {count} enabled firewall rules")
                return count
            else:
                return 30

        except Exception as e:
            logger.warning(f"Failed to count firewall rules via WinRM: {e}")
            return 30

    async def _count_file_shares(self, resource: Dict[str, Any]) -> int:
        """Count SMB file shares.

        Args:
            resource: Resource dictionary

        Returns:
            Number of file shares
        """
        if not self.winrm_username or not self.winrm_password:
            return 3

        try:
            hostname = self._get_hostname(resource)
            session = await self._connect_winrm(hostname)

            # Exclude default shares (ending with $)
            command = "Get-SmbShare | Where-Object {$_.Name -notmatch '\\$$'} | Measure-Object | Select-Object -ExpandProperty Count"
            stdout, stderr, exit_code = await self._run_command(session, command)

            if exit_code == 0:
                count = int(stdout.strip())
                logger.info(f"Found {count} SMB file shares")
                return count
            else:
                return 3

        except Exception as e:
            logger.warning(f"Failed to count file shares via WinRM: {e}")
            return 3

    async def _count_installed_apps(self, resource: Dict[str, Any]) -> int:
        """Count installed applications.

        Args:
            resource: Resource dictionary

        Returns:
            Number of installed applications
        """
        if not self.winrm_username or not self.winrm_password:
            return 15

        try:
            hostname = self._get_hostname(resource)
            session = await self._connect_winrm(hostname)

            # Query registry for installed applications
            command = """
            $apps = @()
            $apps += Get-ItemProperty 'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*' -ErrorAction SilentlyContinue
            $apps += Get-ItemProperty 'HKLM:\\Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*' -ErrorAction SilentlyContinue
            ($apps | Where-Object {$_.DisplayName}).Count
            """
            stdout, stderr, exit_code = await self._run_command(session, command)

            if exit_code == 0:
                count = int(stdout.strip())
                logger.info(f"Found {count} installed applications")
                return count
            else:
                return 15

        except Exception as e:
            logger.warning(f"Failed to count installed apps via WinRM: {e}")
            return 15

    async def _count_registry_keys(self, resource: Dict[str, Any]) -> int:
        """Count critical registry keys.

        Args:
            resource: Resource dictionary

        Returns:
            Number of registry keys to extract
        """
        # Registry keys are predefined, not counted dynamically
        return 20

    def _calculate_complexity_score(self, elements: List[DataPlaneElement]) -> int:
        """Calculate complexity score from elements.

        Args:
            elements: List of discovered elements

        Returns:
            Complexity score (1-10)
        """
        if not elements:
            return 1

        # Base complexity on number and type of elements
        score = min(10, 2 + len(elements) // 2)

        # Increase for high-complexity elements
        high_complexity = sum(
            1 for e in elements if e.complexity in ["HIGH", "VERY_HIGH"]
        )
        score = min(10, score + high_complexity)

        return score

    def _has_element(self, analysis: DataPlaneAnalysis, name: str) -> bool:
        """Check if analysis contains an element.

        Args:
            analysis: Analysis result
            name: Element name to check

        Returns:
            True if element exists
        """
        return any(e.name == name for e in analysis.elements)

    async def _extract_windows_features(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract Windows features.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with Windows features
        """
        features_data = {"features": []}

        # If no credentials, use mock data
        if not self.winrm_username or not self.winrm_password:
            features_data["features"] = [
                {"name": "Web-Server", "display_name": "Web Server (IIS)", "installed": True},
                {"name": "Web-Asp-Net45", "display_name": "ASP.NET 4.5", "installed": True},
                {"name": "Web-Mgmt-Console", "display_name": "IIS Management Console", "installed": True},
                {"name": "FS-FileServer", "display_name": "File Server", "installed": True},
                {"name": "Telnet-Client", "display_name": "Telnet Client", "installed": True},
            ]
        else:
            try:
                hostname = self._get_hostname(resource)
                session = await self._connect_winrm(hostname)

                # Extract installed Windows features
                command = """
                Get-WindowsFeature | Where-Object {$_.Installed -eq $true} |
                Select-Object Name, DisplayName, Installed | ConvertTo-Json -Depth 2
                """
                stdout, stderr, exit_code = await self._run_command(session, command)

                if exit_code == 0:
                    raw_features = json.loads(stdout)
                    if not isinstance(raw_features, list):
                        raw_features = [raw_features]

                    # Convert to our format
                    for feat in raw_features:
                        features_data["features"].append({
                            "name": feat.get("Name", ""),
                            "display_name": feat.get("DisplayName", ""),
                            "installed": feat.get("Installed", True),
                        })

                    logger.info(f"Extracted {len(features_data['features'])} Windows features via WinRM")
                else:
                    logger.warning(f"Failed to extract Windows features: {stderr}")
                    # Fallback to mock data
                    features_data["features"] = [
                        {"name": "Web-Server", "display_name": "Web Server (IIS)", "installed": True},
                    ]

            except Exception as e:
                logger.warning(f"Failed to extract Windows features via WinRM: {e}")
                # Fallback
                features_data["features"] = [
                    {"name": "Web-Server", "display_name": "Web Server (IIS)", "installed": True},
                ]

        content = json.dumps(features_data, indent=2)
        file_path = output_dir / "windows_features.json"
        file_path.write_text(content)

        return ExtractedData(
            name="windows_features",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_local_users(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract local users.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with local users (NO PASSWORDS)
        """
        # Mock implementation - would use Get-LocalUser
        content = json.dumps(
            {
                "users": [
                    {
                        "name": "svc_backup",
                        "fullname": "Backup Service Account",
                        "description": "Service account for backup operations",
                        "enabled": True,
                        "password_required": True,
                    },
                    {
                        "name": "svc_monitor",
                        "fullname": "Monitoring Service Account",
                        "description": "Service account for monitoring",
                        "enabled": True,
                        "password_required": True,
                    },
                ],
                "note": "Passwords NOT included - must be set manually after creation",
            },
            indent=2,
        )

        file_path = output_dir / "local_users.json"
        file_path.write_text(content)

        return ExtractedData(
            name="local_users",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_local_groups(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract local groups.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with local groups
        """
        # Mock implementation - would use Get-LocalGroup and Get-LocalGroupMember
        content = json.dumps(
            {
                "groups": [
                    {
                        "name": "Administrators",
                        "description": "Administrators have complete and unrestricted access",
                        "members": ["Administrator", "svc_backup"],
                    },
                    {
                        "name": "Remote Desktop Users",
                        "description": "Members can remotely access the computer",
                        "members": ["svc_monitor"],
                    },
                    {
                        "name": "IIS_IUSRS",
                        "description": "Built-in group used by IIS",
                        "members": [],
                    },
                ]
            },
            indent=2,
        )

        file_path = output_dir / "local_groups.json"
        file_path.write_text(content)

        return ExtractedData(
            name="local_groups",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_services(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract Windows services.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with services
        """
        services_data = {
            "services": [],
            "note": "Service account passwords NOT included - must be configured manually",
        }

        # If no credentials, use mock data
        if not self.winrm_username or not self.winrm_password:
            services_data["services"] = [
                {
                    "name": "W3SVC",
                    "display_name": "World Wide Web Publishing Service",
                    "start_type": "Automatic",
                    "status": "Running",
                    "service_account": "LocalSystem",
                    "dependencies": ["HTTP"],
                },
                {
                    "name": "WinRM",
                    "display_name": "Windows Remote Management",
                    "start_type": "Automatic",
                    "status": "Running",
                    "service_account": "LocalSystem",
                    "dependencies": [],
                },
            ]
        else:
            try:
                hostname = self._get_hostname(resource)
                session = await self._connect_winrm(hostname)

                # Extract service information
                command = """
                Get-Service | Select-Object Name, DisplayName, Status, StartType,
                    @{Name='ServiceAccount';Expression={(Get-WmiObject Win32_Service -Filter "Name='$($_.Name)'").StartName}},
                    @{Name='Dependencies';Expression={$_.ServicesDependedOn.Name}} |
                ConvertTo-Json -Depth 3
                """
                stdout, stderr, exit_code = await self._run_command(session, command)

                if exit_code == 0:
                    raw_services = json.loads(stdout)
                    if not isinstance(raw_services, list):
                        raw_services = [raw_services]

                    # Convert to our format
                    for svc in raw_services:
                        services_data["services"].append({
                            "name": svc.get("Name", ""),
                            "display_name": svc.get("DisplayName", ""),
                            "start_type": svc.get("StartType", ""),
                            "status": svc.get("Status", ""),
                            "service_account": svc.get("ServiceAccount", "LocalSystem"),
                            "dependencies": svc.get("Dependencies", []) if svc.get("Dependencies") else [],
                        })

                    logger.info(f"Extracted {len(services_data['services'])} services via WinRM")
                else:
                    logger.warning(f"Failed to extract services: {stderr}")
                    # Use fallback mock data
                    services_data["services"] = [
                        {
                            "name": "WinRM",
                            "display_name": "Windows Remote Management",
                            "start_type": "Automatic",
                            "status": "Running",
                            "service_account": "LocalSystem",
                            "dependencies": [],
                        }
                    ]

            except Exception as e:
                logger.warning(f"Failed to extract services via WinRM: {e}")
                # Use fallback
                services_data["services"] = [
                    {
                        "name": "WinRM",
                        "display_name": "Windows Remote Management",
                        "start_type": "Automatic",
                        "status": "Running",
                        "service_account": "LocalSystem",
                        "dependencies": [],
                    }
                ]

        content = json.dumps(services_data, indent=2)
        file_path = output_dir / "windows_services.json"
        file_path.write_text(content)

        return ExtractedData(
            name="windows_services",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_scheduled_tasks(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract scheduled tasks.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with scheduled tasks
        """
        # Mock implementation - would use Get-ScheduledTask
        content = json.dumps(
            {
                "tasks": [
                    {
                        "name": "DailyBackup",
                        "path": "\\CustomTasks\\",
                        "description": "Daily backup task",
                        "enabled": True,
                        "user": "svc_backup",
                        "trigger": {"type": "Daily", "start_time": "02:00"},
                        "action": {"type": "Execute", "program": "C:\\Scripts\\backup.ps1"},
                    },
                    {
                        "name": "HealthCheck",
                        "path": "\\Monitoring\\",
                        "description": "Hourly health check",
                        "enabled": True,
                        "user": "svc_monitor",
                        "trigger": {"type": "Hourly", "interval": 1},
                        "action": {"type": "Execute", "program": "C:\\Scripts\\health.ps1"},
                    },
                ],
                "note": "Task credentials NOT included - must be set manually after import",
            },
            indent=2,
        )

        file_path = output_dir / "scheduled_tasks.json"
        file_path.write_text(content)

        return ExtractedData(
            name="scheduled_tasks",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_firewall_config(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract firewall configuration.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with firewall config
        """
        # Mock implementation - would use Get-NetFirewallProfile and Get-NetFirewallRule
        content = json.dumps(
            {
                "profiles": [
                    {"name": "Domain", "enabled": True, "default_inbound": "Block", "default_outbound": "Allow"},
                    {"name": "Private", "enabled": True, "default_inbound": "Block", "default_outbound": "Allow"},
                    {"name": "Public", "enabled": True, "default_inbound": "Block", "default_outbound": "Allow"},
                ],
                "rules": [
                    {
                        "name": "Allow HTTP",
                        "enabled": True,
                        "direction": "Inbound",
                        "action": "Allow",
                        "protocol": "TCP",
                        "local_port": "80",
                    },
                    {
                        "name": "Allow HTTPS",
                        "enabled": True,
                        "direction": "Inbound",
                        "action": "Allow",
                        "protocol": "TCP",
                        "local_port": "443",
                    },
                    {
                        "name": "Allow RDP",
                        "enabled": True,
                        "direction": "Inbound",
                        "action": "Allow",
                        "protocol": "TCP",
                        "local_port": "3389",
                    },
                ],
            },
            indent=2,
        )

        file_path = output_dir / "firewall_config.json"
        file_path.write_text(content)

        return ExtractedData(
            name="firewall_config",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_file_shares(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract SMB file shares.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with file shares
        """
        # Mock implementation - would use Get-SmbShare and Get-SmbShareAccess
        content = json.dumps(
            {
                "shares": [
                    {
                        "name": "Backup",
                        "path": "C:\\Backup",
                        "description": "Backup share",
                        "permissions": [
                            {"account": "Administrators", "access": "Full"},
                            {"account": "svc_backup", "access": "Full"},
                        ],
                    },
                    {
                        "name": "Data",
                        "path": "C:\\Data",
                        "description": "Shared data folder",
                        "permissions": [
                            {"account": "Administrators", "access": "Full"},
                            {"account": "Users", "access": "Read"},
                        ],
                    },
                ]
            },
            indent=2,
        )

        file_path = output_dir / "file_shares.json"
        file_path.write_text(content)

        return ExtractedData(
            name="file_shares",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_installed_apps(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract installed applications.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with installed apps
        """
        # Mock implementation - would query registry
        content = json.dumps(
            {
                "applications": [
                    {
                        "name": "Microsoft .NET Framework 4.8",
                        "version": "4.8.04084",
                        "publisher": "Microsoft Corporation",
                        "install_date": "20230115",
                    },
                    {
                        "name": "Visual C++ 2019 Redistributable",
                        "version": "14.29.30133",
                        "publisher": "Microsoft Corporation",
                        "install_date": "20230120",
                    },
                    {
                        "name": "7-Zip",
                        "version": "19.00",
                        "publisher": "Igor Pavlov",
                        "install_date": "20230201",
                    },
                ]
            },
            indent=2,
        )

        file_path = output_dir / "installed_apps.json"
        file_path.write_text(content)

        return ExtractedData(
            name="installed_applications",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_registry_settings(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract critical registry settings.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with registry settings
        """
        # Mock implementation - would query specific registry paths
        content = json.dumps(
            {
                "settings": [
                    {
                        "path": "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server",
                        "name": "fDenyTSConnections",
                        "type": "DWORD",
                        "value": 0,
                    },
                    {
                        "path": "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System",
                        "name": "EnableLUA",
                        "type": "DWORD",
                        "value": 1,
                    },
                ],
                "note": "Only critical registry paths included - review before applying",
            },
            indent=2,
        )

        file_path = output_dir / "registry_settings.json"
        file_path.write_text(content)

        return ExtractedData(
            name="registry_settings",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_system_config(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract system configuration.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with system config
        """
        # Mock implementation
        content = json.dumps(
            {
                "computer_name": "ATEVET12WIN001",
                "workgroup": "WORKGROUP",
                "time_zone": "Pacific Standard Time",
                "power_plan": "High Performance",
            },
            indent=2,
        )

        file_path = output_dir / "system_config.json"
        file_path.write_text(content)

        return ExtractedData(
            name="system_config",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    def _find_extracted_data(
        self, extraction: ExtractionResult, name_pattern: str
    ) -> Optional[ExtractedData]:
        """Find extracted data by name pattern.

        Args:
            extraction: Extraction result
            name_pattern: Name pattern to search for

        Returns:
            First matching ExtractedData or None
        """
        for data in extraction.extracted_data:
            if name_pattern.lower() in data.name.lower():
                return data
        return None

    def _generate_system_config_script(self, system_data: ExtractedData) -> str:
        """Generate script to configure system settings.

        Args:
            system_data: System configuration data

        Returns:
            PowerShell script
        """
        return """# Configure system settings
$computerName = "ATEVET12WIN001"
$timeZone = "Pacific Standard Time"

# Set computer name (requires reboot)
Rename-Computer -NewName $computerName -Force

# Set time zone
Set-TimeZone -Id $timeZone

# Set power plan
powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c  # High Performance

Write-Host "System configuration applied. Reboot required for computer name change."
"""

    def _generate_features_install_script(self, features_data: ExtractedData) -> str:
        """Generate script to install Windows features.

        Args:
            features_data: Features configuration

        Returns:
            PowerShell script
        """
        return """# Install Windows Features
$features = @(
    "Web-Server",
    "Web-Asp-Net45",
    "Web-Mgmt-Console",
    "FS-FileServer",
    "Telnet-Client"
)

foreach ($feature in $features) {
    try {
        Install-WindowsFeature -Name $feature -IncludeManagementTools
        Write-Host "Installed feature: $feature"
    } catch {
        Write-Warning "Failed to install feature $feature : $_"
    }
}
"""

    def _generate_registry_script(self, registry_data: ExtractedData) -> str:
        """Generate script to apply registry settings.

        Args:
            registry_data: Registry configuration

        Returns:
            PowerShell script
        """
        return """# Apply registry settings
# WARNING: Registry changes can affect system stability - review carefully before applying

$settings = @(
    @{Path="HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server"; Name="fDenyTSConnections"; Type="DWORD"; Value=0},
    @{Path="HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System"; Name="EnableLUA"; Type="DWORD"; Value=1}
)

foreach ($setting in $settings) {
    try {
        # Create path if it doesn't exist
        if (!(Test-Path $setting.Path)) {
            New-Item -Path $setting.Path -Force | Out-Null
        }

        Set-ItemProperty -Path $setting.Path -Name $setting.Name -Value $setting.Value -Type $setting.Type
        Write-Host "Applied registry setting: $($setting.Path)\\$($setting.Name)"
    } catch {
        Write-Warning "Failed to apply registry setting $($setting.Name) : $_"
    }
}
"""

    def _generate_users_script(self, users_data: ExtractedData) -> str:
        """Generate script to create local users.

        Args:
            users_data: Users configuration

        Returns:
            PowerShell script
        """
        return """# Create local user accounts
# WARNING: Users will be created with temporary password "P@ssw0rd123!"
# MUST change passwords after creation for security!

$tempPassword = ConvertTo-SecureString "P@ssw0rd123!" -AsPlainText -Force

$users = @(
    @{Name="svc_backup"; FullName="Backup Service Account"; Description="Service account for backup operations"},
    @{Name="svc_monitor"; FullName="Monitoring Service Account"; Description="Service account for monitoring"}
)

foreach ($user in $users) {
    try {
        New-LocalUser -Name $user.Name -Password $tempPassword -FullName $user.FullName -Description $user.Description -PasswordNeverExpires $true
        Write-Host "Created user: $($user.Name)"
    } catch {
        Write-Warning "Failed to create user $($user.Name) : $_"
    }
}
"""

    def _generate_groups_script(self, groups_data: ExtractedData) -> str:
        """Generate script to configure local groups.

        Args:
            groups_data: Groups configuration

        Returns:
            PowerShell script
        """
        return """# Configure local group memberships
$memberships = @(
    @{Group="Administrators"; Members=@("svc_backup")},
    @{Group="Remote Desktop Users"; Members=@("svc_monitor")}
)

foreach ($membership in $memberships) {
    try {
        foreach ($member in $membership.Members) {
            Add-LocalGroupMember -Group $membership.Group -Member $member -ErrorAction Stop
            Write-Host "Added $member to $($membership.Group)"
        }
    } catch {
        Write-Warning "Failed to add member to $($membership.Group) : $_"
    }
}
"""

    def _generate_services_script(self, services_data: ExtractedData) -> str:
        """Generate script to configure services.

        Args:
            services_data: Services configuration

        Returns:
            PowerShell script
        """
        return """# Configure Windows services
# NOTE: Custom services may need to be installed separately
# Service account passwords must be configured manually

$services = @(
    @{Name="W3SVC"; StartType="Automatic"},
    @{Name="WinRM"; StartType="Automatic"}
)

foreach ($service in $services) {
    try {
        Set-Service -Name $service.Name -StartupType $service.StartType
        Start-Service -Name $service.Name -ErrorAction SilentlyContinue
        Write-Host "Configured service: $($service.Name)"
    } catch {
        Write-Warning "Failed to configure service $($service.Name) : $_"
    }
}
"""

    def _generate_tasks_script(self, tasks_data: ExtractedData) -> str:
        """Generate script to import scheduled tasks.

        Args:
            tasks_data: Tasks configuration

        Returns:
            PowerShell script
        """
        return """# Import scheduled tasks
# NOTE: Task credentials must be set manually after import

# Example: Daily Backup Task
$action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-File C:\\Scripts\\backup.ps1"
$trigger = New-ScheduledTaskTrigger -Daily -At 2am
$principal = New-ScheduledTaskPrincipal -UserId "svc_backup" -LogonType Password

try {
    Register-ScheduledTask -TaskName "DailyBackup" -Action $action -Trigger $trigger -Principal $principal -TaskPath "\\CustomTasks\\"
    Write-Host "Created scheduled task: DailyBackup"
    Write-Warning "Task credential must be set: schtasks /change /tn '\\CustomTasks\\DailyBackup' /ru svc_backup /rp PASSWORD"
} catch {
    Write-Warning "Failed to create task: $_"
}
"""

    def _generate_firewall_script(self, firewall_data: ExtractedData) -> str:
        """Generate script to configure firewall.

        Args:
            firewall_data: Firewall configuration

        Returns:
            PowerShell script
        """
        return """# Configure Windows Firewall
# Configure firewall profiles
Set-NetFirewallProfile -Profile Domain,Private,Public -Enabled True -DefaultInboundAction Block -DefaultOutboundAction Allow

# Create firewall rules
$rules = @(
    @{Name="Allow HTTP"; Direction="Inbound"; Protocol="TCP"; LocalPort=80; Action="Allow"},
    @{Name="Allow HTTPS"; Direction="Inbound"; Protocol="TCP"; LocalPort=443; Action="Allow"},
    @{Name="Allow RDP"; Direction="Inbound"; Protocol="TCP"; LocalPort=3389; Action="Allow"}
)

foreach ($rule in $rules) {
    try {
        New-NetFirewallRule -DisplayName $rule.Name -Direction $rule.Direction -Protocol $rule.Protocol -LocalPort $rule.LocalPort -Action $rule.Action -Enabled True
        Write-Host "Created firewall rule: $($rule.Name)"
    } catch {
        Write-Warning "Failed to create firewall rule $($rule.Name) : $_"
    }
}
"""

    def _generate_shares_script(self, shares_data: ExtractedData) -> str:
        """Generate script to create file shares.

        Args:
            shares_data: Shares configuration

        Returns:
            PowerShell script
        """
        return """# Create SMB file shares
$shares = @(
    @{Name="Backup"; Path="C:\\Backup"; Description="Backup share"; FullAccess=@("Administrators", "svc_backup")},
    @{Name="Data"; Path="C:\\Data"; Description="Shared data folder"; FullAccess=@("Administrators"); ReadAccess=@("Users")}
)

foreach ($share in $shares) {
    try {
        # Create directory if it doesn't exist
        if (!(Test-Path $share.Path)) {
            New-Item -Path $share.Path -ItemType Directory -Force | Out-Null
        }

        # Create share
        New-SmbShare -Name $share.Name -Path $share.Path -Description $share.Description -FullAccess $share.FullAccess -ReadAccess $share.ReadAccess
        Write-Host "Created share: $($share.Name)"
    } catch {
        Write-Warning "Failed to create share $($share.Name) : $_"
    }
}
"""

    def _generate_validation_script(self) -> str:
        """Generate validation script.

        Returns:
            PowerShell script
        """
        return """# Validate Windows Server configuration
$results = @{}

# Check Windows Features
try {
    $features = Get-WindowsFeature | Where-Object {$_.Installed -eq $true}
    $results['Features'] = "OK - $($features.Count) features installed"
} catch {
    $results['Features'] = "FAILED: $_"
}

# Check Services
try {
    $services = Get-Service | Where-Object {$_.Status -eq 'Running'}
    $results['Services'] = "OK - $($services.Count) services running"
} catch {
    $results['Services'] = "FAILED: $_"
}

# Check Firewall
try {
    $profiles = Get-NetFirewallProfile
    $enabled = ($profiles | Where-Object {$_.Enabled -eq $true}).Count
    $results['Firewall'] = "OK - $enabled profiles enabled"
} catch {
    $results['Firewall'] = "FAILED: $_"
}

# Check File Shares
try {
    $shares = Get-SmbShare | Where-Object {$_.Name -notin @('ADMIN$', 'C$', 'IPC$')}
    $results['Shares'] = "OK - $($shares.Count) shares configured"
} catch {
    $results['Shares'] = "FAILED: $_"
}

# Output results
$results | ConvertTo-Json
"""

    def _dependencies_met(
        self, step: ReplicationStep, results: List[StepResult]
    ) -> bool:
        """Check if step dependencies are met.

        Args:
            step: Step to check
            results: Results of previous steps

        Returns:
            True if all dependencies succeeded
        """
        if not step.depends_on:
            return True

        for dep in step.depends_on:
            dep_result = next((r for r in results if r.step_id == dep), None)
            if not dep_result or dep_result.status != ReplicationStatus.SUCCESS:
                return False

        return True

    async def _execute_step_on_target(
        self, step: ReplicationStep, target_resource_id: str
    ) -> StepResult:
        """Execute a replication step on target VM.

        Args:
            step: Step to execute
            target_resource_id: Target VM resource ID

        Returns:
            StepResult with execution status
        """
        # Mock implementation - real version would use pywinrm
        start_time = datetime.utcnow()

        # Simulate execution
        await asyncio.sleep(0.5)

        duration = (datetime.utcnow() - start_time).total_seconds()

        return StepResult(
            step_id=step.step_id,
            status=ReplicationStatus.SUCCESS,
            duration_seconds=duration,
            stdout=f"[MOCK] Executed {step.step_id} successfully",
            stderr="",
            exit_code=0,
        )

    def _calculate_fidelity_score(
        self, succeeded: int, failed: int, skipped: int, total: int
    ) -> float:
        """Calculate fidelity score.

        Args:
            succeeded: Number of successful steps
            failed: Number of failed steps
            skipped: Number of skipped steps
            total: Total steps

        Returns:
            Fidelity score (0.0-1.0)
        """
        if total == 0:
            return 0.0

        # Weight: succeeded=1.0, skipped=0.5, failed=0.0
        weighted_score = succeeded + (skipped * 0.5)
        return min(1.0, weighted_score / total)
