"""Tests for Active Directory replication plugin."""

import json
from pathlib import Path

import pytest

from src.iac.plugins.active_directory_plugin import ActiveDirectoryReplicationPlugin
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


@pytest.fixture
def plugin():
    """Create plugin instance for testing."""
    return ActiveDirectoryReplicationPlugin(
        config={"output_dir": "/tmp/ad_test", "dry_run": True}
    )


@pytest.fixture
def ad_resource():
    """Create mock AD domain controller resource."""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-dc",
        "name": "test-dc",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "tags": {"role": "domain-controller"},
        "properties": {
            "osProfile": {"computerName": "TEST-DC-001"},
            "hardwareProfile": {"vmSize": "Standard_D2s_v3"},
        },
    }


@pytest.fixture
def non_ad_resource():
    """Create mock non-AD resource."""
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
        resource_id="/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-dc",
        resource_type="Microsoft.Compute/virtualMachines",
        status=AnalysisStatus.SUCCESS,
        elements=[
            DataPlaneElement(
                name="forest_configuration",
                element_type="AD Forest",
                description="Forest: simuland.local",
                complexity="HIGH",
                estimated_size_mb=0.1,
                dependencies=[],
            ),
            DataPlaneElement(
                name="user_accounts",
                element_type="Users",
                description="50 user accounts",
                complexity="MEDIUM",
                estimated_size_mb=2.5,
                dependencies=["organizational_units"],
            ),
        ],
        total_estimated_size_mb=2.6,
        complexity_score=7,
        requires_credentials=True,
        requires_network_access=True,
        connection_methods=["WinRM", "PowerShell"],
        estimated_extraction_time_minutes=15,
    )


class TestPluginMetadata:
    """Test plugin metadata."""

    def test_metadata_structure(self, plugin):
        """Test that metadata has correct structure."""
        metadata = plugin.metadata

        assert metadata.name == "active_directory"
        assert metadata.version == "1.0.0"
        assert isinstance(metadata.description, str)
        assert "Microsoft.Compute/virtualMachines" in metadata.resource_types
        assert metadata.requires_credentials is True
        assert metadata.requires_network_access is True
        assert metadata.complexity == "HIGH"
        assert metadata.estimated_effort_weeks > 0

    def test_supported_formats(self, plugin):
        """Test that plugin supports expected formats."""
        metadata = plugin.metadata

        assert ExtractionFormat.LDIF in metadata.supported_formats
        assert ExtractionFormat.POWERSHELL_DSC in metadata.supported_formats
        assert ExtractionFormat.JSON in metadata.supported_formats
        assert ExtractionFormat.CSV in metadata.supported_formats


class TestResourceDetection:
    """Test resource type detection."""

    def test_can_handle_ad_resource_by_tag(self, plugin, ad_resource):
        """Test detection of AD DC by tag."""
        assert plugin.can_handle(ad_resource) is True

    def test_can_handle_ad_resource_by_name_dc(self, plugin):
        """Test detection of AD DC by name pattern (dc)."""
        resource = {
            "id": "test-id",
            "name": "atevet12dc001",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {"osProfile": {"computerName": "WINDOWS-DC"}},
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_ad_resource_by_name_ads(self, plugin):
        """Test detection of AD DC by name pattern (ads)."""
        resource = {
            "id": "test-id",
            "name": "atevet12ads001",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {"osProfile": {"computerName": "WINDOWS-ADS"}},
        }
        assert plugin.can_handle(resource) is True

    def test_cannot_handle_non_ad_resource(self, plugin, non_ad_resource):
        """Test rejection of non-AD resource."""
        assert plugin.can_handle(non_ad_resource) is False

    def test_cannot_handle_wrong_resource_type(self, plugin):
        """Test rejection of wrong resource type."""
        resource = {
            "id": "test-id",
            "name": "test-dc",
            "type": "Microsoft.Storage/storageAccounts",
            "tags": {"role": "domain-controller"},
        }
        assert plugin.can_handle(resource) is False


class TestAnalyzeSource:
    """Test source analysis functionality."""

    @pytest.mark.asyncio
    async def test_analyze_success(self, plugin, ad_resource):
        """Test successful AD analysis."""
        analysis = await plugin.analyze_source(ad_resource)

        assert analysis.status == AnalysisStatus.SUCCESS
        assert len(analysis.elements) > 0
        assert analysis.requires_credentials is True
        assert analysis.requires_network_access is True
        assert "WinRM" in analysis.connection_methods
        assert analysis.complexity_score >= 1

    @pytest.mark.asyncio
    async def test_analyze_discovers_forest(self, plugin, ad_resource):
        """Test that analysis discovers forest configuration."""
        analysis = await plugin.analyze_source(ad_resource)

        forest_element = next(
            (e for e in analysis.elements if e.name == "forest_configuration"), None
        )
        assert forest_element is not None
        assert forest_element.element_type == "AD Forest"
        assert forest_element.complexity == "HIGH"

    @pytest.mark.asyncio
    async def test_analyze_discovers_users(self, plugin, ad_resource):
        """Test that analysis discovers users."""
        analysis = await plugin.analyze_source(ad_resource)

        user_element = next(
            (e for e in analysis.elements if e.name == "user_accounts"), None
        )
        assert user_element is not None
        assert "user" in user_element.description.lower()

    @pytest.mark.asyncio
    async def test_analyze_discovers_groups(self, plugin, ad_resource):
        """Test that analysis discovers groups."""
        analysis = await plugin.analyze_source(ad_resource)

        group_element = next(
            (e for e in analysis.elements if e.name == "groups"), None
        )
        assert group_element is not None
        assert "group" in group_element.description.lower()

    @pytest.mark.asyncio
    async def test_analyze_discovers_gpos(self, plugin, ad_resource):
        """Test that analysis discovers GPOs."""
        analysis = await plugin.analyze_source(ad_resource)

        gpo_element = next(
            (e for e in analysis.elements if e.name == "group_policies"), None
        )
        assert gpo_element is not None
        assert "gpo" in gpo_element.description.lower() or "policy" in gpo_element.description.lower()

    @pytest.mark.asyncio
    async def test_analyze_calculates_size(self, plugin, ad_resource):
        """Test that analysis calculates total size."""
        analysis = await plugin.analyze_source(ad_resource)

        assert analysis.total_estimated_size_mb > 0
        assert analysis.total_estimated_size_mb == sum(
            e.estimated_size_mb for e in analysis.elements
        )

    @pytest.mark.asyncio
    async def test_analyze_estimates_time(self, plugin, ad_resource):
        """Test that analysis estimates extraction time."""
        analysis = await plugin.analyze_source(ad_resource)

        assert analysis.estimated_extraction_time_minutes > 0


class TestExtractData:
    """Test data extraction functionality."""

    @pytest.mark.asyncio
    async def test_extract_success(self, plugin, ad_resource, mock_analysis, tmp_path):
        """Test successful data extraction."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(ad_resource, mock_analysis)

        assert extraction.status in [
            AnalysisStatus.SUCCESS,
            AnalysisStatus.PARTIAL,
        ]
        assert len(extraction.extracted_data) > 0
        assert extraction.items_extracted > 0
        assert extraction.extraction_duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_extract_creates_files(self, plugin, ad_resource, mock_analysis, tmp_path):
        """Test that extraction creates output files."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(ad_resource, mock_analysis)

        # Check that at least one file was created
        for data in extraction.extracted_data:
            if data.file_path:
                assert Path(data.file_path).exists()

    @pytest.mark.asyncio
    async def test_extract_forest_config(self, plugin, ad_resource, mock_analysis, tmp_path):
        """Test extraction of forest configuration."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(ad_resource, mock_analysis)

        forest_data = next(
            (d for d in extraction.extracted_data if "forest" in d.name.lower()), None
        )
        assert forest_data is not None
        assert forest_data.format == ExtractionFormat.JSON

        # Verify content is valid JSON
        content = json.loads(forest_data.content)
        assert "forest_name" in content

    @pytest.mark.asyncio
    async def test_extract_includes_checksum(self, plugin, ad_resource, mock_analysis, tmp_path):
        """Test that extracted data includes checksums."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(ad_resource, mock_analysis)

        for data in extraction.extracted_data:
            assert data.checksum is not None
            assert len(data.checksum) == 64  # SHA256 hex length

    @pytest.mark.asyncio
    async def test_extract_warns_about_passwords(self, plugin, ad_resource, mock_analysis, tmp_path):
        """Test that extraction warns about missing passwords."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(ad_resource, mock_analysis)

        # Should have warning about passwords
        password_warning = any(
            "password" in w.lower() for w in extraction.warnings
        )
        assert password_warning is True


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
                    name="forest_config",
                    format=ExtractionFormat.JSON,
                    content='{"forest_name": "test.local"}',
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
        """Test that steps include prerequisite installation."""
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
        assert "feature" in prereq_step.description.lower() or "install" in prereq_step.description.lower()

    @pytest.mark.asyncio
    async def test_steps_have_dependencies(self, plugin, tmp_path):
        """Test that steps have proper dependency ordering."""
        extraction = ExtractionResult(
            resource_id="test-id",
            status=AnalysisStatus.SUCCESS,
            extracted_data=[
                ExtractedData(
                    name="forest_config",
                    format=ExtractionFormat.JSON,
                    content='{"forest_name": "test.local"}',
                    size_bytes=100,
                ),
                ExtractedData(
                    name="domain_config",
                    format=ExtractionFormat.JSON,
                    content='{"domain_name": "test.local"}',
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
    async def test_step_scripts_are_powershell(self, plugin, tmp_path):
        """Test that generated scripts are PowerShell DSC."""
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

        for step in steps:
            assert step.script_format == ExtractionFormat.POWERSHELL_DSC
            assert len(step.script_content) > 0


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
                script_content="echo 'test'",
                script_format=ExtractionFormat.POWERSHELL_DSC,
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
                script_content="echo '1'",
                script_format=ExtractionFormat.POWERSHELL_DSC,
            ),
            ReplicationStep(
                step_id="step2",
                step_type=StepType.CONFIGURATION,
                description="Step 2",
                script_content="echo '2'",
                script_format=ExtractionFormat.POWERSHELL_DSC,
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
                script_content="echo '1'",
                script_format=ExtractionFormat.POWERSHELL_DSC,
            ),
            ReplicationStep(
                step_id="step2",
                step_type=StepType.CONFIGURATION,
                description="Step 2",
                script_content="echo '2'",
                script_format=ExtractionFormat.POWERSHELL_DSC,
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
                script_content="echo 'test'",
                script_format=ExtractionFormat.POWERSHELL_DSC,
            )
        ]

        result = await plugin.apply_to_target(steps, "test-target-id")

        assert 0.0 <= result.fidelity_score <= 1.0


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
                complexity="HIGH",
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
            script_content="test",
            script_format=ExtractionFormat.POWERSHELL_DSC,
            depends_on=[],
        )

        assert plugin._dependencies_met(step, []) is True

    def test_dependencies_met_success(self, plugin):
        """Test dependency checking with met dependencies."""
        step = ReplicationStep(
            step_id="test",
            step_type=StepType.CONFIGURATION,
            description="test",
            script_content="test",
            script_format=ExtractionFormat.POWERSHELL_DSC,
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
            script_content="test",
            script_format=ExtractionFormat.POWERSHELL_DSC,
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


class TestConfigurationHandling:
    """Test configuration handling."""

    def test_plugin_accepts_config(self):
        """Test that plugin accepts configuration."""
        config = {"output_dir": "/custom/path", "dry_run": True}
        plugin = ActiveDirectoryReplicationPlugin(config=config)

        assert plugin.get_config_value("output_dir") == "/custom/path"
        assert plugin.get_config_value("dry_run") is True

    def test_plugin_default_config(self):
        """Test plugin with default configuration."""
        plugin = ActiveDirectoryReplicationPlugin()

        assert plugin.get_config_value("nonexistent", "default") == "default"

    def test_get_config_value_with_default(self, plugin):
        """Test getting config value with default."""
        value = plugin.get_config_value("nonexistent_key", "default_value")
        assert value == "default_value"


class TestIntegration:
    """Integration tests for full workflow."""

    @pytest.mark.asyncio
    async def test_full_replication_workflow(self, plugin, ad_resource, tmp_path):
        """Test full replication workflow from analysis to application."""
        plugin.config["output_dir"] = str(tmp_path)
        plugin.config["dry_run"] = True

        # Step 1: Analyze
        analysis = await plugin.analyze_source(ad_resource)
        assert analysis.status == AnalysisStatus.SUCCESS

        # Step 2: Extract
        extraction = await plugin.extract_data(ad_resource, analysis)
        assert extraction.status in [
            AnalysisStatus.SUCCESS,
            AnalysisStatus.PARTIAL,
        ]

        # Step 3: Generate steps
        steps = await plugin.generate_replication_steps(extraction)
        assert len(steps) > 0

        # Step 4: Apply to target
        result = await plugin.apply_to_target(steps, "target-dc-id")
        assert result.status in [
            ReplicationStatus.SUCCESS,
            ReplicationStatus.PARTIAL_SUCCESS,
        ]
        assert result.fidelity_score > 0

    @pytest.mark.asyncio
    async def test_replicate_convenience_method(self, plugin, ad_resource):
        """Test convenience replicate() method."""
        plugin.config["dry_run"] = True

        result = await plugin.replicate(ad_resource, "target-dc-id")

        assert isinstance(result, ReplicationResult)
        assert result.status in [
            ReplicationStatus.SUCCESS,
            ReplicationStatus.PARTIAL_SUCCESS,
        ]
