"""VM Extensions replication plugin for Azure Virtual Machines.

This plugin handles data-plane replication for VM extensions, including:
- CustomScriptExtension (Windows and Linux)
- Other VM extensions (monitoring, antimalware, diagnostics, etc.)
- Extension settings and configuration
- Script content extraction (when accessible)
- Extension dependencies and ordering

Security Note: This plugin NEVER extracts protected settings values. Protected
settings are documented but must be manually reconfigured in the target environment.
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


class VMExtensionsReplicationPlugin(ResourceReplicationPlugin):
    """Handles VM extension data-plane replication.

    This plugin replicates VM extensions including:
    - Extension metadata (publisher, type, version)
    - Public settings (configuration)
    - Protected settings metadata (NOT values)
    - Script content (when accessible)
    - Extension dependencies and ordering

    Requires:
    - Azure Resource Manager API access
    - Permission to list VM extensions
    - Optional: Access to storage accounts for script downloads
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        """Initialize the VM Extensions plugin.

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
            name="vm_extensions",
            version="1.0.0",
            description="Replicates Azure VM extensions and their configurations",
            author="Azure Tenant Grapher",
            resource_types=["Microsoft.Compute/virtualMachines/extensions"],
            supported_formats=[
                ExtractionFormat.TERRAFORM,
                ExtractionFormat.JSON,
                ExtractionFormat.SHELL_SCRIPT,
            ],
            requires_credentials=True,
            requires_network_access=True,
            complexity="MEDIUM",
            estimated_effort_weeks=1.5,
            tags=["vm", "extensions", "scripts", "configuration"],
            documentation_url="https://docs.microsoft.com/en-us/azure/virtual-machines/extensions/overview",
        )

    def can_handle(self, resource: Dict[str, Any]) -> bool:
        """Check if resource is a VM extension.

        Args:
            resource: Resource dictionary

        Returns:
            True if resource is a VM extension
        """
        resource_type = resource.get("type", "")
        return resource_type == "Microsoft.Compute/virtualMachines/extensions"

    async def analyze_source(self, resource: Dict[str, Any]) -> DataPlaneAnalysis:
        """Analyze VM extension configuration on source VM.

        Args:
            resource: Source VM extension resource dictionary

        Returns:
            DataPlaneAnalysis with discovered extension elements

        Raises:
            ConnectionError: If cannot access Azure API
            PermissionError: If insufficient permissions
        """
        logger.info(f"Analyzing VM extension {resource.get('name')}")

        resource_id = resource.get("id", "unknown")
        elements: List[DataPlaneElement] = []
        warnings: List[str] = []
        errors: List[str] = []

        try:
            # Extract extension properties
            properties = resource.get("properties", {})
            publisher = properties.get("publisher", "unknown")
            extension_type = properties.get("type", "unknown")
            type_handler_version = properties.get("typeHandlerVersion", "unknown")
            provisioning_state = properties.get("provisioningState", "unknown")

            # Extension metadata
            elements.append(
                DataPlaneElement(
                    name="extension_metadata",
                    element_type="Extension Metadata",
                    description=f"{publisher}/{extension_type} v{type_handler_version}",
                    complexity="LOW",
                    estimated_size_mb=0.01,
                    dependencies=[],
                    metadata={
                        "publisher": publisher,
                        "type": extension_type,
                        "version": type_handler_version,
                        "state": provisioning_state,
                    },
                )
            )

            # Public settings
            settings = properties.get("settings", {})
            if settings:
                settings_size = len(json.dumps(settings).encode()) / (1024 * 1024)
                elements.append(
                    DataPlaneElement(
                        name="public_settings",
                        element_type="Public Settings",
                        description=f"Public configuration ({len(settings)} keys)",
                        complexity="LOW",
                        estimated_size_mb=max(0.01, settings_size),
                        dependencies=["extension_metadata"],
                        metadata={"key_count": len(settings)},
                    )
                )

            # Protected settings (metadata only)
            protected_settings = properties.get("protectedSettings", {})
            if protected_settings:
                elements.append(
                    DataPlaneElement(
                        name="protected_settings",
                        element_type="Protected Settings",
                        description="Protected settings (values NOT extractable)",
                        complexity="MEDIUM",
                        estimated_size_mb=0.01,
                        dependencies=["extension_metadata"],
                        metadata={
                            "key_count": len(protected_settings),
                            "keys": list(protected_settings.keys()),
                        },
                        is_sensitive=True,
                    )
                )
                warnings.append(
                    f"Protected settings detected ({len(protected_settings)} keys) - "
                    "values cannot be extracted and must be manually configured"
                )

            # Script content (for CustomScriptExtension)
            if "CustomScript" in extension_type or "customScript" in extension_type:
                file_uris = settings.get("fileUris", [])
                if file_uris:
                    total_script_size = len(file_uris) * 0.1  # Estimate
                    elements.append(
                        DataPlaneElement(
                            name="script_content",
                            element_type="Script Files",
                            description=f"{len(file_uris)} script file(s)",
                            complexity="MEDIUM",
                            estimated_size_mb=total_script_size,
                            dependencies=["public_settings"],
                            metadata={
                                "file_count": len(file_uris),
                                "file_uris": file_uris,
                            },
                        )
                    )

                command_to_execute = settings.get("commandToExecute")
                if command_to_execute:
                    elements.append(
                        DataPlaneElement(
                            name="execute_command",
                            element_type="Command",
                            description="Execution command",
                            complexity="LOW",
                            estimated_size_mb=0.01,
                            dependencies=["script_content"],
                            metadata={"command": command_to_execute},
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
                connection_methods=["Azure Resource Manager API"],
                estimated_extraction_time_minutes=max(5, len(elements) * 2),
                warnings=warnings,
                errors=errors,
                metadata={
                    "publisher": publisher,
                    "extension_type": extension_type,
                    "version": type_handler_version,
                },
            )

        except Exception as e:
            logger.error(f"Failed to analyze VM extension: {e}")
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
                connection_methods=["Azure Resource Manager API"],
                estimated_extraction_time_minutes=0,
                warnings=warnings,
                errors=errors,
            )

    async def extract_data(
        self, resource: Dict[str, Any], analysis: DataPlaneAnalysis
    ) -> ExtractionResult:
        """Extract VM extension configuration from source.

        Args:
            resource: Source VM extension resource dictionary
            analysis: Previous analysis result

        Returns:
            ExtractionResult with extracted extension configuration

        Raises:
            ConnectionError: If cannot access Azure API
            IOError: If cannot write extracted data
        """
        logger.info(f"Extracting VM extension data from {resource.get('name')}")

        resource_id = resource.get("id", "unknown")
        extracted_data: List[ExtractedData] = []
        warnings: List[str] = []
        errors: List[str] = []
        items_extracted = 0
        items_failed = 0
        start_time = datetime.utcnow()

        # Get output directory
        output_dir = Path(self.get_config_value("output_dir", "./vm_extensions"))
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Extract extension metadata
            if self._has_element(analysis, "extension_metadata"):
                try:
                    metadata_data = await self._extract_extension_metadata(
                        resource, output_dir
                    )
                    extracted_data.append(metadata_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract extension metadata: {e}")
                    errors.append(f"Extension metadata: {e}")
                    items_failed += 1

            # Extract public settings
            if self._has_element(analysis, "public_settings"):
                try:
                    settings_data = await self._extract_public_settings(
                        resource, output_dir
                    )
                    extracted_data.append(settings_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract public settings: {e}")
                    errors.append(f"Public settings: {e}")
                    items_failed += 1

            # Extract protected settings metadata
            if self._has_element(analysis, "protected_settings"):
                try:
                    protected_data = await self._extract_protected_settings_metadata(
                        resource, output_dir
                    )
                    extracted_data.append(protected_data)
                    items_extracted += 1
                    warnings.append(
                        "Protected settings values NOT extracted - must be manually configured"
                    )
                except Exception as e:
                    logger.error(f"Failed to extract protected settings metadata: {e}")
                    errors.append(f"Protected settings: {e}")
                    items_failed += 1

            # Extract script content
            if self._has_element(analysis, "script_content"):
                try:
                    script_data = await self._extract_script_content(resource, output_dir)
                    extracted_data.append(script_data)
                    items_extracted += 1
                    warnings.append(
                        "Scripts may contain credentials - review and sanitize before use"
                    )
                except Exception as e:
                    logger.error(f"Failed to extract script content: {e}")
                    errors.append(f"Script content: {e}")
                    items_failed += 1

            # Extract command
            if self._has_element(analysis, "execute_command"):
                try:
                    command_data = await self._extract_command(resource, output_dir)
                    extracted_data.append(command_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract command: {e}")
                    errors.append(f"Execute command: {e}")
                    items_failed += 1

            # Calculate totals
            total_size_mb = sum(d.size_bytes / (1024 * 1024) for d in extracted_data)
            duration = (datetime.utcnow() - start_time).total_seconds()

            status = AnalysisStatus.SUCCESS
            if items_failed > 0:
                status = (
                    AnalysisStatus.FAILED if items_extracted == 0 else AnalysisStatus.PARTIAL
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
        """Generate Terraform steps to replicate VM extensions to target.

        Args:
            extraction: Result from extract_data()

        Returns:
            List of ReplicationStep objects in execution order
        """
        logger.info("Generating VM extension replication steps")

        steps: List[ReplicationStep] = []

        # Step 1: Generate Terraform for extension
        metadata_data = self._find_extracted_data(extraction, "metadata")
        settings_data = self._find_extracted_data(extraction, "settings")
        protected_data = self._find_extracted_data(extraction, "protected")

        if metadata_data or settings_data:
            steps.append(
                ReplicationStep(
                    step_id="generate_terraform",
                    step_type=StepType.PREREQUISITE,
                    description="Generate Terraform configuration for VM extension",
                    script_content=self._generate_terraform_config(
                        metadata_data, settings_data, protected_data, extraction
                    ),
                    script_format=ExtractionFormat.TERRAFORM,
                    depends_on=[],
                    estimated_duration_minutes=2,
                    is_critical=True,
                    can_retry=True,
                )
            )

        # Step 2: Upload scripts (if any)
        script_data = self._find_extracted_data(extraction, "script")
        if script_data:
            steps.append(
                ReplicationStep(
                    step_id="upload_scripts",
                    step_type=StepType.PREREQUISITE,
                    description="Upload extension scripts to storage",
                    script_content=self._generate_upload_script(script_data),
                    script_format=ExtractionFormat.SHELL_SCRIPT,
                    depends_on=[],
                    estimated_duration_minutes=5,
                    is_critical=True,
                    can_retry=True,
                )
            )

        # Step 3: Apply Terraform
        if metadata_data or settings_data:
            depends = ["upload_scripts"] if script_data else []
            steps.append(
                ReplicationStep(
                    step_id="apply_terraform",
                    step_type=StepType.CONFIGURATION,
                    description="Apply Terraform to create VM extension",
                    script_content=self._generate_terraform_apply_script(),
                    script_format=ExtractionFormat.SHELL_SCRIPT,
                    depends_on=depends,
                    estimated_duration_minutes=10,
                    is_critical=True,
                    can_retry=True,
                )
            )

        # Step 4: Configure protected settings
        if protected_data:
            steps.append(
                ReplicationStep(
                    step_id="configure_protected_settings",
                    step_type=StepType.POST_CONFIG,
                    description="MANUAL: Configure protected settings (see documentation)",
                    script_content=self._generate_protected_settings_doc(protected_data),
                    script_format=ExtractionFormat.JSON,
                    depends_on=["apply_terraform"],
                    estimated_duration_minutes=5,
                    is_critical=False,
                    can_retry=False,
                )
            )

        # Step 5: Validation
        steps.append(
            ReplicationStep(
                step_id="validate_extension",
                step_type=StepType.VALIDATION,
                description="Validate VM extension installation",
                script_content=self._generate_validation_script(),
                script_format=ExtractionFormat.SHELL_SCRIPT,
                depends_on=[s.step_id for s in steps if s.step_id != "configure_protected_settings"],
                estimated_duration_minutes=2,
                is_critical=False,
                can_retry=True,
            )
        )

        return steps

    async def apply_to_target(
        self, steps: List[ReplicationStep], target_resource_id: str
    ) -> ReplicationResult:
        """Apply VM extension replication steps to target VM.

        Args:
            steps: Replication steps to execute
            target_resource_id: Azure resource ID of target VM

        Returns:
            ReplicationResult with execution status
        """
        logger.info(f"Applying VM extension replication to {target_resource_id}")

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

                # Skip manual steps in automated execution
                if "MANUAL" in step.description:
                    logger.info(f"Skipping manual step: {step.step_id}")
                    step_results.append(
                        StepResult(
                            step_id=step.step_id,
                            status=ReplicationStatus.SKIPPED,
                            duration_seconds=0,
                            stdout=step.script_content,
                            error_message="Manual step - requires human intervention",
                        )
                    )
                    steps_skipped += 1
                    warnings.append(f"Manual step required: {step.description}")
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
                        # Execute via Azure API or Terraform
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

        # Increase for sensitive elements
        sensitive_count = sum(1 for e in elements if e.is_sensitive)
        score = min(10, score + sensitive_count * 2)

        return score

    def _has_element(self, analysis: DataPlaneAnalysis, name: str) -> bool:
        """Check if analysis contains an element.

        Args:
            analysis: Analysis result
            name: Element name to check

        Returns:
            True if element exists
        """
        return any(name in e.name for e in analysis.elements)

    async def _extract_extension_metadata(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract extension metadata.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with extension metadata
        """
        properties = resource.get("properties", {})
        content = json.dumps(
            {
                "extension_name": resource.get("name"),
                "publisher": properties.get("publisher"),
                "type": properties.get("type"),
                "typeHandlerVersion": properties.get("typeHandlerVersion"),
                "autoUpgradeMinorVersion": properties.get("autoUpgradeMinorVersion", True),
                "provisioningState": properties.get("provisioningState"),
                "instanceView": properties.get("instanceView", {}),
            },
            indent=2,
        )

        file_path = output_dir / "extension_metadata.json"
        file_path.write_text(content)

        return ExtractedData(
            name="extension_metadata",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_public_settings(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract public settings.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with public settings
        """
        properties = resource.get("properties", {})
        settings = properties.get("settings", {})

        content = json.dumps(settings, indent=2)

        file_path = output_dir / "public_settings.json"
        file_path.write_text(content)

        return ExtractedData(
            name="public_settings",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_protected_settings_metadata(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract protected settings metadata (NOT values).

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with protected settings metadata
        """
        properties = resource.get("properties", {})
        protected_settings = properties.get("protectedSettings", {})

        # Only extract keys, not values
        metadata = {
            "note": "Protected settings values are NOT accessible via API",
            "required_keys": list(protected_settings.keys()),
            "manual_configuration_required": True,
            "example": dict.fromkeys(protected_settings.keys(), "<REDACTED - CONFIGURE MANUALLY>"),
        }

        content = json.dumps(metadata, indent=2)

        file_path = output_dir / "protected_settings_metadata.json"
        file_path.write_text(content)

        return ExtractedData(
            name="protected_settings_metadata",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
            metadata={"is_sensitive": True},
        )

    async def _extract_script_content(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract script content (mock - would download from URIs in real impl).

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with script content
        """
        properties = resource.get("properties", {})
        settings = properties.get("settings", {})
        file_uris = settings.get("fileUris", [])

        # In real implementation, would download from URIs
        # For now, document the URIs and create placeholder
        scripts_info = {
            "note": "Script content should be downloaded from file URIs",
            "file_uris": file_uris,
            "download_instructions": [
                "1. Access each URI and download the script content",
                "2. Review scripts for hardcoded credentials or sensitive data",
                "3. Sanitize scripts before uploading to target storage",
                "4. Update fileUris in extension configuration to point to new storage",
            ],
            "example_download_command": f"# Download script (example)\n# curl -o script.sh '{file_uris[0]}'"
            if file_uris
            else "# No file URIs found",
        }

        content = json.dumps(scripts_info, indent=2)

        file_path = output_dir / "script_content_info.json"
        file_path.write_text(content)

        return ExtractedData(
            name="script_content_info",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_command(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract execution command.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with command
        """
        properties = resource.get("properties", {})
        settings = properties.get("settings", {})
        command = settings.get("commandToExecute", "")

        content = json.dumps(
            {"commandToExecute": command, "note": "Review command for credentials or sensitive data"},
            indent=2,
        )

        file_path = output_dir / "command.json"
        file_path.write_text(content)

        return ExtractedData(
            name="execute_command",
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

    def _generate_terraform_config(
        self,
        metadata_data: Optional[ExtractedData],
        settings_data: Optional[ExtractedData],
        protected_data: Optional[ExtractedData],
        extraction: ExtractionResult,
    ) -> str:
        """Generate Terraform configuration for extension.

        Args:
            metadata_data: Extension metadata
            settings_data: Public settings
            protected_data: Protected settings metadata
            extraction: Full extraction result

        Returns:
            Terraform configuration string
        """
        # Parse metadata
        metadata = {}
        if metadata_data:
            metadata = json.loads(metadata_data.content)

        # Parse settings
        settings = {}
        if settings_data:
            settings = json.loads(settings_data.content)

        extension_name = metadata.get("extension_name", "extension")
        publisher = metadata.get("publisher", "Microsoft.Azure.Extensions")
        ext_type = metadata.get("type", "CustomScript")
        version = metadata.get("typeHandlerVersion", "2.0")

        # Generate Terraform
        tf_config = f'''# VM Extension Terraform Configuration
# Extension: {extension_name}
# Publisher: {publisher}
# Type: {ext_type}
# Version: {version}

resource "azurerm_virtual_machine_extension" "{extension_name}" {{
  name                       = "{extension_name}"
  virtual_machine_id         = var.target_vm_id
  publisher                  = "{publisher}"
  type                       = "{ext_type}"
  type_handler_version       = "{version}"
  auto_upgrade_minor_version = true

  settings = jsonencode({{
'''

        # Add settings
        for key, value in settings.items():
            if isinstance(value, str):
                tf_config += f'    {key} = "{value}"\n'
            elif isinstance(value, list):
                tf_config += f'    {key} = {json.dumps(value)}\n'
            else:
                tf_config += f'    {key} = {json.dumps(value)}\n'

        tf_config += "  })\n\n"

        # Add protected settings placeholder
        if protected_data:
            protected_meta = json.loads(protected_data.content)
            required_keys = protected_meta.get("required_keys", [])
            if required_keys:
                tf_config += "  # Protected settings (CONFIGURE MANUALLY)\n"
                tf_config += "  # protected_settings = jsonencode({\n"
                for key in required_keys:
                    tf_config += f'  #   {key} = "<CONFIGURE_MANUALLY>"\n'
                tf_config += "  # })\n\n"

        tf_config += "}\n"

        return tf_config

    def _generate_upload_script(self, script_data: ExtractedData) -> str:
        """Generate script to upload extension scripts to storage.

        Args:
            script_data: Script content data

        Returns:
            Shell script to upload scripts
        """
        return '''#!/bin/bash
# Upload VM extension scripts to Azure Storage

# Configuration
STORAGE_ACCOUNT="<YOUR_STORAGE_ACCOUNT>"
CONTAINER_NAME="<YOUR_CONTAINER>"
RESOURCE_GROUP="<YOUR_RESOURCE_GROUP>"

# Ensure Azure CLI is installed and authenticated
if ! command -v az &> /dev/null; then
    echo "Azure CLI is not installed. Please install it first."
    exit 1
fi

# Upload scripts
# NOTE: Download scripts from original URIs first, then upload to new storage
# Review scripts for credentials before uploading

# Example:
# az storage blob upload \\
#   --account-name "$STORAGE_ACCOUNT" \\
#   --container-name "$CONTAINER_NAME" \\
#   --name "script.sh" \\
#   --file "./downloaded_scripts/script.sh" \\
#   --auth-mode login

echo "Manual script upload required - see comments above"
echo "Download scripts from original URIs, review, sanitize, then upload to target storage"
'''

    def _generate_terraform_apply_script(self) -> str:
        """Generate script to apply Terraform configuration.

        Returns:
            Shell script to apply Terraform
        """
        return '''#!/bin/bash
# Apply Terraform configuration for VM extension

# Ensure Terraform is installed
if ! command -v terraform &> /dev/null; then
    echo "Terraform is not installed. Please install it first."
    exit 1
fi

# Initialize Terraform
terraform init

# Plan changes
terraform plan -out=extension.tfplan

# Apply changes
terraform apply extension.tfplan

echo "VM extension applied successfully"
'''

    def _generate_protected_settings_doc(self, protected_data: ExtractedData) -> str:
        """Generate documentation for protected settings configuration.

        Args:
            protected_data: Protected settings metadata

        Returns:
            JSON documentation
        """
        protected_meta = json.loads(protected_data.content)
        required_keys = protected_meta.get("required_keys", [])

        doc = {
            "manual_configuration_required": True,
            "reason": "Protected settings values cannot be extracted via Azure API",
            "required_keys": required_keys,
            "instructions": [
                "1. Identify the values for protected settings from source environment",
                "2. Securely transfer these values (use Azure Key Vault if possible)",
                "3. Update Terraform configuration with protected_settings block",
                "4. Apply Terraform configuration",
            ],
            "terraform_example": {
                "protected_settings": dict.fromkeys(required_keys, "<VALUE_FROM_SOURCE>")
            },
            "security_notes": [
                "Never commit protected settings values to source control",
                "Use Terraform variables or Azure Key Vault for sensitive values",
                "Rotate credentials after migration",
            ],
        }

        return json.dumps(doc, indent=2)

    def _generate_validation_script(self) -> str:
        """Generate validation script.

        Returns:
            Shell script to validate extension
        """
        return '''#!/bin/bash
# Validate VM extension installation

VM_NAME="<TARGET_VM_NAME>"
RESOURCE_GROUP="<TARGET_RESOURCE_GROUP>"
EXTENSION_NAME="<EXTENSION_NAME>"

# Check extension status
az vm extension show \\
  --name "$EXTENSION_NAME" \\
  --vm-name "$VM_NAME" \\
  --resource-group "$RESOURCE_GROUP" \\
  --query "provisioningState" \\
  -o tsv

# Check extension output
az vm extension show \\
  --name "$EXTENSION_NAME" \\
  --vm-name "$VM_NAME" \\
  --resource-group "$RESOURCE_GROUP" \\
  --query "instanceView.statuses[*].[code,message]" \\
  -o table

echo "Validation complete"
'''

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
        # Mock implementation - real version would use Azure SDK or Terraform
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

        # Weight: succeeded=1.0, skipped=0.5 (manual steps), failed=0.0
        weighted_score = succeeded + (skipped * 0.5)
        return min(1.0, weighted_score / total)
