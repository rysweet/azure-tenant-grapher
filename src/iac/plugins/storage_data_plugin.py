"""Storage Account Data replication plugin.

This plugin handles data-plane replication for Azure Storage Accounts,
including blob containers, file shares, tables, and queues. It generates
azcopy commands for data transfer and Terraform for container/share creation.

Security Note: This plugin requires storage account keys or SAS tokens.
All sensitive credentials are sanitized from outputs.
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


class StorageDataReplicationPlugin(ResourceReplicationPlugin):
    """Handles Azure Storage Account data-plane replication.

    This plugin replicates storage account data:
    - Blob containers and blob inventory
    - File shares and directory structure
    - Table storage schema and sample data
    - Queue storage metadata
    - CORS rules and lifecycle policies
    - Blob versioning and soft delete settings

    Requires:
    - Azure Storage credentials (account key or SAS token)
    - azcopy utility installed (for data transfer)
    - Network connectivity to storage accounts

    Note:
    - Large data transfers can take hours or days
    - Transfer time estimates are provided
    - Credentials are sanitized from outputs
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        """Initialize the Storage Data plugin.

        Args:
            config: Optional configuration dictionary with keys:
                - output_dir: Directory for extracted data (default: ./storage_extraction)
                - dry_run: If True, don't make actual changes (default: False)
                - max_blobs_per_container: Max blobs to inventory (default: 1000)
                - include_sample_data: Include table sample data (default: True)
                - azcopy_path: Path to azcopy binary (default: 'azcopy')
                - strict_validation: Require all validations to pass (default: False)
                - generate_sas_tokens: Auto-generate SAS tokens (default: True)
                - sas_expiry_hours: SAS token expiry in hours (default: 24)
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
            name="storage_data",
            version="1.0.0",
            description="Replicates Azure Storage Account data (blobs, files, tables, queues)",
            author="Azure Tenant Grapher",
            resource_types=["Microsoft.Storage/storageAccounts"],
            supported_formats=[
                ExtractionFormat.JSON,
                ExtractionFormat.TERRAFORM,
                ExtractionFormat.SHELL_SCRIPT,
            ],
            requires_credentials=True,
            requires_network_access=True,
            complexity="HIGH",
            estimated_effort_weeks=2.0,
            tags=["storage", "blob", "file-share", "table", "queue", "azcopy"],
            documentation_url="https://docs.microsoft.com/en-us/azure/storage/",
        )

    async def analyze_source(self, resource: Dict[str, Any]) -> DataPlaneAnalysis:
        """Analyze Storage Account data plane on source resource.

        Args:
            resource: Source storage account resource dictionary

        Returns:
            DataPlaneAnalysis with discovered storage elements

        Raises:
            ConnectionError: If cannot connect to storage account
            PermissionError: If lacking storage access permissions
        """
        logger.info(f"Analyzing Storage Account {resource.get('name')}")

        resource_id = resource.get("id", "unknown")
        resource_name = resource.get("name", "unknown")
        elements: List[DataPlaneElement] = []
        warnings: List[str] = []
        errors: List[str] = []

        try:
            # Check connectivity
            if not await self._check_storage_connectivity(resource):
                raise ConnectionError(
                    "Cannot connect to Storage Account - check credentials and network access"
                )

            # Analyze blob containers
            blob_stats = await self._analyze_blob_containers(resource)
            if blob_stats["container_count"] > 0:
                elements.append(
                    DataPlaneElement(
                        name="blob_containers",
                        element_type="Blob Storage",
                        description=f"{blob_stats['container_count']} blob containers with {blob_stats['blob_count']} blobs",
                        complexity="MEDIUM",
                        estimated_size_mb=blob_stats["total_size_mb"],
                        dependencies=[],
                        metadata=blob_stats,
                    )
                )

                # Add lifecycle policies
                if blob_stats.get("has_lifecycle_policy"):
                    elements.append(
                        DataPlaneElement(
                            name="lifecycle_policies",
                            element_type="Lifecycle Management",
                            description="Blob lifecycle management policies",
                            complexity="LOW",
                            estimated_size_mb=0.1,
                            dependencies=["blob_containers"],
                            metadata={"policy_count": blob_stats.get("policy_count", 1)},
                        )
                    )

            # Analyze file shares
            file_stats = await self._analyze_file_shares(resource)
            if file_stats["share_count"] > 0:
                elements.append(
                    DataPlaneElement(
                        name="file_shares",
                        element_type="File Shares",
                        description=f"{file_stats['share_count']} file shares with {file_stats['file_count']} files",
                        complexity="MEDIUM",
                        estimated_size_mb=file_stats["total_size_mb"],
                        dependencies=[],
                        metadata=file_stats,
                    )
                )

            # Analyze table storage
            table_stats = await self._analyze_tables(resource)
            if table_stats["table_count"] > 0:
                elements.append(
                    DataPlaneElement(
                        name="table_storage",
                        element_type="Table Storage",
                        description=f"{table_stats['table_count']} tables with ~{table_stats['estimated_entities']} entities",
                        complexity="MEDIUM",
                        estimated_size_mb=table_stats["estimated_size_mb"],
                        dependencies=[],
                        metadata=table_stats,
                    )
                )

            # Analyze queue storage
            queue_stats = await self._analyze_queues(resource)
            if queue_stats["queue_count"] > 0:
                elements.append(
                    DataPlaneElement(
                        name="queue_storage",
                        element_type="Queue Storage",
                        description=f"{queue_stats['queue_count']} queues with {queue_stats['message_count']} messages",
                        complexity="LOW",
                        estimated_size_mb=queue_stats["estimated_size_mb"],
                        dependencies=[],
                        metadata=queue_stats,
                    )
                )

            # Analyze CORS rules
            cors_enabled = await self._check_cors_rules(resource)
            if cors_enabled:
                elements.append(
                    DataPlaneElement(
                        name="cors_rules",
                        element_type="CORS Configuration",
                        description="Cross-Origin Resource Sharing rules",
                        complexity="LOW",
                        estimated_size_mb=0.05,
                        dependencies=[],
                        metadata={"cors_enabled": True},
                    )
                )

            # Analyze soft delete settings
            soft_delete_enabled = await self._check_soft_delete(resource)
            if soft_delete_enabled:
                elements.append(
                    DataPlaneElement(
                        name="soft_delete_settings",
                        element_type="Soft Delete",
                        description="Blob soft delete configuration",
                        complexity="LOW",
                        estimated_size_mb=0.05,
                        dependencies=[],
                        metadata={"enabled": True},
                    )
                )

            # Add warnings
            total_size_gb = sum(e.estimated_size_mb for e in elements) / 1024
            if total_size_gb > 100:
                warnings.append(
                    f"Large data transfer: ~{total_size_gb:.1f} GB - will take significant time"
                )

            warnings.append(
                "Storage account credentials required - use account key or SAS token"
            )
            warnings.append("azcopy utility must be installed for data transfer")

            # Calculate totals
            total_size = sum(e.estimated_size_mb for e in elements)
            complexity_score = self._calculate_complexity_score(elements, total_size)

            # Estimate extraction time (1 GB = ~10 minutes @ 100 Mbps)
            base_time = 5
            transfer_time = int(total_size / 1024 * 10) if total_size > 0 else 0
            estimated_time = base_time + transfer_time + len(elements) * 2

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
                connection_methods=["HTTPS", "azcopy"],
                estimated_extraction_time_minutes=estimated_time,
                warnings=warnings,
                errors=errors,
                metadata={
                    "storage_account_name": resource_name,
                    "total_size_gb": total_size / 1024,
                    "transfer_estimate_hours": transfer_time / 60,
                },
            )

        except Exception as e:
            logger.error(f"Failed to analyze Storage Account: {e}")
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
                connection_methods=["HTTPS"],
                estimated_extraction_time_minutes=0,
                warnings=warnings,
                errors=errors,
            )

    async def extract_data(
        self, resource: Dict[str, Any], analysis: DataPlaneAnalysis
    ) -> ExtractionResult:
        """Extract Storage Account data from source.

        Args:
            resource: Source storage account resource dictionary
            analysis: Previous analysis result

        Returns:
            ExtractionResult with extracted storage data

        Raises:
            ConnectionError: If cannot connect to storage account
            IOError: If cannot write extracted data
        """
        logger.info(f"Extracting Storage Account data from {resource.get('name')}")

        resource_id = resource.get("id", "unknown")
        extracted_data: List[ExtractedData] = []
        warnings: List[str] = []
        errors: List[str] = []
        items_extracted = 0
        items_failed = 0
        start_time = datetime.utcnow()

        # Get output directory
        output_dir = Path(self.get_config_value("output_dir", "./storage_extraction"))
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Extract blob container inventory
            if self._has_element(analysis, "blob_containers"):
                try:
                    blob_data = await self._extract_blob_inventory(resource, output_dir)
                    extracted_data.append(blob_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract blob inventory: {e}")
                    errors.append(f"Blob containers: {e}")
                    items_failed += 1

            # Extract file share structure
            if self._has_element(analysis, "file_shares"):
                try:
                    file_data = await self._extract_file_share_structure(
                        resource, output_dir
                    )
                    extracted_data.append(file_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract file shares: {e}")
                    errors.append(f"File shares: {e}")
                    items_failed += 1

            # Extract table schemas
            if self._has_element(analysis, "table_storage"):
                try:
                    table_data = await self._extract_table_schemas(resource, output_dir)
                    extracted_data.append(table_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract table schemas: {e}")
                    errors.append(f"Table storage: {e}")
                    items_failed += 1

            # Extract queue metadata
            if self._has_element(analysis, "queue_storage"):
                try:
                    queue_data = await self._extract_queue_metadata(resource, output_dir)
                    extracted_data.append(queue_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract queue metadata: {e}")
                    errors.append(f"Queue storage: {e}")
                    items_failed += 1

            # Extract lifecycle policies
            if self._has_element(analysis, "lifecycle_policies"):
                try:
                    lifecycle_data = await self._extract_lifecycle_policies(
                        resource, output_dir
                    )
                    extracted_data.append(lifecycle_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract lifecycle policies: {e}")
                    errors.append(f"Lifecycle policies: {e}")
                    items_failed += 1

            # Extract CORS rules
            if self._has_element(analysis, "cors_rules"):
                try:
                    cors_data = await self._extract_cors_rules(resource, output_dir)
                    extracted_data.append(cors_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract CORS rules: {e}")
                    errors.append(f"CORS rules: {e}")
                    items_failed += 1

            # Extract soft delete settings
            if self._has_element(analysis, "soft_delete_settings"):
                try:
                    soft_delete_data = await self._extract_soft_delete_settings(
                        resource, output_dir
                    )
                    extracted_data.append(soft_delete_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract soft delete settings: {e}")
                    errors.append(f"Soft delete settings: {e}")
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

            warnings.append(
                "Actual data transfer must be performed using azcopy commands"
            )
            warnings.append("Credentials in generated scripts are sanitized placeholders")

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
                    "credentials_required": True,
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
        """Generate steps to replicate Storage Account to target.

        Args:
            extraction: Result from extract_data()

        Returns:
            List of ReplicationStep objects in execution order
        """
        logger.info("Generating Storage Account replication steps")

        steps: List[ReplicationStep] = []

        # Step 1: Prerequisites
        steps.append(
            ReplicationStep(
                step_id="prereq_azcopy",
                step_type=StepType.PREREQUISITE,
                description="Verify azcopy utility is installed",
                script_content=self._generate_azcopy_check_script(),
                script_format=ExtractionFormat.SHELL_SCRIPT,
                depends_on=[],
                estimated_duration_minutes=1,
                is_critical=True,
                can_retry=False,
            )
        )

        # Step 2: Create blob containers
        blob_data = self._find_extracted_data(extraction, "blob")
        if blob_data:
            steps.append(
                ReplicationStep(
                    step_id="create_blob_containers",
                    step_type=StepType.CONFIGURATION,
                    description="Create blob containers using Terraform",
                    script_content=self._generate_blob_container_terraform(blob_data),
                    script_format=ExtractionFormat.TERRAFORM,
                    depends_on=[],
                    estimated_duration_minutes=5,
                    is_critical=True,
                    can_retry=True,
                )
            )

            # Step 3: Copy blob data
            steps.append(
                ReplicationStep(
                    step_id="copy_blob_data",
                    step_type=StepType.DATA_IMPORT,
                    description="Copy blob data using azcopy",
                    script_content=self._generate_blob_copy_script(blob_data),
                    script_format=ExtractionFormat.SHELL_SCRIPT,
                    depends_on=["create_blob_containers"],
                    estimated_duration_minutes=self._estimate_transfer_time(blob_data),
                    is_critical=True,
                    can_retry=True,
                    max_retries=5,
                    metadata={
                        "manual_execution_required": True,
                        "note": "Update SAS tokens and account names before execution",
                    },
                )
            )

        # Step 4: Create file shares
        file_data = self._find_extracted_data(extraction, "file_share")
        if file_data:
            steps.append(
                ReplicationStep(
                    step_id="create_file_shares",
                    step_type=StepType.CONFIGURATION,
                    description="Create file shares using Terraform",
                    script_content=self._generate_file_share_terraform(file_data),
                    script_format=ExtractionFormat.TERRAFORM,
                    depends_on=[],
                    estimated_duration_minutes=5,
                    is_critical=True,
                    can_retry=True,
                )
            )

            # Step 5: Copy file share data
            steps.append(
                ReplicationStep(
                    step_id="copy_file_data",
                    step_type=StepType.DATA_IMPORT,
                    description="Copy file share data using azcopy",
                    script_content=self._generate_file_copy_script(file_data),
                    script_format=ExtractionFormat.SHELL_SCRIPT,
                    depends_on=["create_file_shares"],
                    estimated_duration_minutes=self._estimate_transfer_time(file_data),
                    is_critical=True,
                    can_retry=True,
                    max_retries=5,
                    metadata={
                        "manual_execution_required": True,
                        "note": "Update SAS tokens and account names before execution",
                    },
                )
            )

        # Step 6: Create tables
        table_data = self._find_extracted_data(extraction, "table")
        if table_data:
            steps.append(
                ReplicationStep(
                    step_id="create_tables",
                    step_type=StepType.CONFIGURATION,
                    description="Create table storage using Terraform",
                    script_content=self._generate_table_terraform(table_data),
                    script_format=ExtractionFormat.TERRAFORM,
                    depends_on=[],
                    estimated_duration_minutes=5,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 7: Create queues
        queue_data = self._find_extracted_data(extraction, "queue")
        if queue_data:
            steps.append(
                ReplicationStep(
                    step_id="create_queues",
                    step_type=StepType.CONFIGURATION,
                    description="Create queue storage using Terraform",
                    script_content=self._generate_queue_terraform(queue_data),
                    script_format=ExtractionFormat.TERRAFORM,
                    depends_on=[],
                    estimated_duration_minutes=5,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 8: Apply lifecycle policies
        lifecycle_data = self._find_extracted_data(extraction, "lifecycle")
        if lifecycle_data:
            steps.append(
                ReplicationStep(
                    step_id="apply_lifecycle_policies",
                    step_type=StepType.CONFIGURATION,
                    description="Apply blob lifecycle management policies",
                    script_content=self._generate_lifecycle_terraform(lifecycle_data),
                    script_format=ExtractionFormat.TERRAFORM,
                    depends_on=["create_blob_containers"],
                    estimated_duration_minutes=5,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 9: Apply CORS rules
        cors_data = self._find_extracted_data(extraction, "cors")
        if cors_data:
            steps.append(
                ReplicationStep(
                    step_id="apply_cors_rules",
                    step_type=StepType.CONFIGURATION,
                    description="Apply CORS rules to storage account",
                    script_content=self._generate_cors_script(cors_data),
                    script_format=ExtractionFormat.SHELL_SCRIPT,
                    depends_on=[],
                    estimated_duration_minutes=2,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 10: Configure soft delete
        soft_delete_data = self._find_extracted_data(extraction, "soft_delete")
        if soft_delete_data:
            steps.append(
                ReplicationStep(
                    step_id="configure_soft_delete",
                    step_type=StepType.CONFIGURATION,
                    description="Configure blob soft delete settings",
                    script_content=self._generate_soft_delete_script(soft_delete_data),
                    script_format=ExtractionFormat.SHELL_SCRIPT,
                    depends_on=["create_blob_containers"],
                    estimated_duration_minutes=2,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 11: Validation
        steps.append(
            ReplicationStep(
                step_id="validate_storage",
                step_type=StepType.VALIDATION,
                description="Validate storage account configuration and data transfer",
                script_content=self._generate_validation_script(),
                script_format=ExtractionFormat.SHELL_SCRIPT,
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
        """Apply Storage Account replication steps to target.

        Args:
            steps: Replication steps to execute
            target_resource_id: Azure resource ID of target storage account

        Returns:
            ReplicationResult with execution status
        """
        logger.info(f"Applying Storage Account replication to {target_resource_id}")

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

        warnings.append(
            "IMPORTANT: Data transfer steps require manual execution with valid credentials"
        )
        warnings.append(
            "Update SAS tokens and storage account names in generated scripts"
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

                # Skip manual execution steps in automated mode
                if step.metadata.get("manual_execution_required") and not is_dry_run:
                    logger.info(f"Skipping {step.step_id} - requires manual execution")
                    step_results.append(
                        StepResult(
                            step_id=step.step_id,
                            status=ReplicationStatus.SKIPPED,
                            duration_seconds=0,
                            stdout="[MANUAL] Script generated - must be executed manually with credentials",
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
                        # Execute step
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
                metadata={"dry_run": is_dry_run, "credentials_required": True},
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

    async def _check_storage_connectivity(self, resource: Dict[str, Any]) -> bool:
        """Check if storage account is accessible.

        Args:
            resource: Resource dictionary

        Returns:
            True if storage account is accessible
        """
        # In real implementation, would attempt to list containers
        # For now, return True if not in strict mode
        return not self.get_config_value("strict_validation", False)

    async def _analyze_blob_containers(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze blob containers in storage account.

        Args:
            resource: Resource dictionary

        Returns:
            Dictionary with blob statistics
        """
        # Mock implementation - real version would use BlobServiceClient
        return {
            "container_count": 5,
            "blob_count": 1250,
            "total_size_mb": 10240.5,  # ~10 GB
            "has_lifecycle_policy": True,
            "policy_count": 2,
            "access_tiers": ["Hot", "Cool", "Archive"],
            "versioning_enabled": True,
        }

    async def _analyze_file_shares(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze file shares in storage account.

        Args:
            resource: Resource dictionary

        Returns:
            Dictionary with file share statistics
        """
        # Mock implementation
        return {
            "share_count": 3,
            "file_count": 850,
            "total_size_mb": 5120.0,  # ~5 GB
            "total_directories": 120,
            "snapshots_enabled": True,
        }

    async def _analyze_tables(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze table storage in storage account.

        Args:
            resource: Resource dictionary

        Returns:
            Dictionary with table statistics
        """
        # Mock implementation
        return {
            "table_count": 4,
            "estimated_entities": 50000,
            "estimated_size_mb": 25.0,
            "has_sample_data": True,
        }

    async def _analyze_queues(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze queue storage in storage account.

        Args:
            resource: Resource dictionary

        Returns:
            Dictionary with queue statistics
        """
        # Mock implementation
        return {
            "queue_count": 6,
            "message_count": 1500,
            "estimated_size_mb": 2.5,
        }

    async def _check_cors_rules(self, resource: Dict[str, Any]) -> bool:
        """Check if CORS rules are configured.

        Args:
            resource: Resource dictionary

        Returns:
            True if CORS is configured
        """
        # Mock implementation
        return True

    async def _check_soft_delete(self, resource: Dict[str, Any]) -> bool:
        """Check if soft delete is enabled.

        Args:
            resource: Resource dictionary

        Returns:
            True if soft delete is enabled
        """
        # Mock implementation
        return True

    def _calculate_complexity_score(
        self, elements: List[DataPlaneElement], total_size_mb: float
    ) -> int:
        """Calculate complexity score from elements.

        Args:
            elements: List of discovered elements
            total_size_mb: Total size in MB

        Returns:
            Complexity score (1-10)
        """
        if not elements:
            return 1

        # Base complexity on number of elements
        score = min(10, 2 + len(elements))

        # Increase for large data sizes
        if total_size_mb > 100 * 1024:  # > 100 GB
            score = min(10, score + 3)
        elif total_size_mb > 10 * 1024:  # > 10 GB
            score = min(10, score + 2)
        elif total_size_mb > 1024:  # > 1 GB
            score = min(10, score + 1)

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

    async def _extract_blob_inventory(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract blob container inventory.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with blob inventory
        """
        # Mock implementation
        max_blobs = self.get_config_value("max_blobs_per_container", 1000)
        content = json.dumps(
            {
                "storage_account": resource.get("name", "unknown"),
                "containers": [
                    {
                        "name": "images",
                        "public_access": "None",
                        "blob_count": 450,
                        "total_size_mb": 3500.0,
                        "sample_blobs": [
                            {
                                "name": "products/laptop-01.png",
                                "size_mb": 2.5,
                                "content_type": "image/png",
                                "access_tier": "Hot",
                                "last_modified": "2025-01-10T10:30:00Z",
                            },
                            {
                                "name": "products/phone-02.jpg",
                                "size_mb": 1.8,
                                "content_type": "image/jpeg",
                                "access_tier": "Hot",
                                "last_modified": "2025-01-09T14:20:00Z",
                            },
                        ],
                        "note": f"Showing sample blobs (max {max_blobs} per container)",
                    },
                    {
                        "name": "documents",
                        "public_access": "None",
                        "blob_count": 300,
                        "total_size_mb": 1200.0,
                        "sample_blobs": [
                            {
                                "name": "reports/2024-q4.pdf",
                                "size_mb": 5.2,
                                "content_type": "application/pdf",
                                "access_tier": "Cool",
                                "last_modified": "2024-12-31T23:59:00Z",
                            }
                        ],
                    },
                    {
                        "name": "backups",
                        "public_access": "None",
                        "blob_count": 200,
                        "total_size_mb": 4500.0,
                        "sample_blobs": [
                            {
                                "name": "db-backup-2025-01-10.bak",
                                "size_mb": 450.0,
                                "content_type": "application/octet-stream",
                                "access_tier": "Archive",
                                "last_modified": "2025-01-10T02:00:00Z",
                            }
                        ],
                    },
                    {
                        "name": "logs",
                        "public_access": "None",
                        "blob_count": 250,
                        "total_size_mb": 800.0,
                        "sample_blobs": [
                            {
                                "name": "app-logs-2025-01-10.json",
                                "size_mb": 15.5,
                                "content_type": "application/json",
                                "access_tier": "Hot",
                                "last_modified": "2025-01-10T23:00:00Z",
                            }
                        ],
                    },
                    {
                        "name": "static-website",
                        "public_access": "Blob",
                        "blob_count": 50,
                        "total_size_mb": 240.5,
                        "sample_blobs": [
                            {
                                "name": "index.html",
                                "size_mb": 0.05,
                                "content_type": "text/html",
                                "access_tier": "Hot",
                                "last_modified": "2025-01-05T12:00:00Z",
                            }
                        ],
                    },
                ],
                "summary": {
                    "total_containers": 5,
                    "total_blobs": 1250,
                    "total_size_gb": 10.0,
                    "versioning_enabled": True,
                    "soft_delete_enabled": True,
                },
            },
            indent=2,
        )

        file_path = output_dir / "blob_inventory.json"
        file_path.write_text(content)

        return ExtractedData(
            name="blob_inventory",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_file_share_structure(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract file share directory structure.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with file share structure
        """
        # Mock implementation
        content = json.dumps(
            {
                "storage_account": resource.get("name", "unknown"),
                "file_shares": [
                    {
                        "name": "fileshare1",
                        "quota_gb": 100,
                        "used_gb": 45.2,
                        "snapshot_count": 3,
                        "directories": [
                            {
                                "path": "/",
                                "subdirs": ["projects", "archive", "temp"],
                                "file_count": 25,
                                "total_size_mb": 150.0,
                            },
                            {
                                "path": "/projects",
                                "subdirs": ["project-a", "project-b"],
                                "file_count": 450,
                                "total_size_mb": 3200.0,
                            },
                            {
                                "path": "/archive",
                                "subdirs": ["2023", "2024"],
                                "file_count": 200,
                                "total_size_mb": 1500.0,
                            },
                        ],
                    },
                    {
                        "name": "userdata",
                        "quota_gb": 50,
                        "used_gb": 12.5,
                        "snapshot_count": 1,
                        "directories": [
                            {
                                "path": "/",
                                "subdirs": ["user1", "user2", "user3"],
                                "file_count": 150,
                                "total_size_mb": 800.0,
                            }
                        ],
                    },
                    {
                        "name": "shared-resources",
                        "quota_gb": 25,
                        "used_gb": 5.8,
                        "snapshot_count": 0,
                        "directories": [
                            {
                                "path": "/",
                                "subdirs": ["templates", "tools"],
                                "file_count": 50,
                                "total_size_mb": 370.0,
                            }
                        ],
                    },
                ],
                "summary": {
                    "total_shares": 3,
                    "total_files": 850,
                    "total_size_gb": 5.0,
                    "total_quota_gb": 175,
                },
            },
            indent=2,
        )

        file_path = output_dir / "file_share_structure.json"
        file_path.write_text(content)

        return ExtractedData(
            name="file_share_structure",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_table_schemas(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract table storage schemas.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with table schemas
        """
        # Mock implementation
        include_sample = self.get_config_value("include_sample_data", True)
        content = json.dumps(
            {
                "storage_account": resource.get("name", "unknown"),
                "tables": [
                    {
                        "name": "Customers",
                        "estimated_entities": 15000,
                        "partition_key": "CountryCode",
                        "row_key": "CustomerId",
                        "properties": [
                            "Name",
                            "Email",
                            "Phone",
                            "CreatedDate",
                            "IsActive",
                        ],
                        "sample_data": [
                            {
                                "PartitionKey": "US",
                                "RowKey": "CUST-001",
                                "Name": "John Doe",
                                "Email": "john.doe@example.com",
                                "CreatedDate": "2024-01-15T10:00:00Z",
                                "IsActive": True,
                            }
                        ]
                        if include_sample
                        else [],
                    },
                    {
                        "name": "Orders",
                        "estimated_entities": 25000,
                        "partition_key": "Year",
                        "row_key": "OrderId",
                        "properties": [
                            "CustomerId",
                            "OrderDate",
                            "TotalAmount",
                            "Status",
                        ],
                        "sample_data": [
                            {
                                "PartitionKey": "2025",
                                "RowKey": "ORD-12345",
                                "CustomerId": "CUST-001",
                                "OrderDate": "2025-01-10T14:30:00Z",
                                "TotalAmount": 299.99,
                                "Status": "Shipped",
                            }
                        ]
                        if include_sample
                        else [],
                    },
                    {
                        "name": "Products",
                        "estimated_entities": 5000,
                        "partition_key": "Category",
                        "row_key": "ProductId",
                        "properties": ["Name", "Price", "StockQuantity", "Description"],
                        "sample_data": [
                            {
                                "PartitionKey": "Electronics",
                                "RowKey": "PROD-789",
                                "Name": "Laptop Pro 15",
                                "Price": 1499.99,
                                "StockQuantity": 25,
                            }
                        ]
                        if include_sample
                        else [],
                    },
                    {
                        "name": "Logs",
                        "estimated_entities": 5000,
                        "partition_key": "Date",
                        "row_key": "LogId",
                        "properties": ["Level", "Message", "Source", "Timestamp"],
                        "sample_data": [
                            {
                                "PartitionKey": "2025-01-10",
                                "RowKey": "LOG-001",
                                "Level": "INFO",
                                "Message": "Application started",
                                "Timestamp": "2025-01-10T08:00:00Z",
                            }
                        ]
                        if include_sample
                        else [],
                    },
                ],
                "summary": {
                    "total_tables": 4,
                    "estimated_total_entities": 50000,
                    "sample_data_included": include_sample,
                },
            },
            indent=2,
        )

        file_path = output_dir / "table_schemas.json"
        file_path.write_text(content)

        return ExtractedData(
            name="table_schemas",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_queue_metadata(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract queue storage metadata.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with queue metadata
        """
        # Mock implementation
        content = json.dumps(
            {
                "storage_account": resource.get("name", "unknown"),
                "queues": [
                    {
                        "name": "order-processing",
                        "message_count": 450,
                        "metadata": {
                            "purpose": "Order processing queue",
                            "max_delivery_count": 5,
                        },
                    },
                    {
                        "name": "notification-queue",
                        "message_count": 320,
                        "metadata": {
                            "purpose": "Email notifications",
                            "max_delivery_count": 3,
                        },
                    },
                    {
                        "name": "data-import-queue",
                        "message_count": 180,
                        "metadata": {
                            "purpose": "Background data import",
                            "max_delivery_count": 10,
                        },
                    },
                    {
                        "name": "audit-log-queue",
                        "message_count": 550,
                        "metadata": {"purpose": "Audit log processing"},
                    },
                    {
                        "name": "dead-letter-queue",
                        "message_count": 0,
                        "metadata": {
                            "purpose": "Failed messages",
                            "retention_days": 7,
                        },
                    },
                ],
                "summary": {
                    "total_queues": 6,
                    "total_messages": 1500,
                    "note": "Queue messages are not replicated, only queue structure",
                },
            },
            indent=2,
        )

        file_path = output_dir / "queue_metadata.json"
        file_path.write_text(content)

        return ExtractedData(
            name="queue_metadata",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_lifecycle_policies(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract blob lifecycle management policies.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with lifecycle policies
        """
        # Mock implementation
        content = json.dumps(
            {
                "storage_account": resource.get("name", "unknown"),
                "lifecycle_policies": [
                    {
                        "name": "archive-old-blobs",
                        "enabled": True,
                        "rules": [
                            {
                                "name": "move-to-cool",
                                "type": "Lifecycle",
                                "definition": {
                                    "filters": {"blobTypes": ["blockBlob"]},
                                    "actions": {
                                        "baseBlob": {
                                            "tierToCool": {"daysAfterModificationGreaterThan": 30},
                                            "tierToArchive": {
                                                "daysAfterModificationGreaterThan": 90
                                            },
                                            "delete": {
                                                "daysAfterModificationGreaterThan": 365
                                            },
                                        }
                                    },
                                },
                            }
                        ],
                    },
                    {
                        "name": "delete-old-snapshots",
                        "enabled": True,
                        "rules": [
                            {
                                "name": "cleanup-snapshots",
                                "type": "Lifecycle",
                                "definition": {
                                    "filters": {"blobTypes": ["blockBlob"]},
                                    "actions": {
                                        "snapshot": {
                                            "delete": {
                                                "daysAfterCreationGreaterThan": 30
                                            }
                                        }
                                    },
                                },
                            }
                        ],
                    },
                ],
                "summary": {
                    "total_policies": 2,
                    "total_rules": 2,
                },
            },
            indent=2,
        )

        file_path = output_dir / "lifecycle_policies.json"
        file_path.write_text(content)

        return ExtractedData(
            name="lifecycle_policies",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_cors_rules(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract CORS rules.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with CORS rules
        """
        # Mock implementation
        content = json.dumps(
            {
                "storage_account": resource.get("name", "unknown"),
                "cors_rules": {
                    "blob_service": [
                        {
                            "allowed_origins": ["https://example.com"],
                            "allowed_methods": ["GET", "HEAD", "POST"],
                            "allowed_headers": ["*"],
                            "exposed_headers": ["*"],
                            "max_age_seconds": 3600,
                        }
                    ],
                    "file_service": [],
                    "table_service": [],
                    "queue_service": [],
                },
            },
            indent=2,
        )

        file_path = output_dir / "cors_rules.json"
        file_path.write_text(content)

        return ExtractedData(
            name="cors_rules",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_soft_delete_settings(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract soft delete settings.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with soft delete settings
        """
        # Mock implementation
        content = json.dumps(
            {
                "storage_account": resource.get("name", "unknown"),
                "soft_delete_settings": {
                    "blob_soft_delete": {
                        "enabled": True,
                        "retention_days": 7,
                    },
                    "container_soft_delete": {
                        "enabled": True,
                        "retention_days": 7,
                    },
                    "share_soft_delete": {
                        "enabled": True,
                        "retention_days": 7,
                    },
                },
            },
            indent=2,
        )

        file_path = output_dir / "soft_delete_settings.json"
        file_path.write_text(content)

        return ExtractedData(
            name="soft_delete_settings",
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

    def _estimate_transfer_time(self, data: ExtractedData) -> int:
        """Estimate data transfer time in minutes.

        Args:
            data: Extracted data

        Returns:
            Estimated time in minutes
        """
        # Parse size from metadata or estimate
        size_mb = data.metadata.get("total_size_mb", 0)

        # Assume 100 Mbps connection = ~12.5 MB/s
        # Add 20% overhead
        if size_mb > 0:
            seconds = (size_mb / 12.5) * 1.2
            return max(5, int(seconds / 60))

        return 10

    def _generate_azcopy_check_script(self) -> str:
        """Generate script to check azcopy installation.

        Returns:
            Shell script content
        """
        azcopy_path = self.get_config_value("azcopy_path", "azcopy")
        return f"""#!/bin/bash
# Check azcopy installation

echo "Checking for azcopy utility..."

if command -v {azcopy_path} &> /dev/null; then
    echo "azcopy found: $({azcopy_path} --version)"
    exit 0
else
    echo "ERROR: azcopy not found in PATH"
    echo "Please install azcopy from: https://aka.ms/downloadazcopy"
    exit 1
fi
"""

    def _generate_blob_container_terraform(self, blob_data: ExtractedData) -> str:
        """Generate Terraform for blob containers.

        Args:
            blob_data: Blob inventory data

        Returns:
            Terraform HCL content
        """
        # Parse blob data
        try:
            data = json.loads(blob_data.content)
            containers = data.get("containers", [])
        except Exception:
            containers = []

        tf_content = """# Blob Container Creation
# Generated by Azure Tenant Grapher Storage Data Plugin

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

variable "storage_account_name" {
  description = "Target storage account name"
  type        = string
}

variable "resource_group_name" {
  description = "Resource group name"
  type        = string
}

"""

        for container in containers[:10]:  # Limit to 10 for example
            name = container.get("name", "unknown")
            access = container.get("public_access", "None").lower()
            if access == "none":
                access = "None"
            elif access == "blob":
                access = "Blob"
            elif access == "container":
                access = "Container"

            tf_content += f"""
resource "azurerm_storage_container" "{name.replace('-', '_')}" {{
  name                  = "{name}"
  storage_account_name  = var.storage_account_name
  container_access_type = "{access}"
}}
"""

        return tf_content

    def _generate_blob_copy_script(self, blob_data: ExtractedData) -> str:
        """Generate azcopy script for blob data transfer.

        Args:
            blob_data: Blob inventory data

        Returns:
            Shell script content
        """
        # Parse blob data
        try:
            data = json.loads(blob_data.content)
            containers = data.get("containers", [])
            source_account = data.get("storage_account", "SOURCE_ACCOUNT")
        except Exception:
            containers = []
            source_account = "SOURCE_ACCOUNT"

        azcopy_path = self.get_config_value("azcopy_path", "azcopy")
        expiry_hours = self.get_config_value("sas_expiry_hours", 24)

        script = f"""#!/bin/bash
# Blob Data Transfer Script
# Generated by Azure Tenant Grapher Storage Data Plugin
#
# IMPORTANT: Update the following before execution:
# 1. SOURCE_ACCOUNT - source storage account name
# 2. TARGET_ACCOUNT - target storage account name
# 3. SOURCE_SAS - source account SAS token (with read/list permissions)
# 4. TARGET_SAS - target account SAS token (with write permissions)
#
# To generate SAS tokens:
# az storage account generate-sas --account-name <name> --permissions rl --resource-types sco --services b --expiry {expiry_hours}h

# Configuration
SOURCE_ACCOUNT="{source_account}"
TARGET_ACCOUNT="TARGET_ACCOUNT"
SOURCE_SAS="?sv=YYYY-MM-DD&ss=b&srt=sco&sp=rl&se=YYYY-MM-DDTHH:MM:SSZ&st=YYYY-MM-DDTHH:MM:SSZ&spr=https&sig=SANITIZED"
TARGET_SAS="?sv=YYYY-MM-DD&ss=b&srt=sco&sp=w&se=YYYY-MM-DDTHH:MM:SSZ&st=YYYY-MM-DDTHH:MM:SSZ&spr=https&sig=SANITIZED"

# Logging
LOG_DIR="./azcopy_logs"
mkdir -p $LOG_DIR

echo "Starting blob data transfer..."
echo "Source: $SOURCE_ACCOUNT"
echo "Target: $TARGET_ACCOUNT"
echo "Containers to copy: {len(containers)}"
echo ""

"""

        for container in containers:
            name = container.get("name", "unknown")
            size_mb = container.get("total_size_mb", 0)

            script += f"""
# Transfer container: {name} (~{size_mb:.1f} MB)
echo "Copying container: {name}"
{azcopy_path} copy \\
    "https://${{SOURCE_ACCOUNT}}.blob.core.windows.net/{name}${{SOURCE_SAS}}" \\
    "https://${{TARGET_ACCOUNT}}.blob.core.windows.net/{name}${{TARGET_SAS}}" \\
    --recursive \\
    --log-level=INFO \\
    --output-type=json \\
    --output-level=error \\
    > "$LOG_DIR/{name}_$(date +%Y%m%d_%H%M%S).log" 2>&1

if [ $? -eq 0 ]; then
    echo "  ✓ {name} copied successfully"
else
    echo "  ✗ {name} copy failed - check log file"
fi

"""

        script += """
echo ""
echo "Blob data transfer complete!"
echo "Review logs in: $LOG_DIR"
"""

        return script

    def _generate_file_share_terraform(self, file_data: ExtractedData) -> str:
        """Generate Terraform for file shares.

        Args:
            file_data: File share structure data

        Returns:
            Terraform HCL content
        """
        # Parse file share data
        try:
            data = json.loads(file_data.content)
            shares = data.get("file_shares", [])
        except Exception:
            shares = []

        tf_content = """# File Share Creation
# Generated by Azure Tenant Grapher Storage Data Plugin

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

variable "storage_account_name" {
  description = "Target storage account name"
  type        = string
}

"""

        for share in shares:
            name = share.get("name", "unknown")
            quota_gb = share.get("quota_gb", 100)

            tf_content += f"""
resource "azurerm_storage_share" "{name.replace('-', '_')}" {{
  name                 = "{name}"
  storage_account_name = var.storage_account_name
  quota                = {quota_gb}
}}
"""

        return tf_content

    def _generate_file_copy_script(self, file_data: ExtractedData) -> str:
        """Generate azcopy script for file share transfer.

        Args:
            file_data: File share structure data

        Returns:
            Shell script content
        """
        # Parse file share data
        try:
            data = json.loads(file_data.content)
            shares = data.get("file_shares", [])
            source_account = data.get("storage_account", "SOURCE_ACCOUNT")
        except Exception:
            shares = []
            source_account = "SOURCE_ACCOUNT"

        azcopy_path = self.get_config_value("azcopy_path", "azcopy")

        script = f"""#!/bin/bash
# File Share Transfer Script
# Generated by Azure Tenant Grapher Storage Data Plugin

# Configuration
SOURCE_ACCOUNT="{source_account}"
TARGET_ACCOUNT="TARGET_ACCOUNT"
SOURCE_SAS="?sv=YYYY-MM-DD&ss=f&srt=sco&sp=rl&se=YYYY-MM-DDTHH:MM:SSZ&sig=SANITIZED"
TARGET_SAS="?sv=YYYY-MM-DD&ss=f&srt=sco&sp=w&se=YYYY-MM-DDTHH:MM:SSZ&sig=SANITIZED"

# Logging
LOG_DIR="./azcopy_logs"
mkdir -p $LOG_DIR

echo "Starting file share transfer..."
echo "Source: $SOURCE_ACCOUNT"
echo "Target: $TARGET_ACCOUNT"
echo "Shares to copy: {len(shares)}"
echo ""

"""

        for share in shares:
            name = share.get("name", "unknown")
            used_gb = share.get("used_gb", 0)

            script += f"""
# Transfer file share: {name} (~{used_gb:.1f} GB)
echo "Copying file share: {name}"
{azcopy_path} copy \\
    "https://${{SOURCE_ACCOUNT}}.file.core.windows.net/{name}${{SOURCE_SAS}}" \\
    "https://${{TARGET_ACCOUNT}}.file.core.windows.net/{name}${{TARGET_SAS}}" \\
    --recursive \\
    --preserve-smb-permissions=true \\
    --preserve-smb-info=true \\
    --log-level=INFO \\
    > "$LOG_DIR/{name}_$(date +%Y%m%d_%H%M%S).log" 2>&1

if [ $? -eq 0 ]; then
    echo "  ✓ {name} copied successfully"
else
    echo "  ✗ {name} copy failed - check log file"
fi

"""

        script += """
echo ""
echo "File share transfer complete!"
echo "Review logs in: $LOG_DIR"
"""

        return script

    def _generate_table_terraform(self, table_data: ExtractedData) -> str:
        """Generate Terraform for table storage.

        Args:
            table_data: Table schema data

        Returns:
            Terraform HCL content
        """
        # Parse table data
        try:
            data = json.loads(table_data.content)
            tables = data.get("tables", [])
        except Exception:
            tables = []

        tf_content = """# Table Storage Creation
# Generated by Azure Tenant Grapher Storage Data Plugin

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

variable "storage_account_name" {
  description = "Target storage account name"
  type        = string
}

"""

        for table in tables:
            name = table.get("name", "unknown")

            tf_content += f"""
resource "azurerm_storage_table" "{name.lower()}" {{
  name                 = "{name}"
  storage_account_name = var.storage_account_name
}}
"""

        tf_content += """
# Note: Table data must be migrated separately using Azure SDK or tools
# Terraform only creates the table structure
"""

        return tf_content

    def _generate_queue_terraform(self, queue_data: ExtractedData) -> str:
        """Generate Terraform for queue storage.

        Args:
            queue_data: Queue metadata

        Returns:
            Terraform HCL content
        """
        # Parse queue data
        try:
            data = json.loads(queue_data.content)
            queues = data.get("queues", [])
        except Exception:
            queues = []

        tf_content = """# Queue Storage Creation
# Generated by Azure Tenant Grapher Storage Data Plugin

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

variable "storage_account_name" {
  description = "Target storage account name"
  type        = string
}

"""

        for queue in queues:
            name = queue.get("name", "unknown")
            metadata = queue.get("metadata", {})

            tf_content += f"""
resource "azurerm_storage_queue" "{name.replace('-', '_')}" {{
  name                 = "{name}"
  storage_account_name = var.storage_account_name
"""

            if metadata:
                tf_content += "  metadata = {\n"
                for key, value in metadata.items():
                    if isinstance(value, str):
                        tf_content += f'    {key} = "{value}"\n'
                tf_content += "  }\n"

            tf_content += "}\n"

        tf_content += """
# Note: Queue messages are not migrated
"""

        return tf_content

    def _generate_lifecycle_terraform(self, lifecycle_data: ExtractedData) -> str:
        """Generate Terraform for lifecycle policies.

        Args:
            lifecycle_data: Lifecycle policy data

        Returns:
            Terraform HCL content
        """
        return """# Blob Lifecycle Management Policy
# Generated by Azure Tenant Grapher Storage Data Plugin

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

variable "storage_account_id" {
  description = "Target storage account resource ID"
  type        = string
}

resource "azurerm_storage_management_policy" "lifecycle" {
  storage_account_id = var.storage_account_id

  rule {
    name    = "move-to-cool"
    enabled = true

    filters {
      blob_types = ["blockBlob"]
    }

    actions {
      base_blob {
        tier_to_cool_after_days_since_modification_greater_than    = 30
        tier_to_archive_after_days_since_modification_greater_than = 90
        delete_after_days_since_modification_greater_than          = 365
      }
      snapshot {
        delete_after_days_since_creation_greater_than = 30
      }
    }
  }
}
"""

    def _generate_cors_script(self, cors_data: ExtractedData) -> str:
        """Generate script to apply CORS rules.

        Args:
            cors_data: CORS rules data

        Returns:
            Shell script content
        """
        return """#!/bin/bash
# Apply CORS Rules
# Generated by Azure Tenant Grapher Storage Data Plugin

STORAGE_ACCOUNT="TARGET_ACCOUNT"
RESOURCE_GROUP="TARGET_RESOURCE_GROUP"

echo "Applying CORS rules to storage account: $STORAGE_ACCOUNT"

# Blob Service CORS
az storage cors add \\
    --account-name $STORAGE_ACCOUNT \\
    --services b \\
    --methods GET HEAD POST \\
    --origins "https://example.com" \\
    --allowed-headers "*" \\
    --exposed-headers "*" \\
    --max-age 3600

echo "CORS rules applied successfully"
"""

    def _generate_soft_delete_script(self, soft_delete_data: ExtractedData) -> str:
        """Generate script to configure soft delete.

        Args:
            soft_delete_data: Soft delete settings data

        Returns:
            Shell script content
        """
        return """#!/bin/bash
# Configure Soft Delete
# Generated by Azure Tenant Grapher Storage Data Plugin

STORAGE_ACCOUNT="TARGET_ACCOUNT"
RESOURCE_GROUP="TARGET_RESOURCE_GROUP"

echo "Configuring soft delete for storage account: $STORAGE_ACCOUNT"

# Enable blob soft delete (7 day retention)
az storage blob service-properties delete-policy update \\
    --account-name $STORAGE_ACCOUNT \\
    --enable true \\
    --days-retained 7

# Enable container soft delete
az storage account blob-service-properties update \\
    --account-name $STORAGE_ACCOUNT \\
    --resource-group $RESOURCE_GROUP \\
    --enable-container-delete-retention true \\
    --container-delete-retention-days 7

echo "Soft delete configured successfully"
"""

    def _generate_validation_script(self) -> str:
        """Generate validation script for storage account.

        Returns:
            Shell script content
        """
        return """#!/bin/bash
# Validate Storage Account Configuration
# Generated by Azure Tenant Grapher Storage Data Plugin

STORAGE_ACCOUNT="TARGET_ACCOUNT"

echo "Validating storage account: $STORAGE_ACCOUNT"
echo ""

# Check blob containers
echo "Blob Containers:"
az storage container list --account-name $STORAGE_ACCOUNT --output table

# Check file shares
echo ""
echo "File Shares:"
az storage share list --account-name $STORAGE_ACCOUNT --output table

# Check tables
echo ""
echo "Tables:"
az storage table list --account-name $STORAGE_ACCOUNT --output table

# Check queues
echo ""
echo "Queues:"
az storage queue list --account-name $STORAGE_ACCOUNT --output table

echo ""
echo "Validation complete!"
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
        """Execute a replication step on target storage account.

        Args:
            step: Step to execute
            target_resource_id: Target storage account resource ID

        Returns:
            StepResult with execution status
        """
        # Mock implementation - real version would use Azure SDK
        start_time = datetime.utcnow()

        # Simulate execution
        await asyncio.sleep(0.2)

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
