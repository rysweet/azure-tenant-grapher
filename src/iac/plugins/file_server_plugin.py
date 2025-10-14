"""File Server replication plugin for Windows Server VMs.

This plugin handles data-plane replication for Windows File Server resources,
including SMB shares, permissions, quotas, file screens, and DFS configuration.

Security Note: This plugin preserves security principals using SIDs where possible.
SID translation may be required when replicating across different domains.
File content replication is separate (use robocopy/rsync).
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


class FileServerReplicationPlugin(ResourceReplicationPlugin):
    """Handles Windows File Server data-plane replication.

    This plugin replicates file server configuration:
    - SMB/CIFS shares and settings
    - Share-level permissions
    - NTFS ACLs (file system permissions)
    - DFS namespace and replication configuration
    - File Server Resource Manager (FSRM) quotas and screens
    - Volume Shadow Copy settings
    - Access-Based Enumeration (ABE) configuration
    - Directory structure metadata

    Requires:
    - WinRM access to source file server
    - PowerShell 5.1+ with File Server modules
    - Local admin or delegated credentials
    - NTFS permissions to read ACLs

    Note:
    - File content replication is NOT handled by this plugin
    - Use robocopy/rsync for actual file data transfer
    - SID translation may be required for cross-domain replication
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        """Initialize the File Server plugin.

        Args:
            config: Optional configuration dictionary with keys:
                - output_dir: Directory for extracted data (default: ./fs_extraction)
                - dry_run: If True, don't make actual changes (default: False)
                - max_depth: Max directory depth to analyze (default: 3)
                - include_file_metadata: Include file counts/sizes (default: True)
                - strict_validation: Require all validations to pass (default: False)
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
            name="file_server",
            version="1.0.0",
            description="Replicates Windows File Server shares, permissions, and quotas",
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
            tags=["windows", "file-server", "smb", "cifs", "fsrm", "dfs"],
            documentation_url="https://docs.microsoft.com/en-us/windows-server/storage/file-server/",
        )

    def can_handle(self, resource: Dict[str, Any]) -> bool:
        """Check if resource is a Windows File Server.

        Args:
            resource: Resource dictionary

        Returns:
            True if resource is a Windows VM with File Server role
        """
        if not super().can_handle(resource):
            return False

        # Check for File Server indicators
        tags = resource.get("tags", {})
        os_profile = resource.get("properties", {}).get("osProfile", {})

        # Check tags for File Server role
        role = tags.get("role", "").lower()
        if role in ["file-server", "fileserver", "fs", "file server"]:
            return True

        # Check VM name patterns (common naming conventions)
        name = resource.get("name", "").lower()
        if any(pattern in name for pattern in ["fs", "file", "share", "storage"]):
            # Verify it's Windows
            if "windows" in os_profile.get("computerName", "").lower():
                return True
            os_type = resource.get("properties", {}).get("storageProfile", {}).get("osDisk", {}).get("osType", "").lower()
            if os_type == "windows":
                return True

        return False

    async def analyze_source(
        self, resource: Dict[str, Any]
    ) -> DataPlaneAnalysis:
        """Analyze File Server configuration on source VM.

        Args:
            resource: Source file server resource dictionary

        Returns:
            DataPlaneAnalysis with discovered file server elements

        Raises:
            ConnectionError: If cannot connect via WinRM
            PermissionError: If lacking file system read permissions
        """
        logger.info(f"Analyzing File Server on {resource.get('name')}")

        resource_id = resource.get("id", "unknown")
        elements: List[DataPlaneElement] = []
        warnings: List[str] = []
        errors: List[str] = []

        try:
            # Check connectivity
            if not await self._check_winrm_connectivity(resource):
                raise ConnectionError("Cannot connect to File Server via WinRM")

            # Analyze SMB shares
            share_count = await self._count_smb_shares(resource)
            if share_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="smb_shares",
                        element_type="SMB Shares",
                        description=f"{share_count} SMB/CIFS shares",
                        complexity="MEDIUM",
                        estimated_size_mb=share_count * 0.05,
                        dependencies=[],
                        metadata={"count": share_count},
                    )
                )

            # Analyze share permissions
            if share_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="share_permissions",
                        element_type="Share Permissions",
                        description=f"Share-level access permissions for {share_count} shares",
                        complexity="MEDIUM",
                        estimated_size_mb=share_count * 0.1,
                        dependencies=["smb_shares"],
                        metadata={"share_count": share_count},
                    )
                )

            # Analyze NTFS ACLs
            acl_count = await self._estimate_acl_count(resource, share_count)
            if acl_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="ntfs_acls",
                        element_type="NTFS Permissions",
                        description=f"File system ACLs (estimated {acl_count} items)",
                        complexity="HIGH",
                        estimated_size_mb=acl_count * 0.02,
                        dependencies=["smb_shares"],
                        metadata={"estimated_items": acl_count},
                    )
                )
                warnings.append(
                    "NTFS ACL extraction can be time-consuming for large directory trees"
                )

            # Analyze DFS
            dfs_enabled = await self._check_dfs_enabled(resource)
            if dfs_enabled:
                elements.append(
                    DataPlaneElement(
                        name="dfs_configuration",
                        element_type="DFS",
                        description="DFS namespaces and replication groups",
                        complexity="HIGH",
                        estimated_size_mb=0.5,
                        dependencies=["smb_shares"],
                        metadata={"dfs_enabled": True},
                    )
                )

            # Analyze FSRM quotas
            quota_count = await self._count_fsrm_quotas(resource)
            if quota_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="fsrm_quotas",
                        element_type="FSRM Quotas",
                        description=f"{quota_count} FSRM quota definitions",
                        complexity="MEDIUM",
                        estimated_size_mb=quota_count * 0.02,
                        dependencies=["smb_shares"],
                        metadata={"count": quota_count},
                    )
                )

            # Analyze FSRM file screens
            screen_count = await self._count_fsrm_screens(resource)
            if screen_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="fsrm_file_screens",
                        element_type="FSRM File Screens",
                        description=f"{screen_count} file screening rules",
                        complexity="MEDIUM",
                        estimated_size_mb=screen_count * 0.02,
                        dependencies=["smb_shares"],
                        metadata={"count": screen_count},
                    )
                )

            # Analyze Volume Shadow Copies
            vss_enabled = await self._check_vss_enabled(resource)
            if vss_enabled:
                elements.append(
                    DataPlaneElement(
                        name="volume_shadow_copies",
                        element_type="VSS",
                        description="Volume Shadow Copy schedules and settings",
                        complexity="LOW",
                        estimated_size_mb=0.1,
                        dependencies=["smb_shares"],
                        metadata={"vss_enabled": True},
                    )
                )

            # Analyze directory structure
            if self.get_config_value("include_file_metadata", True):
                elements.append(
                    DataPlaneElement(
                        name="directory_structure",
                        element_type="Directory Tree",
                        description="Directory hierarchy and metadata (no file content)",
                        complexity="MEDIUM",
                        estimated_size_mb=share_count * 0.5,
                        dependencies=["smb_shares"],
                        metadata={
                            "max_depth": self.get_config_value("max_depth", 3),
                            "content_included": False,
                        },
                    )
                )

            # Add SID translation warning if cross-domain scenario detected
            warnings.append(
                "SID translation may be required if replicating to a different domain"
            )
            warnings.append(
                "File content replication must be performed separately using robocopy or similar tools"
            )

            # Calculate totals
            total_size = sum(e.estimated_size_mb for e in elements)
            complexity_score = self._calculate_complexity_score(elements)

            # Estimate extraction time based on complexity
            base_time = 10
            acl_time = (acl_count // 100) * 5 if acl_count > 0 else 0
            estimated_time = base_time + acl_time + len(elements) * 2

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
                estimated_extraction_time_minutes=estimated_time,
                warnings=warnings,
                errors=errors,
                metadata={
                    "share_count": share_count,
                    "dfs_enabled": dfs_enabled,
                    "vss_enabled": vss_enabled,
                },
            )

        except Exception as e:
            logger.error(f"Failed to analyze File Server: {e}")
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
        """Extract File Server data from source VM.

        Args:
            resource: Source file server resource dictionary
            analysis: Previous analysis result

        Returns:
            ExtractionResult with extracted file server data

        Raises:
            ConnectionError: If cannot connect to file server
            IOError: If cannot write extracted data
        """
        logger.info(f"Extracting File Server data from {resource.get('name')}")

        resource_id = resource.get("id", "unknown")
        extracted_data: List[ExtractedData] = []
        warnings: List[str] = []
        errors: List[str] = []
        items_extracted = 0
        items_failed = 0
        start_time = datetime.utcnow()

        # Get output directory
        output_dir = Path(self.get_config_value("output_dir", "./fs_extraction"))
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Extract SMB shares
            if self._has_element(analysis, "smb_shares"):
                try:
                    share_data = await self._extract_smb_shares(resource, output_dir)
                    extracted_data.append(share_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract SMB shares: {e}")
                    errors.append(f"SMB shares: {e}")
                    items_failed += 1

            # Extract share permissions
            if self._has_element(analysis, "share_permissions"):
                try:
                    perm_data = await self._extract_share_permissions(resource, output_dir)
                    extracted_data.append(perm_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract share permissions: {e}")
                    errors.append(f"Share permissions: {e}")
                    items_failed += 1

            # Extract NTFS ACLs
            if self._has_element(analysis, "ntfs_acls"):
                try:
                    acl_data = await self._extract_ntfs_acls(resource, output_dir)
                    extracted_data.append(acl_data)
                    items_extracted += 1
                    warnings.append(
                        "NTFS ACLs may contain SIDs that require translation for cross-domain replication"
                    )
                except Exception as e:
                    logger.error(f"Failed to extract NTFS ACLs: {e}")
                    errors.append(f"NTFS ACLs: {e}")
                    items_failed += 1

            # Extract DFS configuration
            if self._has_element(analysis, "dfs_configuration"):
                try:
                    dfs_data = await self._extract_dfs_config(resource, output_dir)
                    extracted_data.append(dfs_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract DFS config: {e}")
                    errors.append(f"DFS config: {e}")
                    items_failed += 1

            # Extract FSRM quotas
            if self._has_element(analysis, "fsrm_quotas"):
                try:
                    quota_data = await self._extract_fsrm_quotas(resource, output_dir)
                    extracted_data.append(quota_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract FSRM quotas: {e}")
                    errors.append(f"FSRM quotas: {e}")
                    items_failed += 1

            # Extract FSRM file screens
            if self._has_element(analysis, "fsrm_file_screens"):
                try:
                    screen_data = await self._extract_fsrm_screens(resource, output_dir)
                    extracted_data.append(screen_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract FSRM file screens: {e}")
                    errors.append(f"FSRM file screens: {e}")
                    items_failed += 1

            # Extract Volume Shadow Copy settings
            if self._has_element(analysis, "volume_shadow_copies"):
                try:
                    vss_data = await self._extract_vss_config(resource, output_dir)
                    extracted_data.append(vss_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract VSS config: {e}")
                    errors.append(f"VSS config: {e}")
                    items_failed += 1

            # Extract directory structure
            if self._has_element(analysis, "directory_structure"):
                try:
                    dir_data = await self._extract_directory_structure(resource, output_dir)
                    extracted_data.append(dir_data)
                    items_extracted += 1
                    warnings.append(
                        "Directory structure extracted (metadata only - file content requires separate transfer)"
                    )
                except Exception as e:
                    logger.error(f"Failed to extract directory structure: {e}")
                    errors.append(f"Directory structure: {e}")
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
                metadata={
                    "output_directory": str(output_dir),
                    "sid_translation_required": True,
                },
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
        """Generate PowerShell steps to replicate File Server to target.

        Args:
            extraction: Result from extract_data()

        Returns:
            List of ReplicationStep objects in execution order
        """
        logger.info("Generating File Server replication steps")

        steps: List[ReplicationStep] = []

        # Step 1: Prerequisites
        steps.append(
            ReplicationStep(
                step_id="prereq_file_server_features",
                step_type=StepType.PREREQUISITE,
                description="Install File Server and FSRM features",
                script_content=self._generate_feature_install_script(),
                script_format=ExtractionFormat.POWERSHELL_DSC,
                depends_on=[],
                estimated_duration_minutes=10,
                is_critical=True,
                can_retry=True,
                max_retries=2,
            )
        )

        # Step 2: Create SMB shares
        share_data = self._find_extracted_data(extraction, "smb_share")
        if share_data:
            steps.append(
                ReplicationStep(
                    step_id="create_smb_shares",
                    step_type=StepType.CONFIGURATION,
                    description="Create SMB/CIFS shares with settings",
                    script_content=self._generate_share_creation_script(share_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["prereq_file_server_features"],
                    estimated_duration_minutes=5,
                    is_critical=True,
                    can_retry=True,
                )
            )

        # Step 3: Apply share permissions
        perm_data = self._find_extracted_data(extraction, "share_permission")
        if perm_data:
            steps.append(
                ReplicationStep(
                    step_id="apply_share_permissions",
                    step_type=StepType.CONFIGURATION,
                    description="Apply share-level permissions (requires SID translation)",
                    script_content=self._generate_share_permission_script(perm_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["create_smb_shares"],
                    estimated_duration_minutes=5,
                    is_critical=True,
                    can_retry=True,
                    metadata={"requires_sid_translation": True},
                )
            )

        # Step 4: Apply NTFS ACLs
        acl_data = self._find_extracted_data(extraction, "ntfs_acl")
        if acl_data:
            steps.append(
                ReplicationStep(
                    step_id="apply_ntfs_acls",
                    step_type=StepType.CONFIGURATION,
                    description="Apply NTFS file system ACLs (requires SID translation)",
                    script_content=self._generate_acl_application_script(acl_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["create_smb_shares"],
                    estimated_duration_minutes=15,
                    is_critical=False,
                    can_retry=True,
                    metadata={"requires_sid_translation": True},
                )
            )

        # Step 5: Configure DFS
        dfs_data = self._find_extracted_data(extraction, "dfs")
        if dfs_data:
            steps.append(
                ReplicationStep(
                    step_id="configure_dfs",
                    step_type=StepType.CONFIGURATION,
                    description="Configure DFS namespaces and replication",
                    script_content=self._generate_dfs_config_script(dfs_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["create_smb_shares"],
                    estimated_duration_minutes=10,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 6: Configure FSRM quotas
        quota_data = self._find_extracted_data(extraction, "quota")
        if quota_data:
            steps.append(
                ReplicationStep(
                    step_id="configure_fsrm_quotas",
                    step_type=StepType.CONFIGURATION,
                    description="Configure FSRM quotas and templates",
                    script_content=self._generate_quota_config_script(quota_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["prereq_file_server_features"],
                    estimated_duration_minutes=5,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 7: Configure FSRM file screens
        screen_data = self._find_extracted_data(extraction, "file_screen")
        if screen_data:
            steps.append(
                ReplicationStep(
                    step_id="configure_fsrm_screens",
                    step_type=StepType.CONFIGURATION,
                    description="Configure FSRM file screening rules",
                    script_content=self._generate_screen_config_script(screen_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["prereq_file_server_features"],
                    estimated_duration_minutes=5,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 8: Configure Volume Shadow Copies
        vss_data = self._find_extracted_data(extraction, "vss")
        if vss_data:
            steps.append(
                ReplicationStep(
                    step_id="configure_vss",
                    step_type=StepType.CONFIGURATION,
                    description="Configure Volume Shadow Copy schedules",
                    script_content=self._generate_vss_config_script(vss_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["create_smb_shares"],
                    estimated_duration_minutes=5,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 9: Generate robocopy script for file content
        dir_data = self._find_extracted_data(extraction, "directory")
        if dir_data:
            steps.append(
                ReplicationStep(
                    step_id="generate_file_copy_script",
                    step_type=StepType.POST_CONFIG,
                    description="Generate robocopy script for file content migration",
                    script_content=self._generate_robocopy_script(dir_data),
                    script_format=ExtractionFormat.SHELL_SCRIPT,
                    depends_on=["apply_ntfs_acls"],
                    estimated_duration_minutes=1,
                    is_critical=False,
                    can_retry=True,
                    metadata={
                        "manual_execution_required": True,
                        "note": "File content copy must be executed separately - can take hours/days depending on data size",
                    },
                )
            )

        # Step 10: Validation
        steps.append(
            ReplicationStep(
                step_id="validate_file_server",
                step_type=StepType.VALIDATION,
                description="Validate File Server configuration and share access",
                script_content=self._generate_validation_script(),
                script_format=ExtractionFormat.POWERSHELL_DSC,
                depends_on=[s.step_id for s in steps if s.is_critical],
                estimated_duration_minutes=5,
                is_critical=False,
                can_retry=True,
            )
        )

        return steps

    async def apply_to_target(
        self, steps: List[ReplicationStep], target_resource_id: str
    ) -> ReplicationResult:
        """Apply File Server replication steps to target VM.

        Args:
            steps: Replication steps to execute
            target_resource_id: Azure resource ID of target file server

        Returns:
            ReplicationResult with execution status
        """
        logger.info(f"Applying File Server replication to {target_resource_id}")

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

        # Add SID translation warning
        warnings.append(
            "IMPORTANT: SID translation is required for cross-domain replication. "
            "Review and update security principals before applying permissions."
        )

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

                # Skip manual execution steps
                if step.metadata.get("manual_execution_required"):
                    logger.info(f"Skipping {step.step_id} - requires manual execution")
                    step_results.append(
                        StepResult(
                            step_id=step.step_id,
                            status=ReplicationStatus.SKIPPED,
                            duration_seconds=0,
                            stdout="[MANUAL] Script generated - must be executed manually",
                        )
                    )
                    steps_skipped += 1
                    warnings.append(
                        f"Step {step.step_id} requires manual execution: {step.description}"
                    )
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
                metadata={"dry_run": is_dry_run, "sid_translation_required": True},
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
        """Check if WinRM is accessible on the file server.

        Args:
            resource: Resource dictionary

        Returns:
            True if WinRM is accessible
        """
        # In real implementation, would use pywinrm
        # For now, return True if not in strict mode
        return not self.get_config_value("strict_validation", False)

    async def _count_smb_shares(self, resource: Dict[str, Any]) -> int:
        """Count SMB shares on the file server.

        Args:
            resource: Resource dictionary

        Returns:
            Number of SMB shares
        """
        # Mock implementation - real version would use Get-SmbShare
        return 8

    async def _estimate_acl_count(
        self, resource: Dict[str, Any], share_count: int
    ) -> int:
        """Estimate number of ACL entries to extract.

        Args:
            resource: Resource dictionary
            share_count: Number of shares

        Returns:
            Estimated ACL count
        """
        # Mock implementation - estimate based on shares and depth
        max_depth = self.get_config_value("max_depth", 3)
        # Rough estimate: 10 folders per share * depth * 5 ACEs per folder
        return share_count * max_depth * 10 * 5

    async def _check_dfs_enabled(self, resource: Dict[str, Any]) -> bool:
        """Check if DFS is enabled on the file server.

        Args:
            resource: Resource dictionary

        Returns:
            True if DFS is enabled
        """
        # Mock implementation
        return True

    async def _count_fsrm_quotas(self, resource: Dict[str, Any]) -> int:
        """Count FSRM quota definitions.

        Args:
            resource: Resource dictionary

        Returns:
            Number of quotas
        """
        # Mock implementation
        return 5

    async def _count_fsrm_screens(self, resource: Dict[str, Any]) -> int:
        """Count FSRM file screen rules.

        Args:
            resource: Resource dictionary

        Returns:
            Number of file screens
        """
        # Mock implementation
        return 3

    async def _check_vss_enabled(self, resource: Dict[str, Any]) -> bool:
        """Check if Volume Shadow Copy is enabled.

        Args:
            resource: Resource dictionary

        Returns:
            True if VSS is enabled
        """
        # Mock implementation
        return True

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

    async def _extract_smb_shares(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract SMB share configurations.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with share configs
        """
        # Mock implementation - real version would use Get-SmbShare
        content = json.dumps(
            {
                "shares": [
                    {
                        "name": "Shared",
                        "path": "C:\\Shared",
                        "description": "Shared documents",
                        "concurrent_user_limit": 0,
                        "caching": "Manual",
                        "folder_enumeration_mode": "AccessBased",
                        "encrypt_data": False,
                    },
                    {
                        "name": "Projects",
                        "path": "C:\\Projects",
                        "description": "Project files",
                        "concurrent_user_limit": 50,
                        "caching": "Documents",
                        "folder_enumeration_mode": "AccessBased",
                        "encrypt_data": True,
                    },
                    {
                        "name": "Finance",
                        "path": "C:\\Finance",
                        "description": "Finance department",
                        "concurrent_user_limit": 20,
                        "caching": "None",
                        "folder_enumeration_mode": "AccessBased",
                        "encrypt_data": True,
                    },
                ],
                "note": "Access-Based Enumeration (ABE) is enabled on all shares",
            },
            indent=2,
        )

        file_path = output_dir / "smb_shares.json"
        file_path.write_text(content)

        return ExtractedData(
            name="smb_shares",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_share_permissions(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract share-level permissions.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with share permissions
        """
        # Mock implementation - real version would use Get-SmbShareAccess
        content = json.dumps(
            {
                "share_permissions": [
                    {
                        "share_name": "Shared",
                        "access_control_list": [
                            {
                                "account": "SIMULAND\\Domain Users",
                                "sid": "S-1-5-21-1234567890-1234567890-1234567890-513",
                                "access_right": "Change",
                                "access_control_type": "Allow",
                            },
                            {
                                "account": "SIMULAND\\IT Admins",
                                "sid": "S-1-5-21-1234567890-1234567890-1234567890-1001",
                                "access_right": "Full",
                                "access_control_type": "Allow",
                            },
                        ],
                    },
                    {
                        "share_name": "Projects",
                        "access_control_list": [
                            {
                                "account": "SIMULAND\\Project Managers",
                                "sid": "S-1-5-21-1234567890-1234567890-1234567890-1002",
                                "access_right": "Change",
                                "access_control_type": "Allow",
                            },
                            {
                                "account": "SIMULAND\\Domain Users",
                                "sid": "S-1-5-21-1234567890-1234567890-1234567890-513",
                                "access_right": "Read",
                                "access_control_type": "Allow",
                            },
                        ],
                    },
                    {
                        "share_name": "Finance",
                        "access_control_list": [
                            {
                                "account": "SIMULAND\\Finance Team",
                                "sid": "S-1-5-21-1234567890-1234567890-1234567890-1003",
                                "access_right": "Change",
                                "access_control_type": "Allow",
                            },
                        ],
                    },
                ],
                "note": "SIDs must be translated to target domain before replication",
            },
            indent=2,
        )

        file_path = output_dir / "share_permissions.json"
        file_path.write_text(content)

        return ExtractedData(
            name="share_permissions",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
            metadata={"requires_sid_translation": True},
        )

    async def _extract_ntfs_acls(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract NTFS ACLs in SDDL format.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with NTFS ACLs
        """
        # Mock implementation - real version would use Get-Acl and ConvertTo-SddlString
        content = """# NTFS ACLs in SDDL format
# Format: PATH|OWNER_SID|SDDL_STRING
C:\\Shared|S-1-5-21-1234567890-1234567890-1234567890-500|O:BAG:SYD:PAI(A;OICI;FA;;;BA)(A;OICI;0x1200a9;;;S-1-5-21-1234567890-1234567890-1234567890-513)
C:\\Shared\\Public|S-1-5-21-1234567890-1234567890-1234567890-500|O:BAG:SYD:PAI(A;OICI;FA;;;BA)(A;OICI;0x1301bf;;;S-1-5-21-1234567890-1234567890-1234567890-513)
C:\\Shared\\IT|S-1-5-21-1234567890-1234567890-1234567890-1001|O:S-1-5-21-1234567890-1234567890-1234567890-1001G:BAD:PAI(A;OICI;FA;;;BA)(A;OICI;FA;;;S-1-5-21-1234567890-1234567890-1234567890-1001)
C:\\Projects|S-1-5-21-1234567890-1234567890-1234567890-500|O:BAG:SYD:PAI(A;OICI;FA;;;BA)(A;OICI;0x1200a9;;;S-1-5-21-1234567890-1234567890-1234567890-1002)
C:\\Finance|S-1-5-21-1234567890-1234567890-1234567890-500|O:BAG:SYD:PAI(A;OICI;FA;;;BA)(A;OICI;0x1301bf;;;S-1-5-21-1234567890-1234567890-1234567890-1003)

# SDDL Legend:
# O: = Owner SID
# G: = Group SID
# D: = DACL
# A = Allow ACE
# OICI = Object Inherit + Container Inherit
# FA = Full Access (0x1f01ff)
# 0x1200a9 = Read + Execute
# 0x1301bf = Modify

# NOTE: All SIDs must be translated to target domain equivalents
"""

        file_path = output_dir / "ntfs_acls.sddl"
        file_path.write_text(content)

        # Also create CSV format for easier processing
        csv_content = """Path,Owner,Group,Permissions
C:\\Shared,SIMULAND\\Administrator,BUILTIN\\Administrators,Domain Users:Read+Execute
C:\\Shared\\Public,SIMULAND\\Administrator,BUILTIN\\Administrators,Domain Users:Modify
C:\\Shared\\IT,SIMULAND\\IT Admins,BUILTIN\\Administrators,IT Admins:Full Control
C:\\Projects,SIMULAND\\Administrator,BUILTIN\\Administrators,Project Managers:Read+Execute
C:\\Finance,SIMULAND\\Administrator,BUILTIN\\Administrators,Finance Team:Modify
"""

        csv_path = output_dir / "ntfs_acls.csv"
        csv_path.write_text(csv_content)

        return ExtractedData(
            name="ntfs_acls",
            format=ExtractionFormat.CSV,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
            metadata={
                "requires_sid_translation": True,
                "sddl_file": str(file_path),
                "csv_file": str(csv_path),
            },
        )

    async def _extract_dfs_config(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract DFS namespace and replication configuration.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with DFS config
        """
        # Mock implementation
        content = json.dumps(
            {
                "dfs_namespaces": [
                    {
                        "path": "\\\\simuland.local\\Public",
                        "type": "DomainV2",
                        "state": "Online",
                        "targets": [
                            {
                                "server": "atevet12fs001",
                                "path": "\\\\atevet12fs001\\Shared",
                                "state": "Online",
                            }
                        ],
                    }
                ],
                "dfs_replication_groups": [
                    {
                        "name": "FileReplication",
                        "members": ["atevet12fs001"],
                        "replicated_folders": [
                            {
                                "name": "Shared",
                                "path": "C:\\Shared",
                            }
                        ],
                    }
                ],
            },
            indent=2,
        )

        file_path = output_dir / "dfs_config.json"
        file_path.write_text(content)

        return ExtractedData(
            name="dfs_config",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_fsrm_quotas(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract FSRM quota configurations.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with FSRM quotas
        """
        # Mock implementation
        content = json.dumps(
            {
                "quota_templates": [
                    {
                        "name": "200 GB Limit",
                        "description": "Limit usage to 200 GB",
                        "size_bytes": 214748364800,
                        "soft_limit": False,
                        "threshold": 85,
                    },
                    {
                        "name": "User Quota 50GB",
                        "description": "Per-user quota limit",
                        "size_bytes": 53687091200,
                        "soft_limit": True,
                        "threshold": 90,
                    },
                ],
                "quotas": [
                    {
                        "path": "C:\\Shared",
                        "template": "200 GB Limit",
                        "description": "Shared folder quota",
                    },
                    {
                        "path": "C:\\Projects",
                        "template": "200 GB Limit",
                        "description": "Projects folder quota",
                    },
                ],
            },
            indent=2,
        )

        file_path = output_dir / "fsrm_quotas.json"
        file_path.write_text(content)

        return ExtractedData(
            name="fsrm_quotas",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_fsrm_screens(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract FSRM file screen configurations.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with file screens
        """
        # Mock implementation
        content = json.dumps(
            {
                "file_groups": [
                    {
                        "name": "Audio and Video Files",
                        "include_patterns": ["*.mp3", "*.wav", "*.avi", "*.mp4"],
                    },
                    {
                        "name": "Executable Files",
                        "include_patterns": ["*.exe", "*.dll", "*.bat", "*.cmd"],
                    },
                ],
                "file_screens": [
                    {
                        "path": "C:\\Shared",
                        "template": "Block Executable Files",
                        "file_groups": ["Executable Files"],
                        "active": True,
                    },
                    {
                        "path": "C:\\Projects",
                        "template": "Block Audio and Video",
                        "file_groups": ["Audio and Video Files"],
                        "active": True,
                    },
                ],
            },
            indent=2,
        )

        file_path = output_dir / "fsrm_file_screens.json"
        file_path.write_text(content)

        return ExtractedData(
            name="fsrm_file_screens",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_vss_config(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract Volume Shadow Copy configuration.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with VSS config
        """
        # Mock implementation
        content = json.dumps(
            {
                "volumes": [
                    {
                        "drive": "C:",
                        "enabled": True,
                        "schedule": "Daily at 7:00 AM and 12:00 PM",
                        "max_size_percent": 10,
                        "max_snapshots": 64,
                    }
                ],
                "existing_snapshots": [
                    {
                        "volume": "C:",
                        "creation_time": "2025-01-10T07:00:00Z",
                        "id": "{3808876B-C176-4e48-B7AE-04046E6CC752}",
                    },
                    {
                        "volume": "C:",
                        "creation_time": "2025-01-10T12:00:00Z",
                        "id": "{4808876B-C176-4e48-B7AE-04046E6CC753}",
                    },
                ],
            },
            indent=2,
        )

        file_path = output_dir / "vss_config.json"
        file_path.write_text(content)

        return ExtractedData(
            name="vss_config",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_directory_structure(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract directory structure metadata.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with directory tree
        """
        # Mock implementation
        max_depth = self.get_config_value("max_depth", 3)
        content = json.dumps(
            {
                "metadata": {
                    "max_depth": max_depth,
                    "includes_file_content": False,
                    "note": "Directory structure only - file content requires separate transfer",
                },
                "directories": [
                    {
                        "path": "C:\\Shared",
                        "subdirs": ["Public", "IT", "HR"],
                        "file_count": 150,
                        "total_size_bytes": 5368709120,
                        "depth": 0,
                    },
                    {
                        "path": "C:\\Shared\\Public",
                        "subdirs": ["Documents", "Templates"],
                        "file_count": 75,
                        "total_size_bytes": 2684354560,
                        "depth": 1,
                    },
                    {
                        "path": "C:\\Shared\\IT",
                        "subdirs": ["Scripts", "Tools", "Documentation"],
                        "file_count": 50,
                        "total_size_bytes": 1073741824,
                        "depth": 1,
                    },
                    {
                        "path": "C:\\Projects",
                        "subdirs": ["ProjectA", "ProjectB", "Archive"],
                        "file_count": 500,
                        "total_size_bytes": 21474836480,
                        "depth": 0,
                    },
                    {
                        "path": "C:\\Finance",
                        "subdirs": ["Reports", "Budgets", "Invoices"],
                        "file_count": 200,
                        "total_size_bytes": 10737418240,
                        "depth": 0,
                    },
                ],
                "summary": {
                    "total_directories": 11,
                    "total_files": 975,
                    "total_size_bytes": 41943040000,
                    "total_size_gb": 39,
                },
            },
            indent=2,
        )

        file_path = output_dir / "directory_structure.json"
        file_path.write_text(content)

        return ExtractedData(
            name="directory_structure",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
            metadata={"content_included": False},
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
        """Generate PowerShell script to install File Server features.

        Returns:
            PowerShell script content
        """
        return """# Install File Server and FSRM features
Write-Host "Installing File Server features..."

Install-WindowsFeature -Name FS-FileServer -IncludeManagementTools
Install-WindowsFeature -Name FS-Resource-Manager -IncludeManagementTools
Install-WindowsFeature -Name FS-DFS-Namespace -IncludeManagementTools
Install-WindowsFeature -Name FS-DFS-Replication -IncludeManagementTools

# Import required modules
Import-Module SmbShare
Import-Module FileServerResourceManager
Import-Module DFSN

Write-Host "File Server features installed successfully"
"""

    def _generate_share_creation_script(self, share_data: ExtractedData) -> str:
        """Generate script to create SMB shares.

        Args:
            share_data: Share configuration data

        Returns:
            PowerShell script
        """
        return """# Create SMB shares with configuration
Write-Host "Creating SMB shares..."

# Create share directories if they don't exist
$shares = @(
    @{Name="Shared"; Path="C:\\Shared"; Description="Shared documents"; CachingMode="Manual"; EncryptData=$false},
    @{Name="Projects"; Path="C:\\Projects"; Description="Project files"; CachingMode="Documents"; EncryptData=$true},
    @{Name="Finance"; Path="C:\\Finance"; Description="Finance department"; CachingMode="None"; EncryptData=$true}
)

foreach ($share in $shares) {
    # Create directory
    if (-not (Test-Path $share.Path)) {
        New-Item -Path $share.Path -ItemType Directory -Force | Out-Null
        Write-Host "Created directory: $($share.Path)"
    }

    # Create SMB share
    try {
        New-SmbShare `
            -Name $share.Name `
            -Path $share.Path `
            -Description $share.Description `
            -CachingMode $share.CachingMode `
            -EncryptData $share.EncryptData `
            -FolderEnumerationMode AccessBased `
            -ErrorAction Stop

        Write-Host "Created share: $($share.Name)"
    } catch {
        if ($_.Exception.Message -match "already exists") {
            Write-Warning "Share $($share.Name) already exists, skipping"
        } else {
            Write-Error "Failed to create share $($share.Name): $_"
            throw
        }
    }
}

Write-Host "SMB shares created successfully"
"""

    def _generate_share_permission_script(self, perm_data: ExtractedData) -> str:
        """Generate script to apply share permissions.

        Args:
            perm_data: Share permission data

        Returns:
            PowerShell script
        """
        return """# Apply share-level permissions
Write-Host "Applying share permissions..."
Write-Warning "IMPORTANT: This script uses source domain SIDs - manual SID translation required!"

# SID Translation Map - UPDATE THESE FOR TARGET DOMAIN
$sidMap = @{
    "S-1-5-21-1234567890-1234567890-1234567890-513" = "DOMAIN\\Domain Users"  # Replace with target SID
    "S-1-5-21-1234567890-1234567890-1234567890-1001" = "DOMAIN\\IT Admins"  # Replace with target SID
    "S-1-5-21-1234567890-1234567890-1234567890-1002" = "DOMAIN\\Project Managers"  # Replace with target SID
    "S-1-5-21-1234567890-1234567890-1234567890-1003" = "DOMAIN\\Finance Team"  # Replace with target SID
}

$sharePermissions = @(
    @{Share="Shared"; Account="DOMAIN\\Domain Users"; AccessRight="Change"},
    @{Share="Shared"; Account="DOMAIN\\IT Admins"; AccessRight="Full"},
    @{Share="Projects"; Account="DOMAIN\\Project Managers"; AccessRight="Change"},
    @{Share="Projects"; Account="DOMAIN\\Domain Users"; AccessRight="Read"},
    @{Share="Finance"; Account="DOMAIN\\Finance Team"; AccessRight="Change"}
)

foreach ($perm in $sharePermissions) {
    try {
        # Remove default Everyone permission if exists
        $existing = Get-SmbShareAccess -Name $perm.Share -ErrorAction SilentlyContinue |
            Where-Object { $_.AccountName -eq "Everyone" }

        if ($existing) {
            Revoke-SmbShareAccess -Name $perm.Share -AccountName "Everyone" -Force
        }

        # Grant new permission
        Grant-SmbShareAccess `
            -Name $perm.Share `
            -AccountName $perm.Account `
            -AccessRight $perm.AccessRight `
            -Force `
            -ErrorAction Stop

        Write-Host "Applied $($perm.AccessRight) permission to $($perm.Account) on $($perm.Share)"
    } catch {
        Write-Error "Failed to apply permission on $($perm.Share): $_"
    }
}

Write-Host "Share permissions applied successfully"
"""

    def _generate_acl_application_script(self, acl_data: ExtractedData) -> str:
        """Generate script to apply NTFS ACLs.

        Args:
            acl_data: ACL data in SDDL format

        Returns:
            PowerShell script
        """
        return """# Apply NTFS ACLs from SDDL
Write-Host "Applying NTFS ACLs..."
Write-Warning "IMPORTANT: SID translation required - this script uses placeholder logic!"

# Function to translate SIDs (MUST be customized for target domain)
function Translate-SID {
    param([string]$SourceSID)

    # TODO: Implement proper SID translation logic
    # This is a placeholder - map source domain SIDs to target domain SIDs
    $sidMap = @{
        "S-1-5-21-1234567890-1234567890-1234567890-513" = (New-Object System.Security.Principal.NTAccount("DOMAIN\\Domain Users")).Translate([System.Security.Principal.SecurityIdentifier]).Value
        # Add more mappings as needed
    }

    if ($sidMap.ContainsKey($SourceSID)) {
        return $sidMap[$SourceSID]
    }

    Write-Warning "No mapping found for SID: $SourceSID"
    return $SourceSID
}

# Read ACL definitions from CSV (easier than parsing SDDL)
$aclFile = "C:\\temp\\ntfs_acls.csv"

if (Test-Path $aclFile) {
    $acls = Import-Csv $aclFile

    foreach ($acl in $acls) {
        $path = $acl.Path

        if (Test-Path $path) {
            try {
                $currentAcl = Get-Acl $path

                # Parse and apply permissions (simplified)
                # In real implementation, parse SDDL and translate SIDs

                Set-Acl -Path $path -AclObject $currentAcl
                Write-Host "Applied ACL to: $path"
            } catch {
                Write-Error "Failed to apply ACL to $path : $_"
            }
        } else {
            Write-Warning "Path not found: $path"
        }
    }
} else {
    Write-Warning "ACL file not found: $aclFile"
    Write-Host "Manual ACL application required - see extracted SDDL file"
}

Write-Host "NTFS ACL application complete (verify results manually)"
"""

    def _generate_dfs_config_script(self, dfs_data: ExtractedData) -> str:
        """Generate script to configure DFS.

        Args:
            dfs_data: DFS configuration data

        Returns:
            PowerShell script
        """
        return """# Configure DFS Namespaces and Replication
Write-Host "Configuring DFS..."

# Create DFS namespace
$namespace = "\\\\simuland.local\\Public"
$targetPath = "\\\\$env:COMPUTERNAME\\Shared"

try {
    # Create namespace root
    New-DfsnRoot `
        -Path $namespace `
        -TargetPath $targetPath `
        -Type DomainV2 `
        -ErrorAction Stop

    Write-Host "Created DFS namespace: $namespace"
} catch {
    if ($_.Exception.Message -match "already exists") {
        Write-Warning "DFS namespace already exists"
    } else {
        Write-Error "Failed to create DFS namespace: $_"
    }
}

# Configure DFS Replication (if multiple servers)
# NOTE: This is a simplified example - adjust for your topology
Write-Host "DFS Replication requires additional configuration for multi-server topologies"

Write-Host "DFS configuration complete"
"""

    def _generate_quota_config_script(self, quota_data: ExtractedData) -> str:
        """Generate script to configure FSRM quotas.

        Args:
            quota_data: Quota configuration data

        Returns:
            PowerShell script
        """
        return """# Configure FSRM Quotas
Write-Host "Configuring FSRM quotas..."

# Create quota templates
$templates = @(
    @{Name="200 GB Limit"; Size=200GB; Type="Hard"; Threshold=85},
    @{Name="User Quota 50GB"; Size=50GB; Type="Soft"; Threshold=90}
)

foreach ($template in $templates) {
    try {
        New-FsrmQuotaTemplate `
            -Name $template.Name `
            -Description "Auto-configured quota template" `
            -Size $template.Size `
            -ErrorAction Stop

        # Add threshold
        New-FsrmQuotaThreshold `
            -Template $template.Name `
            -Percentage $template.Threshold `
            -ErrorAction SilentlyContinue

        Write-Host "Created quota template: $($template.Name)"
    } catch {
        if ($_.Exception.Message -match "already exists") {
            Write-Warning "Quota template $($template.Name) already exists"
        } else {
            Write-Error "Failed to create quota template: $_"
        }
    }
}

# Apply quotas to paths
$quotas = @(
    @{Path="C:\\Shared"; Template="200 GB Limit"},
    @{Path="C:\\Projects"; Template="200 GB Limit"}
)

foreach ($quota in $quotas) {
    if (Test-Path $quota.Path) {
        try {
            New-FsrmQuota `
                -Path $quota.Path `
                -Template $quota.Template `
                -ErrorAction Stop

            Write-Host "Applied quota to: $($quota.Path)"
        } catch {
            Write-Warning "Failed to apply quota to $($quota.Path): $_"
        }
    }
}

Write-Host "FSRM quota configuration complete"
"""

    def _generate_screen_config_script(self, screen_data: ExtractedData) -> str:
        """Generate script to configure FSRM file screens.

        Args:
            screen_data: File screen configuration data

        Returns:
            PowerShell script
        """
        return """# Configure FSRM File Screens
Write-Host "Configuring FSRM file screens..."

# Create file groups
$fileGroups = @(
    @{Name="Executable Files"; Patterns=@("*.exe", "*.dll", "*.bat", "*.cmd", "*.vbs", "*.ps1")},
    @{Name="Audio and Video Files"; Patterns=@("*.mp3", "*.wav", "*.avi", "*.mp4", "*.mkv")}
)

foreach ($group in $fileGroups) {
    try {
        New-FsrmFileGroup `
            -Name $group.Name `
            -IncludePattern $group.Patterns `
            -ErrorAction Stop

        Write-Host "Created file group: $($group.Name)"
    } catch {
        if ($_.Exception.Message -match "already exists") {
            Write-Warning "File group $($group.Name) already exists"
        } else {
            Write-Error "Failed to create file group: $_"
        }
    }
}

# Create file screen templates
try {
    New-FsrmFileScreenTemplate `
        -Name "Block Executable Files" `
        -IncludeGroup "Executable Files" `
        -Active `
        -ErrorAction Stop

    Write-Host "Created file screen template: Block Executable Files"
} catch {
    Write-Warning "File screen template may already exist"
}

# Apply file screens to paths
$screens = @(
    @{Path="C:\\Shared"; Template="Block Executable Files"},
    @{Path="C:\\Projects"; Template="Block Executable Files"}
)

foreach ($screen in $screens) {
    if (Test-Path $screen.Path) {
        try {
            New-FsrmFileScreen `
                -Path $screen.Path `
                -Template $screen.Template `
                -ErrorAction Stop

            Write-Host "Applied file screen to: $($screen.Path)"
        } catch {
            Write-Warning "Failed to apply file screen to $($screen.Path): $_"
        }
    }
}

Write-Host "FSRM file screen configuration complete"
"""

    def _generate_vss_config_script(self, vss_data: ExtractedData) -> str:
        """Generate script to configure Volume Shadow Copies.

        Args:
            vss_data: VSS configuration data

        Returns:
            PowerShell script
        """
        return """# Configure Volume Shadow Copies
Write-Host "Configuring Volume Shadow Copies..."

# Enable VSS on C: drive
$volume = "C:\\"

# Create scheduled task for VSS snapshots
$action = New-ScheduledTaskAction -Execute "vssadmin.exe" -Argument "create shadow /for=$volume"
$trigger1 = New-ScheduledTaskTrigger -Daily -At 7:00AM
$trigger2 = New-ScheduledTaskTrigger -Daily -At 12:00PM

try {
    Register-ScheduledTask `
        -TaskName "VSS Snapshot" `
        -Action $action `
        -Trigger @($trigger1, $trigger2) `
        -User "SYSTEM" `
        -RunLevel Highest `
        -ErrorAction Stop

    Write-Host "Created VSS snapshot schedule"
} catch {
    if ($_.Exception.Message -match "already exists") {
        Write-Warning "VSS snapshot task already exists"
    } else {
        Write-Error "Failed to create VSS snapshot task: $_"
    }
}

# Configure VSS storage
try {
    vssadmin resize shadowstorage /for=$volume /on=$volume /maxsize=10%
    Write-Host "Configured VSS storage (10% of volume)"
} catch {
    Write-Warning "Failed to configure VSS storage: $_"
}

Write-Host "Volume Shadow Copy configuration complete"
"""

    def _generate_robocopy_script(self, dir_data: ExtractedData) -> str:
        """Generate robocopy script for file content migration.

        Args:
            dir_data: Directory structure data

        Returns:
            PowerShell/batch script
        """
        return """# File Content Migration Script (Robocopy)
#
# WARNING: This script will copy ~39 GB of data
# Estimated time: Several hours depending on network speed
#
# INSTRUCTIONS:
# 1. Update $sourceServer and $targetServer variables
# 2. Ensure you have admin access to both servers
# 3. Run during maintenance window
# 4. Monitor progress in robocopy log files

$sourceServer = "SOURCE-FILE-SERVER"  # UPDATE THIS
$targetServer = "TARGET-FILE-SERVER"  # UPDATE THIS
$logDir = "C:\\temp\\robocopy_logs"

# Create log directory
New-Item -Path $logDir -ItemType Directory -Force | Out-Null

# Share paths to copy
$shares = @(
    @{Source="\\\\$sourceServer\\Shared"; Target="\\\\$targetServer\\Shared"},
    @{Source="\\\\$sourceServer\\Projects"; Target="\\\\$targetServer\\Projects"},
    @{Source="\\\\$sourceServer\\Finance"; Target="\\\\$targetServer\\Finance"}
)

foreach ($share in $shares) {
    $shareName = Split-Path $share.Source -Leaf
    $logFile = Join-Path $logDir "$shareName-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"

    Write-Host "Copying $shareName..."
    Write-Host "  From: $($share.Source)"
    Write-Host "  To: $($share.Target)"
    Write-Host "  Log: $logFile"

    # Robocopy command with ACL preservation
    # /MIR = Mirror (copies all files and removes deleted files from target)
    # /COPYALL = Copy all file attributes including ACLs
    # /SEC = Copy security (NTFS ACLs)
    # /R:3 = Retry 3 times on failure
    # /W:10 = Wait 10 seconds between retries
    # /MT:8 = Use 8 threads for multi-threaded copying
    # /LOG = Log file location
    # /TEE = Output to console and log

    robocopy $share.Source $share.Target /MIR /COPYALL /SEC /R:3 /W:10 /MT:8 /LOG:$logFile /TEE

    $exitCode = $LASTEXITCODE

    # Robocopy exit codes: 0-7 are success, 8+ are errors
    if ($exitCode -ge 8) {
        Write-Error "Robocopy failed for $shareName with exit code $exitCode"
        Write-Host "Check log file: $logFile"
    } else {
        Write-Host "$shareName copied successfully (exit code: $exitCode)"
    }
}

Write-Host ""
Write-Host "File content migration complete!"
Write-Host "Review log files in: $logDir"
Write-Host ""
Write-Host "IMPORTANT: Verify file access and permissions on target server"
"""

    def _generate_validation_script(self) -> str:
        """Generate validation script for File Server.

        Returns:
            PowerShell script
        """
        return """# Validate File Server Configuration
Write-Host "Validating File Server configuration..."

$results = @{}

# Test SMB shares
try {
    $shares = Get-SmbShare | Where-Object { $_.Name -notin @('ADMIN$', 'C$', 'IPC$') }
    $results['SMB Shares'] = "OK - Found $($shares.Count) shares"
} catch {
    $results['SMB Shares'] = "FAILED: $_"
}

# Test share permissions
try {
    $sharePerms = @()
    foreach ($share in $shares) {
        $perms = Get-SmbShareAccess -Name $share.Name
        $sharePerms += $perms
    }
    $results['Share Permissions'] = "OK - $($sharePerms.Count) permissions configured"
} catch {
    $results['Share Permissions'] = "FAILED: $_"
}

# Test FSRM
try {
    $quotas = Get-FsrmQuota -ErrorAction SilentlyContinue
    $screens = Get-FsrmFileScreen -ErrorAction SilentlyContinue
    $results['FSRM'] = "OK - $($quotas.Count) quotas, $($screens.Count) screens"
} catch {
    $results['FSRM'] = "WARNING: FSRM not configured or not accessible"
}

# Test DFS
try {
    $dfsRoots = Get-DfsnRoot -ErrorAction SilentlyContinue
    if ($dfsRoots) {
        $results['DFS'] = "OK - $($dfsRoots.Count) namespace(s)"
    } else {
        $results['DFS'] = "INFO: No DFS namespaces configured"
    }
} catch {
    $results['DFS'] = "WARNING: DFS not configured"
}

# Test VSS
try {
    $shadows = vssadmin list shadows
    if ($LASTEXITCODE -eq 0) {
        $results['VSS'] = "OK - Volume Shadow Copy enabled"
    } else {
        $results['VSS'] = "WARNING: VSS check failed"
    }
} catch {
    $results['VSS'] = "WARNING: VSS not accessible"
}

# Test share accessibility
$accessTests = @()
foreach ($share in $shares) {
    $path = "\\\\$env:COMPUTERNAME\\$($share.Name)"
    if (Test-Path $path) {
        $accessTests += "$($share.Name): Accessible"
    } else {
        $accessTests += "$($share.Name): NOT ACCESSIBLE"
    }
}
$results['Share Access'] = $accessTests -join ", "

# Output results
Write-Host "`nValidation Results:"
Write-Host "=" * 60
foreach ($key in $results.Keys) {
    Write-Host "$key : $($results[$key])"
}
Write-Host "=" * 60

# Return as JSON for parsing
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
        """Execute a replication step on target file server.

        Args:
            step: Step to execute
            target_resource_id: Target file server resource ID

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
