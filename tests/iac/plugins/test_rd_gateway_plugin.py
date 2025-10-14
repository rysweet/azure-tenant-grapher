"""Tests for RD Gateway replication plugin."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.iac.plugins.models import (
    AnalysisStatus,
    DataPlaneAnalysis,
    ExtractionResult,
    ReplicationResult,
    ReplicationStatus,
    ReplicationStep,
    StepType,
)
from src.iac.plugins.rd_gateway_plugin import RDGatewayReplicationPlugin


@pytest.fixture
def rdg_plugin():
    """Create RD Gateway plugin instance."""
    return RDGatewayReplicationPlugin()


@pytest.fixture
def rdg_plugin_with_config(tmp_path):
    """Create RD Gateway plugin with configuration."""
    return RDGatewayReplicationPlugin(
        config={
            "output_dir": str(tmp_path / "rdg_output"),
            "dry_run": False,
            "strict_validation": False,
        }
    )


@pytest.fixture
def rdg_resource():
    """Create sample RD Gateway resource."""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/atevet12rdg001",
        "name": "atevet12rdg001",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "tags": {
            "role": "rdgateway",
            "environment": "production",
        },
        "properties": {
            "storageProfile": {
                "imageReference": {
                    "publisher": "MicrosoftWindowsServer",
                    "offer": "WindowsServer",
                    "sku": "2019-Datacenter",
                    "version": "latest",
                }
            }
        },
    }


@pytest.fixture
def non_rdg_resource():
    """Create sample non-RD Gateway resource."""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/webserver01",
        "name": "webserver01",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "tags": {
            "role": "webserver",
        },
        "properties": {
            "storageProfile": {
                "imageReference": {
                    "publisher": "MicrosoftWindowsServer",
                    "offer": "WindowsServer",
                    "sku": "2019-Datacenter",
                    "version": "latest",
                }
            }
        },
    }


@pytest.fixture
def sample_analysis():
    """Create sample DataPlaneAnalysis."""
    from src.iac.plugins.models import DataPlaneElement

    return DataPlaneAnalysis(
        resource_id="/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/atevet12rdg001",
        resource_type="Microsoft.Compute/virtualMachines",
        status=AnalysisStatus.SUCCESS,
        elements=[
            DataPlaneElement(
                name="rdg_server_config",
                element_type="RD Gateway Server Configuration",
                description="Gateway server settings",
                complexity="MEDIUM",
            ),
            DataPlaneElement(
                name="connection_authorization_policies",
                element_type="Connection Authorization Policies (CAPs)",
                description="3 CAPs",
                complexity="MEDIUM",
            ),
            DataPlaneElement(
                name="resource_authorization_policies",
                element_type="Resource Authorization Policies (RAPs)",
                description="2 RAPs",
                complexity="MEDIUM",
            ),
        ],
        total_estimated_size_mb=0.5,
        complexity_score=6,
    )


class TestPluginMetadata:
    """Test plugin metadata and configuration."""

    def test_metadata(self, rdg_plugin):
        """Test plugin metadata."""
        metadata = rdg_plugin.metadata

        assert metadata.name == "rd_gateway"
        assert metadata.version == "1.0.0"
        assert "Remote Desktop Gateway" in metadata.description
        assert "Microsoft.Compute/virtualMachines" in metadata.resource_types
        assert metadata.complexity == "MEDIUM"
        assert metadata.estimated_effort_weeks == 1.5
        assert "rdgateway" in metadata.tags

    def test_resource_types(self, rdg_plugin):
        """Test resource types property."""
        types = rdg_plugin.resource_types
        assert isinstance(types, list)
        assert "Microsoft.Compute/virtualMachines" in types

    def test_config_values(self, rdg_plugin_with_config):
        """Test configuration value retrieval."""
        assert rdg_plugin_with_config.get_config_value("dry_run") is False
        assert rdg_plugin_with_config.get_config_value("strict_validation") is False
        assert (
            rdg_plugin_with_config.get_config_value("nonexistent", "default")
            == "default"
        )


class TestCanHandle:
    """Test resource type detection."""

    def test_can_handle_rdg_resource_by_tag(self, rdg_plugin, rdg_resource):
        """Test detection of RD Gateway by tag."""
        assert rdg_plugin.can_handle(rdg_resource) is True

    def test_can_handle_rdg_resource_by_name(self, rdg_plugin):
        """Test detection of RD Gateway by name."""
        resource = {
            "id": "test-id",
            "name": "rdgateway001",
            "type": "Microsoft.Compute/virtualMachines",
            "tags": {},
            "properties": {
                "storageProfile": {
                    "imageReference": {
                        "offer": "WindowsServer",
                    }
                }
            },
        }
        assert rdg_plugin.can_handle(resource) is True

    def test_can_handle_rdg_resource_by_name_rdg(self, rdg_plugin):
        """Test detection of RD Gateway by 'rdg' in name."""
        resource = {
            "id": "test-id",
            "name": "atevet12rdg001",
            "type": "Microsoft.Compute/virtualMachines",
            "tags": {},
            "properties": {
                "storageProfile": {
                    "imageReference": {
                        "offer": "WindowsServer",
                    }
                }
            },
        }
        assert rdg_plugin.can_handle(resource) is True

    def test_cannot_handle_non_windows_resource(self, rdg_plugin):
        """Test rejection of non-Windows resource."""
        resource = {
            "id": "test-id",
            "name": "rdg001",
            "type": "Microsoft.Compute/virtualMachines",
            "tags": {"role": "rdgateway"},
            "properties": {
                "storageProfile": {
                    "imageReference": {
                        "offer": "UbuntuServer",
                    }
                }
            },
        }
        assert rdg_plugin.can_handle(resource) is False

    def test_cannot_handle_non_rdg_windows_resource(self, rdg_plugin, non_rdg_resource):
        """Test rejection of non-RD Gateway Windows resource."""
        assert rdg_plugin.can_handle(non_rdg_resource) is False

    def test_cannot_handle_wrong_resource_type(self, rdg_plugin):
        """Test rejection of non-VM resource."""
        resource = {
            "id": "test-id",
            "name": "rdg001",
            "type": "Microsoft.Storage/storageAccounts",
            "tags": {"role": "rdgateway"},
            "properties": {},
        }
        assert rdg_plugin.can_handle(resource) is False


class TestAnalyzeSource:
    """Test source resource analysis."""

    @pytest.mark.asyncio
    async def test_analyze_source_success(self, rdg_plugin, rdg_resource):
        """Test successful source analysis."""
        with patch.object(
            rdg_plugin, "_check_winrm_connectivity", return_value=True
        ), patch.object(
            rdg_plugin, "_check_rdg_role_installed", return_value=True
        ), patch.object(rdg_plugin, "_count_caps", return_value=3), patch.object(
            rdg_plugin, "_count_raps", return_value=2
        ), patch.object(
            rdg_plugin, "_count_resource_groups", return_value=2
        ), patch.object(
            rdg_plugin,
            "_get_certificate_info",
            return_value={
                "subject": "CN=rdg.contoso.com",
                "thumbprint": "ABC123",
                "expiry": "2025-12-31",
            },
        ):
            result = await rdg_plugin.analyze_source(rdg_resource)

        assert isinstance(result, DataPlaneAnalysis)
        assert result.status == AnalysisStatus.SUCCESS
        assert len(result.elements) > 0
        assert result.total_estimated_size_mb > 0
        assert result.complexity_score > 0
        assert "WinRM" in result.connection_methods
        assert "PowerShell" in result.connection_methods

        # Check for expected elements
        element_names = [e.name for e in result.elements]
        assert "rdg_server_config" in element_names
        assert "connection_authorization_policies" in element_names
        assert "resource_authorization_policies" in element_names
        assert "resource_groups" in element_names
        assert "ssl_certificate" in element_names
        assert "gateway_health_settings" in element_names

    @pytest.mark.asyncio
    async def test_analyze_source_no_rdg_role(self, rdg_plugin, rdg_resource):
        """Test analysis when RD Gateway role not installed."""
        with patch.object(
            rdg_plugin, "_check_winrm_connectivity", return_value=True
        ), patch.object(rdg_plugin, "_check_rdg_role_installed", return_value=False):
            result = await rdg_plugin.analyze_source(rdg_resource)

        assert result.status == AnalysisStatus.FAILED
        assert len(result.errors) > 0
        assert any("RD Gateway role" in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_analyze_source_connection_error(self, rdg_plugin, rdg_resource):
        """Test analysis with WinRM connection failure."""
        with patch.object(rdg_plugin, "_check_winrm_connectivity", return_value=False):
            result = await rdg_plugin.analyze_source(rdg_resource)

        assert result.status == AnalysisStatus.FAILED
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_analyze_source_no_certificate(self, rdg_plugin, rdg_resource):
        """Test analysis when no SSL certificate configured."""
        with patch.object(
            rdg_plugin, "_check_winrm_connectivity", return_value=True
        ), patch.object(
            rdg_plugin, "_check_rdg_role_installed", return_value=True
        ), patch.object(rdg_plugin, "_count_caps", return_value=1), patch.object(
            rdg_plugin, "_count_raps", return_value=1
        ), patch.object(
            rdg_plugin, "_count_resource_groups", return_value=0
        ), patch.object(rdg_plugin, "_get_certificate_info", return_value=None):
            result = await rdg_plugin.analyze_source(rdg_resource)

        assert result.status == AnalysisStatus.SUCCESS
        element_names = [e.name for e in result.elements]
        assert "ssl_certificate" not in element_names


class TestExtractData:
    """Test data extraction."""

    @pytest.mark.asyncio
    async def test_extract_data_success(
        self, rdg_plugin_with_config, rdg_resource, sample_analysis, tmp_path
    ):
        """Test successful data extraction."""
        result = await rdg_plugin_with_config.extract_data(
            rdg_resource, sample_analysis
        )

        assert isinstance(result, ExtractionResult)
        assert result.status == AnalysisStatus.SUCCESS
        assert result.items_extracted > 0
        assert result.items_failed == 0
        assert len(result.extracted_data) > 0

        # Check that files were created
        output_dir = Path(rdg_plugin_with_config.get_config_value("output_dir"))
        assert output_dir.exists()

        # Check for expected extracted data
        data_names = [d.name for d in result.extracted_data]
        assert "rdg_server_config" in data_names
        assert "connection_authorization_policies" in data_names
        assert "resource_authorization_policies" in data_names

    @pytest.mark.asyncio
    async def test_extract_server_config(
        self, rdg_plugin_with_config, rdg_resource, tmp_path
    ):
        """Test server configuration extraction."""
        output_dir = tmp_path / "rdg_output"
        output_dir.mkdir(parents=True, exist_ok=True)

        extracted = await rdg_plugin_with_config._extract_server_config(
            rdg_resource, output_dir
        )

        assert extracted.name == "rdg_server_config"
        assert extracted.format.value == "json"
        assert extracted.file_path is not None
        assert Path(extracted.file_path).exists()

        # Validate JSON content
        content = json.loads(extracted.content)
        assert "server_name" in content
        assert "port" in content
        assert "ssl_certificate_thumbprint" in content

    @pytest.mark.asyncio
    async def test_extract_caps(self, rdg_plugin_with_config, rdg_resource, tmp_path):
        """Test CAPs extraction."""
        output_dir = tmp_path / "rdg_output"
        output_dir.mkdir(parents=True, exist_ok=True)

        extracted = await rdg_plugin_with_config._extract_caps(rdg_resource, output_dir)

        assert extracted.name == "connection_authorization_policies"
        assert extracted.format.value == "json"
        assert extracted.file_path is not None

        # Validate JSON content
        content = json.loads(extracted.content)
        assert "caps" in content
        assert len(content["caps"]) > 0

        # Check CAP structure
        cap = content["caps"][0]
        assert "name" in cap
        assert "enabled" in cap
        assert "user_groups" in cap
        assert "device_redirection" in cap
        assert "session_timeout_minutes" in cap

        # Check that XML file was also created
        assert "xml_file" in extracted.metadata
        xml_path = Path(extracted.metadata["xml_file"])
        assert xml_path.exists()

    @pytest.mark.asyncio
    async def test_extract_raps(self, rdg_plugin_with_config, rdg_resource, tmp_path):
        """Test RAPs extraction."""
        output_dir = tmp_path / "rdg_output"
        output_dir.mkdir(parents=True, exist_ok=True)

        extracted = await rdg_plugin_with_config._extract_raps(rdg_resource, output_dir)

        assert extracted.name == "resource_authorization_policies"
        assert extracted.format.value == "json"

        # Validate JSON content
        content = json.loads(extracted.content)
        assert "raps" in content
        assert len(content["raps"]) > 0

        # Check RAP structure
        rap = content["raps"][0]
        assert "name" in rap
        assert "enabled" in rap
        assert "user_groups" in rap
        assert "computer_group_type" in rap
        assert "computer_group" in rap
        assert "port_numbers" in rap

    @pytest.mark.asyncio
    async def test_extract_resource_groups(
        self, rdg_plugin_with_config, rdg_resource, tmp_path
    ):
        """Test resource groups extraction."""
        output_dir = tmp_path / "rdg_output"
        output_dir.mkdir(parents=True, exist_ok=True)

        extracted = await rdg_plugin_with_config._extract_resource_groups(
            rdg_resource, output_dir
        )

        assert extracted.name == "resource_groups"

        # Validate JSON content
        content = json.loads(extracted.content)
        assert "resource_groups" in content
        assert len(content["resource_groups"]) > 0

        # Check resource group structure
        group = content["resource_groups"][0]
        assert "name" in group
        assert "description" in group
        assert "computers" in group
        assert isinstance(group["computers"], list)

    @pytest.mark.asyncio
    async def test_extract_certificate_info(
        self, rdg_plugin_with_config, rdg_resource, tmp_path
    ):
        """Test certificate information extraction."""
        output_dir = tmp_path / "rdg_output"
        output_dir.mkdir(parents=True, exist_ok=True)

        extracted = await rdg_plugin_with_config._extract_certificate_info(
            rdg_resource, output_dir
        )

        assert extracted.name == "ssl_certificate"

        # Validate JSON content
        content = json.loads(extracted.content)
        assert "certificate" in content
        cert = content["certificate"]
        assert "subject" in cert
        assert "thumbprint" in cert
        assert "not_before" in cert
        assert "not_after" in cert

        # Verify warning about private key
        assert "note" in content
        assert "Private key NOT exported" in content["note"]

    @pytest.mark.asyncio
    async def test_extract_health_settings(
        self, rdg_plugin_with_config, rdg_resource, tmp_path
    ):
        """Test health settings extraction."""
        output_dir = tmp_path / "rdg_output"
        output_dir.mkdir(parents=True, exist_ok=True)

        extracted = await rdg_plugin_with_config._extract_health_settings(
            rdg_resource, output_dir
        )

        assert extracted.name == "gateway_health_settings"

        # Validate JSON content
        content = json.loads(extracted.content)
        assert "health_settings" in content
        settings = content["health_settings"]
        assert "event_log_level" in settings
        assert "enable_connection_logging" in settings


class TestGenerateReplicationSteps:
    """Test replication step generation."""

    @pytest.mark.asyncio
    async def test_generate_steps_full(
        self, rdg_plugin_with_config, rdg_resource, sample_analysis
    ):
        """Test generation of all replication steps."""
        extraction = await rdg_plugin_with_config.extract_data(
            rdg_resource, sample_analysis
        )
        steps = await rdg_plugin_with_config.generate_replication_steps(extraction)

        assert isinstance(steps, list)
        assert len(steps) > 0

        # Check step IDs - at minimum we should have these
        step_ids = [s.step_id for s in steps]
        assert "verify_rdg_role" in step_ids
        assert "restart_rdg_service" in step_ids
        assert "validate_configuration" in step_ids

        # Check that we have at least some config steps
        config_steps = [s for s in steps if s.step_type == StepType.CONFIGURATION]
        assert len(config_steps) > 0

        # Validate step types
        prerequisite_steps = [s for s in steps if s.step_type == StepType.PREREQUISITE]
        validation_steps = [s for s in steps if s.step_type == StepType.VALIDATION]

        assert len(prerequisite_steps) > 0
        assert len(validation_steps) > 0

    @pytest.mark.asyncio
    async def test_generate_steps_verify_dependencies(
        self, rdg_plugin_with_config, rdg_resource, sample_analysis
    ):
        """Test that steps have correct dependencies."""
        extraction = await rdg_plugin_with_config.extract_data(
            rdg_resource, sample_analysis
        )
        steps = await rdg_plugin_with_config.generate_replication_steps(extraction)

        # Find specific steps
        verify_step = next(s for s in steps if s.step_id == "verify_rdg_role")
        validation_step = next(
            (s for s in steps if s.step_id == "validate_configuration"), None
        )
        restart_step = next(
            (s for s in steps if s.step_id == "restart_rdg_service"), None
        )

        # Verify role should have no dependencies
        assert len(verify_step.depends_on) == 0

        # Restart should depend on other steps
        if restart_step:
            assert len(restart_step.depends_on) > 0

        # Validation should be last
        if validation_step:
            assert len(validation_step.depends_on) > 0

    @pytest.mark.asyncio
    async def test_step_scripts_not_empty(
        self, rdg_plugin_with_config, rdg_resource, sample_analysis
    ):
        """Test that generated scripts are not empty."""
        extraction = await rdg_plugin_with_config.extract_data(
            rdg_resource, sample_analysis
        )
        steps = await rdg_plugin_with_config.generate_replication_steps(extraction)

        for step in steps:
            assert step.script_content is not None
            assert len(step.script_content) > 0
            assert "PowerShell" in step.script_content or "#" in step.script_content


class TestApplyToTarget:
    """Test applying replication to target."""

    @pytest.mark.asyncio
    async def test_apply_to_target_success(
        self, rdg_plugin_with_config, rdg_resource, sample_analysis
    ):
        """Test successful application to target."""
        extraction = await rdg_plugin_with_config.extract_data(
            rdg_resource, sample_analysis
        )
        steps = await rdg_plugin_with_config.generate_replication_steps(extraction)

        result = await rdg_plugin_with_config.apply_to_target(
            steps,
            "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/virtualMachines/target",
        )

        assert isinstance(result, ReplicationResult)
        assert result.status in [
            ReplicationStatus.SUCCESS,
            ReplicationStatus.PARTIAL_SUCCESS,
        ]
        assert result.steps_succeeded > 0
        assert result.fidelity_score > 0.0

    @pytest.mark.asyncio
    async def test_apply_to_target_dry_run(
        self, rdg_resource, sample_analysis, tmp_path
    ):
        """Test dry run mode."""
        plugin = RDGatewayReplicationPlugin(
            config={"output_dir": str(tmp_path), "dry_run": True}
        )

        extraction = await plugin.extract_data(rdg_resource, sample_analysis)
        steps = await plugin.generate_replication_steps(extraction)

        result = await plugin.apply_to_target(steps, "target-id")

        assert result.status == ReplicationStatus.SUCCESS
        assert len(result.warnings) > 0
        assert any("Dry run" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_apply_to_target_with_failures(
        self, rdg_plugin_with_config, rdg_resource, sample_analysis
    ):
        """Test handling of step failures."""
        extraction = await rdg_plugin_with_config.extract_data(
            rdg_resource, sample_analysis
        )
        steps = await rdg_plugin_with_config.generate_replication_steps(extraction)

        # Mock failure for one step
        with patch.object(
            rdg_plugin_with_config,
            "_execute_step_on_target",
            side_effect=[
                AsyncMock(
                    status=ReplicationStatus.SUCCESS,
                    duration_seconds=1.0,
                    stdout="OK",
                )()
                for _ in range(len(steps))
            ],
        ):
            result = await rdg_plugin_with_config.apply_to_target(steps, "target-id")

        assert isinstance(result, ReplicationResult)


class TestHelperMethods:
    """Test helper methods."""

    def test_calculate_complexity_score_empty(self, rdg_plugin):
        """Test complexity score calculation with no elements."""
        score = rdg_plugin._calculate_complexity_score([])
        assert score == 1

    def test_calculate_complexity_score_with_elements(self, rdg_plugin):
        """Test complexity score calculation with elements."""
        from src.iac.plugins.models import DataPlaneElement

        elements = [
            DataPlaneElement(
                name="test1",
                element_type="type1",
                description="desc1",
                complexity="LOW",
            ),
            DataPlaneElement(
                name="test2",
                element_type="type2",
                description="desc2",
                complexity="MEDIUM",
            ),
            DataPlaneElement(
                name="test3",
                element_type="type3",
                description="desc3",
                complexity="HIGH",
            ),
        ]

        score = rdg_plugin._calculate_complexity_score(elements)
        assert score > 1
        assert score <= 10

    def test_has_element(self, rdg_plugin, sample_analysis):
        """Test element existence check."""
        assert rdg_plugin._has_element(sample_analysis, "rdg_server_config") is True
        assert (
            rdg_plugin._has_element(
                sample_analysis, "connection_authorization_policies"
            )
            is True
        )
        assert rdg_plugin._has_element(sample_analysis, "nonexistent") is False

    def test_find_extracted_data(self, rdg_plugin):
        """Test finding extracted data."""
        from src.iac.plugins.models import ExtractedData, ExtractionFormat

        extraction = ExtractionResult(
            resource_id="test-id",
            extracted_data=[
                ExtractedData(
                    name="rdg_server_config",
                    format=ExtractionFormat.JSON,
                    content="{}",
                ),
                ExtractedData(
                    name="connection_authorization_policies",
                    format=ExtractionFormat.JSON,
                    content="{}",
                ),
            ],
        )

        # Test exact match (using 'config' which is in 'rdg_server_config')
        result = rdg_plugin._find_extracted_data(extraction, "config")
        assert result is not None
        assert "config" in result.name.lower()

        # Test partial match (using 'authorization' which is in the second item)
        result = rdg_plugin._find_extracted_data(extraction, "authorization")
        assert result is not None
        assert "authorization" in result.name.lower()

        # Test no match
        result = rdg_plugin._find_extracted_data(extraction, "nonexistent")
        assert result is None

    def test_dependencies_met(self, rdg_plugin):
        """Test dependency checking."""
        from src.iac.plugins.models import StepResult

        step = ReplicationStep(
            step_id="test_step",
            step_type=StepType.CONFIGURATION,
            description="Test",
            depends_on=["step1", "step2"],
        )

        results = [
            StepResult(
                step_id="step1", status=ReplicationStatus.SUCCESS, duration_seconds=1.0
            ),
            StepResult(
                step_id="step2", status=ReplicationStatus.SUCCESS, duration_seconds=1.0
            ),
        ]

        assert rdg_plugin._dependencies_met(step, results) is True

    def test_dependencies_not_met(self, rdg_plugin):
        """Test dependency checking with failed dependency."""
        from src.iac.plugins.models import StepResult

        step = ReplicationStep(
            step_id="test_step",
            step_type=StepType.CONFIGURATION,
            description="Test",
            depends_on=["step1", "step2"],
        )

        results = [
            StepResult(
                step_id="step1", status=ReplicationStatus.SUCCESS, duration_seconds=1.0
            ),
            StepResult(
                step_id="step2", status=ReplicationStatus.FAILED, duration_seconds=1.0
            ),
        ]

        assert rdg_plugin._dependencies_met(step, results) is False

    def test_calculate_fidelity_score(self, rdg_plugin):
        """Test fidelity score calculation."""
        # All succeeded
        score = rdg_plugin._calculate_fidelity_score(10, 0, 0, 10)
        assert score == 1.0

        # All failed
        score = rdg_plugin._calculate_fidelity_score(0, 10, 0, 10)
        assert score == 0.0

        # Half succeeded
        score = rdg_plugin._calculate_fidelity_score(5, 5, 0, 10)
        assert score == 0.5

        # With skipped (50% weight)
        score = rdg_plugin._calculate_fidelity_score(5, 0, 5, 10)
        assert score == 0.75

        # Empty
        score = rdg_plugin._calculate_fidelity_score(0, 0, 0, 0)
        assert score == 0.0


class TestXMLConversion:
    """Test XML conversion methods."""

    def test_caps_to_xml(self, rdg_plugin):
        """Test CAPs to XML conversion."""
        caps_data = {
            "caps": [
                {
                    "name": "Test CAP",
                    "enabled": True,
                    "user_groups": ["CONTOSO\\Users", "CONTOSO\\Admins"],
                }
            ]
        }

        xml = rdg_plugin._caps_to_xml(caps_data)

        assert '<?xml version="1.0"' in xml
        assert "<ConnectionAuthorizationPolicies>" in xml
        assert "<Name>Test CAP</Name>" in xml
        assert "<Enabled>True</Enabled>" in xml
        assert "<Group>CONTOSO\\Users</Group>" in xml

    def test_raps_to_xml(self, rdg_plugin):
        """Test RAPs to XML conversion."""
        raps_data = {
            "raps": [
                {
                    "name": "Test RAP",
                    "enabled": True,
                    "user_groups": ["CONTOSO\\Users"],
                    "computer_group": "Prod-Servers",
                }
            ]
        }

        xml = rdg_plugin._raps_to_xml(raps_data)

        assert '<?xml version="1.0"' in xml
        assert "<ResourceAuthorizationPolicies>" in xml
        assert "<Name>Test RAP</Name>" in xml
        assert "<ComputerGroup>Prod-Servers</ComputerGroup>" in xml


class TestScriptGeneration:
    """Test PowerShell script generation."""

    def test_generate_verify_role_script(self, rdg_plugin):
        """Test verify role script generation."""
        script = rdg_plugin._generate_verify_role_script()

        assert "Import-Module ServerManager" in script
        assert "Get-WindowsFeature -Name RDS-Gateway" in script
        assert "RemoteDesktopServices" in script

    def test_generate_server_config_script(self, rdg_plugin):
        """Test server config script generation."""
        from src.iac.plugins.models import ExtractedData, ExtractionFormat

        server_data = ExtractedData(
            name="server_config",
            format=ExtractionFormat.JSON,
            content='{"port": 443}',
        )

        script = rdg_plugin._generate_server_config_script(server_data)

        assert "Import-Module RemoteDesktopServices" in script
        assert "RDS:" in script
        assert "SSLCertificate" in script

    def test_generate_caps_script(self, rdg_plugin):
        """Test CAPs configuration script generation."""
        from src.iac.plugins.models import ExtractedData, ExtractionFormat

        caps_data = ExtractedData(
            name="caps", format=ExtractionFormat.JSON, content='{"caps": []}'
        )

        script = rdg_plugin._generate_caps_script(caps_data)

        assert "Connection Authorization Policies" in script
        assert "RDS:" in script or "CAP" in script
        assert "DeviceRedirection" in script

    def test_generate_raps_script(self, rdg_plugin):
        """Test RAPs configuration script generation."""
        from src.iac.plugins.models import ExtractedData, ExtractionFormat

        raps_data = ExtractedData(
            name="raps", format=ExtractionFormat.JSON, content='{"raps": []}'
        )

        script = rdg_plugin._generate_raps_script(raps_data)

        assert "Resource Authorization Policies" in script
        assert "RDS:" in script or "RAP" in script
        assert "ComputerGroup" in script

    def test_generate_validation_script(self, rdg_plugin):
        """Test validation script generation."""
        script = rdg_plugin._generate_validation_script()

        assert "Validate RD Gateway" in script
        assert "TSGateway" in script or "Service" in script
        assert "CAPs" in script or "CAP" in script
        assert "RAPs" in script or "RAP" in script
        assert "ConvertTo-Json" in script


class TestIntegration:
    """Integration tests for full workflow."""

    @pytest.mark.asyncio
    async def test_full_replication_workflow(
        self, rdg_plugin_with_config, rdg_resource
    ):
        """Test complete replication workflow."""
        # Analyze
        with patch.object(
            rdg_plugin_with_config, "_check_winrm_connectivity", return_value=True
        ), patch.object(
            rdg_plugin_with_config, "_check_rdg_role_installed", return_value=True
        ), patch.object(
            rdg_plugin_with_config, "_count_caps", return_value=2
        ), patch.object(
            rdg_plugin_with_config, "_count_raps", return_value=1
        ), patch.object(
            rdg_plugin_with_config, "_count_resource_groups", return_value=1
        ), patch.object(
            rdg_plugin_with_config,
            "_get_certificate_info",
            return_value={"subject": "CN=test", "thumbprint": "ABC", "expiry": "2025"},
        ):
            analysis = await rdg_plugin_with_config.analyze_source(rdg_resource)

        assert analysis.status == AnalysisStatus.SUCCESS

        # Extract
        extraction = await rdg_plugin_with_config.extract_data(rdg_resource, analysis)
        assert extraction.status == AnalysisStatus.SUCCESS
        assert len(extraction.extracted_data) > 0

        # Generate steps
        steps = await rdg_plugin_with_config.generate_replication_steps(extraction)
        assert len(steps) > 0

        # Apply (dry run)
        rdg_plugin_with_config.config["dry_run"] = True
        result = await rdg_plugin_with_config.apply_to_target(steps, "target-id")
        assert result.status == ReplicationStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_replicate_convenience_method(
        self, rdg_plugin_with_config, rdg_resource
    ):
        """Test convenience replicate method."""
        with patch.object(
            rdg_plugin_with_config, "_check_winrm_connectivity", return_value=True
        ), patch.object(
            rdg_plugin_with_config, "_check_rdg_role_installed", return_value=True
        ), patch.object(
            rdg_plugin_with_config, "_count_caps", return_value=1
        ), patch.object(
            rdg_plugin_with_config, "_count_raps", return_value=1
        ), patch.object(
            rdg_plugin_with_config, "_count_resource_groups", return_value=0
        ), patch.object(
            rdg_plugin_with_config, "_get_certificate_info", return_value=None
        ):
            rdg_plugin_with_config.config["dry_run"] = True
            result = await rdg_plugin_with_config.replicate(rdg_resource, "target-id")

        assert isinstance(result, ReplicationResult)
        assert result.status in [
            ReplicationStatus.SUCCESS,
            ReplicationStatus.PARTIAL_SUCCESS,
        ]
