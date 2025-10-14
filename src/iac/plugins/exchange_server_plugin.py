"""Exchange Server replication plugin for Exchange Server VMs.

This plugin handles data-plane replication for Microsoft Exchange Server instances,
including organization configuration, mailbox databases, mailbox metadata, distribution
groups, mail flow rules, client access settings, and public folders.

Security Note: This plugin NEVER extracts actual mailbox content, password hashes,
or service credentials. Generated configurations use placeholder passwords that must
be manually set. Mailbox content migration must be done using native Exchange tools.

Complexity: VERY_HIGH - Exchange is one of the most complex Microsoft server products.
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


class ExchangeServerReplicationPlugin(ResourceReplicationPlugin):
    """Handles Exchange Server instance replication.

    This plugin replicates Exchange Server configuration and metadata:
    - Exchange organization settings
    - Mailbox databases (metadata only, not content)
    - User mailboxes list (metadata: sizes, quotas, permissions)
    - Distribution groups and mail-enabled security groups
    - Send/Receive connectors
    - Transport rules
    - Accepted domains and email address policies
    - Client access virtual directories (OWA, EWS, MAPI, ActiveSync, OAB)
    - Public folder structure (if used)

    Does NOT replicate:
    - Actual mailbox content (too large, use native Exchange tools)
    - Password hashes or service credentials
    - Full database backups (use Exchange native backup)

    Requires:
    - WinRM access to Exchange server
    - PowerShell 5.1+ with Exchange Management Shell
    - Exchange admin credentials
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        """Initialize the Exchange Server plugin.

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
            name="exchange_server",
            version="1.0.0",
            description="Replicates Exchange Server organization configuration and mailbox metadata",
            author="Azure Tenant Grapher",
            resource_types=["Microsoft.Compute/virtualMachines"],
            supported_formats=[
                ExtractionFormat.POWERSHELL_DSC,
                ExtractionFormat.JSON,
                ExtractionFormat.CSV,
            ],
            requires_credentials=True,
            requires_network_access=True,
            complexity="VERY_HIGH",
            estimated_effort_weeks=4.0,
            tags=["exchange", "exchange-server", "mail", "windows", "office365-hybrid"],
            documentation_url="https://docs.microsoft.com/en-us/exchange/exchange-server",
        )

    def can_handle(self, resource: Dict[str, Any]) -> bool:
        """Check if resource is an Exchange Server VM.

        Args:
            resource: Resource dictionary

        Returns:
            True if resource is a Windows VM with Exchange Server role
        """
        if not super().can_handle(resource):
            return False

        # Check for Exchange indicators
        tags = resource.get("tags", {})
        name = resource.get("name", "").lower()

        # Check tags for Exchange role
        role = tags.get("role", "").lower()
        if "exchange" in role or "mail" in role or "ex" == role:
            return True

        # Check VM name patterns (common Exchange naming conventions)
        if any(pattern in name for pattern in ["ex", "exchange", "mail", "mbx"]):
            return True

        # Check for Exchange in tag values
        if any("exchange" in str(v).lower() for v in tags.values()):
            return True

        return False

    async def analyze_source(
        self, resource: Dict[str, Any]
    ) -> DataPlaneAnalysis:
        """Analyze Exchange Server instance on source VM.

        Args:
            resource: Source VM resource dictionary

        Returns:
            DataPlaneAnalysis with discovered Exchange elements

        Raises:
            ConnectionError: If cannot connect to Exchange server
            PermissionError: If lacking Exchange admin permissions
        """
        logger.info(f"Analyzing Exchange Server on {resource.get('name')}")

        resource_id = resource.get("id", "unknown")
        elements: List[DataPlaneElement] = []
        warnings: List[str] = []
        errors: List[str] = []

        try:
            # Check connectivity
            if not await self._check_winrm_connectivity(resource):
                raise ConnectionError("Cannot connect to Exchange server via WinRM")

            # Analyze Exchange organization
            org_info = await self._analyze_organization(resource)
            if org_info:
                elements.append(
                    DataPlaneElement(
                        name="exchange_organization",
                        element_type="Exchange Organization",
                        description=f"Exchange Org: {org_info.get('name', 'unknown')}",
                        complexity="MEDIUM",
                        estimated_size_mb=0.5,
                        dependencies=[],
                        metadata=org_info,
                    )
                )

            # Analyze mailbox databases
            db_count = await self._count_mailbox_databases(resource)
            if db_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="mailbox_databases",
                        element_type="Mailbox Databases",
                        description=f"{db_count} mailbox databases (metadata only)",
                        complexity="HIGH",
                        estimated_size_mb=db_count * 0.5,
                        dependencies=["exchange_organization"],
                        metadata={"count": db_count},
                    )
                )

            # Analyze mailboxes
            mailbox_count = await self._count_mailboxes(resource)
            if mailbox_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="mailboxes",
                        element_type="Mailboxes",
                        description=f"{mailbox_count} mailboxes (metadata only, no content)",
                        complexity="VERY_HIGH",
                        estimated_size_mb=mailbox_count * 0.1,
                        dependencies=["mailbox_databases"],
                        metadata={"count": mailbox_count},
                    )
                )
                warnings.append(
                    f"Mailbox content NOT extracted ({mailbox_count} mailboxes) - use native Exchange tools for content migration"
                )

            # Analyze distribution groups
            group_count = await self._count_distribution_groups(resource)
            if group_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="distribution_groups",
                        element_type="Distribution Groups",
                        description=f"{group_count} distribution groups and mail-enabled security groups",
                        complexity="MEDIUM",
                        estimated_size_mb=group_count * 0.05,
                        dependencies=["exchange_organization"],
                        metadata={"count": group_count},
                    )
                )

            # Analyze mail flow
            transport_count = await self._count_transport_rules(resource)
            connector_count = await self._count_connectors(resource)
            if transport_count > 0 or connector_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="mail_flow",
                        element_type="Mail Flow",
                        description=f"{transport_count} transport rules, {connector_count} connectors",
                        complexity="HIGH",
                        estimated_size_mb=0.5,
                        dependencies=["exchange_organization"],
                        metadata={
                            "transport_rules": transport_count,
                            "connectors": connector_count,
                        },
                    )
                )

            # Analyze accepted domains
            domain_count = await self._count_accepted_domains(resource)
            if domain_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="accepted_domains",
                        element_type="Accepted Domains",
                        description=f"{domain_count} accepted domains and email address policies",
                        complexity="MEDIUM",
                        estimated_size_mb=0.1,
                        dependencies=["exchange_organization"],
                        metadata={"count": domain_count},
                    )
                )

            # Analyze client access
            vdir_count = await self._count_virtual_directories(resource)
            if vdir_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="client_access",
                        element_type="Client Access",
                        description=f"{vdir_count} virtual directories (OWA, EWS, MAPI, ActiveSync, OAB)",
                        complexity="HIGH",
                        estimated_size_mb=0.3,
                        dependencies=["exchange_organization"],
                        metadata={"count": vdir_count},
                    )
                )

            # Analyze public folders (if enabled)
            pf_count = await self._count_public_folders(resource)
            if pf_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="public_folders",
                        element_type="Public Folders",
                        description=f"{pf_count} public folders (structure only)",
                        complexity="MEDIUM",
                        estimated_size_mb=pf_count * 0.02,
                        dependencies=["exchange_organization"],
                        metadata={"count": pf_count},
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
                connection_methods=["WinRM", "PowerShell", "Exchange Management Shell"],
                estimated_extraction_time_minutes=max(20, len(elements) * 15),
                warnings=warnings,
                errors=errors,
                metadata={
                    "exchange_version": org_info.get("version") if org_info else None,
                    "organization_name": org_info.get("name") if org_info else None,
                },
            )

        except Exception as e:
            logger.error(f"Failed to analyze Exchange Server: {e}")
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
        """Extract Exchange Server data from source instance.

        Args:
            resource: Source VM resource dictionary
            analysis: Previous analysis result

        Returns:
            ExtractionResult with extracted Exchange data

        Raises:
            ConnectionError: If cannot connect to Exchange server
            IOError: If cannot write extracted data
        """
        logger.info(f"Extracting Exchange Server data from {resource.get('name')}")

        resource_id = resource.get("id", "unknown")
        extracted_data: List[ExtractedData] = []
        warnings: List[str] = []
        errors: List[str] = []
        items_extracted = 0
        items_failed = 0
        start_time = datetime.utcnow()

        # Get output directory
        output_dir = Path(
            self.get_config_value("output_dir", "./exchange_extraction")
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Extract organization configuration
            if self._has_element(analysis, "exchange_organization"):
                try:
                    org_data = await self._extract_organization_config(
                        resource, output_dir
                    )
                    extracted_data.append(org_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract organization config: {e}")
                    errors.append(f"Organization config: {e}")
                    items_failed += 1

            # Extract mailbox databases
            if self._has_element(analysis, "mailbox_databases"):
                try:
                    db_data = await self._extract_mailbox_databases(resource, output_dir)
                    extracted_data.append(db_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract mailbox databases: {e}")
                    errors.append(f"Mailbox databases: {e}")
                    items_failed += 1

            # Extract mailbox metadata
            if self._has_element(analysis, "mailboxes"):
                try:
                    mailbox_data = await self._extract_mailboxes(resource, output_dir)
                    extracted_data.append(mailbox_data)
                    items_extracted += 1
                    warnings.append(
                        "Mailbox metadata extracted - actual mailbox content must be migrated using native Exchange tools"
                    )
                except Exception as e:
                    logger.error(f"Failed to extract mailboxes: {e}")
                    errors.append(f"Mailboxes: {e}")
                    items_failed += 1

            # Extract distribution groups
            if self._has_element(analysis, "distribution_groups"):
                try:
                    group_data = await self._extract_distribution_groups(
                        resource, output_dir
                    )
                    extracted_data.append(group_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract distribution groups: {e}")
                    errors.append(f"Distribution groups: {e}")
                    items_failed += 1

            # Extract mail flow configuration
            if self._has_element(analysis, "mail_flow"):
                try:
                    mail_flow_data = await self._extract_mail_flow(resource, output_dir)
                    extracted_data.append(mail_flow_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract mail flow: {e}")
                    errors.append(f"Mail flow: {e}")
                    items_failed += 1

            # Extract accepted domains
            if self._has_element(analysis, "accepted_domains"):
                try:
                    domain_data = await self._extract_accepted_domains(
                        resource, output_dir
                    )
                    extracted_data.append(domain_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract accepted domains: {e}")
                    errors.append(f"Accepted domains: {e}")
                    items_failed += 1

            # Extract client access settings
            if self._has_element(analysis, "client_access"):
                try:
                    client_data = await self._extract_client_access(resource, output_dir)
                    extracted_data.append(client_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract client access: {e}")
                    errors.append(f"Client access: {e}")
                    items_failed += 1

            # Extract public folders
            if self._has_element(analysis, "public_folders"):
                try:
                    pf_data = await self._extract_public_folders(resource, output_dir)
                    extracted_data.append(pf_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract public folders: {e}")
                    errors.append(f"Public folders: {e}")
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
        """Generate PowerShell steps to replicate Exchange to target.

        Args:
            extraction: Result from extract_data()

        Returns:
            List of ReplicationStep objects in execution order
        """
        logger.info("Generating Exchange Server replication steps")

        steps: List[ReplicationStep] = []

        # Step 1: Prerequisites
        steps.append(
            ReplicationStep(
                step_id="prereq_exchange_install",
                step_type=StepType.PREREQUISITE,
                description="Verify Exchange Server installation and prerequisites",
                script_content=self._generate_prereq_check_script(),
                script_format=ExtractionFormat.POWERSHELL_DSC,
                depends_on=[],
                estimated_duration_minutes=10,
                is_critical=True,
                can_retry=True,
                max_retries=2,
            )
        )

        # Step 2: Configure organization settings
        org_data = self._find_extracted_data(extraction, "organization")
        if org_data:
            steps.append(
                ReplicationStep(
                    step_id="configure_organization",
                    step_type=StepType.CONFIGURATION,
                    description="Apply Exchange organization settings",
                    script_content=self._generate_organization_config_script(org_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["prereq_exchange_install"],
                    estimated_duration_minutes=10,
                    is_critical=True,
                    can_retry=True,
                )
            )

        # Step 3: Create mailbox databases
        db_data = self._find_extracted_data(extraction, "mailbox_database")
        if db_data:
            steps.append(
                ReplicationStep(
                    step_id="create_mailbox_databases",
                    step_type=StepType.CONFIGURATION,
                    description="Create mailbox databases",
                    script_content=self._generate_database_creation_script(db_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["configure_organization"],
                    estimated_duration_minutes=15,
                    is_critical=True,
                    can_retry=True,
                )
            )

        # Step 4: Create accepted domains
        domain_data = self._find_extracted_data(extraction, "accepted_domain")
        if domain_data:
            steps.append(
                ReplicationStep(
                    step_id="create_accepted_domains",
                    step_type=StepType.CONFIGURATION,
                    description="Create accepted domains and email address policies",
                    script_content=self._generate_accepted_domains_script(domain_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["configure_organization"],
                    estimated_duration_minutes=5,
                    is_critical=True,
                    can_retry=True,
                )
            )

        # Step 5: Configure mail flow
        mail_flow_data = self._find_extracted_data(extraction, "mail_flow")
        if mail_flow_data:
            steps.append(
                ReplicationStep(
                    step_id="configure_mail_flow",
                    step_type=StepType.CONFIGURATION,
                    description="Configure send/receive connectors and transport rules",
                    script_content=self._generate_mail_flow_script(mail_flow_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["create_accepted_domains"],
                    estimated_duration_minutes=10,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 6: Create mailboxes (metadata only)
        mailbox_data = self._find_extracted_data(extraction, "mailbox")
        if mailbox_data:
            # Build dependency list - mailbox databases are required, accepted domains are preferred
            mailbox_deps = []
            if self._find_extracted_data(extraction, "mailbox_database"):
                mailbox_deps.append("create_mailbox_databases")
            if self._find_extracted_data(extraction, "accepted_domain"):
                mailbox_deps.append("create_accepted_domains")
            if not mailbox_deps:
                mailbox_deps.append("configure_organization")

            steps.append(
                ReplicationStep(
                    step_id="create_mailboxes",
                    step_type=StepType.DATA_IMPORT,
                    description="Create mailboxes (metadata only - content must be migrated separately)",
                    script_content=self._generate_mailbox_creation_script(mailbox_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=mailbox_deps,
                    estimated_duration_minutes=20,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 7: Create distribution groups
        group_data = self._find_extracted_data(extraction, "distribution_group")
        if group_data:
            steps.append(
                ReplicationStep(
                    step_id="create_distribution_groups",
                    step_type=StepType.DATA_IMPORT,
                    description="Create distribution groups and mail-enabled security groups",
                    script_content=self._generate_distribution_groups_script(
                        group_data
                    ),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["create_mailboxes"],
                    estimated_duration_minutes=10,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 8: Configure client access
        client_data = self._find_extracted_data(extraction, "client_access")
        if client_data:
            steps.append(
                ReplicationStep(
                    step_id="configure_client_access",
                    step_type=StepType.CONFIGURATION,
                    description="Configure virtual directories (OWA, EWS, MAPI, ActiveSync, OAB)",
                    script_content=self._generate_client_access_script(client_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["configure_organization"],
                    estimated_duration_minutes=10,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 9: Create public folders
        pf_data = self._find_extracted_data(extraction, "public_folder")
        if pf_data:
            steps.append(
                ReplicationStep(
                    step_id="create_public_folders",
                    step_type=StepType.DATA_IMPORT,
                    description="Create public folder structure",
                    script_content=self._generate_public_folders_script(pf_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["create_mailbox_databases"],
                    estimated_duration_minutes=10,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 10: Validation
        steps.append(
            ReplicationStep(
                step_id="validate_exchange",
                step_type=StepType.VALIDATION,
                description="Validate Exchange Server configuration and health",
                script_content=self._generate_validation_script(),
                script_format=ExtractionFormat.POWERSHELL_DSC,
                depends_on=[s.step_id for s in steps],
                estimated_duration_minutes=10,
                is_critical=False,
                can_retry=True,
            )
        )

        return steps

    async def apply_to_target(
        self, steps: List[ReplicationStep], target_resource_id: str
    ) -> ReplicationResult:
        """Apply Exchange replication steps to target server.

        Args:
            steps: Replication steps to execute
            target_resource_id: Azure resource ID of target VM

        Returns:
            ReplicationResult with execution status
        """
        logger.info(f"Applying Exchange Server replication to {target_resource_id}")

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
        """Check if WinRM is accessible on the Exchange server.

        Args:
            resource: Resource dictionary

        Returns:
            True if WinRM is accessible
        """
        # In real implementation, would use pywinrm
        # For now, return True if not in strict mode
        return not self.get_config_value("strict_validation", False)

    async def _analyze_organization(
        self, resource: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Analyze Exchange organization configuration.

        Args:
            resource: Resource dictionary

        Returns:
            Organization info dictionary or None
        """
        # Mock implementation - real version would use Get-OrganizationConfig
        return {
            "name": "Simuland",
            "version": "Exchange Server 2019 CU12",
            "build": "15.2.1118.7",
            "admin_display_version": "Version 15.2 (Build 1118.7)",
        }

    async def _count_mailbox_databases(self, resource: Dict[str, Any]) -> int:
        """Count mailbox databases.

        Args:
            resource: Resource dictionary

        Returns:
            Number of mailbox databases
        """
        # Mock implementation - real version would use Get-MailboxDatabase
        return 2

    async def _count_mailboxes(self, resource: Dict[str, Any]) -> int:
        """Count user mailboxes.

        Args:
            resource: Resource dictionary

        Returns:
            Number of mailboxes
        """
        # Mock implementation - real version would use Get-Mailbox -ResultSize Unlimited
        return 25

    async def _count_distribution_groups(self, resource: Dict[str, Any]) -> int:
        """Count distribution groups.

        Args:
            resource: Resource dictionary

        Returns:
            Number of distribution groups
        """
        # Mock implementation - real version would use Get-DistributionGroup
        return 10

    async def _count_transport_rules(self, resource: Dict[str, Any]) -> int:
        """Count transport rules.

        Args:
            resource: Resource dictionary

        Returns:
            Number of transport rules
        """
        # Mock implementation - real version would use Get-TransportRule
        return 5

    async def _count_connectors(self, resource: Dict[str, Any]) -> int:
        """Count send and receive connectors.

        Args:
            resource: Resource dictionary

        Returns:
            Number of connectors
        """
        # Mock implementation - real version would use Get-SendConnector and Get-ReceiveConnector
        return 4

    async def _count_accepted_domains(self, resource: Dict[str, Any]) -> int:
        """Count accepted domains.

        Args:
            resource: Resource dictionary

        Returns:
            Number of accepted domains
        """
        # Mock implementation - real version would use Get-AcceptedDomain
        return 2

    async def _count_virtual_directories(self, resource: Dict[str, Any]) -> int:
        """Count virtual directories.

        Args:
            resource: Resource dictionary

        Returns:
            Number of virtual directories
        """
        # Mock implementation - real version would query OWA, EWS, MAPI, etc.
        return 10

    async def _count_public_folders(self, resource: Dict[str, Any]) -> int:
        """Count public folders.

        Args:
            resource: Resource dictionary

        Returns:
            Number of public folders
        """
        # Mock implementation - real version would use Get-PublicFolder -Recurse
        return 5

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
        score = min(10, 5 + len(elements) // 2)

        # Increase for very high-complexity elements
        very_high_complexity = sum(
            1 for e in elements if e.complexity == "VERY_HIGH"
        )
        score = min(10, score + very_high_complexity)

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

    async def _extract_organization_config(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract Exchange organization configuration.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with organization config
        """
        # Mock implementation
        content = json.dumps(
            {
                "organization_name": "Simuland",
                "exchange_version": "Exchange Server 2019 CU12",
                "build": "15.2.1118.7",
                "settings": {
                    "max_send_size_mb": 25,
                    "max_receive_size_mb": 35,
                    "retention_policy_enabled": True,
                },
            },
            indent=2,
        )

        file_path = output_dir / "organization_config.json"
        file_path.write_text(content)

        return ExtractedData(
            name="organization_config",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_mailbox_databases(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract mailbox database configurations.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with mailbox database info
        """
        # Mock implementation
        content = json.dumps(
            {
                "databases": [
                    {
                        "name": "MailboxDB01",
                        "server": "atevet12ex001",
                        "edb_file_path": "D:\\ExchangeDatabases\\MailboxDB01\\MailboxDB01.edb",
                        "log_folder_path": "D:\\ExchangeDatabases\\MailboxDB01",
                        "is_mailbox_database": True,
                        "mounted": True,
                    },
                    {
                        "name": "MailboxDB02",
                        "server": "atevet12ex002",
                        "edb_file_path": "D:\\ExchangeDatabases\\MailboxDB02\\MailboxDB02.edb",
                        "log_folder_path": "D:\\ExchangeDatabases\\MailboxDB02",
                        "is_mailbox_database": True,
                        "mounted": True,
                    },
                ]
            },
            indent=2,
        )

        file_path = output_dir / "mailbox_databases.json"
        file_path.write_text(content)

        return ExtractedData(
            name="mailbox_databases",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_mailboxes(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract mailbox metadata (NOT content).

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with mailbox metadata
        """
        # Mock implementation - would use Get-Mailbox -ResultSize Unlimited
        mailboxes = []
        for i in range(1, 6):  # Sample 5 mailboxes
            mailboxes.append(
                {
                    "display_name": f"User {i}",
                    "alias": f"user{i}",
                    "primary_smtp_address": f"user{i}@simuland.local",
                    "database": "MailboxDB01" if i <= 3 else "MailboxDB02",
                    "mailbox_size_mb": 150 * i,
                    "item_count": 1000 * i,
                    "issue_warning_quota_mb": 1900,
                    "prohibit_send_quota_mb": 2000,
                    "prohibit_send_receive_quota_mb": 2300,
                    "note": "Content NOT extracted - use New-MoveRequest or PST export for mailbox content migration",
                }
            )

        content = json.dumps(
            {
                "mailboxes": mailboxes,
                "total_count": len(mailboxes),
                "note": "This export contains METADATA ONLY. Actual mailbox content must be migrated using Exchange native tools (New-MoveRequest, New-MailboxExportRequest, or third-party migration tools).",
            },
            indent=2,
        )

        file_path = output_dir / "mailboxes.json"
        file_path.write_text(content)

        # Also create CSV for easy viewing
        csv_content = "DisplayName,Alias,PrimarySmtpAddress,Database,SizeMB,ItemCount\n"
        for mb in mailboxes:
            csv_content += f"{mb['display_name']},{mb['alias']},{mb['primary_smtp_address']},{mb['database']},{mb['mailbox_size_mb']},{mb['item_count']}\n"

        csv_path = output_dir / "mailboxes.csv"
        csv_path.write_text(csv_content)

        return ExtractedData(
            name="mailboxes",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
            metadata={"csv_file": str(csv_path)},
        )

    async def _extract_distribution_groups(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract distribution groups and memberships.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with distribution groups
        """
        # Mock implementation
        content = json.dumps(
            {
                "distribution_groups": [
                    {
                        "name": "All Staff",
                        "alias": "allstaff",
                        "primary_smtp_address": "allstaff@simuland.local",
                        "group_type": "Universal",
                        "members": ["user1@simuland.local", "user2@simuland.local"],
                    },
                    {
                        "name": "IT Department",
                        "alias": "itdept",
                        "primary_smtp_address": "itdept@simuland.local",
                        "group_type": "Universal",
                        "members": ["user3@simuland.local"],
                    },
                ]
            },
            indent=2,
        )

        file_path = output_dir / "distribution_groups.json"
        file_path.write_text(content)

        return ExtractedData(
            name="distribution_groups",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_mail_flow(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract mail flow configuration.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with mail flow config
        """
        # Mock implementation
        content = json.dumps(
            {
                "send_connectors": [
                    {
                        "name": "Internet Send Connector",
                        "address_spaces": ["SMTP:*;1"],
                        "source_transport_servers": ["atevet12ex001"],
                        "smart_hosts": [],
                    }
                ],
                "receive_connectors": [
                    {
                        "name": "Default atevet12ex001",
                        "bindings": ["0.0.0.0:25"],
                        "remote_ip_ranges": ["0.0.0.0-255.255.255.255"],
                    }
                ],
                "transport_rules": [
                    {
                        "name": "Disclaimer Rule",
                        "state": "Enabled",
                        "description": "Add company disclaimer to outbound email",
                    }
                ],
            },
            indent=2,
        )

        file_path = output_dir / "mail_flow.json"
        file_path.write_text(content)

        return ExtractedData(
            name="mail_flow",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_accepted_domains(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract accepted domains and email address policies.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with accepted domains
        """
        # Mock implementation
        content = json.dumps(
            {
                "accepted_domains": [
                    {
                        "name": "simuland.local",
                        "domain_name": "simuland.local",
                        "domain_type": "Authoritative",
                        "default": True,
                    }
                ],
                "email_address_policies": [
                    {
                        "name": "Default Policy",
                        "priority": 1,
                        "enabled_primary_smtp_address_template": "SMTP:%m@simuland.local",
                    }
                ],
            },
            indent=2,
        )

        file_path = output_dir / "accepted_domains.json"
        file_path.write_text(content)

        return ExtractedData(
            name="accepted_domains",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_client_access(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract client access settings.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with client access config
        """
        # Mock implementation
        content = json.dumps(
            {
                "owa_virtual_directories": [
                    {
                        "server": "atevet12ex001",
                        "internal_url": "https://atevet12ex001.simuland.local/owa",
                        "external_url": "https://mail.simuland.com/owa",
                    }
                ],
                "ews_virtual_directories": [
                    {
                        "server": "atevet12ex001",
                        "internal_url": "https://atevet12ex001.simuland.local/EWS/Exchange.asmx",
                        "external_url": "https://mail.simuland.com/EWS/Exchange.asmx",
                    }
                ],
                "activesync_virtual_directories": [
                    {
                        "server": "atevet12ex001",
                        "internal_url": "https://atevet12ex001.simuland.local/Microsoft-Server-ActiveSync",
                        "external_url": "https://mail.simuland.com/Microsoft-Server-ActiveSync",
                    }
                ],
                "oab_virtual_directories": [
                    {
                        "server": "atevet12ex001",
                        "internal_url": "https://atevet12ex001.simuland.local/OAB",
                        "external_url": "https://mail.simuland.com/OAB",
                    }
                ],
                "mapi_virtual_directories": [
                    {
                        "server": "atevet12ex001",
                        "internal_url": "https://atevet12ex001.simuland.local/mapi",
                        "external_url": "https://mail.simuland.com/mapi",
                    }
                ],
            },
            indent=2,
        )

        file_path = output_dir / "client_access.json"
        file_path.write_text(content)

        return ExtractedData(
            name="client_access",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_public_folders(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract public folder structure.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with public folders
        """
        # Mock implementation
        content = json.dumps(
            {
                "public_folders": [
                    {
                        "name": "All Public Folders",
                        "path": "\\",
                        "item_count": 0,
                    },
                    {
                        "name": "Company Documents",
                        "path": "\\Company Documents",
                        "item_count": 50,
                    },
                ],
                "note": "Public folder structure only - content must be migrated separately",
            },
            indent=2,
        )

        file_path = output_dir / "public_folders.json"
        file_path.write_text(content)

        return ExtractedData(
            name="public_folders",
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

    def _generate_prereq_check_script(self) -> str:
        """Generate PowerShell script to check Exchange prerequisites.

        Returns:
            PowerShell script content
        """
        return """# Check Exchange Server installation and prerequisites

# Import Exchange Management Shell
try {
    Add-PSSnapin Microsoft.Exchange.Management.PowerShell.SnapIn -ErrorAction Stop
    Write-Host "Exchange Management Shell loaded successfully"
} catch {
    Write-Error "Exchange Management Shell not found. Ensure Exchange Server is installed."
    exit 1
}

# Check Exchange Server version
try {
    $exVersion = Get-ExchangeServer | Select-Object -First 1 -ExpandProperty AdminDisplayVersion
    Write-Host "Exchange Server version: $exVersion"
} catch {
    Write-Error "Cannot query Exchange Server: $_"
    exit 1
}

# Verify Exchange services are running
$exServices = @('MSExchangeServiceHost', 'MSExchangeTransport', 'MSExchangeIS')
foreach ($svc in $exServices) {
    $service = Get-Service -Name $svc -ErrorAction SilentlyContinue
    if ($service) {
        if ($service.Status -ne 'Running') {
            Write-Warning "Service $svc is not running: $($service.Status)"
        } else {
            Write-Host "Service $svc is running"
        }
    } else {
        Write-Warning "Service $svc not found"
    }
}

Write-Host "Exchange prerequisite check completed"
"""

    def _generate_organization_config_script(self, org_data: ExtractedData) -> str:
        """Generate script to configure organization settings.

        Args:
            org_data: Organization configuration data

        Returns:
            PowerShell script
        """
        return """# Configure Exchange organization settings

Add-PSSnapin Microsoft.Exchange.Management.PowerShell.SnapIn -ErrorAction SilentlyContinue

# Get organization config
$orgConfig = Get-OrganizationConfig

# Set max send/receive sizes
Set-TransportConfig -MaxSendSize 25MB -MaxReceiveSize 35MB

# Enable retention policy (if needed)
# Set-OrganizationConfig -RetentionPolicyEnabled $true

Write-Host "Organization configuration applied"
"""

    def _generate_database_creation_script(self, db_data: ExtractedData) -> str:
        """Generate script to create mailbox databases.

        Args:
            db_data: Database configuration data

        Returns:
            PowerShell script
        """
        return """# Create mailbox databases

Add-PSSnapin Microsoft.Exchange.Management.PowerShell.SnapIn -ErrorAction SilentlyContinue

# Create MailboxDB01
if (-not (Get-MailboxDatabase -Identity "MailboxDB01" -ErrorAction SilentlyContinue)) {
    New-MailboxDatabase -Name "MailboxDB01" `
        -Server $env:COMPUTERNAME `
        -EdbFilePath "D:\\ExchangeDatabases\\MailboxDB01\\MailboxDB01.edb" `
        -LogFolderPath "D:\\ExchangeDatabases\\MailboxDB01"

    Write-Host "Created mailbox database: MailboxDB01"

    # Mount the database
    Mount-Database -Identity "MailboxDB01"
    Write-Host "Mounted mailbox database: MailboxDB01"
} else {
    Write-Host "Mailbox database MailboxDB01 already exists"
}

Write-Host "Mailbox database creation completed"
"""

    def _generate_accepted_domains_script(self, domain_data: ExtractedData) -> str:
        """Generate script to create accepted domains.

        Args:
            domain_data: Domain configuration data

        Returns:
            PowerShell script
        """
        return """# Create accepted domains and email address policies

Add-PSSnapin Microsoft.Exchange.Management.PowerShell.SnapIn -ErrorAction SilentlyContinue

# Create accepted domain (if not default)
if (-not (Get-AcceptedDomain -Identity "simuland.local" -ErrorAction SilentlyContinue)) {
    New-AcceptedDomain -Name "simuland.local" `
        -DomainName "simuland.local" `
        -DomainType Authoritative `
        -MakeDefault $true

    Write-Host "Created accepted domain: simuland.local"
} else {
    Write-Host "Accepted domain simuland.local already exists"
}

# Update email address policy (if needed)
# New-EmailAddressPolicy -Name "Default Policy" -IncludedRecipients AllRecipients -EnabledPrimarySMTPAddressTemplate "SMTP:%m@simuland.local"

Write-Host "Accepted domains configuration completed"
"""

    def _generate_mail_flow_script(self, mail_flow_data: ExtractedData) -> str:
        """Generate script to configure mail flow.

        Args:
            mail_flow_data: Mail flow configuration data

        Returns:
            PowerShell script
        """
        return """# Configure mail flow (connectors and transport rules)

Add-PSSnapin Microsoft.Exchange.Management.PowerShell.SnapIn -ErrorAction SilentlyContinue

# Create Send Connector (if needed)
if (-not (Get-SendConnector -Identity "Internet Send Connector" -ErrorAction SilentlyContinue)) {
    New-SendConnector -Name "Internet Send Connector" `
        -AddressSpaces "SMTP:*;1" `
        -SourceTransportServers $env:COMPUTERNAME `
        -Usage Internet

    Write-Host "Created send connector: Internet Send Connector"
} else {
    Write-Host "Send connector Internet Send Connector already exists"
}

# Receive connectors are typically created during Exchange installation

# Create transport rules (example)
# New-TransportRule -Name "Disclaimer Rule" -ApplyHtmlDisclaimerText "<p>Company Disclaimer</p>" -ApplyHtmlDisclaimerLocation Append

Write-Host "Mail flow configuration completed"
"""

    def _generate_mailbox_creation_script(self, mailbox_data: ExtractedData) -> str:
        """Generate script to create mailboxes.

        Args:
            mailbox_data: Mailbox configuration data

        Returns:
            PowerShell script
        """
        return """# Create mailboxes (metadata only - content must be migrated separately)
# WARNING: This creates EMPTY mailboxes. Use New-MoveRequest or Import-PST for content migration.

Add-PSSnapin Microsoft.Exchange.Management.PowerShell.SnapIn -ErrorAction SilentlyContinue

# Sample mailbox creation
$mailboxes = @(
    @{Alias="user1"; Name="User 1"; Database="MailboxDB01"},
    @{Alias="user2"; Name="User 2"; Database="MailboxDB01"},
    @{Alias="user3"; Name="User 3"; Database="MailboxDB01"}
)

foreach ($mb in $mailboxes) {
    if (-not (Get-Mailbox -Identity $mb.Alias -ErrorAction SilentlyContinue)) {
        # NOTE: This requires AD user to exist first
        # Enable-Mailbox -Identity $mb.Alias -Database $mb.Database
        Write-Host "Would create mailbox: $($mb.Alias) (requires AD user)"
    } else {
        Write-Host "Mailbox $($mb.Alias) already exists"
    }
}

Write-Host "Mailbox creation completed"
Write-Host "IMPORTANT: Mailbox content must be migrated using New-MoveRequest, New-MailboxExportRequest, or PST import"
"""

    def _generate_distribution_groups_script(
        self, group_data: ExtractedData
    ) -> str:
        """Generate script to create distribution groups.

        Args:
            group_data: Distribution group configuration data

        Returns:
            PowerShell script
        """
        return """# Create distribution groups and mail-enabled security groups

Add-PSSnapin Microsoft.Exchange.Management.PowerShell.SnapIn -ErrorAction SilentlyContinue

# Sample distribution group creation
$groups = @(
    @{Name="All Staff"; Alias="allstaff"; Type="Distribution"},
    @{Name="IT Department"; Alias="itdept"; Type="Distribution"}
)

foreach ($grp in $groups) {
    if (-not (Get-DistributionGroup -Identity $grp.Alias -ErrorAction SilentlyContinue)) {
        New-DistributionGroup -Name $grp.Name `
            -Alias $grp.Alias `
            -Type $grp.Type `
            -PrimarySmtpAddress "$($grp.Alias)@simuland.local"

        Write-Host "Created distribution group: $($grp.Name)"
    } else {
        Write-Host "Distribution group $($grp.Name) already exists"
    }
}

# Add members (requires mailboxes to exist)
# Add-DistributionGroupMember -Identity "allstaff" -Member "user1"

Write-Host "Distribution group creation completed"
"""

    def _generate_client_access_script(self, client_data: ExtractedData) -> str:
        """Generate script to configure client access.

        Args:
            client_data: Client access configuration data

        Returns:
            PowerShell script
        """
        return """# Configure client access virtual directories

Add-PSSnapin Microsoft.Exchange.Management.PowerShell.SnapIn -ErrorAction SilentlyContinue

# Configure OWA virtual directory
$owaVdir = Get-OwaVirtualDirectory -Server $env:COMPUTERNAME | Select-Object -First 1
if ($owaVdir) {
    Set-OwaVirtualDirectory -Identity $owaVdir.Identity `
        -InternalUrl "https://$($env:COMPUTERNAME).simuland.local/owa" `
        -ExternalUrl "https://mail.simuland.com/owa"
    Write-Host "Configured OWA virtual directory"
}

# Configure EWS virtual directory
$ewsVdir = Get-WebServicesVirtualDirectory -Server $env:COMPUTERNAME | Select-Object -First 1
if ($ewsVdir) {
    Set-WebServicesVirtualDirectory -Identity $ewsVdir.Identity `
        -InternalUrl "https://$($env:COMPUTERNAME).simuland.local/EWS/Exchange.asmx" `
        -ExternalUrl "https://mail.simuland.com/EWS/Exchange.asmx"
    Write-Host "Configured EWS virtual directory"
}

# Configure ActiveSync virtual directory
$asVdir = Get-ActiveSyncVirtualDirectory -Server $env:COMPUTERNAME | Select-Object -First 1
if ($asVdir) {
    Set-ActiveSyncVirtualDirectory -Identity $asVdir.Identity `
        -InternalUrl "https://$($env:COMPUTERNAME).simuland.local/Microsoft-Server-ActiveSync" `
        -ExternalUrl "https://mail.simuland.com/Microsoft-Server-ActiveSync"
    Write-Host "Configured ActiveSync virtual directory"
}

Write-Host "Client access configuration completed"
"""

    def _generate_public_folders_script(self, pf_data: ExtractedData) -> str:
        """Generate script to create public folders.

        Args:
            pf_data: Public folder configuration data

        Returns:
            PowerShell script
        """
        return """# Create public folder structure

Add-PSSnapin Microsoft.Exchange.Management.PowerShell.SnapIn -ErrorAction SilentlyContinue

# Create public folder mailbox (if not exists)
if (-not (Get-Mailbox -PublicFolder -ErrorAction SilentlyContinue)) {
    New-Mailbox -PublicFolder -Name "PublicFolderMailbox01" -Database "MailboxDB01"
    Write-Host "Created public folder mailbox"
}

# Create public folders
$folders = @("Company Documents", "HR Policies")

foreach ($folder in $folders) {
    if (-not (Get-PublicFolder -Identity "\\$folder" -ErrorAction SilentlyContinue)) {
        New-PublicFolder -Name $folder -Path "\\"
        Write-Host "Created public folder: $folder"
    } else {
        Write-Host "Public folder $folder already exists"
    }
}

Write-Host "Public folder creation completed"
Write-Host "NOTE: Public folder content must be migrated separately"
"""

    def _generate_validation_script(self) -> str:
        """Generate validation script.

        Returns:
            PowerShell script
        """
        return """# Validate Exchange Server configuration and health

Add-PSSnapin Microsoft.Exchange.Management.PowerShell.SnapIn -ErrorAction SilentlyContinue

Write-Host "Running Exchange Server validation..."

# Check Exchange services
$results = @{}

$exServices = @('MSExchangeServiceHost', 'MSExchangeTransport', 'MSExchangeIS')
$runningServices = 0
foreach ($svc in $exServices) {
    $service = Get-Service -Name $svc -ErrorAction SilentlyContinue
    if ($service -and $service.Status -eq 'Running') {
        $runningServices++
    }
}
$results['Services'] = "$runningServices/$($exServices.Count) running"

# Check mailbox databases
try {
    $databases = Get-MailboxDatabase -Status
    $mountedDbs = ($databases | Where-Object { $_.Mounted -eq $true }).Count
    $results['MailboxDatabases'] = "$mountedDbs mounted"
} catch {
    $results['MailboxDatabases'] = "FAILED: $_"
}

# Check mailboxes
try {
    $mailboxCount = (Get-Mailbox -ResultSize Unlimited).Count
    $results['Mailboxes'] = "$mailboxCount total"
} catch {
    $results['Mailboxes'] = "FAILED: $_"
}

# Check mail flow
try {
    $sendConnectors = (Get-SendConnector).Count
    $receiveConnectors = (Get-ReceiveConnector).Count
    $results['MailFlow'] = "$sendConnectors send, $receiveConnectors receive connectors"
} catch {
    $results['MailFlow'] = "FAILED: $_"
}

# Output results
$results | ConvertTo-Json

Write-Host "Validation completed"
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
        """Execute a replication step on target Exchange server.

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
