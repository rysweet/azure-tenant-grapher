"""Tests for VM Extensions replication plugin."""

import json
from unittest.mock import patch

import pytest

from src.iac.plugins.models import (
    AnalysisStatus,
    DataPlaneAnalysis,
    ExtractionFormat,
    ExtractionResult,
    ReplicationResult,
    ReplicationStatus,
    ReplicationStep,
    StepType,
)
from src.iac.plugins.vm_extensions_plugin import VMExtensionsReplicationPlugin


@pytest.fixture
def plugin():
    """Create plugin instance."""
    return VMExtensionsReplicationPlugin()


@pytest.fixture
def plugin_with_config():
    """Create plugin instance with config."""
    return VMExtensionsReplicationPlugin(
        config={
            "output_dir": "/tmp/test_vm_extensions",
            "dry_run": False,
        }
    )


@pytest.fixture
def custom_script_extension():
    """Create mock CustomScriptExtension resource."""
    return {
        "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1/extensions/CustomScriptExtension",
        "name": "CustomScriptExtension",
        "type": "Microsoft.Compute/virtualMachines/extensions",
        "location": "eastus",
        "properties": {
            "publisher": "Microsoft.Compute",
            "type": "CustomScriptExtension",
            "typeHandlerVersion": "1.10",
            "autoUpgradeMinorVersion": True,
            "provisioningState": "Succeeded",
            "settings": {
                "fileUris": [
                    "https://storage.blob.core.windows.net/scripts/setup.ps1",
                    "https://storage.blob.core.windows.net/scripts/config.json",
                ],
                "commandToExecute": "powershell -ExecutionPolicy Unrestricted -File setup.ps1",
            },
            "protectedSettings": {
                "storageAccountName": "storageaccount",
                "storageAccountKey": "<redacted>",
            },
        },
    }


@pytest.fixture
def linux_custom_script_extension():
    """Create mock Linux CustomScript extension resource."""
    return {
        "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm2/extensions/LinuxScript",
        "name": "LinuxScript",
        "type": "Microsoft.Compute/virtualMachines/extensions",
        "location": "westus",
        "properties": {
            "publisher": "Microsoft.Azure.Extensions",
            "type": "CustomScript",
            "typeHandlerVersion": "2.1",
            "autoUpgradeMinorVersion": True,
            "provisioningState": "Succeeded",
            "settings": {
                "fileUris": ["https://storage.blob.core.windows.net/scripts/install.sh"],
                "commandToExecute": "./install.sh",
            },
            "protectedSettings": {
                "storageAccountName": "linuxstorage",
                "storageAccountKey": "<redacted>",
            },
        },
    }


@pytest.fixture
def monitoring_extension():
    """Create mock monitoring extension resource."""
    return {
        "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1/extensions/AzureMonitor",
        "name": "AzureMonitor",
        "type": "Microsoft.Compute/virtualMachines/extensions",
        "location": "eastus",
        "properties": {
            "publisher": "Microsoft.Azure.Monitor",
            "type": "AzureMonitorWindowsAgent",
            "typeHandlerVersion": "1.0",
            "autoUpgradeMinorVersion": True,
            "provisioningState": "Succeeded",
            "settings": {
                "workspaceId": "workspace-123",
            },
            "protectedSettings": {
                "workspaceKey": "<redacted>",
            },
        },
    }


@pytest.fixture
def extension_no_protected_settings():
    """Create mock extension without protected settings."""
    return {
        "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1/extensions/SimpleExtension",
        "name": "SimpleExtension",
        "type": "Microsoft.Compute/virtualMachines/extensions",
        "location": "eastus",
        "properties": {
            "publisher": "Microsoft.Compute",
            "type": "BGInfo",
            "typeHandlerVersion": "2.1",
            "autoUpgradeMinorVersion": True,
            "provisioningState": "Succeeded",
            "settings": {},
        },
    }


class TestPluginMetadata:
    """Test plugin metadata and initialization."""

    def test_plugin_initialization(self, plugin):
        """Test plugin initializes correctly."""
        assert plugin is not None
        assert plugin.config == {}

    def test_plugin_initialization_with_config(self, plugin_with_config):
        """Test plugin initializes with config."""
        assert plugin_with_config.config["output_dir"] == "/tmp/test_vm_extensions"
        assert plugin_with_config.config["dry_run"] is False

    def test_plugin_metadata(self, plugin):
        """Test plugin metadata is correct."""
        metadata = plugin.metadata

        assert metadata.name == "vm_extensions"
        assert metadata.version == "1.0.0"
        assert "VM extensions" in metadata.description
        assert "Microsoft.Compute/virtualMachines/extensions" in metadata.resource_types
        assert ExtractionFormat.TERRAFORM in metadata.supported_formats
        assert ExtractionFormat.JSON in metadata.supported_formats
        assert metadata.requires_credentials is True
        assert metadata.requires_network_access is True
        assert metadata.complexity == "MEDIUM"

    def test_get_config_value(self, plugin_with_config):
        """Test getting config values."""
        assert plugin_with_config.get_config_value("output_dir") == "/tmp/test_vm_extensions"
        assert plugin_with_config.get_config_value("dry_run") is False
        assert plugin_with_config.get_config_value("nonexistent", "default") == "default"

    def test_resource_types_property(self, plugin):
        """Test resource_types property."""
        assert plugin.resource_types == ["Microsoft.Compute/virtualMachines/extensions"]


class TestCanHandle:
    """Test resource filtering logic."""

    def test_can_handle_vm_extension(self, plugin, custom_script_extension):
        """Test plugin can handle VM extension."""
        assert plugin.can_handle(custom_script_extension) is True

    def test_can_handle_linux_extension(self, plugin, linux_custom_script_extension):
        """Test plugin can handle Linux VM extension."""
        assert plugin.can_handle(linux_custom_script_extension) is True

    def test_can_handle_monitoring_extension(self, plugin, monitoring_extension):
        """Test plugin can handle monitoring extension."""
        assert plugin.can_handle(monitoring_extension) is True

    def test_cannot_handle_vm_resource(self, plugin):
        """Test plugin rejects VM resources."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "vm1",
        }
        assert plugin.can_handle(resource) is False

    def test_cannot_handle_other_resources(self, plugin):
        """Test plugin rejects non-extension resources."""
        resource = {
            "type": "Microsoft.Storage/storageAccounts",
            "name": "storage1",
        }
        assert plugin.can_handle(resource) is False


class TestAnalyzeSource:
    """Test source resource analysis."""

    @pytest.mark.asyncio
    async def test_analyze_custom_script_extension(self, plugin, custom_script_extension):
        """Test successful analysis of CustomScriptExtension."""
        analysis = await plugin.analyze_source(custom_script_extension)

        assert isinstance(analysis, DataPlaneAnalysis)
        assert analysis.status == AnalysisStatus.SUCCESS
        assert analysis.resource_id == custom_script_extension["id"]
        assert len(analysis.elements) > 0

        # Check for expected elements
        element_names = [e.name for e in analysis.elements]
        assert "extension_metadata" in element_names
        assert "public_settings" in element_names
        assert "protected_settings" in element_names
        assert "script_content" in element_names
        assert "execute_command" in element_names

        # Check metadata
        assert analysis.requires_credentials is True
        assert analysis.requires_network_access is True
        assert "Azure Resource Manager API" in analysis.connection_methods
        assert analysis.complexity_score > 0

        # Check for protected settings warning
        assert len(analysis.warnings) > 0
        assert any("protected" in w.lower() for w in analysis.warnings)

    @pytest.mark.asyncio
    async def test_analyze_monitoring_extension(self, plugin, monitoring_extension):
        """Test analysis of monitoring extension."""
        analysis = await plugin.analyze_source(monitoring_extension)

        assert analysis.status == AnalysisStatus.SUCCESS
        assert len(analysis.elements) > 0

        # Should have metadata, settings, and protected settings
        element_names = [e.name for e in analysis.elements]
        assert "extension_metadata" in element_names
        assert "public_settings" in element_names
        assert "protected_settings" in element_names

        # Should NOT have script-specific elements
        assert "script_content" not in element_names
        assert "execute_command" not in element_names

    @pytest.mark.asyncio
    async def test_analyze_extension_no_protected_settings(
        self, plugin, extension_no_protected_settings
    ):
        """Test analysis of extension without protected settings."""
        analysis = await plugin.analyze_source(extension_no_protected_settings)

        assert analysis.status == AnalysisStatus.SUCCESS

        # Should not have protected settings element
        element_names = [e.name for e in analysis.elements]
        assert "protected_settings" not in element_names

        # Should have no warnings about protected settings
        assert not any("protected" in w.lower() for w in analysis.warnings)

    @pytest.mark.asyncio
    async def test_analyze_calculates_complexity(self, plugin, custom_script_extension):
        """Test analysis calculates complexity score."""
        analysis = await plugin.analyze_source(custom_script_extension)

        assert 1 <= analysis.complexity_score <= 10
        assert analysis.total_estimated_size_mb > 0
        assert analysis.estimated_extraction_time_minutes > 0

    @pytest.mark.asyncio
    async def test_analyze_handles_malformed_resource(self, plugin):
        """Test analysis handles malformed resource gracefully."""
        malformed = {
            "id": "test",
            "type": "Microsoft.Compute/virtualMachines/extensions",
            "properties": {},  # Missing required fields
        }

        analysis = await plugin.analyze_source(malformed)

        # Should still succeed with minimal elements
        assert analysis.status == AnalysisStatus.SUCCESS
        assert len(analysis.elements) >= 1  # At least metadata


class TestExtractData:
    """Test data extraction."""

    @pytest.mark.asyncio
    async def test_extract_custom_script_extension(
        self, plugin_with_config, custom_script_extension, tmp_path
    ):
        """Test successful data extraction from CustomScriptExtension."""
        # Create analysis
        analysis = await plugin_with_config.analyze_source(custom_script_extension)

        # Update config to use tmp_path
        plugin_with_config.config["output_dir"] = str(tmp_path)

        # Extract data
        extraction = await plugin_with_config.extract_data(custom_script_extension, analysis)

        assert isinstance(extraction, ExtractionResult)
        assert extraction.status in [AnalysisStatus.SUCCESS, AnalysisStatus.PARTIAL]
        assert extraction.items_extracted > 0
        assert len(extraction.extracted_data) > 0

        # Check extracted files were created
        assert tmp_path.exists()
        json_files = list(tmp_path.glob("*.json"))
        assert len(json_files) > 0

        # Check for warnings about protected settings
        assert len(extraction.warnings) > 0
        warning_text = " ".join(extraction.warnings).lower()
        assert "protected" in warning_text

    @pytest.mark.asyncio
    async def test_extract_creates_valid_json(
        self, plugin_with_config, custom_script_extension, tmp_path
    ):
        """Test extracted JSON files are valid."""
        analysis = await plugin_with_config.analyze_source(custom_script_extension)
        plugin_with_config.config["output_dir"] = str(tmp_path)

        extraction = await plugin_with_config.extract_data(custom_script_extension, analysis)

        # Check JSON files are valid
        for data in extraction.extracted_data:
            if data.format == ExtractionFormat.JSON and data.file_path:
                with open(data.file_path) as f:
                    content = json.load(f)
                    assert isinstance(content, dict)

    @pytest.mark.asyncio
    async def test_extract_metadata(self, plugin_with_config, custom_script_extension, tmp_path):
        """Test extraction of extension metadata."""
        analysis = await plugin_with_config.analyze_source(custom_script_extension)
        plugin_with_config.config["output_dir"] = str(tmp_path)

        extraction = await plugin_with_config.extract_data(custom_script_extension, analysis)

        # Find metadata
        metadata = next(
            (d for d in extraction.extracted_data if "metadata" in d.name), None
        )
        assert metadata is not None

        # Validate metadata content
        metadata_content = json.loads(metadata.content)
        assert "publisher" in metadata_content
        assert "type" in metadata_content
        assert "typeHandlerVersion" in metadata_content

    @pytest.mark.asyncio
    async def test_extract_protected_settings_metadata(
        self, plugin_with_config, custom_script_extension, tmp_path
    ):
        """Test extraction of protected settings metadata (not values)."""
        analysis = await plugin_with_config.analyze_source(custom_script_extension)
        plugin_with_config.config["output_dir"] = str(tmp_path)

        extraction = await plugin_with_config.extract_data(custom_script_extension, analysis)

        # Find protected settings metadata
        protected = next(
            (d for d in extraction.extracted_data if "protected" in d.name), None
        )
        assert protected is not None

        # Validate content
        protected_content = json.loads(protected.content)
        assert "required_keys" in protected_content
        assert "manual_configuration_required" in protected_content
        assert protected_content["manual_configuration_required"] is True

        # Ensure values are NOT present
        example = protected_content.get("example", {})
        for value in example.values():
            assert "REDACTED" in value or "CONFIGURE" in value

    @pytest.mark.asyncio
    async def test_extract_script_info(
        self, plugin_with_config, custom_script_extension, tmp_path
    ):
        """Test extraction of script information."""
        analysis = await plugin_with_config.analyze_source(custom_script_extension)
        plugin_with_config.config["output_dir"] = str(tmp_path)

        extraction = await plugin_with_config.extract_data(custom_script_extension, analysis)

        # Find script info
        script_info = next(
            (d for d in extraction.extracted_data if "script" in d.name), None
        )
        assert script_info is not None

        # Validate content
        script_content = json.loads(script_info.content)
        assert "file_uris" in script_content
        assert len(script_content["file_uris"]) > 0

    @pytest.mark.asyncio
    async def test_extract_handles_failures(
        self, plugin_with_config, custom_script_extension, tmp_path
    ):
        """Test extraction handles individual failures."""
        analysis = await plugin_with_config.analyze_source(custom_script_extension)
        plugin_with_config.config["output_dir"] = str(tmp_path)

        # Mock one extraction to fail
        with patch.object(
            plugin_with_config,
            "_extract_extension_metadata",
            side_effect=Exception("Extraction failed"),
        ):
            extraction = await plugin_with_config.extract_data(
                custom_script_extension, analysis
            )

        # Should have some failures
        assert extraction.items_failed > 0
        assert len(extraction.errors) > 0


class TestGenerateReplicationSteps:
    """Test replication step generation."""

    @pytest.mark.asyncio
    async def test_generate_replication_steps(
        self, plugin_with_config, custom_script_extension, tmp_path
    ):
        """Test generating replication steps."""
        # Create analysis and extraction
        analysis = await plugin_with_config.analyze_source(custom_script_extension)

        plugin_with_config.config["output_dir"] = str(tmp_path)
        extraction = await plugin_with_config.extract_data(custom_script_extension, analysis)

        # Generate steps
        steps = await plugin_with_config.generate_replication_steps(extraction)

        assert isinstance(steps, list)
        assert len(steps) > 0

        # Check step structure
        for step in steps:
            assert isinstance(step, ReplicationStep)
            assert step.step_id
            assert step.description
            assert step.script_content
            assert step.estimated_duration_minutes > 0

    @pytest.mark.asyncio
    async def test_steps_include_terraform_generation(
        self, plugin_with_config, custom_script_extension, tmp_path
    ):
        """Test steps include Terraform generation."""
        analysis = await plugin_with_config.analyze_source(custom_script_extension)
        plugin_with_config.config["output_dir"] = str(tmp_path)
        extraction = await plugin_with_config.extract_data(custom_script_extension, analysis)

        steps = await plugin_with_config.generate_replication_steps(extraction)

        # Should have Terraform generation step
        terraform_step = next(
            (s for s in steps if "terraform" in s.step_id.lower()), None
        )
        assert terraform_step is not None
        assert "azurerm_virtual_machine_extension" in terraform_step.script_content

    @pytest.mark.asyncio
    async def test_steps_include_protected_settings_documentation(
        self, plugin_with_config, custom_script_extension, tmp_path
    ):
        """Test steps include protected settings documentation."""
        analysis = await plugin_with_config.analyze_source(custom_script_extension)
        plugin_with_config.config["output_dir"] = str(tmp_path)
        extraction = await plugin_with_config.extract_data(custom_script_extension, analysis)

        steps = await plugin_with_config.generate_replication_steps(extraction)

        # Should have manual configuration step for protected settings
        manual_step = next(
            (s for s in steps if "protected" in s.step_id.lower()), None
        )
        assert manual_step is not None
        assert "MANUAL" in manual_step.description
        assert manual_step.is_critical is False

    @pytest.mark.asyncio
    async def test_steps_have_proper_dependencies(
        self, plugin_with_config, custom_script_extension, tmp_path
    ):
        """Test steps have correct dependency ordering."""
        analysis = await plugin_with_config.analyze_source(custom_script_extension)
        plugin_with_config.config["output_dir"] = str(tmp_path)
        extraction = await plugin_with_config.extract_data(custom_script_extension, analysis)

        steps = await plugin_with_config.generate_replication_steps(extraction)

        # Find validation step - should depend on other steps
        validation_step = next(
            (s for s in steps if s.step_type == StepType.VALIDATION), None
        )
        assert validation_step is not None
        assert len(validation_step.depends_on) > 0

    @pytest.mark.asyncio
    async def test_steps_include_script_upload(
        self, plugin_with_config, custom_script_extension, tmp_path
    ):
        """Test steps include script upload for CustomScript extensions."""
        analysis = await plugin_with_config.analyze_source(custom_script_extension)
        plugin_with_config.config["output_dir"] = str(tmp_path)
        extraction = await plugin_with_config.extract_data(custom_script_extension, analysis)

        steps = await plugin_with_config.generate_replication_steps(extraction)

        # Should have upload step
        upload_step = next((s for s in steps if "upload" in s.step_id.lower()), None)
        assert upload_step is not None
        assert "storage" in upload_step.description.lower()


class TestApplyToTarget:
    """Test applying replication to target."""

    @pytest.mark.asyncio
    async def test_apply_to_target_dry_run(
        self, plugin_with_config, custom_script_extension, tmp_path
    ):
        """Test dry run mode."""
        plugin_with_config.config["dry_run"] = True
        plugin_with_config.config["output_dir"] = str(tmp_path)

        analysis = await plugin_with_config.analyze_source(custom_script_extension)
        extraction = await plugin_with_config.extract_data(custom_script_extension, analysis)
        steps = await plugin_with_config.generate_replication_steps(extraction)

        # Apply to target
        result = await plugin_with_config.apply_to_target(steps, "target-vm-id")

        assert isinstance(result, ReplicationResult)
        assert result.status in [
            ReplicationStatus.SUCCESS,
            ReplicationStatus.PARTIAL_SUCCESS,
        ]
        assert len(result.warnings) > 0
        assert any("dry run" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_apply_to_target_success(
        self, plugin_with_config, custom_script_extension, tmp_path
    ):
        """Test successful replication."""
        plugin_with_config.config["dry_run"] = True
        plugin_with_config.config["output_dir"] = str(tmp_path)

        analysis = await plugin_with_config.analyze_source(custom_script_extension)
        extraction = await plugin_with_config.extract_data(custom_script_extension, analysis)
        steps = await plugin_with_config.generate_replication_steps(extraction)

        result = await plugin_with_config.apply_to_target(steps, "target-vm-id")

        assert result.target_resource_id == "target-vm-id"
        assert result.steps_succeeded > 0
        assert result.total_duration_seconds >= 0
        assert 0.0 <= result.fidelity_score <= 1.0

    @pytest.mark.asyncio
    async def test_apply_skips_manual_steps(
        self, plugin_with_config, custom_script_extension, tmp_path
    ):
        """Test that manual steps are skipped in automated execution."""
        plugin_with_config.config["dry_run"] = True
        plugin_with_config.config["output_dir"] = str(tmp_path)

        analysis = await plugin_with_config.analyze_source(custom_script_extension)
        extraction = await plugin_with_config.extract_data(custom_script_extension, analysis)
        steps = await plugin_with_config.generate_replication_steps(extraction)

        result = await plugin_with_config.apply_to_target(steps, "target-vm-id")

        # Manual steps should be skipped
        assert result.steps_skipped > 0

        # Should have warnings about manual steps
        assert any("manual" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_apply_respects_dependencies(
        self, plugin_with_config, custom_script_extension, tmp_path
    ):
        """Test dependency checking during execution."""
        plugin_with_config.config["dry_run"] = True
        plugin_with_config.config["output_dir"] = str(tmp_path)

        analysis = await plugin_with_config.analyze_source(custom_script_extension)
        extraction = await plugin_with_config.extract_data(custom_script_extension, analysis)
        steps = await plugin_with_config.generate_replication_steps(extraction)

        result = await plugin_with_config.apply_to_target(steps, "target-vm-id")

        # All automated steps should execute or be skipped
        total_executed = result.steps_succeeded + result.steps_skipped
        assert total_executed == len(steps)

    @pytest.mark.asyncio
    async def test_apply_calculates_fidelity(
        self, plugin_with_config, custom_script_extension, tmp_path
    ):
        """Test fidelity score calculation."""
        plugin_with_config.config["dry_run"] = True
        plugin_with_config.config["output_dir"] = str(tmp_path)

        analysis = await plugin_with_config.analyze_source(custom_script_extension)
        extraction = await plugin_with_config.extract_data(custom_script_extension, analysis)
        steps = await plugin_with_config.generate_replication_steps(extraction)

        result = await plugin_with_config.apply_to_target(steps, "target-vm-id")

        # Fidelity should be reasonable (manual steps are skipped)
        assert 0.0 <= result.fidelity_score <= 1.0

        # With manual steps skipped, fidelity should still be positive
        if result.steps_succeeded > 0:
            assert result.fidelity_score > 0.0


class TestPrivateHelpers:
    """Test private helper methods."""

    def test_calculate_complexity_score(self, plugin):
        """Test complexity score calculation."""
        from src.iac.plugins.models import DataPlaneElement

        # Empty elements
        assert plugin._calculate_complexity_score([]) == 1

        # Few elements
        elements = [
            DataPlaneElement(
                name="test1",
                element_type="test",
                description="test",
                complexity="LOW",
            )
        ]
        score = plugin._calculate_complexity_score(elements)
        assert 1 <= score <= 10

        # Sensitive elements increase score
        elements = [
            DataPlaneElement(
                name="test1",
                element_type="test",
                description="test",
                is_sensitive=True,
            ),
            DataPlaneElement(
                name="test2",
                element_type="test",
                description="test",
                is_sensitive=True,
            ),
        ]
        score = plugin._calculate_complexity_score(elements)
        assert score > 2  # Should be higher due to sensitive elements

    def test_has_element(self, plugin):
        """Test element checking."""
        from src.iac.plugins.models import DataPlaneAnalysis, DataPlaneElement

        analysis = DataPlaneAnalysis(
            resource_id="test",
            resource_type="test",
            elements=[
                DataPlaneElement(
                    name="extension_metadata",
                    element_type="test",
                    description="test",
                )
            ],
        )

        assert plugin._has_element(analysis, "metadata") is True
        assert plugin._has_element(analysis, "nonexistent") is False

    def test_find_extracted_data(self, plugin):
        """Test finding extracted data."""
        from src.iac.plugins.models import ExtractedData, ExtractionResult

        extraction = ExtractionResult(
            resource_id="test",
            extracted_data=[
                ExtractedData(
                    name="extension_metadata",
                    format=ExtractionFormat.JSON,
                    content="{}",
                ),
                ExtractedData(
                    name="public_settings",
                    format=ExtractionFormat.JSON,
                    content="{}",
                ),
            ],
        )

        # Should find by partial name
        assert plugin._find_extracted_data(extraction, "metadata") is not None
        assert plugin._find_extracted_data(extraction, "settings") is not None
        assert plugin._find_extracted_data(extraction, "nonexistent") is None

    def test_dependencies_met(self, plugin):
        """Test dependency checking."""
        from src.iac.plugins.models import StepResult

        step = ReplicationStep(
            step_id="step2",
            step_type=StepType.CONFIGURATION,
            description="test",
            depends_on=["step1"],
        )

        # No dependencies met
        results = []
        assert plugin._dependencies_met(step, results) is False

        # Dependencies met
        results = [
            StepResult(
                step_id="step1",
                status=ReplicationStatus.SUCCESS,
                duration_seconds=1.0,
            )
        ]
        assert plugin._dependencies_met(step, results) is True

        # Dependency failed
        results = [
            StepResult(
                step_id="step1",
                status=ReplicationStatus.FAILED,
                duration_seconds=1.0,
            )
        ]
        assert plugin._dependencies_met(step, results) is False

    def test_calculate_fidelity_score(self, plugin):
        """Test fidelity score calculation."""
        # All succeeded
        assert plugin._calculate_fidelity_score(10, 0, 0, 10) == 1.0

        # All failed
        assert plugin._calculate_fidelity_score(0, 10, 0, 10) == 0.0

        # Half succeeded, half skipped (manual steps)
        assert plugin._calculate_fidelity_score(5, 0, 5, 10) == 0.75

        # Mixed
        score = plugin._calculate_fidelity_score(5, 3, 2, 10)
        assert 0.0 <= score <= 1.0

        # No steps
        assert plugin._calculate_fidelity_score(0, 0, 0, 0) == 0.0


class TestTerraformGeneration:
    """Test Terraform configuration generation."""

    @pytest.mark.asyncio
    async def test_generate_terraform_config(
        self, plugin_with_config, custom_script_extension, tmp_path
    ):
        """Test Terraform configuration generation."""
        plugin_with_config.config["output_dir"] = str(tmp_path)

        analysis = await plugin_with_config.analyze_source(custom_script_extension)
        extraction = await plugin_with_config.extract_data(custom_script_extension, analysis)

        # Get data for Terraform generation
        metadata_data = plugin_with_config._find_extracted_data(extraction, "metadata")
        settings_data = plugin_with_config._find_extracted_data(extraction, "settings")
        protected_data = plugin_with_config._find_extracted_data(extraction, "protected")

        tf_config = plugin_with_config._generate_terraform_config(
            metadata_data, settings_data, protected_data, extraction
        )

        assert isinstance(tf_config, str)
        assert len(tf_config) > 0
        assert "azurerm_virtual_machine_extension" in tf_config
        assert "virtual_machine_id" in tf_config
        assert "publisher" in tf_config

    @pytest.mark.asyncio
    async def test_terraform_includes_protected_settings_placeholder(
        self, plugin_with_config, custom_script_extension, tmp_path
    ):
        """Test Terraform includes placeholder for protected settings."""
        plugin_with_config.config["output_dir"] = str(tmp_path)

        analysis = await plugin_with_config.analyze_source(custom_script_extension)
        extraction = await plugin_with_config.extract_data(custom_script_extension, analysis)

        metadata_data = plugin_with_config._find_extracted_data(extraction, "metadata")
        settings_data = plugin_with_config._find_extracted_data(extraction, "settings")
        protected_data = plugin_with_config._find_extracted_data(extraction, "protected")

        tf_config = plugin_with_config._generate_terraform_config(
            metadata_data, settings_data, protected_data, extraction
        )

        # Should have commented protected_settings
        assert "protected_settings" in tf_config
        assert "CONFIGURE MANUALLY" in tf_config or "# " in tf_config


class TestExtractedDataFormats:
    """Test extracted data formats and content."""

    @pytest.mark.asyncio
    async def test_extract_metadata_format(self, plugin, tmp_path):
        """Test extension metadata extraction format."""
        resource = {
            "name": "test-extension",
            "properties": {
                "publisher": "Microsoft.Test",
                "type": "TestExtension",
                "typeHandlerVersion": "1.0",
            },
        }

        data = await plugin._extract_extension_metadata(resource, tmp_path)

        assert data.format == ExtractionFormat.JSON
        assert data.size_bytes > 0
        assert data.checksum is not None

        # Validate JSON content
        content = json.loads(data.content)
        assert "publisher" in content
        assert "type" in content
        assert "typeHandlerVersion" in content

    @pytest.mark.asyncio
    async def test_extract_protected_settings_metadata_format(self, plugin, tmp_path):
        """Test protected settings metadata extraction format."""
        resource = {
            "properties": {
                "protectedSettings": {
                    "key1": "value1",
                    "key2": "value2",
                }
            }
        }

        data = await plugin._extract_protected_settings_metadata(resource, tmp_path)

        assert data.format == ExtractionFormat.JSON
        content = json.loads(data.content)
        assert "required_keys" in content
        assert "manual_configuration_required" in content
        assert content["manual_configuration_required"] is True

        # Ensure values are redacted
        example = content.get("example", {})
        for value in example.values():
            assert "REDACTED" in value or "CONFIGURE" in value


class TestEndToEnd:
    """Test complete end-to-end workflow."""

    @pytest.mark.asyncio
    async def test_full_replication_workflow(
        self, plugin_with_config, custom_script_extension, tmp_path
    ):
        """Test complete replication workflow from analysis to apply."""
        plugin_with_config.config["output_dir"] = str(tmp_path)
        plugin_with_config.config["dry_run"] = True

        # Step 1: Analyze
        analysis = await plugin_with_config.analyze_source(custom_script_extension)
        assert analysis.status == AnalysisStatus.SUCCESS

        # Step 2: Extract
        extraction = await plugin_with_config.extract_data(custom_script_extension, analysis)
        assert extraction.status in [AnalysisStatus.SUCCESS, AnalysisStatus.PARTIAL]

        # Step 3: Generate steps
        steps = await plugin_with_config.generate_replication_steps(extraction)
        assert len(steps) > 0

        # Step 4: Apply
        result = await plugin_with_config.apply_to_target(steps, "target-vm-id")
        assert result.status in [
            ReplicationStatus.SUCCESS,
            ReplicationStatus.PARTIAL_SUCCESS,
        ]

    @pytest.mark.asyncio
    async def test_replicate_convenience_method(
        self, plugin_with_config, custom_script_extension, tmp_path
    ):
        """Test the convenience replicate() method."""
        plugin_with_config.config["output_dir"] = str(tmp_path)
        plugin_with_config.config["dry_run"] = True

        result = await plugin_with_config.replicate(custom_script_extension, "target-vm-id")

        assert isinstance(result, ReplicationResult)
        assert result.target_resource_id == "target-vm-id"


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_resource(self, plugin):
        """Test handling of empty resource."""
        result = plugin.can_handle({})
        assert result is False

    @pytest.mark.asyncio
    async def test_malformed_resource(self, plugin):
        """Test handling of malformed resource."""
        resource = {"name": "test"}  # Missing type
        result = plugin.can_handle(resource)
        assert result is False

    @pytest.mark.asyncio
    async def test_extraction_with_no_output_dir(
        self, plugin, custom_script_extension
    ):
        """Test extraction creates default output directory."""
        analysis = await plugin.analyze_source(custom_script_extension)

        # Should create default directory
        extraction = await plugin.extract_data(custom_script_extension, analysis)

        # Check output dir was created
        assert "output_directory" in extraction.metadata

    @pytest.mark.asyncio
    async def test_generate_steps_with_empty_extraction(self, plugin):
        """Test generating steps with empty extraction."""
        from src.iac.plugins.models import ExtractionResult

        extraction = ExtractionResult(
            resource_id="test",
            extracted_data=[],
        )

        steps = await plugin.generate_replication_steps(extraction)

        # Should still generate validation step
        assert len(steps) >= 1
        assert any(s.step_type == StepType.VALIDATION for s in steps)

    @pytest.mark.asyncio
    async def test_apply_with_empty_steps(self, plugin):
        """Test applying with no steps."""
        result = await plugin.apply_to_target([], "target")

        assert result.status == ReplicationStatus.SUCCESS
        assert result.steps_succeeded == 0
        assert result.steps_failed == 0
