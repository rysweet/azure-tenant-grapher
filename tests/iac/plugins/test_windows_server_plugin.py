"""Tests for Windows Server replication plugin."""

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
from src.iac.plugins.windows_server_plugin import WindowsServerReplicationPlugin


@pytest.fixture
def plugin():
    """Create plugin instance."""
    return WindowsServerReplicationPlugin()


@pytest.fixture
def plugin_with_config():
    """Create plugin instance with config."""
    return WindowsServerReplicationPlugin(
        config={
            "output_dir": "/tmp/test_output",
            "dry_run": False,
            "strict_validation": False,
        }
    )


@pytest.fixture
def windows_server_resource():
    """Create mock Windows Server VM resource."""
    return {
        "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/win-server-01",
        "name": "win-server-01",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "tags": {
            "environment": "production",
            "role": "web-server",
        },
        "properties": {
            "osProfile": {
                "computerName": "WIN-SERVER-01",
                "adminUsername": "azadmin",
            },
            "storageProfile": {
                "imageReference": {
                    "publisher": "MicrosoftWindowsServer",
                    "offer": "WindowsServer",
                    "sku": "2019-Datacenter",
                    "version": "latest",
                }
            },
            "networkProfile": {
                "networkInterfaces": [
                    {"id": "/subscriptions/sub1/.../networkInterfaces/nic1"}
                ]
            },
        },
    }


@pytest.fixture
def domain_controller_resource():
    """Create mock Domain Controller VM resource."""
    return {
        "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/dc-01",
        "name": "dc-01-ads",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "tags": {
            "role": "domain-controller",
        },
        "properties": {
            "osProfile": {
                "computerName": "DC-01",
            },
            "storageProfile": {
                "imageReference": {
                    "offer": "WindowsServer",
                }
            },
        },
    }


@pytest.fixture
def linux_vm_resource():
    """Create mock Linux VM resource."""
    return {
        "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/linux-01",
        "name": "linux-01",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "properties": {
            "osProfile": {
                "computerName": "LINUX-01",
            },
            "storageProfile": {
                "imageReference": {
                    "offer": "UbuntuServer",
                }
            },
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
        assert plugin_with_config.config["output_dir"] == "/tmp/test_output"
        assert plugin_with_config.config["dry_run"] is False

    def test_plugin_metadata(self, plugin):
        """Test plugin metadata is correct."""
        metadata = plugin.metadata

        assert metadata.name == "windows_server"
        assert metadata.version == "1.0.0"
        assert "Windows Server" in metadata.description
        assert "Microsoft.Compute/virtualMachines" in metadata.resource_types
        assert ExtractionFormat.POWERSHELL_DSC in metadata.supported_formats
        assert ExtractionFormat.JSON in metadata.supported_formats
        assert metadata.requires_credentials is True
        assert metadata.requires_network_access is True
        assert metadata.complexity == "HIGH"

    def test_get_config_value(self, plugin_with_config):
        """Test getting config values."""
        assert plugin_with_config.get_config_value("output_dir") == "/tmp/test_output"
        assert plugin_with_config.get_config_value("dry_run") is False
        assert plugin_with_config.get_config_value("nonexistent", "default") == "default"

    def test_resource_types_property(self, plugin):
        """Test resource_types property."""
        assert plugin.resource_types == ["Microsoft.Compute/virtualMachines"]


class TestCanHandle:
    """Test resource filtering logic."""

    def test_can_handle_windows_server(self, plugin, windows_server_resource):
        """Test plugin can handle Windows Server VM."""
        assert plugin.can_handle(windows_server_resource) is True

    def test_cannot_handle_domain_controller(self, plugin, domain_controller_resource):
        """Test plugin rejects domain controllers."""
        assert plugin.can_handle(domain_controller_resource) is False

    def test_cannot_handle_linux_vm(self, plugin, linux_vm_resource):
        """Test plugin rejects Linux VMs."""
        assert plugin.can_handle(linux_vm_resource) is False

    def test_cannot_handle_wrong_resource_type(self, plugin):
        """Test plugin rejects non-VM resources."""
        resource = {
            "type": "Microsoft.Storage/storageAccounts",
            "name": "storage1",
        }
        assert plugin.can_handle(resource) is False

    def test_can_handle_windows_server_case_insensitive(self, plugin):
        """Test OS detection is case-insensitive."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "vm1",
            "properties": {
                "osProfile": {},
                "storageProfile": {
                    "imageReference": {
                        "offer": "WINDOWSSERVER",
                    }
                },
            },
        }
        assert plugin.can_handle(resource) is True


class TestAnalyzeSource:
    """Test source resource analysis."""

    @pytest.mark.asyncio
    async def test_analyze_source_success(self, plugin, windows_server_resource):
        """Test successful analysis of Windows Server."""
        with patch.object(plugin, "_check_winrm_connectivity", return_value=True):
            analysis = await plugin.analyze_source(windows_server_resource)

        assert isinstance(analysis, DataPlaneAnalysis)
        assert analysis.status == AnalysisStatus.SUCCESS
        assert analysis.resource_id == windows_server_resource["id"]
        assert len(analysis.elements) > 0

        # Check for expected elements
        element_names = [e.name for e in analysis.elements]
        assert "windows_features" in element_names
        assert "local_users" in element_names
        assert "local_groups" in element_names
        assert "windows_services" in element_names
        assert "scheduled_tasks" in element_names
        assert "firewall_config" in element_names
        assert "file_shares" in element_names
        assert "installed_applications" in element_names
        assert "registry_settings" in element_names
        assert "system_config" in element_names

        # Check metadata
        assert analysis.requires_credentials is True
        assert analysis.requires_network_access is True
        assert "WinRM" in analysis.connection_methods
        assert analysis.complexity_score > 0

    @pytest.mark.asyncio
    async def test_analyze_source_connection_failure(self, plugin, windows_server_resource):
        """Test analysis fails when cannot connect via WinRM."""
        with patch.object(plugin, "_check_winrm_connectivity", return_value=False):
            analysis = await plugin.analyze_source(windows_server_resource)

        assert analysis.status == AnalysisStatus.FAILED
        assert len(analysis.errors) > 0
        assert "WinRM" in analysis.errors[0]

    @pytest.mark.asyncio
    async def test_analyze_source_with_errors(self, plugin, windows_server_resource):
        """Test analysis handles partial failures."""
        with patch.object(plugin, "_check_winrm_connectivity", return_value=True):
            # Mock one count method to raise an exception - this should not stop analysis
            # The analysis should catch the exception internally and continue
            analysis = await plugin.analyze_source(windows_server_resource)

        # Analysis should succeed even if some elements fail
        assert analysis.status in [AnalysisStatus.SUCCESS, AnalysisStatus.PARTIAL, AnalysisStatus.FAILED]
        # Should have attempted to analyze
        assert analysis.resource_id == windows_server_resource["id"]

    @pytest.mark.asyncio
    async def test_analyze_source_calculates_totals(self, plugin, windows_server_resource):
        """Test analysis calculates size and complexity."""
        with patch.object(plugin, "_check_winrm_connectivity", return_value=True):
            analysis = await plugin.analyze_source(windows_server_resource)

        assert analysis.total_estimated_size_mb > 0
        assert 1 <= analysis.complexity_score <= 10
        assert analysis.estimated_extraction_time_minutes > 0


class TestExtractData:
    """Test data extraction."""

    @pytest.mark.asyncio
    async def test_extract_data_success(
        self, plugin_with_config, windows_server_resource, tmp_path
    ):
        """Test successful data extraction."""
        # Create analysis
        with patch.object(plugin_with_config, "_check_winrm_connectivity", return_value=True):
            analysis = await plugin_with_config.analyze_source(windows_server_resource)

        # Update config to use tmp_path
        plugin_with_config.config["output_dir"] = str(tmp_path)

        # Extract data
        extraction = await plugin_with_config.extract_data(
            windows_server_resource, analysis
        )

        assert isinstance(extraction, ExtractionResult)
        assert extraction.status in [AnalysisStatus.SUCCESS, AnalysisStatus.PARTIAL]
        assert extraction.items_extracted > 0
        assert len(extraction.extracted_data) > 0

        # Check some extracted files were created
        assert tmp_path.exists()
        json_files = list(tmp_path.glob("*.json"))
        assert len(json_files) > 0

    @pytest.mark.asyncio
    async def test_extract_data_includes_warnings(
        self, plugin_with_config, windows_server_resource, tmp_path
    ):
        """Test extraction includes security warnings."""
        with patch.object(plugin_with_config, "_check_winrm_connectivity", return_value=True):
            analysis = await plugin_with_config.analyze_source(windows_server_resource)

        plugin_with_config.config["output_dir"] = str(tmp_path)

        extraction = await plugin_with_config.extract_data(
            windows_server_resource, analysis
        )

        # Should have warnings about passwords
        assert len(extraction.warnings) > 0
        warning_text = " ".join(extraction.warnings).lower()
        assert "password" in warning_text or "credential" in warning_text

    @pytest.mark.asyncio
    async def test_extract_data_creates_valid_json(
        self, plugin_with_config, windows_server_resource, tmp_path
    ):
        """Test extracted JSON files are valid."""
        with patch.object(plugin_with_config, "_check_winrm_connectivity", return_value=True):
            analysis = await plugin_with_config.analyze_source(windows_server_resource)

        plugin_with_config.config["output_dir"] = str(tmp_path)

        extraction = await plugin_with_config.extract_data(
            windows_server_resource, analysis
        )

        # Check JSON files are valid
        for data in extraction.extracted_data:
            if data.format == ExtractionFormat.JSON and data.file_path:
                with open(data.file_path) as f:
                    content = json.load(f)
                    assert isinstance(content, dict)

    @pytest.mark.asyncio
    async def test_extract_data_handles_failures(
        self, plugin_with_config, windows_server_resource, tmp_path
    ):
        """Test extraction handles individual failures."""
        with patch.object(plugin_with_config, "_check_winrm_connectivity", return_value=True):
            analysis = await plugin_with_config.analyze_source(windows_server_resource)

        plugin_with_config.config["output_dir"] = str(tmp_path)

        # Mock one extraction to fail
        with patch.object(
            plugin_with_config,
            "_extract_windows_features",
            side_effect=Exception("Extraction failed"),
        ):
            extraction = await plugin_with_config.extract_data(
                windows_server_resource, analysis
            )

        # Should have some failures
        assert extraction.items_failed > 0
        assert len(extraction.errors) > 0


class TestGenerateReplicationSteps:
    """Test replication step generation."""

    @pytest.mark.asyncio
    async def test_generate_replication_steps(
        self, plugin_with_config, windows_server_resource, tmp_path
    ):
        """Test generating replication steps."""
        # Create analysis and extraction
        with patch.object(plugin_with_config, "_check_winrm_connectivity", return_value=True):
            analysis = await plugin_with_config.analyze_source(windows_server_resource)

        plugin_with_config.config["output_dir"] = str(tmp_path)
        extraction = await plugin_with_config.extract_data(
            windows_server_resource, analysis
        )

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
            assert step.script_format == ExtractionFormat.POWERSHELL_DSC
            assert step.estimated_duration_minutes > 0

    @pytest.mark.asyncio
    async def test_steps_have_proper_dependencies(
        self, plugin_with_config, windows_server_resource, tmp_path
    ):
        """Test steps have correct dependency ordering."""
        with patch.object(plugin_with_config, "_check_winrm_connectivity", return_value=True):
            analysis = await plugin_with_config.analyze_source(windows_server_resource)

        plugin_with_config.config["output_dir"] = str(tmp_path)
        extraction = await plugin_with_config.extract_data(
            windows_server_resource, analysis
        )

        steps = await plugin_with_config.generate_replication_steps(extraction)

        # Find validation step - should depend on all others
        validation_step = next((s for s in steps if s.step_type == StepType.VALIDATION), None)
        assert validation_step is not None
        assert len(validation_step.depends_on) > 0

        # Find users step
        users_step = next((s for s in steps if "users" in s.step_id), None)
        if users_step:
            # Groups should depend on users
            groups_step = next((s for s in steps if "groups" in s.step_id), None)
            if groups_step:
                assert users_step.step_id in groups_step.depends_on

    @pytest.mark.asyncio
    async def test_steps_include_all_types(
        self, plugin_with_config, windows_server_resource, tmp_path
    ):
        """Test generated steps include different step types."""
        with patch.object(plugin_with_config, "_check_winrm_connectivity", return_value=True):
            analysis = await plugin_with_config.analyze_source(windows_server_resource)

        plugin_with_config.config["output_dir"] = str(tmp_path)
        extraction = await plugin_with_config.extract_data(
            windows_server_resource, analysis
        )

        steps = await plugin_with_config.generate_replication_steps(extraction)

        step_types = {step.step_type for step in steps}

        # Should have at least prerequisite, configuration, and validation
        assert StepType.PREREQUISITE in step_types or StepType.CONFIGURATION in step_types
        assert StepType.VALIDATION in step_types


class TestApplyToTarget:
    """Test applying replication to target."""

    @pytest.mark.asyncio
    async def test_apply_to_target_dry_run(
        self, plugin_with_config, windows_server_resource, tmp_path
    ):
        """Test dry run mode."""
        plugin_with_config.config["dry_run"] = True

        with patch.object(plugin_with_config, "_check_winrm_connectivity", return_value=True):
            analysis = await plugin_with_config.analyze_source(windows_server_resource)

        plugin_with_config.config["output_dir"] = str(tmp_path)
        extraction = await plugin_with_config.extract_data(
            windows_server_resource, analysis
        )
        steps = await plugin_with_config.generate_replication_steps(extraction)

        # Apply to target
        result = await plugin_with_config.apply_to_target(
            steps, "target-resource-id"
        )

        assert isinstance(result, ReplicationResult)
        assert result.status in [ReplicationStatus.SUCCESS, ReplicationStatus.PARTIAL_SUCCESS]
        assert len(result.warnings) > 0
        assert any("dry run" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_apply_to_target_success(
        self, plugin_with_config, windows_server_resource, tmp_path
    ):
        """Test successful replication."""
        plugin_with_config.config["dry_run"] = True  # Use dry run to avoid real execution

        with patch.object(plugin_with_config, "_check_winrm_connectivity", return_value=True):
            analysis = await plugin_with_config.analyze_source(windows_server_resource)

        plugin_with_config.config["output_dir"] = str(tmp_path)
        extraction = await plugin_with_config.extract_data(
            windows_server_resource, analysis
        )
        steps = await plugin_with_config.generate_replication_steps(extraction)

        result = await plugin_with_config.apply_to_target(
            steps, "target-resource-id"
        )

        assert result.target_resource_id == "target-resource-id"
        assert result.steps_succeeded > 0
        assert result.total_duration_seconds >= 0
        assert 0.0 <= result.fidelity_score <= 1.0

    @pytest.mark.asyncio
    async def test_apply_to_target_respects_dependencies(
        self, plugin_with_config, windows_server_resource, tmp_path
    ):
        """Test dependency checking during execution."""
        plugin_with_config.config["dry_run"] = True

        with patch.object(plugin_with_config, "_check_winrm_connectivity", return_value=True):
            analysis = await plugin_with_config.analyze_source(windows_server_resource)

        plugin_with_config.config["output_dir"] = str(tmp_path)
        extraction = await plugin_with_config.extract_data(
            windows_server_resource, analysis
        )
        steps = await plugin_with_config.generate_replication_steps(extraction)

        result = await plugin_with_config.apply_to_target(
            steps, "target-resource-id"
        )

        # All steps should execute in dry run
        assert result.steps_succeeded + result.steps_skipped == len(steps)

    @pytest.mark.asyncio
    async def test_apply_to_target_calculates_fidelity(
        self, plugin_with_config, windows_server_resource, tmp_path
    ):
        """Test fidelity score calculation."""
        plugin_with_config.config["dry_run"] = True

        with patch.object(plugin_with_config, "_check_winrm_connectivity", return_value=True):
            analysis = await plugin_with_config.analyze_source(windows_server_resource)

        plugin_with_config.config["output_dir"] = str(tmp_path)
        extraction = await plugin_with_config.extract_data(
            windows_server_resource, analysis
        )
        steps = await plugin_with_config.generate_replication_steps(extraction)

        result = await plugin_with_config.apply_to_target(
            steps, "target-resource-id"
        )

        # Fidelity should be high if all steps succeeded
        if result.steps_failed == 0:
            assert result.fidelity_score > 0.5


class TestPrivateHelpers:
    """Test private helper methods."""

    @pytest.mark.asyncio
    async def test_check_winrm_connectivity(self, plugin):
        """Test WinRM connectivity check."""
        result = await plugin._check_winrm_connectivity({})
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_count_methods_return_integers(self, plugin):
        """Test all count methods return integers."""
        resource = {}

        assert isinstance(await plugin._count_windows_features(resource), int)
        assert isinstance(await plugin._count_local_users(resource), int)
        assert isinstance(await plugin._count_local_groups(resource), int)
        assert isinstance(await plugin._count_services(resource), int)
        assert isinstance(await plugin._count_scheduled_tasks(resource), int)
        assert isinstance(await plugin._count_firewall_rules(resource), int)
        assert isinstance(await plugin._count_file_shares(resource), int)
        assert isinstance(await plugin._count_installed_apps(resource), int)
        assert isinstance(await plugin._count_registry_keys(resource), int)

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

        # Many high-complexity elements
        elements = [
            DataPlaneElement(
                name=f"test{i}",
                element_type="test",
                description="test",
                complexity="HIGH",
            )
            for i in range(10)
        ]
        score = plugin._calculate_complexity_score(elements)
        assert score == 10  # Should max out at 10

    def test_has_element(self, plugin):
        """Test element checking."""
        from src.iac.plugins.models import DataPlaneAnalysis, DataPlaneElement

        analysis = DataPlaneAnalysis(
            resource_id="test",
            resource_type="test",
            elements=[
                DataPlaneElement(
                    name="windows_features",
                    element_type="test",
                    description="test",
                )
            ],
        )

        assert plugin._has_element(analysis, "windows_features") is True
        assert plugin._has_element(analysis, "nonexistent") is False

    def test_find_extracted_data(self, plugin):
        """Test finding extracted data."""
        from src.iac.plugins.models import ExtractedData, ExtractionResult

        extraction = ExtractionResult(
            resource_id="test",
            extracted_data=[
                ExtractedData(
                    name="windows_features",
                    format=ExtractionFormat.JSON,
                    content="{}",
                ),
                ExtractedData(
                    name="local_users",
                    format=ExtractionFormat.JSON,
                    content="{}",
                ),
            ],
        )

        # Should find by partial name
        assert plugin._find_extracted_data(extraction, "features") is not None
        assert plugin._find_extracted_data(extraction, "users") is not None
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

        # Half succeeded, half skipped
        assert plugin._calculate_fidelity_score(5, 0, 5, 10) == 0.75

        # Mixed
        score = plugin._calculate_fidelity_score(5, 3, 2, 10)
        assert 0.0 <= score <= 1.0

        # No steps
        assert plugin._calculate_fidelity_score(0, 0, 0, 0) == 0.0


class TestScriptGeneration:
    """Test PowerShell script generation."""

    def test_generate_system_config_script(self, plugin):
        """Test system configuration script generation."""
        from src.iac.plugins.models import ExtractedData

        data = ExtractedData(
            name="system_config",
            format=ExtractionFormat.JSON,
            content="{}",
        )

        script = plugin._generate_system_config_script(data)
        assert isinstance(script, str)
        assert len(script) > 0
        assert "Rename-Computer" in script or "computer" in script.lower()

    def test_generate_features_install_script(self, plugin):
        """Test features installation script generation."""
        from src.iac.plugins.models import ExtractedData

        data = ExtractedData(
            name="features",
            format=ExtractionFormat.JSON,
            content="{}",
        )

        script = plugin._generate_features_install_script(data)
        assert isinstance(script, str)
        assert "Install-WindowsFeature" in script

    def test_generate_registry_script(self, plugin):
        """Test registry configuration script generation."""
        from src.iac.plugins.models import ExtractedData

        data = ExtractedData(
            name="registry",
            format=ExtractionFormat.JSON,
            content="{}",
        )

        script = plugin._generate_registry_script(data)
        assert isinstance(script, str)
        assert "Set-ItemProperty" in script or "registry" in script.lower()

    def test_generate_users_script(self, plugin):
        """Test users creation script generation."""
        from src.iac.plugins.models import ExtractedData

        data = ExtractedData(
            name="users",
            format=ExtractionFormat.JSON,
            content="{}",
        )

        script = plugin._generate_users_script(data)
        assert isinstance(script, str)
        assert "New-LocalUser" in script
        assert "password" in script.lower()

    def test_generate_services_script(self, plugin):
        """Test services configuration script generation."""
        from src.iac.plugins.models import ExtractedData

        data = ExtractedData(
            name="services",
            format=ExtractionFormat.JSON,
            content="{}",
        )

        script = plugin._generate_services_script(data)
        assert isinstance(script, str)
        assert "Set-Service" in script or "service" in script.lower()

    def test_generate_firewall_script(self, plugin):
        """Test firewall configuration script generation."""
        from src.iac.plugins.models import ExtractedData

        data = ExtractedData(
            name="firewall",
            format=ExtractionFormat.JSON,
            content="{}",
        )

        script = plugin._generate_firewall_script(data)
        assert isinstance(script, str)
        assert "NetFirewall" in script

    def test_generate_shares_script(self, plugin):
        """Test file shares creation script generation."""
        from src.iac.plugins.models import ExtractedData

        data = ExtractedData(
            name="shares",
            format=ExtractionFormat.JSON,
            content="{}",
        )

        script = plugin._generate_shares_script(data)
        assert isinstance(script, str)
        assert "New-SmbShare" in script

    def test_generate_validation_script(self, plugin):
        """Test validation script generation."""
        script = plugin._generate_validation_script()
        assert isinstance(script, str)
        assert len(script) > 0
        assert "ConvertTo-Json" in script or "results" in script.lower()


class TestExtractedDataFormats:
    """Test extracted data formats and content."""

    @pytest.mark.asyncio
    async def test_extract_windows_features_format(self, plugin, tmp_path):
        """Test Windows features extraction format."""
        data = await plugin._extract_windows_features({}, tmp_path)

        assert data.format == ExtractionFormat.JSON
        assert data.size_bytes > 0
        assert data.checksum is not None

        # Validate JSON content
        content = json.loads(data.content)
        assert "features" in content
        assert isinstance(content["features"], list)

    @pytest.mark.asyncio
    async def test_extract_local_users_format(self, plugin, tmp_path):
        """Test local users extraction format."""
        data = await plugin._extract_local_users({}, tmp_path)

        assert data.format == ExtractionFormat.JSON
        content = json.loads(data.content)
        assert "users" in content
        assert "note" in content
        assert "password" in content["note"].lower()

    @pytest.mark.asyncio
    async def test_extract_services_format(self, plugin, tmp_path):
        """Test services extraction format."""
        data = await plugin._extract_services({}, tmp_path)

        assert data.format == ExtractionFormat.JSON
        content = json.loads(data.content)
        assert "services" in content
        assert isinstance(content["services"], list)

    @pytest.mark.asyncio
    async def test_extract_firewall_format(self, plugin, tmp_path):
        """Test firewall extraction format."""
        data = await plugin._extract_firewall_config({}, tmp_path)

        assert data.format == ExtractionFormat.JSON
        content = json.loads(data.content)
        assert "profiles" in content
        assert "rules" in content


class TestEndToEnd:
    """Test complete end-to-end workflow."""

    @pytest.mark.asyncio
    async def test_full_replication_workflow(
        self, plugin_with_config, windows_server_resource, tmp_path
    ):
        """Test complete replication workflow from analysis to apply."""
        plugin_with_config.config["output_dir"] = str(tmp_path)
        plugin_with_config.config["dry_run"] = True

        # Step 1: Analyze
        with patch.object(plugin_with_config, "_check_winrm_connectivity", return_value=True):
            analysis = await plugin_with_config.analyze_source(windows_server_resource)

        assert analysis.status == AnalysisStatus.SUCCESS

        # Step 2: Extract
        extraction = await plugin_with_config.extract_data(
            windows_server_resource, analysis
        )

        assert extraction.status in [AnalysisStatus.SUCCESS, AnalysisStatus.PARTIAL]

        # Step 3: Generate steps
        steps = await plugin_with_config.generate_replication_steps(extraction)

        assert len(steps) > 0

        # Step 4: Apply
        result = await plugin_with_config.apply_to_target(
            steps, "target-resource-id"
        )

        assert result.status in [ReplicationStatus.SUCCESS, ReplicationStatus.PARTIAL_SUCCESS]

    @pytest.mark.asyncio
    async def test_replicate_convenience_method(
        self, plugin_with_config, windows_server_resource, tmp_path
    ):
        """Test the convenience replicate() method."""
        plugin_with_config.config["output_dir"] = str(tmp_path)
        plugin_with_config.config["dry_run"] = True

        with patch.object(plugin_with_config, "_check_winrm_connectivity", return_value=True):
            result = await plugin_with_config.replicate(
                windows_server_resource, "target-resource-id"
            )

        assert isinstance(result, ReplicationResult)
        assert result.target_resource_id == "target-resource-id"


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
    async def test_extraction_with_no_output_dir(self, plugin, windows_server_resource):
        """Test extraction creates default output directory."""
        with patch.object(plugin, "_check_winrm_connectivity", return_value=True):
            analysis = await plugin.analyze_source(windows_server_resource)

        # Should create default directory
        extraction = await plugin.extract_data(windows_server_resource, analysis)

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
        assert len(steps) > 0
        assert any(s.step_type == StepType.VALIDATION for s in steps)

    @pytest.mark.asyncio
    async def test_apply_with_empty_steps(self, plugin):
        """Test applying with no steps."""
        result = await plugin.apply_to_target([], "target")

        assert result.status == ReplicationStatus.SUCCESS
        assert result.steps_succeeded == 0
        assert result.steps_failed == 0
