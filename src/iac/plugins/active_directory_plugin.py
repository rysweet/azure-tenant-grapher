"""Active Directory replication plugin for domain controller VMs.

This plugin handles data-plane replication for Active Directory Domain Services,
including forest/domain configuration, OUs, users, groups, GPOs, and DNS records.

Security Note: This plugin NEVER extracts password hashes. Generated configurations
use placeholder passwords that must be manually set after replication.
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


class ActiveDirectoryReplicationPlugin(ResourceReplicationPlugin):
    """Handles Active Directory domain controller replication.

    This plugin replicates AD structure and configuration:
    - Forest and domain settings
    - Organizational Units (OU) hierarchy
    - User accounts (without passwords)
    - Groups and memberships
    - Group Policy Objects (GPO definitions)
    - DNS zone records for AD
    - Computer objects

    Requires:
    - WinRM access to source DC
    - PowerShell 5.1+ with AD module
    - Domain admin or delegated credentials
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        """Initialize the Active Directory plugin.

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
            name="active_directory",
            version="1.0.0",
            description="Replicates Active Directory domain configuration",
            author="Azure Tenant Grapher",
            resource_types=["Microsoft.Compute/virtualMachines"],
            supported_formats=[
                ExtractionFormat.LDIF,
                ExtractionFormat.POWERSHELL_DSC,
                ExtractionFormat.JSON,
                ExtractionFormat.CSV,
            ],
            requires_credentials=True,
            requires_network_access=True,
            complexity="HIGH",
            estimated_effort_weeks=2.5,
            tags=["windows", "active-directory", "domain-controller", "ldap"],
            documentation_url="https://docs.microsoft.com/en-us/windows-server/identity/ad-ds/",
        )

    def can_handle(self, resource: Dict[str, Any]) -> bool:
        """Check if resource is an AD domain controller.

        Args:
            resource: Resource dictionary

        Returns:
            True if resource is a Windows VM with AD DS role
        """
        if not super().can_handle(resource):
            return False

        # Check for AD indicators
        tags = resource.get("tags", {})
        os_profile = resource.get("properties", {}).get("osProfile", {})

        # Check tags for AD role
        if tags.get("role") == "domain-controller" or tags.get("role") == "AD":
            return True

        # Check VM name patterns (common AD naming conventions)
        name = resource.get("name", "").lower()
        if any(pattern in name for pattern in ["dc", "ads", "ad-", "-ad-"]):
            return True

        # Check OS is Windows
        if "windows" not in os_profile.get("computerName", "").lower():
            return False

        return False

    async def analyze_source(
        self, resource: Dict[str, Any]
    ) -> DataPlaneAnalysis:
        """Analyze Active Directory structure on source DC.

        Args:
            resource: Source DC resource dictionary

        Returns:
            DataPlaneAnalysis with discovered AD elements

        Raises:
            ConnectionError: If cannot connect via WinRM
            PermissionError: If lacking AD read permissions
        """
        logger.info(f"Analyzing AD on {resource.get('name')}")

        resource_id = resource.get("id", "unknown")
        elements: List[DataPlaneElement] = []
        warnings: List[str] = []
        errors: List[str] = []

        try:
            # Check connectivity
            if not await self._check_winrm_connectivity(resource):
                raise ConnectionError("Cannot connect to DC via WinRM")

            # Analyze forest configuration
            forest_info = await self._analyze_forest(resource)
            if forest_info:
                elements.append(
                    DataPlaneElement(
                        name="forest_configuration",
                        element_type="AD Forest",
                        description=f"Forest: {forest_info.get('name', 'unknown')}",
                        complexity="HIGH",
                        estimated_size_mb=0.1,
                        dependencies=[],
                        metadata=forest_info,
                    )
                )

            # Analyze domain configuration
            domain_info = await self._analyze_domain(resource)
            if domain_info:
                elements.append(
                    DataPlaneElement(
                        name="domain_configuration",
                        element_type="AD Domain",
                        description=f"Domain: {domain_info.get('name', 'unknown')}",
                        complexity="HIGH",
                        estimated_size_mb=0.5,
                        dependencies=["forest_configuration"],
                        metadata=domain_info,
                    )
                )

            # Analyze OUs
            ou_count = await self._count_ous(resource)
            if ou_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="organizational_units",
                        element_type="OUs",
                        description=f"{ou_count} Organizational Units",
                        complexity="MEDIUM",
                        estimated_size_mb=ou_count * 0.01,
                        dependencies=["domain_configuration"],
                        metadata={"count": ou_count},
                    )
                )

            # Analyze users
            user_count = await self._count_users(resource)
            if user_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="user_accounts",
                        element_type="Users",
                        description=f"{user_count} user accounts (passwords excluded)",
                        complexity="MEDIUM",
                        estimated_size_mb=user_count * 0.05,
                        dependencies=["organizational_units"],
                        metadata={"count": user_count},
                    )
                )

            # Analyze groups
            group_count = await self._count_groups(resource)
            if group_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="groups",
                        element_type="Groups",
                        description=f"{group_count} groups and memberships",
                        complexity="MEDIUM",
                        estimated_size_mb=group_count * 0.02,
                        dependencies=["user_accounts"],
                        metadata={"count": group_count},
                    )
                )

            # Analyze GPOs
            gpo_count = await self._count_gpos(resource)
            if gpo_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="group_policies",
                        element_type="GPOs",
                        description=f"{gpo_count} Group Policy Objects",
                        complexity="HIGH",
                        estimated_size_mb=gpo_count * 0.5,
                        dependencies=["organizational_units"],
                        metadata={"count": gpo_count},
                    )
                )

            # Analyze DNS zones
            dns_count = await self._count_dns_zones(resource)
            if dns_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="dns_zones",
                        element_type="DNS",
                        description=f"{dns_count} DNS zones",
                        complexity="MEDIUM",
                        estimated_size_mb=dns_count * 0.1,
                        dependencies=["domain_configuration"],
                        metadata={"count": dns_count},
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
                connection_methods=["WinRM", "PowerShell", "LDAP"],
                estimated_extraction_time_minutes=max(10, len(elements) * 5),
                warnings=warnings,
                errors=errors,
                metadata={
                    "ad_functional_level": domain_info.get("functional_level")
                    if domain_info
                    else None,
                    "domain_sid": domain_info.get("sid") if domain_info else None,
                },
            )

        except Exception as e:
            logger.error(f"Failed to analyze AD: {e}")
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
        """Extract Active Directory data from source DC.

        Args:
            resource: Source DC resource dictionary
            analysis: Previous analysis result

        Returns:
            ExtractionResult with extracted AD data

        Raises:
            ConnectionError: If cannot connect to DC
            IOError: If cannot write extracted data
        """
        logger.info(f"Extracting AD data from {resource.get('name')}")

        resource_id = resource.get("id", "unknown")
        extracted_data: List[ExtractedData] = []
        warnings: List[str] = []
        errors: List[str] = []
        items_extracted = 0
        items_failed = 0
        start_time = datetime.utcnow()

        # Get output directory
        output_dir = Path(self.get_config_value("output_dir", "./ad_extraction"))
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Extract forest configuration
            if self._has_element(analysis, "forest_configuration"):
                try:
                    forest_data = await self._extract_forest_config(resource, output_dir)
                    extracted_data.append(forest_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract forest config: {e}")
                    errors.append(f"Forest config: {e}")
                    items_failed += 1

            # Extract domain configuration
            if self._has_element(analysis, "domain_configuration"):
                try:
                    domain_data = await self._extract_domain_config(resource, output_dir)
                    extracted_data.append(domain_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract domain config: {e}")
                    errors.append(f"Domain config: {e}")
                    items_failed += 1

            # Extract OUs
            if self._has_element(analysis, "organizational_units"):
                try:
                    ou_data = await self._extract_ous(resource, output_dir)
                    extracted_data.append(ou_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract OUs: {e}")
                    errors.append(f"OUs: {e}")
                    items_failed += 1

            # Extract users
            if self._has_element(analysis, "user_accounts"):
                try:
                    user_data = await self._extract_users(resource, output_dir)
                    extracted_data.append(user_data)
                    items_extracted += 1
                    warnings.append(
                        "User passwords NOT extracted - must be set manually"
                    )
                except Exception as e:
                    logger.error(f"Failed to extract users: {e}")
                    errors.append(f"Users: {e}")
                    items_failed += 1

            # Extract groups
            if self._has_element(analysis, "groups"):
                try:
                    group_data = await self._extract_groups(resource, output_dir)
                    extracted_data.append(group_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract groups: {e}")
                    errors.append(f"Groups: {e}")
                    items_failed += 1

            # Extract GPOs
            if self._has_element(analysis, "group_policies"):
                try:
                    gpo_data = await self._extract_gpos(resource, output_dir)
                    extracted_data.append(gpo_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract GPOs: {e}")
                    errors.append(f"GPOs: {e}")
                    items_failed += 1

            # Extract DNS
            if self._has_element(analysis, "dns_zones"):
                try:
                    dns_data = await self._extract_dns(resource, output_dir)
                    extracted_data.append(dns_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract DNS: {e}")
                    errors.append(f"DNS: {e}")
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
        """Generate PowerShell DSC steps to replicate AD to target.

        Args:
            extraction: Result from extract_data()

        Returns:
            List of ReplicationStep objects in execution order
        """
        logger.info("Generating AD replication steps")

        steps: List[ReplicationStep] = []

        # Step 1: Prerequisites
        steps.append(
            ReplicationStep(
                step_id="prereq_ad_features",
                step_type=StepType.PREREQUISITE,
                description="Install AD DS and DNS features",
                script_content=self._generate_feature_install_script(),
                script_format=ExtractionFormat.POWERSHELL_DSC,
                depends_on=[],
                estimated_duration_minutes=15,
                is_critical=True,
                can_retry=True,
                max_retries=2,
            )
        )

        # Step 2: Create forest/domain (if new environment)
        forest_data = self._find_extracted_data(extraction, "forest")
        domain_data = self._find_extracted_data(extraction, "domain")

        if forest_data and domain_data:
            steps.append(
                ReplicationStep(
                    step_id="create_forest_domain",
                    step_type=StepType.CONFIGURATION,
                    description="Create AD forest and domain",
                    script_content=self._generate_forest_creation_script(
                        forest_data, domain_data
                    ),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["prereq_ad_features"],
                    estimated_duration_minutes=20,
                    is_critical=True,
                    can_retry=False,
                )
            )

        # Step 3: Create OUs
        ou_data = self._find_extracted_data(extraction, "ous")
        if ou_data:
            steps.append(
                ReplicationStep(
                    step_id="create_ous",
                    step_type=StepType.CONFIGURATION,
                    description="Create Organizational Unit structure",
                    script_content=self._generate_ou_creation_script(ou_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["create_forest_domain"],
                    estimated_duration_minutes=5,
                    is_critical=True,
                    can_retry=True,
                )
            )

        # Step 4: Create users
        user_data = self._find_extracted_data(extraction, "users")
        if user_data:
            steps.append(
                ReplicationStep(
                    step_id="create_users",
                    step_type=StepType.DATA_IMPORT,
                    description="Create user accounts (passwords must be set manually)",
                    script_content=self._generate_user_creation_script(user_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["create_ous"],
                    estimated_duration_minutes=10,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 5: Create groups
        group_data = self._find_extracted_data(extraction, "groups")
        if group_data:
            steps.append(
                ReplicationStep(
                    step_id="create_groups",
                    step_type=StepType.DATA_IMPORT,
                    description="Create groups and memberships",
                    script_content=self._generate_group_creation_script(group_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["create_users"],
                    estimated_duration_minutes=5,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 6: Import GPOs
        gpo_data = self._find_extracted_data(extraction, "gpo")
        if gpo_data:
            steps.append(
                ReplicationStep(
                    step_id="import_gpos",
                    step_type=StepType.CONFIGURATION,
                    description="Import Group Policy Objects",
                    script_content=self._generate_gpo_import_script(gpo_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["create_ous"],
                    estimated_duration_minutes=10,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 7: Configure DNS
        dns_data = self._find_extracted_data(extraction, "dns")
        if dns_data:
            steps.append(
                ReplicationStep(
                    step_id="configure_dns",
                    step_type=StepType.CONFIGURATION,
                    description="Configure DNS zones and records",
                    script_content=self._generate_dns_config_script(dns_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["create_forest_domain"],
                    estimated_duration_minutes=5,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 8: Validation
        steps.append(
            ReplicationStep(
                step_id="validate_ad",
                step_type=StepType.VALIDATION,
                description="Validate AD replication and health",
                script_content=self._generate_validation_script(),
                script_format=ExtractionFormat.POWERSHELL_DSC,
                depends_on=[s.step_id for s in steps],
                estimated_duration_minutes=5,
                is_critical=False,
                can_retry=True,
            )
        )

        return steps

    async def apply_to_target(
        self, steps: List[ReplicationStep], target_resource_id: str
    ) -> ReplicationResult:
        """Apply AD replication steps to target DC.

        Args:
            steps: Replication steps to execute
            target_resource_id: Azure resource ID of target DC

        Returns:
            ReplicationResult with execution status
        """
        logger.info(f"Applying AD replication to {target_resource_id}")

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

    async def _check_winrm_connectivity(self, resource: Dict[str, Any]) -> bool:
        """Check if WinRM is accessible on the DC.

        Args:
            resource: Resource dictionary

        Returns:
            True if WinRM is accessible
        """
        # In real implementation, would use pywinrm
        # For now, return True if not in strict mode
        return not self.get_config_value("strict_validation", False)

    async def _analyze_forest(
        self, resource: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Analyze AD forest configuration.

        Args:
            resource: Resource dictionary

        Returns:
            Forest info dictionary or None
        """
        # Mock implementation - real version would use PowerShell Get-ADForest
        return {
            "name": "simuland.local",
            "functional_level": "Windows2016Forest",
            "root_domain": "simuland.local",
            "schema_master": "atevet12ads001.simuland.local",
        }

    async def _analyze_domain(
        self, resource: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Analyze AD domain configuration.

        Args:
            resource: Resource dictionary

        Returns:
            Domain info dictionary or None
        """
        # Mock implementation - real version would use PowerShell Get-ADDomain
        return {
            "name": "simuland.local",
            "netbios_name": "SIMULAND",
            "functional_level": "Windows2016Domain",
            "sid": "S-1-5-21-1234567890-1234567890-1234567890",
            "pdc_emulator": "atevet12ads001.simuland.local",
        }

    async def _count_ous(self, resource: Dict[str, Any]) -> int:
        """Count organizational units.

        Args:
            resource: Resource dictionary

        Returns:
            Number of OUs
        """
        # Mock implementation
        return 15

    async def _count_users(self, resource: Dict[str, Any]) -> int:
        """Count user accounts.

        Args:
            resource: Resource dictionary

        Returns:
            Number of users
        """
        # Mock implementation
        return 50

    async def _count_groups(self, resource: Dict[str, Any]) -> int:
        """Count groups.

        Args:
            resource: Resource dictionary

        Returns:
            Number of groups
        """
        # Mock implementation
        return 20

    async def _count_gpos(self, resource: Dict[str, Any]) -> int:
        """Count Group Policy Objects.

        Args:
            resource: Resource dictionary

        Returns:
            Number of GPOs
        """
        # Mock implementation
        return 8

    async def _count_dns_zones(self, resource: Dict[str, Any]) -> int:
        """Count DNS zones.

        Args:
            resource: Resource dictionary

        Returns:
            Number of DNS zones
        """
        # Mock implementation
        return 3

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

    async def _extract_forest_config(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract forest configuration.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with forest config
        """
        # Mock implementation
        content = json.dumps(
            {
                "forest_name": "simuland.local",
                "functional_level": "Windows2016Forest",
                "root_domain": "simuland.local",
            },
            indent=2,
        )

        file_path = output_dir / "forest_config.json"
        file_path.write_text(content)

        return ExtractedData(
            name="forest_config",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_domain_config(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract domain configuration.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with domain config
        """
        # Mock implementation
        content = json.dumps(
            {
                "domain_name": "simuland.local",
                "netbios_name": "SIMULAND",
                "functional_level": "Windows2016Domain",
            },
            indent=2,
        )

        file_path = output_dir / "domain_config.json"
        file_path.write_text(content)

        return ExtractedData(
            name="domain_config",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_ous(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract organizational units.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with OUs
        """
        # Mock implementation - would use Get-ADOrganizationalUnit
        content = """# Organizational Units
OU=IT,DC=simuland,DC=local
OU=HR,DC=simuland,DC=local
OU=Finance,DC=simuland,DC=local
OU=Servers,DC=simuland,DC=local
OU=Workstations,DC=simuland,DC=local
"""

        file_path = output_dir / "ous.txt"
        file_path.write_text(content)

        return ExtractedData(
            name="ous",
            format=ExtractionFormat.CSV,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_users(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract user accounts.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with users (NO PASSWORDS)
        """
        # Mock implementation - would use Get-ADUser -Filter * -Properties *
        content = json.dumps(
            {
                "users": [
                    {
                        "samAccountName": "jdoe",
                        "givenName": "John",
                        "surname": "Doe",
                        "userPrincipalName": "jdoe@simuland.local",
                        "enabled": True,
                        "ou": "OU=IT,DC=simuland,DC=local",
                    },
                    {
                        "samAccountName": "asmith",
                        "givenName": "Alice",
                        "surname": "Smith",
                        "userPrincipalName": "asmith@simuland.local",
                        "enabled": True,
                        "ou": "OU=HR,DC=simuland,DC=local",
                    },
                ],
                "note": "Passwords NOT included - must be set manually after import",
            },
            indent=2,
        )

        file_path = output_dir / "users.json"
        file_path.write_text(content)

        return ExtractedData(
            name="users",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_groups(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract groups and memberships.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with groups
        """
        # Mock implementation
        content = json.dumps(
            {
                "groups": [
                    {
                        "name": "IT Admins",
                        "scope": "Global",
                        "category": "Security",
                        "members": ["jdoe"],
                    },
                    {
                        "name": "HR Staff",
                        "scope": "Global",
                        "category": "Security",
                        "members": ["asmith"],
                    },
                ]
            },
            indent=2,
        )

        file_path = output_dir / "groups.json"
        file_path.write_text(content)

        return ExtractedData(
            name="groups",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_gpos(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract Group Policy Objects.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with GPOs
        """
        # Mock implementation - would use Backup-GPO -All
        content = json.dumps(
            {
                "gpos": [
                    {
                        "name": "Default Domain Policy",
                        "guid": "{31B2F340-016D-11D2-945F-00C04FB984F9}",
                        "linked_to": ["DC=simuland,DC=local"],
                    },
                    {
                        "name": "IT Security Policy",
                        "guid": "{12345678-1234-1234-1234-123456789012}",
                        "linked_to": ["OU=IT,DC=simuland,DC=local"],
                    },
                ]
            },
            indent=2,
        )

        file_path = output_dir / "gpos.json"
        file_path.write_text(content)

        return ExtractedData(
            name="gpo_metadata",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_dns(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract DNS zones and records.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with DNS config
        """
        # Mock implementation
        content = json.dumps(
            {
                "zones": [
                    {
                        "name": "simuland.local",
                        "type": "Primary",
                        "records": [
                            {
                                "name": "atevet12ads001",
                                "type": "A",
                                "data": "10.0.1.4",
                            },
                            {
                                "name": "atevet12win001",
                                "type": "A",
                                "data": "10.0.1.5",
                            },
                        ],
                    }
                ]
            },
            indent=2,
        )

        file_path = output_dir / "dns_zones.json"
        file_path.write_text(content)

        return ExtractedData(
            name="dns_zones",
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

    def _generate_feature_install_script(self) -> str:
        """Generate PowerShell script to install AD features.

        Returns:
            PowerShell script content
        """
        return """# Install AD DS and DNS features
Install-WindowsFeature -Name AD-Domain-Services -IncludeManagementTools
Install-WindowsFeature -Name DNS -IncludeManagementTools

# Import AD module
Import-Module ActiveDirectory
"""

    def _generate_forest_creation_script(
        self, forest_data: ExtractedData, domain_data: ExtractedData
    ) -> str:
        """Generate script to create forest and domain.

        Args:
            forest_data: Forest configuration
            domain_data: Domain configuration

        Returns:
            PowerShell DSC script
        """
        return """# Create new AD forest and domain
# NOTE: This script requires manual password input for SafeModeAdministratorPassword

$domainName = "simuland.local"
$netbiosName = "SIMULAND"

# Create forest (interactive - requires password)
Install-ADDSForest `
    -DomainName $domainName `
    -DomainNetbiosName $netbiosName `
    -ForestMode "Win2016" `
    -DomainMode "Win2016" `
    -InstallDns `
    -Force `
    -NoRebootOnCompletion:$false

# Server will reboot after forest creation
"""

    def _generate_ou_creation_script(self, ou_data: ExtractedData) -> str:
        """Generate script to create OUs.

        Args:
            ou_data: OU configuration

        Returns:
            PowerShell script
        """
        return """# Create Organizational Units
$ous = @(
    "OU=IT,DC=simuland,DC=local",
    "OU=HR,DC=simuland,DC=local",
    "OU=Finance,DC=simuland,DC=local",
    "OU=Servers,DC=simuland,DC=local",
    "OU=Workstations,DC=simuland,DC=local"
)

foreach ($ou in $ous) {
    try {
        New-ADOrganizationalUnit -Path $ou.Split(',', 2)[1] -Name $ou.Split(',')[0].Replace('OU=', '') -ProtectedFromAccidentalDeletion $true
        Write-Host "Created OU: $ou"
    } catch {
        Write-Warning "Failed to create OU $ou : $_"
    }
}
"""

    def _generate_user_creation_script(self, user_data: ExtractedData) -> str:
        """Generate script to create users.

        Args:
            user_data: User configuration

        Returns:
            PowerShell script
        """
        return """# Create user accounts
# WARNING: Users will be created with temporary password "P@ssw0rd123!"
# MUST change passwords after creation for security!

$tempPassword = ConvertTo-SecureString "P@ssw0rd123!" -AsPlainText -Force

$users = @(
    @{Name="jdoe"; GivenName="John"; Surname="Doe"; OU="OU=IT,DC=simuland,DC=local"},
    @{Name="asmith"; GivenName="Alice"; Surname="Smith"; OU="OU=HR,DC=simuland,DC=local"}
)

foreach ($user in $users) {
    try {
        New-ADUser `
            -SamAccountName $user.Name `
            -GivenName $user.GivenName `
            -Surname $user.Surname `
            -Name "$($user.GivenName) $($user.Surname)" `
            -UserPrincipalName "$($user.Name)@simuland.local" `
            -Path $user.OU `
            -AccountPassword $tempPassword `
            -Enabled $true `
            -ChangePasswordAtLogon $true
        Write-Host "Created user: $($user.Name)"
    } catch {
        Write-Warning "Failed to create user $($user.Name) : $_"
    }
}
"""

    def _generate_group_creation_script(self, group_data: ExtractedData) -> str:
        """Generate script to create groups.

        Args:
            group_data: Group configuration

        Returns:
            PowerShell script
        """
        return """# Create groups and memberships
$groups = @(
    @{Name="IT Admins"; Scope="Global"; Category="Security"; Members=@("jdoe")},
    @{Name="HR Staff"; Scope="Global"; Category="Security"; Members=@("asmith")}
)

foreach ($group in $groups) {
    try {
        New-ADGroup `
            -Name $group.Name `
            -GroupScope $group.Scope `
            -GroupCategory $group.Category `
            -Path "DC=simuland,DC=local"

        foreach ($member in $group.Members) {
            Add-ADGroupMember -Identity $group.Name -Members $member
        }

        Write-Host "Created group: $($group.Name)"
    } catch {
        Write-Warning "Failed to create group $($group.Name) : $_"
    }
}
"""

    def _generate_gpo_import_script(self, gpo_data: ExtractedData) -> str:
        """Generate script to import GPOs.

        Args:
            gpo_data: GPO configuration

        Returns:
            PowerShell script
        """
        return """# Import Group Policy Objects
# NOTE: GPO backups should be in C:\\GPOBackup directory

$backupPath = "C:\\GPOBackup"

if (Test-Path $backupPath) {
    $gpos = Get-ChildItem $backupPath -Directory

    foreach ($gpo in $gpos) {
        try {
            Import-GPO -BackupId $gpo.Name -TargetName $gpo.Name -Path $backupPath
            Write-Host "Imported GPO: $($gpo.Name)"
        } catch {
            Write-Warning "Failed to import GPO $($gpo.Name) : $_"
        }
    }
} else {
    Write-Warning "GPO backup directory not found: $backupPath"
}
"""

    def _generate_dns_config_script(self, dns_data: ExtractedData) -> str:
        """Generate script to configure DNS.

        Args:
            dns_data: DNS configuration

        Returns:
            PowerShell script
        """
        return """# Configure DNS records
$records = @(
    @{Name="atevet12ads001"; Zone="simuland.local"; Type="A"; Data="10.0.1.4"},
    @{Name="atevet12win001"; Zone="simuland.local"; Type="A"; Data="10.0.1.5"}
)

foreach ($record in $records) {
    try {
        Add-DnsServerResourceRecordA `
            -Name $record.Name `
            -ZoneName $record.Zone `
            -IPv4Address $record.Data
        Write-Host "Created DNS record: $($record.Name)"
    } catch {
        Write-Warning "Failed to create DNS record $($record.Name) : $_"
    }
}
"""

    def _generate_validation_script(self) -> str:
        """Generate validation script.

        Returns:
            PowerShell script
        """
        return """# Validate AD replication and health
$results = @{}

# Test AD replication
try {
    $repl = Get-ADReplicationPartnerMetadata -Target $env:COMPUTERNAME
    $results['Replication'] = 'OK'
} catch {
    $results['Replication'] = "FAILED: $_"
}

# Test DNS
try {
    $dns = Resolve-DnsName -Name $env:USERDNSDOMAIN
    $results['DNS'] = 'OK'
} catch {
    $results['DNS'] = "FAILED: $_"
}

# Check SYSVOL
if (Test-Path "C:\\Windows\\SYSVOL") {
    $results['SYSVOL'] = 'OK'
} else {
    $results['SYSVOL'] = 'FAILED'
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
        """Execute a replication step on target DC.

        Args:
            step: Step to execute
            target_resource_id: Target DC resource ID

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
