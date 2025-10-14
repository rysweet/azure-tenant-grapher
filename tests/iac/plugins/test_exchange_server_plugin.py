"""Tests for Exchange Server replication plugin."""

import json
from pathlib import Path

import pytest

from src.iac.plugins.exchange_server_plugin import ExchangeServerReplicationPlugin
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
    return ExchangeServerReplicationPlugin(
        config={"output_dir": "/tmp/exchange_test", "dry_run": True}
    )


@pytest.fixture
def exchange_resource():
    """Create mock Exchange Server VM resource."""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-ex",
        "name": "atevet12ex001",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "tags": {"role": "exchange"},
        "properties": {
            "osProfile": {"computerName": "ATEVET12EX001"},
            "hardwareProfile": {"vmSize": "Standard_D4s_v3"},
        },
    }


@pytest.fixture
def exchange_resource_mail():
    """Create mock Exchange Server VM with mail role tag."""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-mail",
        "name": "mail-server-01",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "westus",
        "tags": {"role": "mail"},
        "properties": {"osProfile": {"computerName": "MAIL01"}},
    }


@pytest.fixture
def non_exchange_resource():
    """Create mock non-Exchange resource."""
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
        resource_id="/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-ex",
        resource_type="Microsoft.Compute/virtualMachines",
        status=AnalysisStatus.SUCCESS,
        elements=[
            DataPlaneElement(
                name="exchange_organization",
                element_type="Exchange Organization",
                description="Exchange Org: Simuland",
                complexity="MEDIUM",
                estimated_size_mb=0.5,
                dependencies=[],
            ),
            DataPlaneElement(
                name="mailbox_databases",
                element_type="Mailbox Databases",
                description="2 mailbox databases",
                complexity="HIGH",
                estimated_size_mb=1.0,
                dependencies=["exchange_organization"],
            ),
            DataPlaneElement(
                name="mailboxes",
                element_type="Mailboxes",
                description="25 mailboxes (metadata only)",
                complexity="VERY_HIGH",
                estimated_size_mb=2.5,
                dependencies=["mailbox_databases"],
            ),
            DataPlaneElement(
                name="distribution_groups",
                element_type="Distribution Groups",
                description="10 distribution groups",
                complexity="MEDIUM",
                estimated_size_mb=0.5,
                dependencies=["exchange_organization"],
            ),
            DataPlaneElement(
                name="mail_flow",
                element_type="Mail Flow",
                description="5 transport rules, 4 connectors",
                complexity="HIGH",
                estimated_size_mb=0.5,
                dependencies=["exchange_organization"],
            ),
            DataPlaneElement(
                name="client_access",
                element_type="Client Access",
                description="10 virtual directories",
                complexity="HIGH",
                estimated_size_mb=0.3,
                dependencies=["exchange_organization"],
            ),
        ],
        total_estimated_size_mb=5.3,
        complexity_score=9,
        requires_credentials=True,
        requires_network_access=True,
        connection_methods=["WinRM", "PowerShell", "Exchange Management Shell"],
        estimated_extraction_time_minutes=90,
    )


class TestPluginMetadata:
    """Test plugin metadata."""

    def test_metadata_structure(self, plugin):
        """Test that metadata has correct structure."""
        metadata = plugin.metadata

        assert metadata.name == "exchange_server"
        assert metadata.version == "1.0.0"
        assert isinstance(metadata.description, str)
        assert "Microsoft.Compute/virtualMachines" in metadata.resource_types
        assert metadata.requires_credentials is True
        assert metadata.requires_network_access is True
        assert metadata.complexity == "VERY_HIGH"
        assert metadata.estimated_effort_weeks >= 4.0

    def test_supported_formats(self, plugin):
        """Test that plugin supports expected formats."""
        metadata = plugin.metadata

        assert ExtractionFormat.POWERSHELL_DSC in metadata.supported_formats
        assert ExtractionFormat.JSON in metadata.supported_formats
        assert ExtractionFormat.CSV in metadata.supported_formats

    def test_metadata_tags(self, plugin):
        """Test that metadata has appropriate tags."""
        metadata = plugin.metadata

        assert "exchange" in metadata.tags
        assert "exchange-server" in metadata.tags
        assert "mail" in metadata.tags


class TestResourceDetection:
    """Test resource type detection."""

    def test_can_handle_exchange_by_tag(self, plugin, exchange_resource):
        """Test detection of Exchange Server by tag."""
        assert plugin.can_handle(exchange_resource) is True

    def test_can_handle_exchange_by_mail_tag(self, plugin, exchange_resource_mail):
        """Test detection of Exchange Server by mail tag."""
        assert plugin.can_handle(exchange_resource_mail) is True

    def test_can_handle_exchange_by_name_ex(self, plugin):
        """Test detection of Exchange Server by name pattern (ex)."""
        resource = {
            "id": "test-id",
            "name": "atevet12ex001",
            "type": "Microsoft.Compute/virtualMachines",
            "tags": {},
            "properties": {"osProfile": {"computerName": "EX001"}},
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_exchange_by_name_exchange(self, plugin):
        """Test detection of Exchange Server by name pattern (exchange)."""
        resource = {
            "id": "test-id",
            "name": "exchange-server-01",
            "type": "Microsoft.Compute/virtualMachines",
            "tags": {},
            "properties": {"osProfile": {"computerName": "EXCHANGE01"}},
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_exchange_by_name_mail(self, plugin):
        """Test detection of Exchange Server by name pattern (mail)."""
        resource = {
            "id": "test-id",
            "name": "mail-server",
            "type": "Microsoft.Compute/virtualMachines",
            "tags": {},
            "properties": {"osProfile": {"computerName": "MAIL"}},
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_exchange_by_name_mbx(self, plugin):
        """Test detection of Exchange Server by name pattern (mbx)."""
        resource = {
            "id": "test-id",
            "name": "mbx-server-01",
            "type": "Microsoft.Compute/virtualMachines",
            "tags": {},
            "properties": {"osProfile": {"computerName": "MBX01"}},
        }
        assert plugin.can_handle(resource) is True

    def test_can_handle_exchange_in_tag_value(self, plugin):
        """Test detection by Exchange in tag values."""
        resource = {
            "id": "test-id",
            "name": "server01",
            "type": "Microsoft.Compute/virtualMachines",
            "tags": {"application": "Microsoft Exchange Server 2019"},
            "properties": {"osProfile": {"computerName": "SERVER01"}},
        }
        assert plugin.can_handle(resource) is True

    def test_cannot_handle_non_exchange_resource(self, plugin, non_exchange_resource):
        """Test rejection of non-Exchange resource."""
        assert plugin.can_handle(non_exchange_resource) is False

    def test_cannot_handle_wrong_resource_type(self, plugin):
        """Test rejection of wrong resource type."""
        resource = {
            "id": "test-id",
            "name": "test-exchange",
            "type": "Microsoft.Storage/storageAccounts",
            "tags": {"role": "exchange"},
        }
        assert plugin.can_handle(resource) is False


class TestAnalyzeSource:
    """Test source analysis functionality."""

    @pytest.mark.asyncio
    async def test_analyze_success(self, plugin, exchange_resource):
        """Test successful Exchange Server analysis."""
        analysis = await plugin.analyze_source(exchange_resource)

        assert analysis.status == AnalysisStatus.SUCCESS
        assert len(analysis.elements) > 0
        assert analysis.requires_credentials is True
        assert analysis.requires_network_access is True
        assert "Exchange Management Shell" in analysis.connection_methods
        assert analysis.complexity_score >= 5

    @pytest.mark.asyncio
    async def test_analyze_discovers_organization(self, plugin, exchange_resource):
        """Test that analysis discovers Exchange organization."""
        analysis = await plugin.analyze_source(exchange_resource)

        org_element = next(
            (e for e in analysis.elements if e.name == "exchange_organization"), None
        )
        assert org_element is not None
        assert org_element.element_type == "Exchange Organization"
        assert "Exchange Org" in org_element.description

    @pytest.mark.asyncio
    async def test_analyze_discovers_mailbox_databases(self, plugin, exchange_resource):
        """Test that analysis discovers mailbox databases."""
        analysis = await plugin.analyze_source(exchange_resource)

        db_element = next(
            (e for e in analysis.elements if e.name == "mailbox_databases"), None
        )
        assert db_element is not None
        assert "database" in db_element.description.lower()

    @pytest.mark.asyncio
    async def test_analyze_discovers_mailboxes(self, plugin, exchange_resource):
        """Test that analysis discovers mailboxes."""
        analysis = await plugin.analyze_source(exchange_resource)

        mailbox_element = next(
            (e for e in analysis.elements if e.name == "mailboxes"), None
        )
        assert mailbox_element is not None
        assert "mailbox" in mailbox_element.description.lower()
        assert "metadata only" in mailbox_element.description.lower()

    @pytest.mark.asyncio
    async def test_analyze_discovers_distribution_groups(self, plugin, exchange_resource):
        """Test that analysis discovers distribution groups."""
        analysis = await plugin.analyze_source(exchange_resource)

        group_element = next(
            (e for e in analysis.elements if e.name == "distribution_groups"), None
        )
        assert group_element is not None
        assert "distribution" in group_element.description.lower()

    @pytest.mark.asyncio
    async def test_analyze_discovers_mail_flow(self, plugin, exchange_resource):
        """Test that analysis discovers mail flow configuration."""
        analysis = await plugin.analyze_source(exchange_resource)

        mail_flow_element = next(
            (e for e in analysis.elements if e.name == "mail_flow"), None
        )
        assert mail_flow_element is not None
        assert "transport" in mail_flow_element.description.lower() or "connector" in mail_flow_element.description.lower()

    @pytest.mark.asyncio
    async def test_analyze_discovers_accepted_domains(self, plugin, exchange_resource):
        """Test that analysis discovers accepted domains."""
        analysis = await plugin.analyze_source(exchange_resource)

        domain_element = next(
            (e for e in analysis.elements if e.name == "accepted_domains"), None
        )
        assert domain_element is not None
        assert "domain" in domain_element.description.lower()

    @pytest.mark.asyncio
    async def test_analyze_discovers_client_access(self, plugin, exchange_resource):
        """Test that analysis discovers client access settings."""
        analysis = await plugin.analyze_source(exchange_resource)

        client_element = next(
            (e for e in analysis.elements if e.name == "client_access"), None
        )
        assert client_element is not None
        assert "virtual" in client_element.description.lower() or "owa" in client_element.description.lower()

    @pytest.mark.asyncio
    async def test_analyze_discovers_public_folders(self, plugin, exchange_resource):
        """Test that analysis discovers public folders."""
        analysis = await plugin.analyze_source(exchange_resource)

        pf_element = next(
            (e for e in analysis.elements if e.name == "public_folders"), None
        )
        assert pf_element is not None
        assert "public folder" in pf_element.description.lower()

    @pytest.mark.asyncio
    async def test_analyze_calculates_size(self, plugin, exchange_resource):
        """Test that analysis calculates total size."""
        analysis = await plugin.analyze_source(exchange_resource)

        assert analysis.total_estimated_size_mb > 0
        assert analysis.total_estimated_size_mb == sum(
            e.estimated_size_mb for e in analysis.elements
        )

    @pytest.mark.asyncio
    async def test_analyze_estimates_time(self, plugin, exchange_resource):
        """Test that analysis estimates extraction time."""
        analysis = await plugin.analyze_source(exchange_resource)

        assert analysis.estimated_extraction_time_minutes >= 20

    @pytest.mark.asyncio
    async def test_analyze_warns_about_mailbox_content(self, plugin, exchange_resource):
        """Test that analysis warns about mailbox content not being extracted."""
        analysis = await plugin.analyze_source(exchange_resource)

        # Should have warning about mailbox content
        content_warning = any("content" in w.lower() and "native" in w.lower() for w in analysis.warnings)
        assert content_warning is True


class TestExtractData:
    """Test data extraction functionality."""

    @pytest.mark.asyncio
    async def test_extract_success(
        self, plugin, exchange_resource, mock_analysis, tmp_path
    ):
        """Test successful data extraction."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(exchange_resource, mock_analysis)

        assert extraction.status in [
            AnalysisStatus.SUCCESS,
            AnalysisStatus.PARTIAL,
        ]
        assert len(extraction.extracted_data) > 0
        assert extraction.items_extracted > 0
        assert extraction.extraction_duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_extract_creates_files(
        self, plugin, exchange_resource, mock_analysis, tmp_path
    ):
        """Test that extraction creates output files."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(exchange_resource, mock_analysis)

        # Check that at least one file was created
        for data in extraction.extracted_data:
            if data.file_path:
                assert Path(data.file_path).exists()

    @pytest.mark.asyncio
    async def test_extract_organization_config(
        self, plugin, exchange_resource, mock_analysis, tmp_path
    ):
        """Test extraction of organization configuration."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(exchange_resource, mock_analysis)

        org_data = next(
            (d for d in extraction.extracted_data if "organization" in d.name.lower()), None
        )
        assert org_data is not None
        assert org_data.format == ExtractionFormat.JSON

        # Verify content is valid JSON
        content = json.loads(org_data.content)
        assert "organization_name" in content or "exchange_version" in content

    @pytest.mark.asyncio
    async def test_extract_mailbox_databases(
        self, plugin, exchange_resource, mock_analysis, tmp_path
    ):
        """Test extraction of mailbox databases."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(exchange_resource, mock_analysis)

        db_data = next(
            (d for d in extraction.extracted_data if "mailbox_database" in d.name.lower()),
            None,
        )
        assert db_data is not None
        assert db_data.format == ExtractionFormat.JSON

        # Verify databases in content
        content = json.loads(db_data.content)
        assert "databases" in content

    @pytest.mark.asyncio
    async def test_extract_mailboxes(
        self, plugin, exchange_resource, mock_analysis, tmp_path
    ):
        """Test extraction of mailbox metadata."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(exchange_resource, mock_analysis)

        mailbox_data = next(
            (d for d in extraction.extracted_data if "mailbox" in d.name.lower() and "database" not in d.name.lower()),
            None,
        )
        assert mailbox_data is not None
        assert mailbox_data.format == ExtractionFormat.JSON

        # Verify mailbox metadata structure
        content = json.loads(mailbox_data.content)
        assert "mailboxes" in content or "total_count" in content

    @pytest.mark.asyncio
    async def test_extract_distribution_groups(
        self, plugin, exchange_resource, mock_analysis, tmp_path
    ):
        """Test extraction of distribution groups."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(exchange_resource, mock_analysis)

        group_data = next(
            (d for d in extraction.extracted_data if "distribution_group" in d.name.lower()),
            None,
        )
        assert group_data is not None
        assert group_data.format == ExtractionFormat.JSON

    @pytest.mark.asyncio
    async def test_extract_mail_flow(
        self, plugin, exchange_resource, mock_analysis, tmp_path
    ):
        """Test extraction of mail flow configuration."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(exchange_resource, mock_analysis)

        mail_flow_data = next(
            (d for d in extraction.extracted_data if "mail_flow" in d.name.lower()),
            None,
        )
        assert mail_flow_data is not None
        assert mail_flow_data.format == ExtractionFormat.JSON

        # Verify mail flow components
        content = json.loads(mail_flow_data.content)
        assert "send_connectors" in content or "receive_connectors" in content or "transport_rules" in content

    @pytest.mark.asyncio
    async def test_extract_client_access(
        self, plugin, exchange_resource, mock_analysis, tmp_path
    ):
        """Test extraction of client access settings."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(exchange_resource, mock_analysis)

        client_data = next(
            (d for d in extraction.extracted_data if "client_access" in d.name.lower()),
            None,
        )
        assert client_data is not None
        assert client_data.format == ExtractionFormat.JSON

        # Verify virtual directories
        content = json.loads(client_data.content)
        assert any(key.endswith("_virtual_directories") for key in content.keys())

    @pytest.mark.asyncio
    async def test_extract_includes_checksum(
        self, plugin, exchange_resource, mock_analysis, tmp_path
    ):
        """Test that extracted data includes checksums."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(exchange_resource, mock_analysis)

        for data in extraction.extracted_data:
            assert data.checksum is not None
            assert len(data.checksum) == 64  # SHA256 hex length

    @pytest.mark.asyncio
    async def test_extract_warns_about_mailbox_content(
        self, plugin, exchange_resource, mock_analysis, tmp_path
    ):
        """Test that extraction warns about mailbox content."""
        plugin.config["output_dir"] = str(tmp_path)

        extraction = await plugin.extract_data(exchange_resource, mock_analysis)

        # Should have warning about mailbox content
        content_warning = any(
            "content" in w.lower() and ("native" in w.lower() or "tool" in w.lower())
            for w in extraction.warnings
        )
        assert content_warning is True


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
                    name="organization_config",
                    format=ExtractionFormat.JSON,
                    content='{"organization_name": "Simuland"}',
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
        assert "exchange" in prereq_step.description.lower()

    @pytest.mark.asyncio
    async def test_steps_have_dependencies(self, plugin, tmp_path):
        """Test that steps have proper dependency ordering."""
        extraction = ExtractionResult(
            resource_id="test-id",
            status=AnalysisStatus.SUCCESS,
            extracted_data=[
                ExtractedData(
                    name="organization_config",
                    format=ExtractionFormat.JSON,
                    content='{"organization_name": "Simuland"}',
                    size_bytes=100,
                ),
                ExtractedData(
                    name="mailbox_databases",
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
    async def test_step_scripts_are_powershell(self, plugin, tmp_path):
        """Test that generated scripts are PowerShell."""
        extraction = ExtractionResult(
            resource_id="test-id",
            status=AnalysisStatus.SUCCESS,
            extracted_data=[
                ExtractedData(
                    name="mailbox_databases",
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
            assert step.script_format == ExtractionFormat.POWERSHELL_DSC
            assert len(step.script_content) > 0

    @pytest.mark.asyncio
    async def test_organization_config_step(self, plugin, tmp_path):
        """Test organization configuration step generation."""
        extraction = ExtractionResult(
            resource_id="test-id",
            status=AnalysisStatus.SUCCESS,
            extracted_data=[
                ExtractedData(
                    name="organization_config",
                    format=ExtractionFormat.JSON,
                    content='{"organization_name": "Simuland"}',
                    size_bytes=100,
                )
            ],
            total_size_mb=0.1,
            extraction_duration_seconds=1.0,
            items_extracted=1,
            items_failed=0,
        )

        steps = await plugin.generate_replication_steps(extraction)

        org_step = next(
            (s for s in steps if "organization" in s.step_id.lower()), None
        )
        assert org_step is not None
        assert org_step.script_format == ExtractionFormat.POWERSHELL_DSC

    @pytest.mark.asyncio
    async def test_database_creation_step(self, plugin, tmp_path):
        """Test database creation step generation."""
        extraction = ExtractionResult(
            resource_id="test-id",
            status=AnalysisStatus.SUCCESS,
            extracted_data=[
                ExtractedData(
                    name="mailbox_databases",
                    format=ExtractionFormat.JSON,
                    content='{"databases": [{"name": "MailboxDB01"}]}',
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
            (s for s in steps if "mailbox_database" in s.step_id.lower()), None
        )
        assert db_step is not None
        assert db_step.script_format == ExtractionFormat.POWERSHELL_DSC

    @pytest.mark.asyncio
    async def test_mailbox_creation_step(self, plugin, tmp_path):
        """Test mailbox creation step generation."""
        extraction = ExtractionResult(
            resource_id="test-id",
            status=AnalysisStatus.SUCCESS,
            extracted_data=[
                ExtractedData(
                    name="mailboxes",
                    format=ExtractionFormat.JSON,
                    content='{"mailboxes": [{"alias": "user1"}]}',
                    size_bytes=100,
                )
            ],
            total_size_mb=0.1,
            extraction_duration_seconds=1.0,
            items_extracted=1,
            items_failed=0,
        )

        steps = await plugin.generate_replication_steps(extraction)

        mailbox_step = next(
            (s for s in steps if "mailbox" in s.step_id.lower() and "database" not in s.step_id.lower()), None
        )
        assert mailbox_step is not None
        assert "metadata only" in mailbox_step.description.lower() or "content" in mailbox_step.description.lower()

    @pytest.mark.asyncio
    async def test_mail_flow_step(self, plugin, tmp_path):
        """Test mail flow configuration step generation."""
        extraction = ExtractionResult(
            resource_id="test-id",
            status=AnalysisStatus.SUCCESS,
            extracted_data=[
                ExtractedData(
                    name="mail_flow",
                    format=ExtractionFormat.JSON,
                    content='{"send_connectors": [], "transport_rules": []}',
                    size_bytes=100,
                )
            ],
            total_size_mb=0.1,
            extraction_duration_seconds=1.0,
            items_extracted=1,
            items_failed=0,
        )

        steps = await plugin.generate_replication_steps(extraction)

        mail_flow_step = next(
            (s for s in steps if "mail_flow" in s.step_id.lower()), None
        )
        assert mail_flow_step is not None
        assert "connector" in mail_flow_step.description.lower() or "transport" in mail_flow_step.description.lower()

    @pytest.mark.asyncio
    async def test_client_access_step(self, plugin, tmp_path):
        """Test client access configuration step generation."""
        extraction = ExtractionResult(
            resource_id="test-id",
            status=AnalysisStatus.SUCCESS,
            extracted_data=[
                ExtractedData(
                    name="client_access",
                    format=ExtractionFormat.JSON,
                    content='{"owa_virtual_directories": []}',
                    size_bytes=100,
                )
            ],
            total_size_mb=0.1,
            extraction_duration_seconds=1.0,
            items_extracted=1,
            items_failed=0,
        )

        steps = await plugin.generate_replication_steps(extraction)

        client_step = next(
            (s for s in steps if "client_access" in s.step_id.lower()), None
        )
        assert client_step is not None
        assert "virtual" in client_step.description.lower() or "owa" in client_step.description.lower()


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
                script_content="Write-Host 'Test'",
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
                script_content="Write-Host 'Step 1'",
                script_format=ExtractionFormat.POWERSHELL_DSC,
            ),
            ReplicationStep(
                step_id="step2",
                step_type=StepType.CONFIGURATION,
                description="Step 2",
                script_content="Write-Host 'Step 2'",
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
                script_content="Write-Host 'Step 1'",
                script_format=ExtractionFormat.POWERSHELL_DSC,
            ),
            ReplicationStep(
                step_id="step2",
                step_type=StepType.CONFIGURATION,
                description="Step 2",
                script_content="Write-Host 'Step 2'",
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
                script_content="Write-Host 'Test'",
                script_format=ExtractionFormat.POWERSHELL_DSC,
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
                script_content="Write-Host 'Test'",
                script_format=ExtractionFormat.POWERSHELL_DSC,
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
                complexity="MEDIUM",
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

    def test_calculate_complexity_score_very_high(self, plugin):
        """Test complexity score increases for very high complexity elements."""
        elements = [
            DataPlaneElement(
                name="elem1",
                element_type="type1",
                description="desc1",
                complexity="VERY_HIGH",
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
        assert score >= 7

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
            script_content="Write-Host 'Test'",
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
            script_content="Write-Host 'Test'",
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
            script_content="Write-Host 'Test'",
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

    def test_find_extracted_data_found(self, plugin):
        """Test finding extracted data by pattern."""
        extraction = ExtractionResult(
            resource_id="test-id",
            status=AnalysisStatus.SUCCESS,
            extracted_data=[
                ExtractedData(
                    name="organization_config",
                    format=ExtractionFormat.JSON,
                    content="{}",
                    size_bytes=2,
                ),
                ExtractedData(
                    name="mailbox_databases",
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

        result = plugin._find_extracted_data(extraction, "organization")
        assert result is not None
        assert result.name == "organization_config"

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
        plugin = ExchangeServerReplicationPlugin(config=config)

        assert plugin.get_config_value("output_dir") == "/custom/path"
        assert plugin.get_config_value("dry_run") is True

    def test_plugin_default_config(self):
        """Test plugin with default configuration."""
        plugin = ExchangeServerReplicationPlugin()

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
        assert "Exchange" in script or "exchange" in script

    def test_generate_organization_config_script(self, plugin):
        """Test organization configuration script generation."""
        data = ExtractedData(
            name="organization_config",
            format=ExtractionFormat.JSON,
            content='{"organization_name": "Simuland"}',
            size_bytes=20,
        )

        script = plugin._generate_organization_config_script(data)

        assert len(script) > 0
        assert "OrganizationConfig" in script or "organization" in script.lower()

    def test_generate_database_creation_script(self, plugin):
        """Test database creation script generation."""
        data = ExtractedData(
            name="mailbox_databases",
            format=ExtractionFormat.JSON,
            content='{"databases": []}',
            size_bytes=20,
        )

        script = plugin._generate_database_creation_script(data)

        assert len(script) > 0
        assert "New-MailboxDatabase" in script or "MailboxDatabase" in script

    def test_generate_mailbox_creation_script(self, plugin):
        """Test mailbox creation script generation."""
        data = ExtractedData(
            name="mailboxes",
            format=ExtractionFormat.JSON,
            content='{"mailboxes": []}',
            size_bytes=20,
        )

        script = plugin._generate_mailbox_creation_script(data)

        assert len(script) > 0
        assert "Mailbox" in script
        # Should warn about content migration
        assert "content" in script.lower() or "migration" in script.lower()

    def test_generate_mail_flow_script(self, plugin):
        """Test mail flow configuration script generation."""
        data = ExtractedData(
            name="mail_flow",
            format=ExtractionFormat.JSON,
            content='{"send_connectors": [], "transport_rules": []}',
            size_bytes=20,
        )

        script = plugin._generate_mail_flow_script(data)

        assert len(script) > 0
        assert "Connector" in script or "Transport" in script

    def test_generate_client_access_script(self, plugin):
        """Test client access configuration script generation."""
        data = ExtractedData(
            name="client_access",
            format=ExtractionFormat.JSON,
            content='{"owa_virtual_directories": []}',
            size_bytes=20,
        )

        script = plugin._generate_client_access_script(data)

        assert len(script) > 0
        assert "VirtualDirectory" in script or "Owa" in script or "EWS" in script

    def test_generate_validation_script(self, plugin):
        """Test validation script generation."""
        script = plugin._generate_validation_script()

        assert len(script) > 0
        assert "validation" in script.lower() or "validate" in script.lower()


class TestIntegration:
    """Integration tests for full workflow."""

    @pytest.mark.asyncio
    async def test_full_replication_workflow(self, plugin, exchange_resource, tmp_path):
        """Test full replication workflow from analysis to application."""
        plugin.config["output_dir"] = str(tmp_path)
        plugin.config["dry_run"] = True

        # Step 1: Analyze
        analysis = await plugin.analyze_source(exchange_resource)
        assert analysis.status == AnalysisStatus.SUCCESS

        # Step 2: Extract
        extraction = await plugin.extract_data(exchange_resource, analysis)
        assert extraction.status in [
            AnalysisStatus.SUCCESS,
            AnalysisStatus.PARTIAL,
        ]

        # Step 3: Generate steps
        steps = await plugin.generate_replication_steps(extraction)
        assert len(steps) > 0

        # Step 4: Apply to target
        result = await plugin.apply_to_target(steps, "target-exchange-id")
        assert result.status in [
            ReplicationStatus.SUCCESS,
            ReplicationStatus.PARTIAL_SUCCESS,
        ]
        assert result.fidelity_score > 0

    @pytest.mark.asyncio
    async def test_replicate_convenience_method(self, plugin, exchange_resource):
        """Test convenience replicate() method."""
        plugin.config["dry_run"] = True

        result = await plugin.replicate(exchange_resource, "target-exchange-id")

        assert isinstance(result, ReplicationResult)
        assert result.status in [
            ReplicationStatus.SUCCESS,
            ReplicationStatus.PARTIAL_SUCCESS,
        ]

    @pytest.mark.asyncio
    async def test_extract_creates_directory(self, plugin, exchange_resource, tmp_path):
        """Test that extraction creates output directory."""
        output_dir = tmp_path / "exchange_output"
        plugin.config["output_dir"] = str(output_dir)

        mock_analysis = DataPlaneAnalysis(
            resource_id=exchange_resource["id"],
            resource_type=exchange_resource["type"],
            status=AnalysisStatus.SUCCESS,
            elements=[
                DataPlaneElement(
                    name="exchange_organization",
                    element_type="Config",
                    description="Exchange organization",
                    complexity="MEDIUM",
                    estimated_size_mb=0.5,
                )
            ],
            total_estimated_size_mb=0.5,
            complexity_score=5,
        )

        await plugin.extract_data(exchange_resource, mock_analysis)

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
                script_content="Write-Host 'First'",
                script_format=ExtractionFormat.POWERSHELL_DSC,
            ),
            ReplicationStep(
                step_id="step_b",
                step_type=StepType.CONFIGURATION,
                description="Second",
                script_content="Write-Host 'Second'",
                script_format=ExtractionFormat.POWERSHELL_DSC,
                depends_on=["step_a"],
            ),
            ReplicationStep(
                step_id="step_c",
                step_type=StepType.VALIDATION,
                description="Third",
                script_content="Write-Host 'Third'",
                script_format=ExtractionFormat.POWERSHELL_DSC,
                depends_on=["step_b"],
            ),
        ]

        result = await plugin.apply_to_target(steps, "target-id")

        # All steps should execute in order
        assert len(result.steps_executed) == 3
        assert result.steps_executed[0].step_id == "step_a"
        assert result.steps_executed[1].step_id == "step_b"
        assert result.steps_executed[2].step_id == "step_c"

    @pytest.mark.asyncio
    async def test_mailbox_csv_generation(self, plugin, exchange_resource, tmp_path):
        """Test that mailbox extraction creates CSV file."""
        plugin.config["output_dir"] = str(tmp_path)

        mock_analysis = DataPlaneAnalysis(
            resource_id=exchange_resource["id"],
            resource_type=exchange_resource["type"],
            status=AnalysisStatus.SUCCESS,
            elements=[
                DataPlaneElement(
                    name="mailboxes",
                    element_type="Mailboxes",
                    description="25 mailboxes",
                    complexity="VERY_HIGH",
                    estimated_size_mb=2.5,
                )
            ],
            total_estimated_size_mb=2.5,
            complexity_score=8,
        )

        await plugin.extract_data(exchange_resource, mock_analysis)

        # Check for CSV file
        csv_file = tmp_path / "mailboxes.csv"
        assert csv_file.exists()
        assert csv_file.read_text().startswith("DisplayName,")
