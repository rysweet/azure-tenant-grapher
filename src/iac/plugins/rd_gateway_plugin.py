"""RD Gateway replication plugin for Remote Desktop Gateway servers.

This plugin handles data-plane replication for RD Gateway servers, including:
- RD Gateway Server Configuration (ports, SSL certificates, settings)
- Connection Authorization Policies (CAPs) - who can connect
- Resource Authorization Policies (RAPs) - what resources users can access
- Resource Groups - server lists
- SSL Certificate bindings
- Gateway health and monitoring settings

Security Note: This plugin NEVER extracts certificate private keys or credentials.
Generated configurations use placeholders that must be manually configured.
"""

import asyncio
import hashlib
import json
import logging
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


class RDGatewayReplicationPlugin(ResourceReplicationPlugin):
    """Handles RD Gateway data-plane replication.

    This plugin replicates Remote Desktop Gateway configuration:
    - Server settings (ports, certificate bindings, SSL configuration)
    - Connection Authorization Policies (CAPs) - define who can connect
    - Resource Authorization Policies (RAPs) - define what resources are accessible
    - Resource Groups - lists of servers users can access
    - SSL Certificates (metadata only, no private keys)
    - Gateway health monitoring settings

    Requires:
    - WinRM access to source server
    - PowerShell 5.1+ on target
    - RD Gateway role installed
    - Local administrator credentials
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        """Initialize the RD Gateway plugin.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}

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
            name="rd_gateway",
            version="1.0.0",
            description="Replicates Remote Desktop Gateway configuration and policies",
            author="Azure Tenant Grapher",
            resource_types=["Microsoft.Compute/virtualMachines"],
            supported_formats=[
                ExtractionFormat.POWERSHELL_DSC,
                ExtractionFormat.JSON,
                ExtractionFormat.XML,
            ],
            requires_credentials=True,
            requires_network_access=True,
            complexity="MEDIUM",
            estimated_effort_weeks=1.5,
            tags=["windows", "rdgateway", "remote-desktop", "security", "gateway"],
            documentation_url="https://docs.microsoft.com/en-us/windows-server/remote/remote-desktop-services/",
        )

    def can_handle(self, resource: Dict[str, Any]) -> bool:
        """Check if resource is an RD Gateway server.

        Args:
            resource: Resource dictionary

        Returns:
            True if resource is a Windows VM with RD Gateway role
        """
        if not super().can_handle(resource):
            return False

        # Check for Windows OS
        storage_profile = resource.get("properties", {}).get("storageProfile", {})
        image_ref = storage_profile.get("imageReference", {})
        offer = image_ref.get("offer", "").lower()

        is_windows = "windows" in offer or "windowsserver" in offer.replace(
            "-", ""
        ).replace("_", "")

        if not is_windows:
            return False

        # Check tags for RD Gateway role
        tags = resource.get("tags", {})
        name = resource.get("name", "").lower()

        # Look for RDG indicators in tags or name
        is_rdg = tags.get("role") == "rdgateway" or "rdg" in name or "rdgateway" in name

        return is_rdg

    async def analyze_source(self, resource: Dict[str, Any]) -> DataPlaneAnalysis:
        """Analyze RD Gateway configuration on source VM.

        Args:
            resource: Source VM resource dictionary

        Returns:
            DataPlaneAnalysis with discovered RD Gateway elements

        Raises:
            ConnectionError: If cannot connect via WinRM
            PermissionError: If lacking admin permissions
        """
        logger.info(f"Analyzing RD Gateway on {resource.get('name')}")

        resource_id = resource.get("id", "unknown")
        elements: List[DataPlaneElement] = []
        warnings: List[str] = []
        errors: List[str] = []

        try:
            # Check connectivity
            if not await self._check_winrm_connectivity(resource):
                raise ConnectionError("Cannot connect to server via WinRM")

            # Check if RD Gateway role is installed
            if not await self._check_rdg_role_installed(resource):
                errors.append("RD Gateway role not installed on server")
                raise ValueError("RD Gateway role not found")

            # Analyze Server Configuration
            elements.append(
                DataPlaneElement(
                    name="rdg_server_config",
                    element_type="RD Gateway Server Configuration",
                    description="Gateway server settings, ports, SSL configuration",
                    complexity="MEDIUM",
                    estimated_size_mb=0.1,
                    dependencies=[],
                    metadata={"critical": True},
                )
            )

            # Analyze Connection Authorization Policies (CAPs)
            caps_count = await self._count_caps(resource)
            if caps_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="connection_authorization_policies",
                        element_type="Connection Authorization Policies (CAPs)",
                        description=f"{caps_count} CAPs defining who can connect to the gateway",
                        complexity="MEDIUM",
                        estimated_size_mb=caps_count * 0.05,
                        dependencies=["rdg_server_config"],
                        metadata={"count": caps_count, "priority": "high"},
                    )
                )

            # Analyze Resource Authorization Policies (RAPs)
            raps_count = await self._count_raps(resource)
            if raps_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="resource_authorization_policies",
                        element_type="Resource Authorization Policies (RAPs)",
                        description=f"{raps_count} RAPs defining accessible resources",
                        complexity="MEDIUM",
                        estimated_size_mb=raps_count * 0.05,
                        dependencies=["connection_authorization_policies"],
                        metadata={"count": raps_count, "priority": "high"},
                    )
                )

            # Analyze Resource Groups
            resource_groups_count = await self._count_resource_groups(resource)
            if resource_groups_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="resource_groups",
                        element_type="Resource Groups",
                        description=f"{resource_groups_count} resource groups with server lists",
                        complexity="LOW",
                        estimated_size_mb=resource_groups_count * 0.02,
                        dependencies=["resource_authorization_policies"],
                        metadata={"count": resource_groups_count},
                    )
                )

            # Analyze SSL Certificate
            cert_info = await self._get_certificate_info(resource)
            if cert_info:
                elements.append(
                    DataPlaneElement(
                        name="ssl_certificate",
                        element_type="SSL Certificate",
                        description=f"SSL certificate: {cert_info.get('subject', 'Unknown')}",
                        complexity="LOW",
                        estimated_size_mb=0.05,
                        dependencies=[],
                        metadata={
                            "thumbprint": cert_info.get("thumbprint"),
                            "expiry": cert_info.get("expiry"),
                        },
                        is_sensitive=True,
                    )
                )
                warnings.append(
                    "Certificate private key NOT extracted - must be configured manually"
                )

            # Analyze Gateway Health Settings
            elements.append(
                DataPlaneElement(
                    name="gateway_health_settings",
                    element_type="Gateway Health Settings",
                    description="Health monitoring and logging configuration",
                    complexity="LOW",
                    estimated_size_mb=0.02,
                    dependencies=["rdg_server_config"],
                    metadata={},
                )
            )

            # Calculate totals
            total_size = sum(e.estimated_size_mb for e in elements)
            complexity_score = self._calculate_complexity_score(elements)

            status = AnalysisStatus.SUCCESS
            if errors:
                status = (
                    AnalysisStatus.FAILED if not elements else AnalysisStatus.PARTIAL
                )

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
                estimated_extraction_time_minutes=max(10, len(elements) * 2),
                warnings=warnings,
                errors=errors,
                metadata={
                    "rdg_version": "Windows Server 2019/2022",
                    "powershell_module": "RemoteDesktopServices",
                },
            )

        except Exception as e:
            logger.error(f"Failed to analyze RD Gateway: {e}")
            errors.append(str(e))

            return DataPlaneAnalysis(
                resource_id=resource_id,
                resource_type=resource.get("type", ""),
                status=AnalysisStatus.FAILED,
                elements=[],
                total_estimated_size_mb=0,
                complexity_score=8,
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
        """Extract RD Gateway configuration from source VM.

        Args:
            resource: Source VM resource dictionary
            analysis: Previous analysis result

        Returns:
            ExtractionResult with extracted RD Gateway configuration

        Raises:
            ConnectionError: If cannot connect to server
            IOError: If cannot write extracted data
        """
        logger.info(f"Extracting RD Gateway data from {resource.get('name')}")

        resource_id = resource.get("id", "unknown")
        extracted_data: List[ExtractedData] = []
        warnings: List[str] = []
        errors: List[str] = []
        items_extracted = 0
        items_failed = 0
        start_time = datetime.utcnow()

        # Get output directory
        output_dir = Path(self.get_config_value("output_dir", "./rdg_extraction"))
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Extract Server Configuration
            if self._has_element(analysis, "rdg_server_config"):
                try:
                    server_config = await self._extract_server_config(
                        resource, output_dir
                    )
                    extracted_data.append(server_config)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract server config: {e}")
                    errors.append(f"Server config: {e}")
                    items_failed += 1

            # Extract Connection Authorization Policies (CAPs)
            if self._has_element(analysis, "connection_authorization_policies"):
                try:
                    caps_data = await self._extract_caps(resource, output_dir)
                    extracted_data.append(caps_data)
                    items_extracted += 1
                    warnings.append(
                        "CAP credentials NOT extracted - must be configured manually"
                    )
                except Exception as e:
                    logger.error(f"Failed to extract CAPs: {e}")
                    errors.append(f"CAPs: {e}")
                    items_failed += 1

            # Extract Resource Authorization Policies (RAPs)
            if self._has_element(analysis, "resource_authorization_policies"):
                try:
                    raps_data = await self._extract_raps(resource, output_dir)
                    extracted_data.append(raps_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract RAPs: {e}")
                    errors.append(f"RAPs: {e}")
                    items_failed += 1

            # Extract Resource Groups
            if self._has_element(analysis, "resource_groups"):
                try:
                    groups_data = await self._extract_resource_groups(
                        resource, output_dir
                    )
                    extracted_data.append(groups_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract resource groups: {e}")
                    errors.append(f"Resource groups: {e}")
                    items_failed += 1

            # Extract SSL Certificate Info
            if self._has_element(analysis, "ssl_certificate"):
                try:
                    cert_data = await self._extract_certificate_info(
                        resource, output_dir
                    )
                    extracted_data.append(cert_data)
                    items_extracted += 1
                    warnings.append(
                        "Certificate private key NOT extracted - must be installed manually"
                    )
                except Exception as e:
                    logger.error(f"Failed to extract certificate info: {e}")
                    errors.append(f"Certificate: {e}")
                    items_failed += 1

            # Extract Gateway Health Settings
            if self._has_element(analysis, "gateway_health_settings"):
                try:
                    health_data = await self._extract_health_settings(
                        resource, output_dir
                    )
                    extracted_data.append(health_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract health settings: {e}")
                    errors.append(f"Health settings: {e}")
                    items_failed += 1

            # Calculate totals
            total_size_mb = sum(d.size_bytes / (1024 * 1024) for d in extracted_data)
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
        """Generate PowerShell steps to replicate RD Gateway config to target.

        Args:
            extraction: Result from extract_data()

        Returns:
            List of ReplicationStep objects in execution order
        """
        logger.info("Generating RD Gateway replication steps")

        steps: List[ReplicationStep] = []

        # Step 1: Verify RD Gateway Role
        steps.append(
            ReplicationStep(
                step_id="verify_rdg_role",
                step_type=StepType.PREREQUISITE,
                description="Verify RD Gateway role is installed",
                script_content=self._generate_verify_role_script(),
                script_format=ExtractionFormat.POWERSHELL_DSC,
                depends_on=[],
                estimated_duration_minutes=2,
                is_critical=True,
                can_retry=True,
            )
        )

        # Step 2: Import SSL Certificate
        cert_data = self._find_extracted_data(extraction, "certificate")
        if cert_data:
            steps.append(
                ReplicationStep(
                    step_id="import_ssl_certificate",
                    step_type=StepType.PREREQUISITE,
                    description="Import SSL certificate (requires manual certificate installation)",
                    script_content=self._generate_certificate_script(cert_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["verify_rdg_role"],
                    estimated_duration_minutes=5,
                    is_critical=True,
                    can_retry=True,
                )
            )

        # Step 3: Configure Server Settings
        server_data = self._find_extracted_data(extraction, "server_config")
        if server_data:
            steps.append(
                ReplicationStep(
                    step_id="configure_server",
                    step_type=StepType.CONFIGURATION,
                    description="Configure RD Gateway server settings",
                    script_content=self._generate_server_config_script(server_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["import_ssl_certificate"]
                    if cert_data
                    else ["verify_rdg_role"],
                    estimated_duration_minutes=5,
                    is_critical=True,
                    can_retry=True,
                )
            )

        # Step 4: Create Resource Groups
        groups_data = self._find_extracted_data(extraction, "resource_groups")
        if groups_data:
            steps.append(
                ReplicationStep(
                    step_id="create_resource_groups",
                    step_type=StepType.CONFIGURATION,
                    description="Create RD Gateway resource groups",
                    script_content=self._generate_resource_groups_script(groups_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["configure_server"],
                    estimated_duration_minutes=3,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 5: Configure CAPs
        caps_data = self._find_extracted_data(extraction, "caps")
        if caps_data:
            steps.append(
                ReplicationStep(
                    step_id="configure_caps",
                    step_type=StepType.CONFIGURATION,
                    description="Configure Connection Authorization Policies (CAPs)",
                    script_content=self._generate_caps_script(caps_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["configure_server"],
                    estimated_duration_minutes=5,
                    is_critical=True,
                    can_retry=True,
                )
            )

        # Step 6: Configure RAPs
        raps_data = self._find_extracted_data(extraction, "raps")
        if raps_data:
            depends = ["configure_caps"]
            if groups_data:
                depends.append("create_resource_groups")

            steps.append(
                ReplicationStep(
                    step_id="configure_raps",
                    step_type=StepType.CONFIGURATION,
                    description="Configure Resource Authorization Policies (RAPs)",
                    script_content=self._generate_raps_script(raps_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=depends,
                    estimated_duration_minutes=5,
                    is_critical=True,
                    can_retry=True,
                )
            )

        # Step 7: Configure Health Settings
        health_data = self._find_extracted_data(extraction, "health")
        if health_data:
            steps.append(
                ReplicationStep(
                    step_id="configure_health_settings",
                    step_type=StepType.CONFIGURATION,
                    description="Configure gateway health monitoring",
                    script_content=self._generate_health_script(health_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["configure_server"],
                    estimated_duration_minutes=3,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 8: Restart RD Gateway Service
        steps.append(
            ReplicationStep(
                step_id="restart_rdg_service",
                step_type=StepType.POST_CONFIG,
                description="Restart RD Gateway service to apply changes",
                script_content=self._generate_restart_service_script(),
                script_format=ExtractionFormat.POWERSHELL_DSC,
                depends_on=[
                    s.step_id for s in steps if s.step_type == StepType.CONFIGURATION
                ],
                estimated_duration_minutes=2,
                is_critical=True,
                can_retry=True,
            )
        )

        # Step 9: Validation
        steps.append(
            ReplicationStep(
                step_id="validate_configuration",
                step_type=StepType.VALIDATION,
                description="Validate RD Gateway configuration",
                script_content=self._generate_validation_script(),
                script_format=ExtractionFormat.POWERSHELL_DSC,
                depends_on=["restart_rdg_service"],
                estimated_duration_minutes=3,
                is_critical=False,
                can_retry=True,
            )
        )

        return steps

    async def apply_to_target(
        self, steps: List[ReplicationStep], target_resource_id: str
    ) -> ReplicationResult:
        """Apply RD Gateway replication steps to target VM.

        Args:
            steps: Replication steps to execute
            target_resource_id: Azure resource ID of target VM

        Returns:
            ReplicationResult with execution status
        """
        logger.info(f"Applying RD Gateway replication to {target_resource_id}")

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
                source_resource_id="unknown",
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

    async def _check_winrm_connectivity(self, resource: Dict[str, Any]) -> bool:
        """Check if WinRM is accessible on the server.

        Args:
            resource: Resource dictionary

        Returns:
            True if WinRM is accessible
        """
        # In real implementation, would use pywinrm
        # For now, return True if not in strict mode
        return not self.get_config_value("strict_validation", False)

    async def _check_rdg_role_installed(self, resource: Dict[str, Any]) -> bool:
        """Check if RD Gateway role is installed.

        Args:
            resource: Resource dictionary

        Returns:
            True if RD Gateway role is installed
        """
        # Mock implementation - would use Get-WindowsFeature
        return True

    async def _count_caps(self, resource: Dict[str, Any]) -> int:
        """Count Connection Authorization Policies.

        Args:
            resource: Resource dictionary

        Returns:
            Number of CAPs
        """
        # Mock implementation
        return 3

    async def _count_raps(self, resource: Dict[str, Any]) -> int:
        """Count Resource Authorization Policies.

        Args:
            resource: Resource dictionary

        Returns:
            Number of RAPs
        """
        # Mock implementation
        return 2

    async def _count_resource_groups(self, resource: Dict[str, Any]) -> int:
        """Count resource groups.

        Args:
            resource: Resource dictionary

        Returns:
            Number of resource groups
        """
        # Mock implementation
        return 2

    async def _get_certificate_info(
        self, resource: Dict[str, Any]
    ) -> Optional[Dict[str, str]]:
        """Get SSL certificate information.

        Args:
            resource: Resource dictionary

        Returns:
            Certificate info dictionary or None
        """
        # Mock implementation
        return {
            "subject": "CN=rdg.contoso.com",
            "thumbprint": "A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8S9T0",
            "expiry": "2025-12-31",
        }

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
        score = min(10, 3 + len(elements) // 2)

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

    async def _extract_server_config(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract RD Gateway server configuration.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with server configuration
        """
        # Mock implementation - would use Get-RDGatewayConfiguration
        content = json.dumps(
            {
                "server_name": "atevet12rdg001",
                "port": 443,
                "max_connections": 500,
                "ssl_certificate_thumbprint": "A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8S9T0",
                "enable_only_messaging_capable_clients": False,
                "central_cap_enabled": False,
                "central_rap_enabled": False,
                "audit_enabled": True,
                "log_level": "Error",
            },
            indent=2,
        )

        file_path = output_dir / "rdg_server_config.json"
        file_path.write_text(content)

        return ExtractedData(
            name="rdg_server_config",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_caps(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract Connection Authorization Policies.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with CAPs
        """
        # Mock implementation - would use Get-RDGConnectionAuthorization
        content = json.dumps(
            {
                "caps": [
                    {
                        "name": "All Domain Users",
                        "enabled": True,
                        "user_groups": ["CONTOSO\\Domain Users"],
                        "device_redirection": {
                            "clipboard": True,
                            "disk_drives": False,
                            "printers": True,
                            "serial_ports": False,
                            "smart_cards": True,
                        },
                        "session_timeout_minutes": 480,
                        "idle_timeout_minutes": 60,
                        "allow_only_sdrts_servers": False,
                    },
                    {
                        "name": "IT Administrators",
                        "enabled": True,
                        "user_groups": ["CONTOSO\\IT Admins"],
                        "device_redirection": {
                            "clipboard": True,
                            "disk_drives": True,
                            "printers": True,
                            "serial_ports": True,
                            "smart_cards": True,
                        },
                        "session_timeout_minutes": 1440,
                        "idle_timeout_minutes": 0,
                        "allow_only_sdrts_servers": False,
                    },
                    {
                        "name": "External Contractors",
                        "enabled": True,
                        "user_groups": ["CONTOSO\\Contractors"],
                        "device_redirection": {
                            "clipboard": False,
                            "disk_drives": False,
                            "printers": False,
                            "serial_ports": False,
                            "smart_cards": True,
                        },
                        "session_timeout_minutes": 240,
                        "idle_timeout_minutes": 30,
                        "allow_only_sdrts_servers": True,
                    },
                ],
                "note": "User group membership must be configured in Active Directory",
            },
            indent=2,
        )

        file_path = output_dir / "rdg_caps.json"
        file_path.write_text(content)

        # Also export as XML for compatibility
        xml_content = self._caps_to_xml(json.loads(content))
        xml_path = output_dir / "rdg_caps.xml"
        xml_path.write_text(xml_content)

        return ExtractedData(
            name="connection_authorization_policies",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
            metadata={"xml_file": str(xml_path)},
        )

    async def _extract_raps(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract Resource Authorization Policies.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with RAPs
        """
        # Mock implementation - would use Get-RDGResourceAuthorization
        content = json.dumps(
            {
                "raps": [
                    {
                        "name": "Production Servers",
                        "enabled": True,
                        "user_groups": ["CONTOSO\\Domain Users", "CONTOSO\\IT Admins"],
                        "computer_group_type": "AD_GROUP",
                        "computer_group": "CONTOSO\\Production Servers",
                        "port_numbers": [3389],
                        "allow_only_sdrts_servers": False,
                    },
                    {
                        "name": "Development Servers",
                        "enabled": True,
                        "user_groups": ["CONTOSO\\Developers", "CONTOSO\\IT Admins"],
                        "computer_group_type": "RESOURCE_GROUP",
                        "computer_group": "Dev-Servers",
                        "port_numbers": [3389, 3390],
                        "allow_only_sdrts_servers": False,
                    },
                ],
                "note": "Computer groups and user groups must exist before applying RAPs",
            },
            indent=2,
        )

        file_path = output_dir / "rdg_raps.json"
        file_path.write_text(content)

        # Also export as XML
        xml_content = self._raps_to_xml(json.loads(content))
        xml_path = output_dir / "rdg_raps.xml"
        xml_path.write_text(xml_content)

        return ExtractedData(
            name="resource_authorization_policies",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
            metadata={"xml_file": str(xml_path)},
        )

    async def _extract_resource_groups(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract resource groups.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with resource groups
        """
        # Mock implementation
        content = json.dumps(
            {
                "resource_groups": [
                    {
                        "name": "Dev-Servers",
                        "description": "Development environment servers",
                        "computers": [
                            "devserver01.contoso.com",
                            "devserver02.contoso.com",
                            "devserver03.contoso.com",
                        ],
                    },
                    {
                        "name": "QA-Servers",
                        "description": "QA environment servers",
                        "computers": [
                            "qaserver01.contoso.com",
                            "qaserver02.contoso.com",
                        ],
                    },
                ]
            },
            indent=2,
        )

        file_path = output_dir / "rdg_resource_groups.json"
        file_path.write_text(content)

        return ExtractedData(
            name="resource_groups",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_certificate_info(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract SSL certificate information.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with certificate info
        """
        # Mock implementation - would query certificate store
        content = json.dumps(
            {
                "certificate": {
                    "subject": "CN=rdg.contoso.com",
                    "issuer": "CN=Contoso Root CA, DC=contoso, DC=com",
                    "thumbprint": "A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8S9T0",
                    "not_before": "2024-01-01T00:00:00Z",
                    "not_after": "2025-12-31T23:59:59Z",
                    "serial_number": "1234567890ABCDEF",
                    "key_size": 2048,
                    "signature_algorithm": "sha256RSA",
                    "enhanced_key_usage": ["Server Authentication"],
                },
                "note": "Private key NOT exported - certificate must be installed manually with private key",
            },
            indent=2,
        )

        file_path = output_dir / "rdg_certificate.json"
        file_path.write_text(content)

        return ExtractedData(
            name="ssl_certificate",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_health_settings(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract gateway health settings.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with health settings
        """
        # Mock implementation
        content = json.dumps(
            {
                "health_settings": {
                    "event_log_level": "Error",
                    "max_log_size_mb": 100,
                    "enable_connection_logging": True,
                    "enable_resource_authorization_logging": True,
                    "enable_authentication_logging": True,
                    "connection_timeout_seconds": 30,
                    "health_check_interval_minutes": 5,
                }
            },
            indent=2,
        )

        file_path = output_dir / "rdg_health_settings.json"
        file_path.write_text(content)

        return ExtractedData(
            name="gateway_health_settings",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    def _caps_to_xml(self, caps_data: Dict[str, Any]) -> str:
        """Convert CAPs to XML format for Export-Clixml compatibility.

        Args:
            caps_data: CAPs data dictionary

        Returns:
            XML string
        """
        xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml_lines.append("<ConnectionAuthorizationPolicies>")

        for cap in caps_data.get("caps", []):
            xml_lines.append("  <Policy>")
            xml_lines.append(f"    <Name>{cap['name']}</Name>")
            xml_lines.append(f"    <Enabled>{cap['enabled']}</Enabled>")
            xml_lines.append("    <UserGroups>")
            for group in cap.get("user_groups", []):
                xml_lines.append(f"      <Group>{group}</Group>")
            xml_lines.append("    </UserGroups>")
            xml_lines.append("  </Policy>")

        xml_lines.append("</ConnectionAuthorizationPolicies>")
        return "\n".join(xml_lines)

    def _raps_to_xml(self, raps_data: Dict[str, Any]) -> str:
        """Convert RAPs to XML format.

        Args:
            raps_data: RAPs data dictionary

        Returns:
            XML string
        """
        xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml_lines.append("<ResourceAuthorizationPolicies>")

        for rap in raps_data.get("raps", []):
            xml_lines.append("  <Policy>")
            xml_lines.append(f"    <Name>{rap['name']}</Name>")
            xml_lines.append(f"    <Enabled>{rap['enabled']}</Enabled>")
            xml_lines.append("    <UserGroups>")
            for group in rap.get("user_groups", []):
                xml_lines.append(f"      <Group>{group}</Group>")
            xml_lines.append("    </UserGroups>")
            xml_lines.append(
                f"    <ComputerGroup>{rap['computer_group']}</ComputerGroup>"
            )
            xml_lines.append("  </Policy>")

        xml_lines.append("</ResourceAuthorizationPolicies>")
        return "\n".join(xml_lines)

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

    def _generate_verify_role_script(self) -> str:
        """Generate script to verify RD Gateway role.

        Returns:
            PowerShell script
        """
        return """# Verify RD Gateway role is installed
Import-Module ServerManager

$feature = Get-WindowsFeature -Name RDS-Gateway
if (-not $feature.Installed) {
    Write-Error "RD Gateway role is not installed. Install using: Install-WindowsFeature RDS-Gateway -IncludeManagementTools"
    exit 1
}

Write-Host "RD Gateway role is installed"

# Import RemoteDesktopServices module
Import-Module RemoteDesktopServices -ErrorAction Stop
Write-Host "RemoteDesktopServices module loaded successfully"
"""

    def _generate_certificate_script(self, cert_data: ExtractedData) -> str:
        """Generate script to configure SSL certificate.

        Args:
            cert_data: Certificate data

        Returns:
            PowerShell script
        """
        return r"""# Configure SSL Certificate for RD Gateway
# NOTE: This script assumes the certificate with private key is already installed in the LocalMachine\My store
# You must manually install the certificate before running this script

$thumbprint = "A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8S9T0"

# Verify certificate exists
$cert = Get-ChildItem -Path Cert:\LocalMachine\My | Where-Object {$_.Thumbprint -eq $thumbprint}
if (-not $cert) {
    Write-Error "Certificate with thumbprint $thumbprint not found in LocalMachine\My store"
    Write-Host "Please install the SSL certificate with private key before continuing"
    exit 1
}

Write-Host "Found certificate: $($cert.Subject)"
Write-Host "Certificate expires: $($cert.NotAfter)"

# Verify certificate has private key
if (-not $cert.HasPrivateKey) {
    Write-Error "Certificate does not have a private key"
    exit 1
}

Write-Host "Certificate has private key - ready for use"
"""

    def _generate_server_config_script(self, server_data: ExtractedData) -> str:
        """Generate script to configure server settings.

        Args:
            server_data: Server configuration data

        Returns:
            PowerShell script
        """
        return r"""# Configure RD Gateway Server Settings
Import-Module RemoteDesktopServices

# Set SSL certificate
$thumbprint = "A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8S9T0"
Set-Item -Path "RDS:\GatewayServer\SSLCertificate\Thumbprint" -Value $thumbprint

# Configure port (default 443)
Set-Item -Path "RDS:\GatewayServer\Port" -Value 443

# Configure max connections
Set-Item -Path "RDS:\GatewayServer\MaxConnections" -Value 500

# Enable audit logging
Set-Item -Path "RDS:\GatewayServer\AuditLog\Enable" -Value 1

# Set log level to Error
Set-Item -Path "RDS:\GatewayServer\EventLog\Level" -Value 2  # 1=Info, 2=Warning, 3=Error

Write-Host "RD Gateway server configuration applied successfully"
"""

    def _generate_resource_groups_script(self, groups_data: ExtractedData) -> str:
        """Generate script to create resource groups.

        Args:
            groups_data: Resource groups data

        Returns:
            PowerShell script
        """
        return r"""# Create RD Gateway Resource Groups
Import-Module RemoteDesktopServices

$resourceGroups = @(
    @{Name="Dev-Servers"; Description="Development environment servers";
      Computers=@("devserver01.contoso.com", "devserver02.contoso.com", "devserver03.contoso.com")},
    @{Name="QA-Servers"; Description="QA environment servers";
      Computers=@("qaserver01.contoso.com", "qaserver02.contoso.com")}
)

foreach ($group in $resourceGroups) {
    try {
        # Check if group exists
        $existingGroup = Get-Item -Path "RDS:\GatewayServer\ResourceGroups\$($group.Name)" -ErrorAction SilentlyContinue

        if ($existingGroup) {
            Write-Host "Resource group '$($group.Name)' already exists - updating"
            Remove-Item -Path "RDS:\GatewayServer\ResourceGroups\$($group.Name)" -Recurse -Force
        }

        # Create new resource group
        New-Item -Path "RDS:\GatewayServer\ResourceGroups" -Name $group.Name -Description $group.Description

        # Add computers to group
        foreach ($computer in $group.Computers) {
            New-Item -Path "RDS:\GatewayServer\ResourceGroups\$($group.Name)\Computers" -Name $computer
        }

        Write-Host "Created resource group: $($group.Name) with $($group.Computers.Count) computers"
    } catch {
        Write-Warning "Failed to create resource group $($group.Name): $_"
    }
}
"""

    def _generate_caps_script(self, caps_data: ExtractedData) -> str:
        """Generate script to configure CAPs.

        Args:
            caps_data: CAPs data

        Returns:
            PowerShell script
        """
        return r"""# Configure Connection Authorization Policies (CAPs)
Import-Module RemoteDesktopServices

$caps = @(
    @{
        Name="All Domain Users"
        Enabled=$true
        UserGroups=@("CONTOSO\Domain Users")
        SessionTimeout=480
        IdleTimeout=60
        DeviceRedirection=@{Clipboard=$true; DiskDrives=$false; Printers=$true; SerialPorts=$false; SmartCards=$true}
    },
    @{
        Name="IT Administrators"
        Enabled=$true
        UserGroups=@("CONTOSO\IT Admins")
        SessionTimeout=1440
        IdleTimeout=0
        DeviceRedirection=@{Clipboard=$true; DiskDrives=$true; Printers=$true; SerialPorts=$true; SmartCards=$true}
    },
    @{
        Name="External Contractors"
        Enabled=$true
        UserGroups=@("CONTOSO\Contractors")
        SessionTimeout=240
        IdleTimeout=30
        DeviceRedirection=@{Clipboard=$false; DiskDrives=$false; Printers=$false; SerialPorts=$false; SmartCards=$true}
    }
)

foreach ($cap in $caps) {
    try {
        # Check if CAP exists
        $existingCap = Get-Item -Path "RDS:\GatewayServer\CAP\$($cap.Name)" -ErrorAction SilentlyContinue

        if ($existingCap) {
            Write-Host "CAP '$($cap.Name)' already exists - removing"
            Remove-Item -Path "RDS:\GatewayServer\CAP\$($cap.Name)" -Recurse -Force
        }

        # Create new CAP
        New-Item -Path "RDS:\GatewayServer\CAP" -Name $cap.Name

        # Set enabled status
        Set-Item -Path "RDS:\GatewayServer\CAP\$($cap.Name)\Enabled" -Value $cap.Enabled

        # Add user groups
        foreach ($group in $cap.UserGroups) {
            New-Item -Path "RDS:\GatewayServer\CAP\$($cap.Name)\UserGroups" -Name $group
        }

        # Set timeouts
        Set-Item -Path "RDS:\GatewayServer\CAP\$($cap.Name)\SessionTimeout" -Value $cap.SessionTimeout
        Set-Item -Path "RDS:\GatewayServer\CAP\$($cap.Name)\IdleTimeout" -Value $cap.IdleTimeout

        # Configure device redirection
        Set-Item -Path "RDS:\GatewayServer\CAP\$($cap.Name)\DeviceRedirection\Clipboard" -Value $cap.DeviceRedirection.Clipboard
        Set-Item -Path "RDS:\GatewayServer\CAP\$($cap.Name)\DeviceRedirection\DiskDrives" -Value $cap.DeviceRedirection.DiskDrives
        Set-Item -Path "RDS:\GatewayServer\CAP\$($cap.Name)\DeviceRedirection\Printers" -Value $cap.DeviceRedirection.Printers
        Set-Item -Path "RDS:\GatewayServer\CAP\$($cap.Name)\DeviceRedirection\SerialPorts" -Value $cap.DeviceRedirection.SerialPorts
        Set-Item -Path "RDS:\GatewayServer\CAP\$($cap.Name)\DeviceRedirection\SmartCards" -Value $cap.DeviceRedirection.SmartCards

        Write-Host "Created CAP: $($cap.Name)"
    } catch {
        Write-Warning "Failed to create CAP $($cap.Name): $_"
    }
}
"""

    def _generate_raps_script(self, raps_data: ExtractedData) -> str:
        """Generate script to configure RAPs.

        Args:
            raps_data: RAPs data

        Returns:
            PowerShell script
        """
        return r"""# Configure Resource Authorization Policies (RAPs)
Import-Module RemoteDesktopServices

$raps = @(
    @{
        Name="Production Servers"
        Enabled=$true
        UserGroups=@("CONTOSO\Domain Users", "CONTOSO\IT Admins")
        ComputerGroupType="AD_GROUP"
        ComputerGroup="CONTOSO\Production Servers"
        PortNumbers=@(3389)
    },
    @{
        Name="Development Servers"
        Enabled=$true
        UserGroups=@("CONTOSO\Developers", "CONTOSO\IT Admins")
        ComputerGroupType="RESOURCE_GROUP"
        ComputerGroup="Dev-Servers"
        PortNumbers=@(3389, 3390)
    }
)

foreach ($rap in $raps) {
    try {
        # Check if RAP exists
        $existingRap = Get-Item -Path "RDS:\GatewayServer\RAP\$($rap.Name)" -ErrorAction SilentlyContinue

        if ($existingRap) {
            Write-Host "RAP '$($rap.Name)' already exists - removing"
            Remove-Item -Path "RDS:\GatewayServer\RAP\$($rap.Name)" -Recurse -Force
        }

        # Create new RAP
        New-Item -Path "RDS:\GatewayServer\RAP" -Name $rap.Name

        # Set enabled status
        Set-Item -Path "RDS:\GatewayServer\RAP\$($rap.Name)\Enabled" -Value $rap.Enabled

        # Add user groups
        foreach ($group in $rap.UserGroups) {
            New-Item -Path "RDS:\GatewayServer\RAP\$($rap.Name)\UserGroups" -Name $group
        }

        # Set computer group type
        Set-Item -Path "RDS:\GatewayServer\RAP\$($rap.Name)\ComputerGroupType" -Value $rap.ComputerGroupType

        # Set computer group
        if ($rap.ComputerGroupType -eq "RESOURCE_GROUP") {
            Set-Item -Path "RDS:\GatewayServer\RAP\$($rap.Name)\ComputerGroup" -Value $rap.ComputerGroup
        } else {
            # AD Group
            New-Item -Path "RDS:\GatewayServer\RAP\$($rap.Name)\ComputerGroups" -Name $rap.ComputerGroup
        }

        # Set port numbers
        foreach ($port in $rap.PortNumbers) {
            New-Item -Path "RDS:\GatewayServer\RAP\$($rap.Name)\PortNumbers" -Name $port
        }

        Write-Host "Created RAP: $($rap.Name)"
    } catch {
        Write-Warning "Failed to create RAP $($rap.Name): $_"
    }
}
"""

    def _generate_health_script(self, health_data: ExtractedData) -> str:
        """Generate script to configure health settings.

        Args:
            health_data: Health settings data

        Returns:
            PowerShell script
        """
        return r"""# Configure Gateway Health Settings
Import-Module RemoteDesktopServices

# Configure event log level
Set-Item -Path "RDS:\GatewayServer\EventLog\Level" -Value 3  # 1=Info, 2=Warning, 3=Error

# Enable connection logging
Set-Item -Path "RDS:\GatewayServer\AuditLog\ConnectionLog\Enable" -Value 1

# Enable resource authorization logging
Set-Item -Path "RDS:\GatewayServer\AuditLog\ResourceAuthorizationLog\Enable" -Value 1

# Enable authentication logging
Set-Item -Path "RDS:\GatewayServer\AuditLog\AuthenticationLog\Enable" -Value 1

Write-Host "Gateway health settings configured successfully"
"""

    def _generate_restart_service_script(self) -> str:
        """Generate script to restart RD Gateway service.

        Returns:
            PowerShell script
        """
        return """# Restart RD Gateway Service
Write-Host "Restarting RD Gateway service to apply changes..."

try {
    Restart-Service TSGateway -Force

    # Wait for service to start
    Start-Sleep -Seconds 5

    $service = Get-Service TSGateway
    if ($service.Status -eq 'Running') {
        Write-Host "RD Gateway service restarted successfully"
    } else {
        Write-Error "RD Gateway service failed to start. Status: $($service.Status)"
        exit 1
    }
} catch {
    Write-Error "Failed to restart RD Gateway service: $_"
    exit 1
}
"""

    def _generate_validation_script(self) -> str:
        """Generate validation script.

        Returns:
            PowerShell script
        """
        return r"""# Validate RD Gateway Configuration
Import-Module RemoteDesktopServices

$results = @{}

# Check RD Gateway service
try {
    $service = Get-Service TSGateway
    if ($service.Status -eq 'Running') {
        $results['Service'] = "OK - RD Gateway service is running"
    } else {
        $results['Service'] = "FAILED - Service status: $($service.Status)"
    }
} catch {
    $results['Service'] = "FAILED: $_"
}

# Check SSL certificate
try {
    $thumbprint = Get-Item -Path "RDS:\GatewayServer\SSLCertificate\Thumbprint"
    $cert = Get-ChildItem -Path Cert:\LocalMachine\My | Where-Object {$_.Thumbprint -eq $thumbprint.CurrentValue}
    if ($cert) {
        $daysUntilExpiry = ($cert.NotAfter - (Get-Date)).Days
        $results['Certificate'] = "OK - Certificate expires in $daysUntilExpiry days"
    } else {
        $results['Certificate'] = "FAILED - Certificate not found"
    }
} catch {
    $results['Certificate'] = "FAILED: $_"
}

# Check CAPs
try {
    $caps = Get-ChildItem -Path "RDS:\GatewayServer\CAP"
    $enabledCaps = ($caps | Where-Object {(Get-Item "RDS:\GatewayServer\CAP\$($_.Name)\Enabled").CurrentValue -eq $true}).Count
    $results['CAPs'] = "OK - $($caps.Count) CAPs configured, $enabledCaps enabled"
} catch {
    $results['CAPs'] = "FAILED: $_"
}

# Check RAPs
try {
    $raps = Get-ChildItem -Path "RDS:\GatewayServer\RAP"
    $enabledRaps = ($raps | Where-Object {(Get-Item "RDS:\GatewayServer\RAP\$($_.Name)\Enabled").CurrentValue -eq $true}).Count
    $results['RAPs'] = "OK - $($raps.Count) RAPs configured, $enabledRaps enabled"
} catch {
    $results['RAPs'] = "FAILED: $_"
}

# Check resource groups
try {
    $groups = Get-ChildItem -Path "RDS:\GatewayServer\ResourceGroups"
    $results['ResourceGroups'] = "OK - $($groups.Count) resource groups configured"
} catch {
    $results['ResourceGroups'] = "FAILED: $_"
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
