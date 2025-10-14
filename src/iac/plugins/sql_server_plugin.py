"""SQL Server replication plugin for SQL Server VMs.

This plugin handles data-plane replication for SQL Server instances,
including databases, schemas, security, SQL Agent jobs, and configuration.

Security Note: This plugin NEVER extracts password hashes or encryption keys.
Generated configurations use placeholder passwords that must be manually set.
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


class SQLServerReplicationPlugin(ResourceReplicationPlugin):
    """Handles SQL Server instance replication.

    This plugin replicates SQL Server configuration and data:
    - Databases and properties
    - Schema objects (tables, views, procedures, functions)
    - Security (logins, users, roles, permissions)
    - SQL Agent (jobs, schedules, operators, alerts)
    - Server configuration (sp_configure settings)
    - Linked servers
    - Database mail configuration
    - Optional: Data export (sample or full)

    Requires:
    - SQL Server connectivity (TCP/IP or named pipes)
    - SQL authentication or Windows authentication
    - Appropriate permissions (sysadmin or granular permissions)
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        """Initialize the SQL Server plugin.

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
            name="sql_server",
            version="1.0.0",
            description="Replicates SQL Server instance configuration and data",
            author="Azure Tenant Grapher",
            resource_types=["Microsoft.Compute/virtualMachines"],
            supported_formats=[
                ExtractionFormat.SQL_SCRIPT,
                ExtractionFormat.JSON,
                ExtractionFormat.CSV,
                ExtractionFormat.POWERSHELL_DSC,
            ],
            requires_credentials=True,
            requires_network_access=True,
            complexity="VERY_HIGH",
            estimated_effort_weeks=3.0,
            tags=["sql-server", "database", "mssql", "windows"],
            documentation_url="https://docs.microsoft.com/en-us/sql/sql-server/",
        )

    def can_handle(self, resource: Dict[str, Any]) -> bool:
        """Check if resource is a SQL Server VM.

        Args:
            resource: Resource dictionary

        Returns:
            True if resource is a Windows VM with SQL Server
        """
        if not super().can_handle(resource):
            return False

        # Check for SQL Server indicators
        tags = resource.get("tags", {})
        name = resource.get("name", "").lower()

        # Check tags for SQL Server role
        if tags.get("role") in ["sql-server", "sql", "database"]:
            return True

        # Check VM name patterns (common SQL Server naming conventions)
        if any(pattern in name for pattern in ["sql", "db", "database"]):
            return True

        # Check for SQL Server in tags
        if any("sql" in str(v).lower() for v in tags.values()):
            return True

        return False

    async def analyze_source(
        self, resource: Dict[str, Any]
    ) -> DataPlaneAnalysis:
        """Analyze SQL Server instance on source VM.

        Args:
            resource: Source VM resource dictionary

        Returns:
            DataPlaneAnalysis with discovered SQL Server elements

        Raises:
            ConnectionError: If cannot connect to SQL Server
            PermissionError: If lacking SQL Server read permissions
        """
        logger.info(f"Analyzing SQL Server on {resource.get('name')}")

        resource_id = resource.get("id", "unknown")
        elements: List[DataPlaneElement] = []
        warnings: List[str] = []
        errors: List[str] = []

        try:
            # Check connectivity
            if not await self._check_sql_connectivity(resource):
                raise ConnectionError("Cannot connect to SQL Server")

            # Analyze server configuration
            server_info = await self._analyze_server_config(resource)
            if server_info:
                elements.append(
                    DataPlaneElement(
                        name="server_configuration",
                        element_type="SQL Server Config",
                        description=f"SQL Server {server_info.get('version', 'unknown')}",
                        complexity="MEDIUM",
                        estimated_size_mb=0.1,
                        dependencies=[],
                        metadata=server_info,
                    )
                )

            # Analyze databases
            db_count = await self._count_databases(resource)
            if db_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="databases",
                        element_type="Databases",
                        description=f"{db_count} databases",
                        complexity="HIGH",
                        estimated_size_mb=db_count * 10.0,  # Rough estimate
                        dependencies=["server_configuration"],
                        metadata={"count": db_count},
                    )
                )

            # Analyze schema objects
            schema_count = await self._count_schema_objects(resource)
            if schema_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="schema_objects",
                        element_type="Schema",
                        description=f"{schema_count} schema objects (tables, views, procedures)",
                        complexity="VERY_HIGH",
                        estimated_size_mb=schema_count * 0.05,
                        dependencies=["databases"],
                        metadata={"count": schema_count},
                    )
                )

            # Analyze security
            login_count = await self._count_logins(resource)
            if login_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="security",
                        element_type="Security",
                        description=f"{login_count} logins and security principals (passwords excluded)",
                        complexity="HIGH",
                        estimated_size_mb=login_count * 0.02,
                        dependencies=["server_configuration"],
                        metadata={"count": login_count},
                    )
                )

            # Analyze SQL Agent
            job_count = await self._count_agent_jobs(resource)
            if job_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="sql_agent",
                        element_type="SQL Agent",
                        description=f"{job_count} SQL Agent jobs and schedules",
                        complexity="MEDIUM",
                        estimated_size_mb=job_count * 0.1,
                        dependencies=["server_configuration"],
                        metadata={"count": job_count},
                    )
                )

            # Analyze linked servers
            linked_count = await self._count_linked_servers(resource)
            if linked_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="linked_servers",
                        element_type="Linked Servers",
                        description=f"{linked_count} linked servers",
                        complexity="MEDIUM",
                        estimated_size_mb=0.05,
                        dependencies=["server_configuration"],
                        metadata={"count": linked_count},
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
                connection_methods=["SQL Server", "TCP/IP", "PowerShell"],
                estimated_extraction_time_minutes=max(15, len(elements) * 10),
                warnings=warnings,
                errors=errors,
                metadata={
                    "sql_version": server_info.get("version") if server_info else None,
                    "edition": server_info.get("edition") if server_info else None,
                },
            )

        except Exception as e:
            logger.error(f"Failed to analyze SQL Server: {e}")
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
                connection_methods=["SQL Server"],
                estimated_extraction_time_minutes=0,
                warnings=warnings,
                errors=errors,
            )

    async def extract_data(
        self, resource: Dict[str, Any], analysis: DataPlaneAnalysis
    ) -> ExtractionResult:
        """Extract SQL Server data from source instance.

        Args:
            resource: Source VM resource dictionary
            analysis: Previous analysis result

        Returns:
            ExtractionResult with extracted SQL Server data

        Raises:
            ConnectionError: If cannot connect to SQL Server
            IOError: If cannot write extracted data
        """
        logger.info(f"Extracting SQL Server data from {resource.get('name')}")

        resource_id = resource.get("id", "unknown")
        extracted_data: List[ExtractedData] = []
        warnings: List[str] = []
        errors: List[str] = []
        items_extracted = 0
        items_failed = 0
        start_time = datetime.utcnow()

        # Get output directory
        output_dir = Path(self.get_config_value("output_dir", "./sql_extraction"))
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Extract server configuration
            if self._has_element(analysis, "server_configuration"):
                try:
                    server_data = await self._extract_server_config(resource, output_dir)
                    extracted_data.append(server_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract server config: {e}")
                    errors.append(f"Server config: {e}")
                    items_failed += 1

            # Extract databases
            if self._has_element(analysis, "databases"):
                try:
                    db_data = await self._extract_databases(resource, output_dir)
                    extracted_data.append(db_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract databases: {e}")
                    errors.append(f"Databases: {e}")
                    items_failed += 1

            # Extract schema objects
            if self._has_element(analysis, "schema_objects"):
                try:
                    schema_data = await self._extract_schema_objects(resource, output_dir)
                    extracted_data.append(schema_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract schema objects: {e}")
                    errors.append(f"Schema objects: {e}")
                    items_failed += 1

            # Extract security
            if self._has_element(analysis, "security"):
                try:
                    security_data = await self._extract_security(resource, output_dir)
                    extracted_data.append(security_data)
                    items_extracted += 1
                    warnings.append(
                        "Login passwords NOT extracted - must be set manually"
                    )
                except Exception as e:
                    logger.error(f"Failed to extract security: {e}")
                    errors.append(f"Security: {e}")
                    items_failed += 1

            # Extract SQL Agent jobs
            if self._has_element(analysis, "sql_agent"):
                try:
                    agent_data = await self._extract_agent_jobs(resource, output_dir)
                    extracted_data.append(agent_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract SQL Agent: {e}")
                    errors.append(f"SQL Agent: {e}")
                    items_failed += 1

            # Extract linked servers
            if self._has_element(analysis, "linked_servers"):
                try:
                    linked_data = await self._extract_linked_servers(resource, output_dir)
                    extracted_data.append(linked_data)
                    items_extracted += 1
                    warnings.append(
                        "Linked server credentials NOT extracted - must be reconfigured"
                    )
                except Exception as e:
                    logger.error(f"Failed to extract linked servers: {e}")
                    errors.append(f"Linked servers: {e}")
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
        """Generate T-SQL and PowerShell steps to replicate SQL Server to target.

        Args:
            extraction: Result from extract_data()

        Returns:
            List of ReplicationStep objects in execution order
        """
        logger.info("Generating SQL Server replication steps")

        steps: List[ReplicationStep] = []

        # Step 1: Prerequisites
        steps.append(
            ReplicationStep(
                step_id="prereq_sql_server",
                step_type=StepType.PREREQUISITE,
                description="Verify SQL Server installation",
                script_content=self._generate_prereq_check_script(),
                script_format=ExtractionFormat.POWERSHELL_DSC,
                depends_on=[],
                estimated_duration_minutes=5,
                is_critical=True,
                can_retry=True,
                max_retries=2,
            )
        )

        # Step 2: Configure server settings
        server_data = self._find_extracted_data(extraction, "server")
        if server_data:
            steps.append(
                ReplicationStep(
                    step_id="configure_server",
                    step_type=StepType.CONFIGURATION,
                    description="Apply server configuration settings",
                    script_content=self._generate_server_config_script(server_data),
                    script_format=ExtractionFormat.SQL_SCRIPT,
                    depends_on=["prereq_sql_server"],
                    estimated_duration_minutes=5,
                    is_critical=True,
                    can_retry=True,
                )
            )

        # Step 3: Create databases
        db_data = self._find_extracted_data(extraction, "database")
        if db_data:
            steps.append(
                ReplicationStep(
                    step_id="create_databases",
                    step_type=StepType.CONFIGURATION,
                    description="Create databases with properties",
                    script_content=self._generate_database_creation_script(db_data),
                    script_format=ExtractionFormat.SQL_SCRIPT,
                    depends_on=["configure_server"],
                    estimated_duration_minutes=10,
                    is_critical=True,
                    can_retry=True,
                )
            )

        # Step 4: Create schema objects
        schema_data = self._find_extracted_data(extraction, "schema")
        if schema_data:
            steps.append(
                ReplicationStep(
                    step_id="create_schema",
                    step_type=StepType.DATA_IMPORT,
                    description="Create tables, views, procedures, and functions",
                    script_content=self._generate_schema_creation_script(schema_data),
                    script_format=ExtractionFormat.SQL_SCRIPT,
                    depends_on=["create_databases"],
                    estimated_duration_minutes=20,
                    is_critical=True,
                    can_retry=True,
                )
            )

        # Step 5: Create logins and security
        security_data = self._find_extracted_data(extraction, "security")
        if security_data:
            steps.append(
                ReplicationStep(
                    step_id="create_security",
                    step_type=StepType.CONFIGURATION,
                    description="Create logins, users, and permissions (passwords must be set manually)",
                    script_content=self._generate_security_script(security_data),
                    script_format=ExtractionFormat.SQL_SCRIPT,
                    depends_on=["create_databases"],
                    estimated_duration_minutes=10,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 6: Create SQL Agent jobs
        agent_data = self._find_extracted_data(extraction, "agent")
        if agent_data:
            steps.append(
                ReplicationStep(
                    step_id="create_agent_jobs",
                    step_type=StepType.CONFIGURATION,
                    description="Create SQL Agent jobs, schedules, and alerts",
                    script_content=self._generate_agent_jobs_script(agent_data),
                    script_format=ExtractionFormat.SQL_SCRIPT,
                    depends_on=["configure_server"],
                    estimated_duration_minutes=10,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 7: Create linked servers
        linked_data = self._find_extracted_data(extraction, "linked")
        if linked_data:
            steps.append(
                ReplicationStep(
                    step_id="create_linked_servers",
                    step_type=StepType.CONFIGURATION,
                    description="Create linked servers (credentials must be set manually)",
                    script_content=self._generate_linked_servers_script(linked_data),
                    script_format=ExtractionFormat.SQL_SCRIPT,
                    depends_on=["configure_server"],
                    estimated_duration_minutes=5,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 8: Validation
        steps.append(
            ReplicationStep(
                step_id="validate_sql",
                step_type=StepType.VALIDATION,
                description="Validate SQL Server configuration and connectivity",
                script_content=self._generate_validation_script(),
                script_format=ExtractionFormat.SQL_SCRIPT,
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
        """Apply SQL Server replication steps to target instance.

        Args:
            steps: Replication steps to execute
            target_resource_id: Azure resource ID of target VM

        Returns:
            ReplicationResult with execution status
        """
        logger.info(f"Applying SQL Server replication to {target_resource_id}")

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
                        # Execute via SQL connection
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

    async def _check_sql_connectivity(self, resource: Dict[str, Any]) -> bool:
        """Check if SQL Server is accessible.

        Args:
            resource: Resource dictionary

        Returns:
            True if SQL Server is accessible
        """
        # In real implementation, would use pyodbc
        # For now, return True if not in strict mode
        return not self.get_config_value("strict_validation", False)

    async def _analyze_server_config(
        self, resource: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Analyze SQL Server configuration.

        Args:
            resource: Resource dictionary

        Returns:
            Server info dictionary or None
        """
        # Mock implementation - real version would query sys.dm_os_sys_info
        return {
            "version": "SQL Server 2019",
            "edition": "Standard Edition",
            "product_level": "RTM",
            "collation": "SQL_Latin1_General_CP1_CI_AS",
        }

    async def _count_databases(self, resource: Dict[str, Any]) -> int:
        """Count user databases.

        Args:
            resource: Resource dictionary

        Returns:
            Number of databases
        """
        # Mock implementation - real version would query sys.databases
        return 5

    async def _count_schema_objects(self, resource: Dict[str, Any]) -> int:
        """Count schema objects.

        Args:
            resource: Resource dictionary

        Returns:
            Number of schema objects
        """
        # Mock implementation - real version would query sys.objects
        return 150

    async def _count_logins(self, resource: Dict[str, Any]) -> int:
        """Count server logins.

        Args:
            resource: Resource dictionary

        Returns:
            Number of logins
        """
        # Mock implementation - real version would query sys.server_principals
        return 10

    async def _count_agent_jobs(self, resource: Dict[str, Any]) -> int:
        """Count SQL Agent jobs.

        Args:
            resource: Resource dictionary

        Returns:
            Number of jobs
        """
        # Mock implementation - real version would query msdb.dbo.sysjobs
        return 8

    async def _count_linked_servers(self, resource: Dict[str, Any]) -> int:
        """Count linked servers.

        Args:
            resource: Resource dictionary

        Returns:
            Number of linked servers
        """
        # Mock implementation - real version would query sys.servers
        return 2

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
        score = min(10, 4 + len(elements) // 2)

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
        """Extract server configuration.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with server config
        """
        # Mock implementation
        content = json.dumps(
            {
                "version": "SQL Server 2019",
                "edition": "Standard Edition",
                "configuration": {
                    "max_server_memory_mb": 8192,
                    "max_degree_of_parallelism": 4,
                    "cost_threshold_for_parallelism": 50,
                },
            },
            indent=2,
        )

        file_path = output_dir / "server_config.json"
        file_path.write_text(content)

        return ExtractedData(
            name="server_config",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_databases(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract database configurations.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with database info
        """
        # Mock implementation
        content = json.dumps(
            {
                "databases": [
                    {
                        "name": "AppDB",
                        "recovery_model": "FULL",
                        "compatibility_level": "150",
                        "collation": "SQL_Latin1_General_CP1_CI_AS",
                    },
                    {
                        "name": "ReportingDB",
                        "recovery_model": "SIMPLE",
                        "compatibility_level": "150",
                        "collation": "SQL_Latin1_General_CP1_CI_AS",
                    },
                ]
            },
            indent=2,
        )

        file_path = output_dir / "databases.json"
        file_path.write_text(content)

        return ExtractedData(
            name="databases",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_schema_objects(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract schema objects.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with schema DDL
        """
        # Mock implementation - would use sys.sql_modules, INFORMATION_SCHEMA
        content = """-- Database: AppDB
-- Schema Objects

-- Tables
CREATE TABLE dbo.Users (
    UserID INT PRIMARY KEY IDENTITY(1,1),
    Username NVARCHAR(50) NOT NULL,
    Email NVARCHAR(100) NOT NULL,
    CreatedDate DATETIME2 DEFAULT GETUTCDATE()
);

CREATE TABLE dbo.Orders (
    OrderID INT PRIMARY KEY IDENTITY(1,1),
    UserID INT NOT NULL,
    OrderDate DATETIME2 DEFAULT GETUTCDATE(),
    TotalAmount DECIMAL(18,2),
    FOREIGN KEY (UserID) REFERENCES dbo.Users(UserID)
);

-- Views
CREATE VIEW dbo.vw_UserOrders AS
SELECT u.Username, o.OrderID, o.OrderDate, o.TotalAmount
FROM dbo.Users u
INNER JOIN dbo.Orders o ON u.UserID = o.UserID;

-- Stored Procedures
CREATE PROCEDURE dbo.sp_GetUserOrders
    @UserID INT
AS
BEGIN
    SELECT * FROM dbo.Orders WHERE UserID = @UserID;
END;
"""

        file_path = output_dir / "schema_objects.sql"
        file_path.write_text(content)

        return ExtractedData(
            name="schema_objects",
            format=ExtractionFormat.SQL_SCRIPT,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_security(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract security configuration.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with security info (NO PASSWORDS)
        """
        # Mock implementation
        content = json.dumps(
            {
                "logins": [
                    {
                        "name": "AppUser",
                        "type": "SQL_LOGIN",
                        "default_database": "AppDB",
                        "note": "Password must be set manually",
                    },
                    {
                        "name": "ReportUser",
                        "type": "SQL_LOGIN",
                        "default_database": "ReportingDB",
                        "note": "Password must be set manually",
                    },
                ],
                "database_users": [
                    {
                        "database": "AppDB",
                        "name": "AppUser",
                        "roles": ["db_datareader", "db_datawriter"],
                    }
                ],
                "note": "Passwords and password hashes NOT included - must be set manually",
            },
            indent=2,
        )

        file_path = output_dir / "security.json"
        file_path.write_text(content)

        return ExtractedData(
            name="security",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_agent_jobs(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract SQL Agent jobs.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with agent jobs
        """
        # Mock implementation
        content = json.dumps(
            {
                "jobs": [
                    {
                        "name": "Daily Backup",
                        "enabled": True,
                        "description": "Full database backup",
                        "schedules": [
                            {
                                "name": "Daily at 2 AM",
                                "frequency": "DAILY",
                                "start_time": "020000",
                            }
                        ],
                        "steps": [
                            {
                                "step_name": "Backup AppDB",
                                "subsystem": "TSQL",
                                "command": "BACKUP DATABASE AppDB TO DISK = 'D:\\Backups\\AppDB.bak'",
                            }
                        ],
                    }
                ]
            },
            indent=2,
        )

        file_path = output_dir / "agent_jobs.json"
        file_path.write_text(content)

        return ExtractedData(
            name="agent_jobs",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_linked_servers(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract linked servers.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with linked servers
        """
        # Mock implementation
        content = json.dumps(
            {
                "linked_servers": [
                    {
                        "name": "REMOTE_SQL",
                        "product": "SQL Server",
                        "provider": "SQLNCLI",
                        "data_source": "remote-sql.example.com",
                        "note": "Credentials must be reconfigured",
                    }
                ],
                "note": "Linked server passwords NOT included - must be set manually",
            },
            indent=2,
        )

        file_path = output_dir / "linked_servers.json"
        file_path.write_text(content)

        return ExtractedData(
            name="linked_servers",
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
        """Generate PowerShell script to check SQL Server.

        Returns:
            PowerShell script content
        """
        return """# Check SQL Server installation
$sqlService = Get-Service -Name MSSQLSERVER -ErrorAction SilentlyContinue

if ($sqlService) {
    Write-Host "SQL Server service found: $($sqlService.Status)"
    if ($sqlService.Status -ne 'Running') {
        Start-Service -Name MSSQLSERVER
        Write-Host "Started SQL Server service"
    }
} else {
    Write-Error "SQL Server service not found"
    exit 1
}

# Verify SQL connectivity
try {
    $connection = New-Object System.Data.SqlClient.SqlConnection
    $connection.ConnectionString = "Server=localhost;Integrated Security=True;Connection Timeout=5"
    $connection.Open()
    Write-Host "SQL Server connectivity verified"
    $connection.Close()
} catch {
    Write-Error "Cannot connect to SQL Server: $_"
    exit 1
}
"""

    def _generate_server_config_script(self, server_data: ExtractedData) -> str:
        """Generate script to configure server settings.

        Args:
            server_data: Server configuration data

        Returns:
            T-SQL script
        """
        return """-- Configure SQL Server settings
-- sp_configure options

EXEC sp_configure 'show advanced options', 1;
RECONFIGURE;

-- Memory configuration
EXEC sp_configure 'max server memory (MB)', 8192;
RECONFIGURE;

-- Parallelism settings
EXEC sp_configure 'max degree of parallelism', 4;
EXEC sp_configure 'cost threshold for parallelism', 50;
RECONFIGURE;

-- Database Mail (if needed)
-- EXEC msdb.dbo.sysmail_configure_sp @parameter_name = 'AccountRetryDelay', @parameter_value = '60', @parameter_value_type = 'number';

PRINT 'Server configuration completed';
"""

    def _generate_database_creation_script(self, db_data: ExtractedData) -> str:
        """Generate script to create databases.

        Args:
            db_data: Database configuration data

        Returns:
            T-SQL script
        """
        return """-- Create databases with properties

-- AppDB
IF NOT EXISTS (SELECT 1 FROM sys.databases WHERE name = 'AppDB')
BEGIN
    CREATE DATABASE AppDB
    ON PRIMARY
    (
        NAME = AppDB_Data,
        FILENAME = 'D:\\SQLData\\AppDB.mdf',
        SIZE = 100MB,
        FILEGROWTH = 10MB
    )
    LOG ON
    (
        NAME = AppDB_Log,
        FILENAME = 'D:\\SQLLogs\\AppDB_log.ldf',
        SIZE = 50MB,
        FILEGROWTH = 10MB
    );

    ALTER DATABASE AppDB SET RECOVERY FULL;
    ALTER DATABASE AppDB COLLATE SQL_Latin1_General_CP1_CI_AS;
    PRINT 'Created database: AppDB';
END
ELSE
BEGIN
    PRINT 'Database AppDB already exists';
END
GO

-- ReportingDB
IF NOT EXISTS (SELECT 1 FROM sys.databases WHERE name = 'ReportingDB')
BEGIN
    CREATE DATABASE ReportingDB
    ON PRIMARY
    (
        NAME = ReportingDB_Data,
        FILENAME = 'D:\\SQLData\\ReportingDB.mdf',
        SIZE = 100MB,
        FILEGROWTH = 10MB
    )
    LOG ON
    (
        NAME = ReportingDB_Log,
        FILENAME = 'D:\\SQLLogs\\ReportingDB_log.ldf',
        SIZE = 50MB,
        FILEGROWTH = 10MB
    );

    ALTER DATABASE ReportingDB SET RECOVERY SIMPLE;
    PRINT 'Created database: ReportingDB';
END
ELSE
BEGIN
    PRINT 'Database ReportingDB already exists';
END
GO

PRINT 'Database creation completed';
"""

    def _generate_schema_creation_script(self, schema_data: ExtractedData) -> str:
        """Generate script to create schema objects.

        Args:
            schema_data: Schema DDL data

        Returns:
            T-SQL script with schema objects
        """
        # In real implementation, would read from schema_data.content
        # For now, return the schema content directly
        if isinstance(schema_data.content, str):
            return schema_data.content
        return "-- Schema objects script would be generated here"

    def _generate_security_script(self, security_data: ExtractedData) -> str:
        """Generate script to create security principals.

        Args:
            security_data: Security configuration data

        Returns:
            T-SQL script
        """
        return """-- Create SQL Server logins and users
-- WARNING: Passwords must be set manually!

USE master;
GO

-- Create logins
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'AppUser')
BEGIN
    CREATE LOGIN AppUser WITH PASSWORD = 'CHANGE_ME_P@ssw0rd123!';
    PRINT 'Created login: AppUser - CHANGE PASSWORD!';
END

IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'ReportUser')
BEGIN
    CREATE LOGIN ReportUser WITH PASSWORD = 'CHANGE_ME_P@ssw0rd123!';
    PRINT 'Created login: ReportUser - CHANGE PASSWORD!';
END
GO

-- Create database users and assign roles
USE AppDB;
GO

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'AppUser')
BEGIN
    CREATE USER AppUser FOR LOGIN AppUser;
    ALTER ROLE db_datareader ADD MEMBER AppUser;
    ALTER ROLE db_datawriter ADD MEMBER AppUser;
    PRINT 'Created user AppUser in AppDB';
END
GO

USE ReportingDB;
GO

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'ReportUser')
BEGIN
    CREATE USER ReportUser FOR LOGIN ReportUser;
    ALTER ROLE db_datareader ADD MEMBER ReportUser;
    PRINT 'Created user ReportUser in ReportingDB';
END
GO

PRINT 'Security configuration completed';
PRINT 'IMPORTANT: Change all login passwords!';
"""

    def _generate_agent_jobs_script(self, agent_data: ExtractedData) -> str:
        """Generate script to create SQL Agent jobs.

        Args:
            agent_data: Agent jobs data

        Returns:
            T-SQL script
        """
        return """-- Create SQL Agent jobs and schedules
USE msdb;
GO

-- Create job: Daily Backup
DECLARE @jobId BINARY(16);

IF NOT EXISTS (SELECT 1 FROM msdb.dbo.sysjobs WHERE name = 'Daily Backup')
BEGIN
    EXEC msdb.dbo.sp_add_job
        @job_name = 'Daily Backup',
        @enabled = 1,
        @description = 'Full database backup',
        @job_id = @jobId OUTPUT;

    -- Add job step
    EXEC msdb.dbo.sp_add_jobstep
        @job_id = @jobId,
        @step_name = 'Backup AppDB',
        @subsystem = 'TSQL',
        @command = 'BACKUP DATABASE AppDB TO DISK = ''D:\\Backups\\AppDB.bak'' WITH INIT',
        @retry_attempts = 3,
        @retry_interval = 5;

    -- Add schedule
    EXEC msdb.dbo.sp_add_schedule
        @schedule_name = 'Daily at 2 AM',
        @freq_type = 4,  -- Daily
        @freq_interval = 1,
        @active_start_time = 020000;

    -- Attach schedule to job
    EXEC msdb.dbo.sp_attach_schedule
        @job_id = @jobId,
        @schedule_name = 'Daily at 2 AM';

    -- Add job to local server
    EXEC msdb.dbo.sp_add_jobserver
        @job_id = @jobId,
        @server_name = N'(local)';

    PRINT 'Created job: Daily Backup';
END
ELSE
BEGIN
    PRINT 'Job Daily Backup already exists';
END
GO

PRINT 'SQL Agent jobs created';
"""

    def _generate_linked_servers_script(self, linked_data: ExtractedData) -> str:
        """Generate script to create linked servers.

        Args:
            linked_data: Linked servers data

        Returns:
            T-SQL script
        """
        return """-- Create linked servers
-- WARNING: Credentials must be reconfigured!

USE master;
GO

-- Create linked server
IF NOT EXISTS (SELECT 1 FROM sys.servers WHERE name = 'REMOTE_SQL')
BEGIN
    EXEC master.dbo.sp_addlinkedserver
        @server = N'REMOTE_SQL',
        @srvproduct = N'SQL Server',
        @provider = N'SQLNCLI',
        @datasrc = N'remote-sql.example.com';

    -- Configure linked server login (placeholder credentials)
    EXEC master.dbo.sp_addlinkedsrvlogin
        @rmtsrvname = N'REMOTE_SQL',
        @useself = N'False',
        @locallogin = NULL,
        @rmtuser = N'CHANGE_ME_remote_user',
        @rmtpassword = N'CHANGE_ME_password';

    PRINT 'Created linked server: REMOTE_SQL - RECONFIGURE CREDENTIALS!';
END
ELSE
BEGIN
    PRINT 'Linked server REMOTE_SQL already exists';
END
GO

PRINT 'Linked servers configured';
PRINT 'IMPORTANT: Update linked server credentials!';
"""

    def _generate_validation_script(self) -> str:
        """Generate validation script.

        Returns:
            T-SQL script
        """
        return """-- Validate SQL Server configuration
SET NOCOUNT ON;

PRINT 'Running SQL Server validation...';

-- Check SQL Server version
DECLARE @version NVARCHAR(128);
SELECT @version = @@VERSION;
PRINT 'SQL Server Version: ' + @version;

-- Check databases
PRINT '';
PRINT 'Databases:';
SELECT name, state_desc, recovery_model_desc
FROM sys.databases
WHERE database_id > 4  -- User databases only
ORDER BY name;

-- Check logins
PRINT '';
PRINT 'Logins:';
SELECT name, type_desc, create_date
FROM sys.server_principals
WHERE type IN ('S', 'U')  -- SQL and Windows logins
  AND name NOT LIKE '##%'  -- Exclude system accounts
ORDER BY name;

-- Check SQL Agent jobs
PRINT '';
PRINT 'SQL Agent Jobs:';
SELECT name, enabled, date_created
FROM msdb.dbo.sysjobs
ORDER BY name;

-- Check linked servers
PRINT '';
PRINT 'Linked Servers:';
SELECT name, provider, data_source
FROM sys.servers
WHERE is_linked = 1
ORDER BY name;

PRINT '';
PRINT 'Validation completed';
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
        """Execute a replication step on target SQL Server.

        Args:
            step: Step to execute
            target_resource_id: Target VM resource ID

        Returns:
            StepResult with execution status
        """
        # Mock implementation - real version would use pyodbc
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
