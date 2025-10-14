"""Tests for SQL Server replication plugin."""

import json
from pathlib import Path

import pytest

from src.iac.plugins.models import (
    AnalysisStatus,
    DataPlaneAnalysis,
    DataPlaneElement,
    ExtractedData,
    ExtractionFormat,
    ExtractionResult,
    ReplicationResult,
    ReplicationStatus,
    ReplicationStep,
    StepResult,
    StepType,
)
from src.iac.plugins.sql_server_plugin import SQLServerReplicationPlugin


@pytest.fixture
def plugin():
    """Create plugin instance for testing."""
    return SQLServerReplicationPlugin(
        config={"output_dir": "/tmp/sql_test", "dry_run": True}
    )


@pytest.fixture
def sql_resource():
    """Create mock SQL Server VM resource."""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-sql",
        "name": "test-sql",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "tags": {"role": "sql-server"},
        "properties": {
            "osProfile": {"computerName": "TEST-SQL-001"},
            "hardwareProfile": {"vmSize": "Standard_D4s_v3"},
        },
    }


@pytest.fixture
def non_sql_resource():
    """Create mock non-SQL resource."""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-web",
        "name": "test-web",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "tags": {"role": "webserver"},
        "properties": {"osProfile": {"computerName": "TEST-WEB-001"}},
    }


@pytest.fixture
def mock_analysis():
    """Create mock analysis result."""
    return DataPlaneAnalysis(
        resource_id="/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-sql",
        resource_type="Microsoft.Compute/virtualMachines",
        status=AnalysisStatus.SUCCESS,
        elements=[
            DataPlaneElement(
                name="server_configuration",
                element_type="SQL Server Config",
                description="SQL Server 2019",
                complexity="MEDIUM",
                estimated_size_mb=0.1,
                dependencies=[],
            ),
            DataPlaneElement(
                name="databases",
                element_type="Databases",
                description="5 databases",
                complexity="HIGH",
                estimated_size_mb=50.0,
                dependencies=["server_configuration"],
            ),
            DataPlaneElement(
                name="schema_objects",
                element_type="Schema",
                description="150 schema objects",
                complexity="VERY_HIGH",
                estimated_size_mb=7.5,
                dependencies=["databases"],
            ),
            DataPlaneElement(
                name="security",
                element_type="Security",
                description="10 logins and security principals (passwords excluded)",
                complexity="HIGH",
                estimated_size_mb=0.2,
                dependencies=["server_configuration"],
            ),
            DataPlaneElement(
                name="linked_servers",
                element_type="Linked Servers",
                description="2 linked servers",
                complexity="MEDIUM",
                estimated_size_mb=0.05,
                dependencies=["server_configuration"],
            ),
        ],
        total_estimated_size_mb=57.85,
        complexity_score=8,
        requires_credentials=True,
        requires_network_access=True,
        connection_methods=["SQL Server", "TCP/IP"],
        estimated_extraction_time_minutes=50,
    )


class TestPluginMetadata:
    """Test plugin metadata."""

    def test_metadata_structure(self, plugin):
        """Test that metadata has correct structure."""
        metadata = plugin.metadata

        assert metadata.name == "sql_server"
        assert metadata.version == "1.0.0"
        assert isinstance(metadata.description, str)
        assert "Microsoft.Compute/virtualMachines" in metadata.resource_types
        assert metadata.requires_credentials is True
        assert metadata.requires_network_access is True
        assert metadata.complexity == "VERY_HIGH"
        assert metadata.estimated_effort_weeks > 0

    def test_supported_formats(self, plugin):
        """Test that plugin supports expected formats."""
        metadata = plugin.metadata

        assert ExtractionFormat.SQL_SCRIPT in metadata.supported_formats
        assert ExtractionFormat.JSON in metadata.supported_formats
        assert ExtractionFormat.CSV in metadata.supported_formats
        assert ExtractionFormat.POWERSHELL_DSC in metadata.supported_formats


class TestResourceDetection:
    """Test resource type detection."""

    def test_can_handle_sql_resource_by_tag(self, plugin, sql_resource):
        """Test detection of SQL Server by tag."""
        assert plugin.can_handle(sql_resource) is True

    def test_can_handle_sql_resource_by_name(self, plugin):
        """Test detection of SQL Server by name pattern."""
        resource = {
            "id": "test-id",
            "name": "atevet12sql001",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {"osProfile": {"computerName": "SQL-SERVER"}},
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_database_name(self, plugin):
        """Test detection by database keyword."""
        resource = {
            "id": "test-id",
            "name": "prod-database-01",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {"osProfile": {"computerName": "DB-SERVER"}},
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_sql_in_tag_value(self, plugin):
        """Test detection by SQL in tag values."""
        resource = {
            "id": "test-id",
            "name": "server01",
            "type": "Microsoft.Compute/virtualMachines",
            "tags": {"application": "SQL Server 2019"},
            "properties": {"osProfile": {"computerName": "SERVER01"}},
        }
        assert plugin.can_handle(resource) is True

    def test_cannot_handle_non_sql_resource(self, plugin, non_sql_resource):
        """Test rejection of non-SQL resource."""
        assert plugin.can_handle(non_sql_resource) is False

    def test_cannot_handle_wrong_resource_type(self, plugin):
        """Test rejection of wrong resource type."""
        resource = {
            "id": "test-id",
            "name": "test-sql",
            "type": "Microsoft.Storage/storageAccounts",
            "tags": {"role": "sql-server"},
        }
        assert plugin.can_handle(resource) is False


class TestAnalyzeSource:
    """Test source analysis functionality."""

    @pytest.mark.asyncio
    async def test_analyze_success(self, plugin, sql_resource):
        """Test successful SQL Server analysis."""
        analysis = await plugin.analyze_source(sql_resource)

        assert analysis.status == AnalysisStatus.SUCCESS
        assert len(analysis.elements) > 0
        assert analysis.requires_credentials is True
        assert analysis.requires_network_access is True
        assert "SQL Server" in analysis.connection_methods
        assert analysis.complexity_score >= 1

    @pytest.mark.asyncio
    async def test_analyze_discovers_server_config(self, plugin, sql_resource):
        """Test that analysis discovers server configuration."""
        analysis = await plugin.analyze_source(sql_resource)

        server_element = next(
            (e for e in analysis.elements if e.name == "server_configuration"), None
        )
        assert server_element is not None
        assert server_element.element_type == "SQL Server Config"
        assert "SQL Server" in server_element.description

    @pytest.mark.asyncio
    async def test_analyze_discovers_databases(self, plugin, sql_resource):
        """Test that analysis discovers databases."""
        analysis = await plugin.analyze_source(sql_resource)

        db_element = next(
            (e for e in analysis.elements if e.name == "databases"), None
        )
        assert db_element is not None
        assert "database" in db_element.description.lower()

    @pytest.mark.asyncio
    async def test_analyze_discovers_schema(self, plugin, sql_resource):
        """Test that analysis discovers schema objects."""
        analysis = await plugin.analyze_source(sql_resource)

        schema_element = next(
            (e for e in analysis.elements if e.name == "schema_objects"), None
        )
        assert schema_element is not None
        assert schema_element.complexity in ["HIGH", "VERY_HIGH"]

    @pytest.mark.asyncio
    async def test_analyze_discovers_security(self, plugin, sql_resource):
        """Test that analysis discovers security."""
        analysis = await plugin.analyze_source(sql_resource)

        security_element = next(
            (e for e in analysis.elements if e.name == "security"), None
        )
        assert security_element is not None
        assert "password" in security_element.description.lower()

    @pytest.mark.asyncio
    async def test_analyze_discovers_agent_jobs(self, plugin, sql_resource):
        """Test that analysis discovers SQL Agent jobs."""
        analysis = await plugin.analyze_source(sql_resource)

        agent_element = next(
            (e for e in analysis.elements if e.name == "sql_agent"), None
        )
        assert agent_element is not None
        assert "job" in agent_element.description.lower()

    @pytest.mark.asyncio
    async def test_analyze_discovers_linked_servers(self, plugin, sql_resource):
        """Test that analysis discovers linked servers."""
        analysis = await plugin.analyze_source(sql_resource)

        linked_element = next(
            (e for e in analysis.elements if e.name == "linked_servers"), None
        )
        assert linked_element is not None
        assert "linked" in linked_element.description.lower()

    @pytest.mark.asyncio
    async def test_analyze_calculates_size(self, plugin, sql_resource):
        """Test that analysis calculates total size."""
        analysis = await plugin.analyze_source(sql_resource)

        assert analysis.total_estimated_size_mb > 0
        assert analysis.total_estimated_size_mb == sum(
            e.estimated_size_mb for e in analysis.elements
        )

    @pytest.mark.asyncio
    async def test_analyze_estimates_time(self, plugin, sql_resource):
        """Test that analysis estimates extraction time."""
        analysis = await plugin.analyze_source(sql_resource)

        assert analysis.estimated_extraction_time_minutes > 0


class TestExtractData:
    """Test data extraction functionality."""

    @pytest.mark.asyncio
    async def test_extract_success(
        self, plugin, sql_resource, mock_analysis, tmp_path
    ):
        """Test successful data extraction."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(sql_resource, mock_analysis)

        assert extraction.status in [
            AnalysisStatus.SUCCESS,
            AnalysisStatus.PARTIAL,
        ]
        assert len(extraction.extracted_data) > 0
        assert extraction.items_extracted > 0
        assert extraction.extraction_duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_extract_creates_files(
        self, plugin, sql_resource, mock_analysis, tmp_path
    ):
        """Test that extraction creates output files."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(sql_resource, mock_analysis)

        # Check that at least one file was created
        for data in extraction.extracted_data:
            if data.file_path:
                assert Path(data.file_path).exists()

    @pytest.mark.asyncio
    async def test_extract_server_config(
        self, plugin, sql_resource, mock_analysis, tmp_path
    ):
        """Test extraction of server configuration."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(sql_resource, mock_analysis)

        server_data = next(
            (d for d in extraction.extracted_data if "server" in d.name.lower()), None
        )
        assert server_data is not None
        assert server_data.format == ExtractionFormat.JSON

        # Verify content is valid JSON
        content = json.loads(server_data.content)
        assert "version" in content

    @pytest.mark.asyncio
    async def test_extract_databases(
        self, plugin, sql_resource, mock_analysis, tmp_path
    ):
        """Test extraction of database configurations."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(sql_resource, mock_analysis)

        db_data = next(
            (d for d in extraction.extracted_data if "database" in d.name.lower()),
            None,
        )
        assert db_data is not None
        assert db_data.format == ExtractionFormat.JSON

    @pytest.mark.asyncio
    async def test_extract_schema(
        self, plugin, sql_resource, mock_analysis, tmp_path
    ):
        """Test extraction of schema objects."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(sql_resource, mock_analysis)

        schema_data = next(
            (d for d in extraction.extracted_data if "schema" in d.name.lower()), None
        )
        assert schema_data is not None
        assert schema_data.format == ExtractionFormat.SQL_SCRIPT

    @pytest.mark.asyncio
    async def test_extract_includes_checksum(
        self, plugin, sql_resource, mock_analysis, tmp_path
    ):
        """Test that extracted data includes checksums."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(sql_resource, mock_analysis)

        for data in extraction.extracted_data:
            assert data.checksum is not None
            assert len(data.checksum) == 64  # SHA256 hex length

    @pytest.mark.asyncio
    async def test_extract_warns_about_passwords(
        self, plugin, sql_resource, mock_analysis, tmp_path
    ):
        """Test that extraction warns about missing passwords."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(sql_resource, mock_analysis)

        # Should have warning about passwords
        password_warning = any("password" in w.lower() for w in extraction.warnings)
        assert password_warning is True

    @pytest.mark.asyncio
    async def test_extract_warns_about_credentials(
        self, plugin, sql_resource, mock_analysis, tmp_path
    ):
        """Test that extraction warns about linked server credentials."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(sql_resource, mock_analysis)

        # Should have warning about credentials
        credential_warning = any(
            "credential" in w.lower() or "linked" in w.lower()
            for w in extraction.warnings
        )
        assert credential_warning is True


class TestGenerateReplicationSteps:
    """Test replication step generation."""

    @pytest.mark.asyncio
    async def test_generate_steps_success(self, plugin, tmp_path):
        """Test successful step generation."""
        extraction = ExtractionResult(
            resource_id="test-id",
            status=AnalysisStatus.SUCCESS,
            extracted_data=[
                ExtractedData(
                    name="server_config",
                    format=ExtractionFormat.JSON,
                    content='{"version": "SQL Server 2019"}',
                    size_bytes=100,
                )
            ],
            total_size_mb=0.1,
            extraction_duration_seconds=5.0,
            items_extracted=1,
            items_failed=0,
        )

        steps = await plugin.generate_replication_steps(extraction)

        assert len(steps) > 0
        assert all(isinstance(s, ReplicationStep) for s in steps)

    @pytest.mark.asyncio
    async def test_steps_include_prerequisites(self, plugin, tmp_path):
        """Test that steps include prerequisite checks."""
        extraction = ExtractionResult(
            resource_id="test-id",
            status=AnalysisStatus.SUCCESS,
            extracted_data=[],
            total_size_mb=0,
            extraction_duration_seconds=1.0,
            items_extracted=0,
            items_failed=0,
        )

        steps = await plugin.generate_replication_steps(extraction)

        prereq_step = next(
            (s for s in steps if s.step_type == StepType.PREREQUISITE), None
        )
        assert prereq_step is not None
        assert "sql" in prereq_step.description.lower() or "server" in prereq_step.description.lower()

    @pytest.mark.asyncio
    async def test_steps_have_dependencies(self, plugin, tmp_path):
        """Test that steps have proper dependency ordering."""
        extraction = ExtractionResult(
            resource_id="test-id",
            status=AnalysisStatus.SUCCESS,
            extracted_data=[
                ExtractedData(
                    name="server_config",
                    format=ExtractionFormat.JSON,
                    content='{"version": "SQL Server 2019"}',
                    size_bytes=100,
                ),
                ExtractedData(
                    name="databases",
                    format=ExtractionFormat.JSON,
                    content='{"databases": []}',
                    size_bytes=100,
                ),
            ],
            total_size_mb=0.2,
            extraction_duration_seconds=5.0,
            items_extracted=2,
            items_failed=0,
        )

        steps = await plugin.generate_replication_steps(extraction)

        # Check that later steps depend on earlier ones
        step_ids = {s.step_id for s in steps}
        for step in steps:
            for dep in step.depends_on:
                assert dep in step_ids

    @pytest.mark.asyncio
    async def test_steps_include_validation(self, plugin, tmp_path):
        """Test that steps include validation."""
        extraction = ExtractionResult(
            resource_id="test-id",
            status=AnalysisStatus.SUCCESS,
            extracted_data=[],
            total_size_mb=0,
            extraction_duration_seconds=1.0,
            items_extracted=0,
            items_failed=0,
        )

        steps = await plugin.generate_replication_steps(extraction)

        validation_step = next(
            (s for s in steps if s.step_type == StepType.VALIDATION), None
        )
        assert validation_step is not None

    @pytest.mark.asyncio
    async def test_step_scripts_are_sql(self, plugin, tmp_path):
        """Test that generated scripts are T-SQL or PowerShell."""
        extraction = ExtractionResult(
            resource_id="test-id",
            status=AnalysisStatus.SUCCESS,
            extracted_data=[
                ExtractedData(
                    name="databases",
                    format=ExtractionFormat.JSON,
                    content='{"databases": []}',
                    size_bytes=100,
                )
            ],
            total_size_mb=0.1,
            extraction_duration_seconds=1.0,
            items_extracted=1,
            items_failed=0,
        )

        steps = await plugin.generate_replication_steps(extraction)

        for step in steps:
            assert step.script_format in [
                ExtractionFormat.SQL_SCRIPT,
                ExtractionFormat.POWERSHELL_DSC,
            ]
            assert len(step.script_content) > 0

    @pytest.mark.asyncio
    async def test_database_creation_step(self, plugin, tmp_path):
        """Test database creation step generation."""
        extraction = ExtractionResult(
            resource_id="test-id",
            status=AnalysisStatus.SUCCESS,
            extracted_data=[
                ExtractedData(
                    name="databases",
                    format=ExtractionFormat.JSON,
                    content='{"databases": [{"name": "TestDB"}]}',
                    size_bytes=100,
                )
            ],
            total_size_mb=0.1,
            extraction_duration_seconds=1.0,
            items_extracted=1,
            items_failed=0,
        )

        steps = await plugin.generate_replication_steps(extraction)

        db_step = next(
            (s for s in steps if "database" in s.step_id.lower()), None
        )
        assert db_step is not None
        assert db_step.script_format == ExtractionFormat.SQL_SCRIPT

    @pytest.mark.asyncio
    async def test_schema_creation_step(self, plugin, tmp_path):
        """Test schema creation step generation."""
        extraction = ExtractionResult(
            resource_id="test-id",
            status=AnalysisStatus.SUCCESS,
            extracted_data=[
                ExtractedData(
                    name="schema_objects",
                    format=ExtractionFormat.SQL_SCRIPT,
                    content="CREATE TABLE test (id INT);",
                    size_bytes=100,
                )
            ],
            total_size_mb=0.1,
            extraction_duration_seconds=1.0,
            items_extracted=1,
            items_failed=0,
        )

        steps = await plugin.generate_replication_steps(extraction)

        schema_step = next(
            (s for s in steps if "schema" in s.step_id.lower()), None
        )
        assert schema_step is not None
        assert schema_step.script_format == ExtractionFormat.SQL_SCRIPT

    @pytest.mark.asyncio
    async def test_security_step_warns_passwords(self, plugin, tmp_path):
        """Test security step includes password warnings."""
        extraction = ExtractionResult(
            resource_id="test-id",
            status=AnalysisStatus.SUCCESS,
            extracted_data=[
                ExtractedData(
                    name="security",
                    format=ExtractionFormat.JSON,
                    content='{"logins": []}',
                    size_bytes=100,
                )
            ],
            total_size_mb=0.1,
            extraction_duration_seconds=1.0,
            items_extracted=1,
            items_failed=0,
        )

        steps = await plugin.generate_replication_steps(extraction)

        security_step = next(
            (s for s in steps if "security" in s.step_id.lower()), None
        )
        assert security_step is not None
        assert "password" in security_step.description.lower()


class TestApplyToTarget:
    """Test application to target resource."""

    @pytest.mark.asyncio
    async def test_apply_dry_run(self, plugin):
        """Test dry run mode."""
        plugin.config["dry_run"] = True

        steps = [
            ReplicationStep(
                step_id="test_step",
                step_type=StepType.CONFIGURATION,
                description="Test step",
                script_content="SELECT 1",
                script_format=ExtractionFormat.SQL_SCRIPT,
            )
        ]

        result = await plugin.apply_to_target(steps, "test-target-id")

        assert result.status in [
            ReplicationStatus.SUCCESS,
            ReplicationStatus.PARTIAL_SUCCESS,
        ]
        assert "dry run" in " ".join(result.warnings).lower()
        assert len(result.steps_executed) == len(steps)

    @pytest.mark.asyncio
    async def test_apply_tracks_step_results(self, plugin):
        """Test that application tracks step results."""
        plugin.config["dry_run"] = True

        steps = [
            ReplicationStep(
                step_id="step1",
                step_type=StepType.PREREQUISITE,
                description="Step 1",
                script_content="SELECT 1",
                script_format=ExtractionFormat.SQL_SCRIPT,
            ),
            ReplicationStep(
                step_id="step2",
                step_type=StepType.CONFIGURATION,
                description="Step 2",
                script_content="SELECT 2",
                script_format=ExtractionFormat.SQL_SCRIPT,
            ),
        ]

        result = await plugin.apply_to_target(steps, "test-target-id")

        assert len(result.steps_executed) == 2
        assert result.steps_executed[0].step_id == "step1"
        assert result.steps_executed[1].step_id == "step2"

    @pytest.mark.asyncio
    async def test_apply_respects_dependencies(self, plugin):
        """Test that application respects step dependencies."""
        plugin.config["dry_run"] = True

        steps = [
            ReplicationStep(
                step_id="step1",
                step_type=StepType.PREREQUISITE,
                description="Step 1",
                script_content="SELECT 1",
                script_format=ExtractionFormat.SQL_SCRIPT,
            ),
            ReplicationStep(
                step_id="step2",
                step_type=StepType.CONFIGURATION,
                description="Step 2",
                script_content="SELECT 2",
                script_format=ExtractionFormat.SQL_SCRIPT,
                depends_on=["step1"],
            ),
        ]

        result = await plugin.apply_to_target(steps, "test-target-id")

        # Both steps should execute since step1 succeeds
        assert result.steps_succeeded >= 1

    @pytest.mark.asyncio
    async def test_apply_calculates_fidelity(self, plugin):
        """Test that application calculates fidelity score."""
        plugin.config["dry_run"] = True

        steps = [
            ReplicationStep(
                step_id="test_step",
                step_type=StepType.CONFIGURATION,
                description="Test step",
                script_content="SELECT 1",
                script_format=ExtractionFormat.SQL_SCRIPT,
            )
        ]

        result = await plugin.apply_to_target(steps, "test-target-id")

        assert 0.0 <= result.fidelity_score <= 1.0

    @pytest.mark.asyncio
    async def test_apply_reports_duration(self, plugin):
        """Test that application reports duration."""
        plugin.config["dry_run"] = True

        steps = [
            ReplicationStep(
                step_id="test_step",
                step_type=StepType.CONFIGURATION,
                description="Test step",
                script_content="SELECT 1",
                script_format=ExtractionFormat.SQL_SCRIPT,
            )
        ]

        result = await plugin.apply_to_target(steps, "test-target-id")

        assert result.total_duration_seconds > 0


class TestHelperMethods:
    """Test helper methods."""

    def test_calculate_complexity_score_empty(self, plugin):
        """Test complexity score calculation with no elements."""
        score = plugin._calculate_complexity_score([])
        assert score == 1

    def test_calculate_complexity_score_with_elements(self, plugin):
        """Test complexity score calculation with elements."""
        elements = [
            DataPlaneElement(
                name="elem1",
                element_type="type1",
                description="desc1",
                complexity="LOW",
                estimated_size_mb=1.0,
            ),
            DataPlaneElement(
                name="elem2",
                element_type="type2",
                description="desc2",
                complexity="VERY_HIGH",
                estimated_size_mb=2.0,
            ),
        ]

        score = plugin._calculate_complexity_score(elements)
        assert 1 <= score <= 10

    def test_calculate_fidelity_all_success(self, plugin):
        """Test fidelity calculation with all steps successful."""
        fidelity = plugin._calculate_fidelity_score(
            succeeded=5, failed=0, skipped=0, total=5
        )
        assert fidelity == 1.0

    def test_calculate_fidelity_partial_success(self, plugin):
        """Test fidelity calculation with partial success."""
        fidelity = plugin._calculate_fidelity_score(
            succeeded=3, failed=1, skipped=1, total=5
        )
        assert 0.0 < fidelity < 1.0

    def test_calculate_fidelity_all_failed(self, plugin):
        """Test fidelity calculation with all steps failed."""
        fidelity = plugin._calculate_fidelity_score(
            succeeded=0, failed=5, skipped=0, total=5
        )
        assert fidelity == 0.0

    def test_dependencies_met_no_deps(self, plugin):
        """Test dependency checking with no dependencies."""
        step = ReplicationStep(
            step_id="test",
            step_type=StepType.CONFIGURATION,
            description="test",
            script_content="SELECT 1",
            script_format=ExtractionFormat.SQL_SCRIPT,
            depends_on=[],
        )

        assert plugin._dependencies_met(step, []) is True

    def test_dependencies_met_success(self, plugin):
        """Test dependency checking with met dependencies."""
        step = ReplicationStep(
            step_id="test",
            step_type=StepType.CONFIGURATION,
            description="test",
            script_content="SELECT 1",
            script_format=ExtractionFormat.SQL_SCRIPT,
            depends_on=["dep1"],
        )

        results = [
            StepResult(
                step_id="dep1",
                status=ReplicationStatus.SUCCESS,
                duration_seconds=1.0,
            )
        ]

        assert plugin._dependencies_met(step, results) is True

    def test_dependencies_not_met(self, plugin):
        """Test dependency checking with unmet dependencies."""
        step = ReplicationStep(
            step_id="test",
            step_type=StepType.CONFIGURATION,
            description="test",
            script_content="SELECT 1",
            script_format=ExtractionFormat.SQL_SCRIPT,
            depends_on=["dep1"],
        )

        results = [
            StepResult(
                step_id="dep1",
                status=ReplicationStatus.FAILED,
                duration_seconds=1.0,
            )
        ]

        assert plugin._dependencies_met(step, results) is False

    def test_find_extracted_data_found(self, plugin):
        """Test finding extracted data by pattern."""
        extraction = ExtractionResult(
            resource_id="test-id",
            status=AnalysisStatus.SUCCESS,
            extracted_data=[
                ExtractedData(
                    name="server_config",
                    format=ExtractionFormat.JSON,
                    content="{}",
                    size_bytes=2,
                ),
                ExtractedData(
                    name="databases",
                    format=ExtractionFormat.JSON,
                    content="{}",
                    size_bytes=2,
                ),
            ],
            total_size_mb=0.0,
            extraction_duration_seconds=1.0,
            items_extracted=2,
            items_failed=0,
        )

        result = plugin._find_extracted_data(extraction, "server")
        assert result is not None
        assert result.name == "server_config"

    def test_find_extracted_data_not_found(self, plugin):
        """Test finding extracted data when not present."""
        extraction = ExtractionResult(
            resource_id="test-id",
            status=AnalysisStatus.SUCCESS,
            extracted_data=[],
            total_size_mb=0.0,
            extraction_duration_seconds=1.0,
            items_extracted=0,
            items_failed=0,
        )

        result = plugin._find_extracted_data(extraction, "nonexistent")
        assert result is None


class TestConfigurationHandling:
    """Test configuration handling."""

    def test_plugin_accepts_config(self):
        """Test that plugin accepts configuration."""
        config = {"output_dir": "/custom/path", "dry_run": True}
        plugin = SQLServerReplicationPlugin(config=config)

        assert plugin.get_config_value("output_dir") == "/custom/path"
        assert plugin.get_config_value("dry_run") is True

    def test_plugin_default_config(self):
        """Test plugin with default configuration."""
        plugin = SQLServerReplicationPlugin()

        assert plugin.get_config_value("nonexistent", "default") == "default"

    def test_get_config_value_with_default(self, plugin):
        """Test getting config value with default."""
        value = plugin.get_config_value("nonexistent_key", "default_value")
        assert value == "default_value"


class TestScriptGeneration:
    """Test script generation methods."""

    def test_generate_prereq_script(self, plugin):
        """Test prerequisite check script generation."""
        script = plugin._generate_prereq_check_script()

        assert len(script) > 0
        assert "SQL" in script or "sql" in script

    def test_generate_server_config_script(self, plugin):
        """Test server configuration script generation."""
        data = ExtractedData(
            name="server_config",
            format=ExtractionFormat.JSON,
            content='{"version": "2019"}',
            size_bytes=20,
        )

        script = plugin._generate_server_config_script(data)

        assert len(script) > 0
        assert "sp_configure" in script

    def test_generate_database_script(self, plugin):
        """Test database creation script generation."""
        data = ExtractedData(
            name="databases",
            format=ExtractionFormat.JSON,
            content='{"databases": []}',
            size_bytes=20,
        )

        script = plugin._generate_database_creation_script(data)

        assert len(script) > 0
        assert "CREATE DATABASE" in script

    def test_generate_security_script(self, plugin):
        """Test security configuration script generation."""
        data = ExtractedData(
            name="security",
            format=ExtractionFormat.JSON,
            content='{"logins": []}',
            size_bytes=20,
        )

        script = plugin._generate_security_script(data)

        assert len(script) > 0
        assert "LOGIN" in script
        assert "PASSWORD" in script or "password" in script

    def test_generate_validation_script(self, plugin):
        """Test validation script generation."""
        script = plugin._generate_validation_script()

        assert len(script) > 0
        assert "validation" in script.lower() or "validate" in script.lower()


class TestIntegration:
    """Integration tests for full workflow."""

    @pytest.mark.asyncio
    async def test_full_replication_workflow(self, plugin, sql_resource, tmp_path):
        """Test full replication workflow from analysis to application."""
        plugin.config["output_dir"] = str(tmp_path)
        plugin.config["dry_run"] = True

        # Step 1: Analyze
        analysis = await plugin.analyze_source(sql_resource)
        assert analysis.status == AnalysisStatus.SUCCESS

        # Step 2: Extract
        extraction = await plugin.extract_data(sql_resource, analysis)
        assert extraction.status in [
            AnalysisStatus.SUCCESS,
            AnalysisStatus.PARTIAL,
        ]

        # Step 3: Generate steps
        steps = await plugin.generate_replication_steps(extraction)
        assert len(steps) > 0

        # Step 4: Apply to target
        result = await plugin.apply_to_target(steps, "target-sql-id")
        assert result.status in [
            ReplicationStatus.SUCCESS,
            ReplicationStatus.PARTIAL_SUCCESS,
        ]
        assert result.fidelity_score > 0

    @pytest.mark.asyncio
    async def test_replicate_convenience_method(self, plugin, sql_resource):
        """Test convenience replicate() method."""
        plugin.config["dry_run"] = True

        result = await plugin.replicate(sql_resource, "target-sql-id")

        assert isinstance(result, ReplicationResult)
        assert result.status in [
            ReplicationStatus.SUCCESS,
            ReplicationStatus.PARTIAL_SUCCESS,
        ]

    @pytest.mark.asyncio
    async def test_extract_creates_directory(self, plugin, sql_resource, tmp_path):
        """Test that extraction creates output directory."""
        output_dir = tmp_path / "sql_output"
        plugin.config["output_dir"] = str(output_dir)

        mock_analysis = DataPlaneAnalysis(
            resource_id=sql_resource["id"],
            resource_type=sql_resource["type"],
            status=AnalysisStatus.SUCCESS,
            elements=[
                DataPlaneElement(
                    name="server_configuration",
                    element_type="Config",
                    description="Server config",
                    complexity="MEDIUM",
                    estimated_size_mb=0.1,
                )
            ],
            total_estimated_size_mb=0.1,
            complexity_score=5,
        )

        await plugin.extract_data(sql_resource, mock_analysis)

        assert output_dir.exists()
        assert output_dir.is_dir()

    @pytest.mark.asyncio
    async def test_step_execution_order(self, plugin):
        """Test that steps execute in correct order."""
        plugin.config["dry_run"] = True

        steps = [
            ReplicationStep(
                step_id="step_a",
                step_type=StepType.PREREQUISITE,
                description="First",
                script_content="SELECT 1",
                script_format=ExtractionFormat.SQL_SCRIPT,
            ),
            ReplicationStep(
                step_id="step_b",
                step_type=StepType.CONFIGURATION,
                description="Second",
                script_content="SELECT 2",
                script_format=ExtractionFormat.SQL_SCRIPT,
                depends_on=["step_a"],
            ),
            ReplicationStep(
                step_id="step_c",
                step_type=StepType.VALIDATION,
                description="Third",
                script_content="SELECT 3",
                script_format=ExtractionFormat.SQL_SCRIPT,
                depends_on=["step_b"],
            ),
        ]

        result = await plugin.apply_to_target(steps, "target-id")

        # All steps should execute in order
        assert len(result.steps_executed) == 3
        assert result.steps_executed[0].step_id == "step_a"
        assert result.steps_executed[1].step_id == "step_b"
        assert result.steps_executed[2].step_id == "step_c"
