"""Tests for Storage Account Data replication plugin."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.iac.plugins.models import (
    AnalysisStatus,
    DataPlaneAnalysis,
    ExtractionResult,
    ReplicationResult,
    ReplicationStatus,
    ReplicationStep,
    StepResult,
    StepType,
)
from src.iac.plugins.storage_data_plugin import StorageDataReplicationPlugin


class TestStorageDataReplicationPlugin:
    """Test suite for StorageDataReplicationPlugin."""

    @pytest.fixture
    def plugin(self):
        """Create plugin instance with test configuration."""
        config = {
            "output_dir": "/tmp/test_storage_extraction",
            "dry_run": True,
            "max_blobs_per_container": 1000,
            "include_sample_data": True,
            "azcopy_path": "azcopy",
            "strict_validation": False,
            "generate_sas_tokens": True,
            "sas_expiry_hours": 24,
        }
        return StorageDataReplicationPlugin(config)

    @pytest.fixture
    def storage_account_resource(self):
        """Create mock storage account resource."""
        return {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage001",
            "name": "teststorage001",
            "type": "Microsoft.Storage/storageAccounts",
            "location": "eastus",
            "tags": {
                "environment": "production",
                "purpose": "data-storage",
            },
            "properties": {
                "primaryEndpoints": {
                    "blob": "https://teststorage001.blob.core.windows.net/",
                    "file": "https://teststorage001.file.core.windows.net/",
                    "table": "https://teststorage001.table.core.windows.net/",
                    "queue": "https://teststorage001.queue.core.windows.net/",
                },
                "provisioningState": "Succeeded",
            },
        }

    @pytest.fixture
    def non_storage_resource(self):
        """Create mock non-storage resource."""
        return {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
            "name": "test-vm",
            "type": "Microsoft.Compute/virtualMachines",
            "location": "eastus",
        }

    def test_plugin_metadata(self, plugin):
        """Test plugin metadata is correctly defined."""
        metadata = plugin.metadata

        assert metadata.name == "storage_data"
        assert metadata.version == "1.0.0"
        assert "Microsoft.Storage/storageAccounts" in metadata.resource_types
        assert metadata.requires_credentials is True
        assert metadata.requires_network_access is True
        assert metadata.complexity == "HIGH"
        assert "storage" in metadata.tags
        assert "blob" in metadata.tags
        assert "azcopy" in metadata.tags

    def test_can_handle_storage_account(self, plugin, storage_account_resource):
        """Test plugin recognizes storage account."""
        assert plugin.can_handle(storage_account_resource) is True

    def test_cannot_handle_non_storage(self, plugin, non_storage_resource):
        """Test plugin rejects non-storage resources."""
        assert plugin.can_handle(non_storage_resource) is False

    def test_cannot_handle_wrong_resource_type(self, plugin):
        """Test plugin rejects wrong resource types."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "test-vm",
        }
        assert plugin.can_handle(resource) is False

    @pytest.mark.asyncio
    async def test_analyze_source_success(self, plugin, storage_account_resource):
        """Test successful analysis of storage account."""
        # Mock connectivity and analysis methods
        plugin._check_storage_connectivity = AsyncMock(return_value=True)
        plugin._analyze_blob_containers = AsyncMock(
            return_value={
                "container_count": 5,
                "blob_count": 1250,
                "total_size_mb": 10240.5,
                "has_lifecycle_policy": True,
                "policy_count": 2,
            }
        )
        plugin._analyze_file_shares = AsyncMock(
            return_value={
                "share_count": 3,
                "file_count": 850,
                "total_size_mb": 5120.0,
            }
        )
        plugin._analyze_tables = AsyncMock(
            return_value={
                "table_count": 4,
                "estimated_entities": 50000,
                "estimated_size_mb": 25.0,
            }
        )
        plugin._analyze_queues = AsyncMock(
            return_value={
                "queue_count": 6,
                "message_count": 1500,
                "estimated_size_mb": 2.5,
            }
        )
        plugin._check_cors_rules = AsyncMock(return_value=True)
        plugin._check_soft_delete = AsyncMock(return_value=True)

        analysis = await plugin.analyze_source(storage_account_resource)

        assert isinstance(analysis, DataPlaneAnalysis)
        assert analysis.status == AnalysisStatus.SUCCESS
        assert len(analysis.elements) == 7  # All elements discovered
        assert analysis.requires_credentials is True
        assert analysis.requires_network_access is True
        assert "HTTPS" in analysis.connection_methods
        assert "azcopy" in analysis.connection_methods
        assert analysis.complexity_score > 0

        # Check specific elements
        element_names = [e.name for e in analysis.elements]
        assert "blob_containers" in element_names
        assert "lifecycle_policies" in element_names
        assert "file_shares" in element_names
        assert "table_storage" in element_names
        assert "queue_storage" in element_names
        assert "cors_rules" in element_names
        assert "soft_delete_settings" in element_names

        # Check warnings
        assert len(analysis.warnings) > 0
        assert any("credentials" in w.lower() for w in analysis.warnings)
        assert any("azcopy" in w.lower() for w in analysis.warnings)

    @pytest.mark.asyncio
    async def test_analyze_source_no_connectivity(self, plugin, storage_account_resource):
        """Test analysis failure when storage is not accessible."""
        plugin._check_storage_connectivity = AsyncMock(
            side_effect=ConnectionError(
                "Cannot connect to Storage Account - check credentials and network access"
            )
        )

        analysis = await plugin.analyze_source(storage_account_resource)

        assert analysis.status == AnalysisStatus.FAILED
        assert len(analysis.errors) > 0
        assert "Cannot connect" in str(analysis.errors[0])

    @pytest.mark.asyncio
    async def test_analyze_source_empty_storage(self, plugin, storage_account_resource):
        """Test analysis when storage account is empty."""
        plugin._check_storage_connectivity = AsyncMock(return_value=True)
        plugin._analyze_blob_containers = AsyncMock(
            return_value={"container_count": 0, "blob_count": 0, "total_size_mb": 0}
        )
        plugin._analyze_file_shares = AsyncMock(
            return_value={"share_count": 0, "file_count": 0, "total_size_mb": 0}
        )
        plugin._analyze_tables = AsyncMock(
            return_value={
                "table_count": 0,
                "estimated_entities": 0,
                "estimated_size_mb": 0,
            }
        )
        plugin._analyze_queues = AsyncMock(
            return_value={"queue_count": 0, "message_count": 0, "estimated_size_mb": 0}
        )
        plugin._check_cors_rules = AsyncMock(return_value=False)
        plugin._check_soft_delete = AsyncMock(return_value=False)

        analysis = await plugin.analyze_source(storage_account_resource)

        assert analysis.status == AnalysisStatus.SUCCESS
        assert len(analysis.elements) == 0
        assert analysis.total_estimated_size_mb == 0

    @pytest.mark.asyncio
    async def test_analyze_source_large_data_warning(
        self, plugin, storage_account_resource
    ):
        """Test analysis warns about large data transfers."""
        plugin._check_storage_connectivity = AsyncMock(return_value=True)
        plugin._analyze_blob_containers = AsyncMock(
            return_value={
                "container_count": 10,
                "blob_count": 50000,
                "total_size_mb": 150000,  # ~146 GB
                "has_lifecycle_policy": False,
            }
        )
        plugin._analyze_file_shares = AsyncMock(
            return_value={"share_count": 0, "file_count": 0, "total_size_mb": 0}
        )
        plugin._analyze_tables = AsyncMock(
            return_value={
                "table_count": 0,
                "estimated_entities": 0,
                "estimated_size_mb": 0,
            }
        )
        plugin._analyze_queues = AsyncMock(
            return_value={"queue_count": 0, "message_count": 0, "estimated_size_mb": 0}
        )
        plugin._check_cors_rules = AsyncMock(return_value=False)
        plugin._check_soft_delete = AsyncMock(return_value=False)

        analysis = await plugin.analyze_source(storage_account_resource)

        assert analysis.status == AnalysisStatus.SUCCESS
        # Should warn about large transfer
        assert any("Large data transfer" in w for w in analysis.warnings)

    @pytest.mark.asyncio
    async def test_extract_data_success(
        self, plugin, storage_account_resource, tmp_path
    ):
        """Test successful data extraction."""
        plugin.config["output_dir"] = str(tmp_path)

        # Create mock analysis
        analysis = DataPlaneAnalysis(
            resource_id=storage_account_resource["id"],
            resource_type=storage_account_resource["type"],
            status=AnalysisStatus.SUCCESS,
            elements=[
                MagicMock(name="blob_containers"),
                MagicMock(name="file_shares"),
                MagicMock(name="table_storage"),
                MagicMock(name="queue_storage"),
                MagicMock(name="lifecycle_policies"),
                MagicMock(name="cors_rules"),
                MagicMock(name="soft_delete_settings"),
            ],
        )

        # Mock extraction methods
        plugin._has_element = MagicMock(return_value=True)

        extraction = await plugin.extract_data(storage_account_resource, analysis)

        assert isinstance(extraction, ExtractionResult)
        assert extraction.status == AnalysisStatus.SUCCESS
        assert extraction.items_extracted == 7
        assert extraction.items_failed == 0
        assert len(extraction.extracted_data) == 7

        # Check output directory was created
        assert tmp_path.exists()

        # Check files were created
        expected_files = [
            "blob_inventory.json",
            "file_share_structure.json",
            "table_schemas.json",
            "queue_metadata.json",
            "lifecycle_policies.json",
            "cors_rules.json",
            "soft_delete_settings.json",
        ]

        for filename in expected_files:
            assert (tmp_path / filename).exists()

        # Check warnings about credentials
        assert any("azcopy" in w.lower() for w in extraction.warnings)
        assert any("credentials" in w.lower() for w in extraction.warnings)

    @pytest.mark.asyncio
    async def test_extract_data_partial_failure(
        self, plugin, storage_account_resource, tmp_path
    ):
        """Test extraction with partial failures."""
        plugin.config["output_dir"] = str(tmp_path)

        analysis = DataPlaneAnalysis(
            resource_id=storage_account_resource["id"],
            resource_type=storage_account_resource["type"],
            status=AnalysisStatus.SUCCESS,
            elements=[
                MagicMock(name="blob_containers"),
                MagicMock(name="file_shares"),
            ],
        )

        # Mock extraction methods - one succeeds, one fails
        plugin._has_element = MagicMock(return_value=True)
        plugin._extract_file_share_structure = AsyncMock(
            side_effect=Exception("Network timeout")
        )

        extraction = await plugin.extract_data(storage_account_resource, analysis)

        assert extraction.status == AnalysisStatus.PARTIAL
        assert extraction.items_extracted > 0
        assert extraction.items_failed > 0
        assert len(extraction.errors) > 0

    @pytest.mark.asyncio
    async def test_extract_data_no_elements(
        self, plugin, storage_account_resource, tmp_path
    ):
        """Test extraction when no elements need extraction."""
        plugin.config["output_dir"] = str(tmp_path)

        analysis = DataPlaneAnalysis(
            resource_id=storage_account_resource["id"],
            resource_type=storage_account_resource["type"],
            status=AnalysisStatus.SUCCESS,
            elements=[],
        )

        extraction = await plugin.extract_data(storage_account_resource, analysis)

        assert extraction.status == AnalysisStatus.SUCCESS
        assert extraction.items_extracted == 0
        assert extraction.items_failed == 0

    @pytest.mark.asyncio
    async def test_generate_replication_steps(self, plugin, tmp_path):
        """Test replication step generation."""
        # Create mock extraction result with proper naming
        blob_mock = MagicMock()
        blob_mock.name = "blob_inventory"
        blob_mock.content = json.dumps(
            {"storage_account": "test", "containers": [{"name": "test-container"}]}
        )
        blob_mock.metadata = {"total_size_mb": 100}

        file_mock = MagicMock()
        file_mock.name = "file_share_structure"
        file_mock.content = json.dumps(
            {"storage_account": "test", "file_shares": [{"name": "test-share"}]}
        )
        file_mock.metadata = {"total_size_mb": 50}

        table_mock = MagicMock()
        table_mock.name = "table_schemas"
        table_mock.content = json.dumps(
            {"storage_account": "test", "tables": [{"name": "TestTable"}]}
        )
        table_mock.metadata = {}

        queue_mock = MagicMock()
        queue_mock.name = "queue_metadata"
        queue_mock.content = json.dumps(
            {"storage_account": "test", "queues": [{"name": "test-queue"}]}
        )
        queue_mock.metadata = {}

        lifecycle_mock = MagicMock()
        lifecycle_mock.name = "lifecycle_policies"
        lifecycle_mock.content = "{}"
        lifecycle_mock.metadata = {}

        cors_mock = MagicMock()
        cors_mock.name = "cors_rules"
        cors_mock.content = "{}"
        cors_mock.metadata = {}

        soft_delete_mock = MagicMock()
        soft_delete_mock.name = "soft_delete_settings"
        soft_delete_mock.content = "{}"
        soft_delete_mock.metadata = {}

        extraction = ExtractionResult(
            resource_id="test-resource-id",
            status=AnalysisStatus.SUCCESS,
            extracted_data=[
                blob_mock,
                file_mock,
                table_mock,
                queue_mock,
                lifecycle_mock,
                cors_mock,
                soft_delete_mock,
            ],
        )

        steps = await plugin.generate_replication_steps(extraction)

        assert isinstance(steps, list)
        assert len(steps) > 0

        # Check step types
        step_types = [s.step_type for s in steps]
        assert StepType.PREREQUISITE in step_types
        assert StepType.CONFIGURATION in step_types
        assert StepType.DATA_IMPORT in step_types
        assert StepType.VALIDATION in step_types

        # Check specific steps
        step_ids = [s.step_id for s in steps]
        assert "prereq_azcopy" in step_ids
        assert "create_blob_containers" in step_ids
        assert "copy_blob_data" in step_ids
        assert "create_file_shares" in step_ids
        assert "copy_file_data" in step_ids
        assert "create_tables" in step_ids
        assert "create_queues" in step_ids
        assert "validate_storage" in step_ids

        # Check dependencies
        prereq_step = next(s for s in steps if s.step_id == "prereq_azcopy")
        assert len(prereq_step.depends_on) == 0

        copy_blob_step = next(s for s in steps if s.step_id == "copy_blob_data")
        assert "create_blob_containers" in copy_blob_step.depends_on

        # Check manual execution flags
        assert copy_blob_step.metadata.get("manual_execution_required") is True

        # Check scripts are generated
        for step in steps:
            assert len(step.script_content) > 0

    @pytest.mark.asyncio
    async def test_generate_replication_steps_minimal(self, plugin):
        """Test step generation with minimal extracted data."""
        extraction = ExtractionResult(
            resource_id="test-resource-id",
            status=AnalysisStatus.SUCCESS,
            extracted_data=[],
        )

        steps = await plugin.generate_replication_steps(extraction)

        # Should still have prerequisite and validation
        assert len(steps) >= 2
        step_ids = [s.step_id for s in steps]
        assert "prereq_azcopy" in step_ids
        assert "validate_storage" in step_ids

    @pytest.mark.asyncio
    async def test_apply_to_target_success(self, plugin):
        """Test successful application to target."""
        steps = [
            ReplicationStep(
                step_id="test_step_1",
                step_type=StepType.PREREQUISITE,
                description="Test step 1",
                script_content="#!/bin/bash\necho 'Test'",
                depends_on=[],
                is_critical=True,
            ),
            ReplicationStep(
                step_id="test_step_2",
                step_type=StepType.CONFIGURATION,
                description="Test step 2",
                script_content="terraform apply",
                depends_on=["test_step_1"],
                is_critical=False,
            ),
        ]

        result = await plugin.apply_to_target(steps, "target-resource-id")

        assert isinstance(result, ReplicationResult)
        assert result.target_resource_id == "target-resource-id"
        assert result.status == ReplicationStatus.SUCCESS
        assert result.steps_succeeded == 2
        assert result.steps_failed == 0
        assert result.fidelity_score > 0

        # Check dry run warning
        assert any("Dry run" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_apply_to_target_with_manual_steps(self, plugin):
        """Test application with manual execution steps.

        Note: In dry-run mode (default for tests), manual steps are simulated like any other step.
        In actual execution (dry_run=False), manual steps would be skipped.
        """
        steps = [
            ReplicationStep(
                step_id="auto_step",
                step_type=StepType.PREREQUISITE,
                description="Auto step",
                script_content="echo 'Auto'",
                depends_on=[],
                is_critical=False,
            ),
            ReplicationStep(
                step_id="manual_step",
                step_type=StepType.DATA_IMPORT,
                description="Manual data copy",
                script_content="azcopy copy ...",
                depends_on=["auto_step"],
                is_critical=True,
                metadata={"manual_execution_required": True},
            ),
        ]

        result = await plugin.apply_to_target(steps, "target-resource-id")

        # In dry run mode, all steps are simulated (including manual ones)
        assert result.status in [ReplicationStatus.SUCCESS, ReplicationStatus.PARTIAL_SUCCESS]
        assert result.steps_succeeded == 2  # Both steps simulated in dry run
        # Check that warnings mention manual execution
        assert any("manual execution" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_apply_to_target_dependency_failure(self, plugin):
        """Test handling of dependency failures."""
        steps = [
            ReplicationStep(
                step_id="step_1",
                step_type=StepType.PREREQUISITE,
                description="Step 1",
                script_content="echo 'Test'",
                depends_on=[],
            ),
            ReplicationStep(
                step_id="step_2",
                step_type=StepType.CONFIGURATION,
                description="Step 2",
                script_content="echo 'Test'",
                depends_on=["nonexistent_step"],
            ),
        ]

        result = await plugin.apply_to_target(steps, "target-resource-id")

        assert result.steps_skipped > 0
        step_results = [r for r in result.steps_executed if isinstance(r, StepResult)]
        skipped = [r for r in step_results if r.status == ReplicationStatus.SKIPPED]
        assert len(skipped) > 0

    @pytest.mark.asyncio
    async def test_apply_to_target_with_actual_execution(self, plugin):
        """Test application with dry_run=False."""
        plugin.config["dry_run"] = False
        plugin._execute_step_on_target = AsyncMock(
            return_value=StepResult(
                step_id="test",
                status=ReplicationStatus.SUCCESS,
                duration_seconds=0.5,
                stdout="Success",
            )
        )

        steps = [
            ReplicationStep(
                step_id="test_step",
                step_type=StepType.CONFIGURATION,
                description="Test",
                script_content="echo 'Test'",
                depends_on=[],
            ),
        ]

        result = await plugin.apply_to_target(steps, "target-resource-id")

        assert result.status == ReplicationStatus.SUCCESS
        plugin._execute_step_on_target.assert_called_once()

    def test_calculate_complexity_score(self, plugin):
        """Test complexity score calculation."""
        elements = [
            MagicMock(complexity="LOW"),
            MagicMock(complexity="MEDIUM"),
            MagicMock(complexity="HIGH"),
        ]

        # Small data size
        score = plugin._calculate_complexity_score(elements, 100)  # 100 MB
        assert isinstance(score, int)
        assert 1 <= score <= 10

        # Large data size (>100 GB)
        score = plugin._calculate_complexity_score(elements, 150 * 1024)
        assert score >= 5

    def test_calculate_complexity_score_empty(self, plugin):
        """Test complexity score with no elements."""
        score = plugin._calculate_complexity_score([], 0)
        assert score == 1

    def test_has_element(self, plugin):
        """Test element checking in analysis."""
        elem1 = MagicMock()
        elem1.name = "blob_containers"

        elem2 = MagicMock()
        elem2.name = "file_shares"

        analysis = DataPlaneAnalysis(
            resource_id="test",
            resource_type="test",
            elements=[elem1, elem2],
        )

        assert plugin._has_element(analysis, "blob_containers") is True
        assert plugin._has_element(analysis, "file_shares") is True
        assert plugin._has_element(analysis, "nonexistent") is False

    def test_find_extracted_data(self, plugin):
        """Test finding extracted data by pattern."""
        data1 = MagicMock()
        data1.name = "blob_inventory"

        data2 = MagicMock()
        data2.name = "file_share_structure"

        data3 = MagicMock()
        data3.name = "table_schemas"

        extraction = ExtractionResult(
            resource_id="test",
            extracted_data=[data1, data2, data3],
        )

        # Test pattern matches
        result = plugin._find_extracted_data(extraction, "blob")
        assert result is not None
        assert result.name == "blob_inventory"

        result = plugin._find_extracted_data(extraction, "file_share")
        assert result is not None

        result = plugin._find_extracted_data(extraction, "table")
        assert result is not None

        # Test no match
        result = plugin._find_extracted_data(extraction, "nonexistent")
        assert result is None

    def test_estimate_transfer_time(self, plugin):
        """Test transfer time estimation."""
        # Small data
        data = MagicMock()
        data.metadata = {"total_size_mb": 100}
        time = plugin._estimate_transfer_time(data)
        assert time >= 5  # Minimum 5 minutes

        # Large data
        data.metadata = {"total_size_mb": 10000}  # ~10 GB
        time = plugin._estimate_transfer_time(data)
        assert time > 10

        # No metadata
        data.metadata = {}
        time = plugin._estimate_transfer_time(data)
        assert time == 10  # Default

    def test_dependencies_met(self, plugin):
        """Test dependency checking."""
        step = ReplicationStep(
            step_id="test",
            step_type=StepType.CONFIGURATION,
            description="Test",
            depends_on=["dep1", "dep2"],
        )

        # All dependencies met
        results = [
            StepResult(
                step_id="dep1",
                status=ReplicationStatus.SUCCESS,
                duration_seconds=1.0,
            ),
            StepResult(
                step_id="dep2",
                status=ReplicationStatus.SUCCESS,
                duration_seconds=1.0,
            ),
        ]
        assert plugin._dependencies_met(step, results) is True

        # One dependency failed
        results[1].status = ReplicationStatus.FAILED
        assert plugin._dependencies_met(step, results) is False

        # Missing dependency
        results = [
            StepResult(
                step_id="dep1",
                status=ReplicationStatus.SUCCESS,
                duration_seconds=1.0,
            ),
        ]
        assert plugin._dependencies_met(step, results) is False

        # No dependencies
        step_no_deps = ReplicationStep(
            step_id="test",
            step_type=StepType.PREREQUISITE,
            description="Test",
            depends_on=[],
        )
        assert plugin._dependencies_met(step_no_deps, []) is True

    def test_calculate_fidelity_score(self, plugin):
        """Test fidelity score calculation."""
        # Perfect execution
        score = plugin._calculate_fidelity_score(
            succeeded=10, failed=0, skipped=0, total=10
        )
        assert score == 1.0

        # Complete failure
        score = plugin._calculate_fidelity_score(
            succeeded=0, failed=10, skipped=0, total=10
        )
        assert score == 0.0

        # Mixed results
        score = plugin._calculate_fidelity_score(
            succeeded=5, failed=3, skipped=2, total=10
        )
        assert 0.0 < score < 1.0

        # Skipped count as half success
        score = plugin._calculate_fidelity_score(
            succeeded=5, failed=0, skipped=5, total=10
        )
        assert score == 0.75  # (5 + 5*0.5) / 10

        # Empty
        score = plugin._calculate_fidelity_score(
            succeeded=0, failed=0, skipped=0, total=0
        )
        assert score == 0.0

    def test_get_config_value(self, plugin):
        """Test configuration value retrieval."""
        assert plugin.get_config_value("dry_run") is True
        assert plugin.get_config_value("max_blobs_per_container") == 1000
        assert plugin.get_config_value("nonexistent", "default") == "default"

    def test_azcopy_check_script(self, plugin):
        """Test azcopy check script generation."""
        script = plugin._generate_azcopy_check_script()

        assert "azcopy" in script.lower()
        assert "--version" in script or "command -v" in script
        assert "#!/bin/bash" in script

    def test_blob_container_terraform(self, plugin):
        """Test blob container Terraform generation."""
        mock_data = MagicMock()
        mock_data.content = json.dumps(
            {
                "storage_account": "test",
                "containers": [
                    {"name": "test-container", "public_access": "None"},
                    {"name": "public-container", "public_access": "Blob"},
                ],
            }
        )

        tf_content = plugin._generate_blob_container_terraform(mock_data)

        assert "terraform" in tf_content
        assert "azurerm_storage_container" in tf_content
        assert "test-container" in tf_content or "test_container" in tf_content
        assert "variable" in tf_content

    def test_blob_copy_script(self, plugin):
        """Test blob copy script generation."""
        mock_data = MagicMock()
        mock_data.content = json.dumps(
            {
                "storage_account": "test",
                "containers": [
                    {
                        "name": "images",
                        "total_size_mb": 1000,
                    }
                ],
            }
        )

        script = plugin._generate_blob_copy_script(mock_data)

        assert "azcopy" in script.lower()
        assert "copy" in script
        assert "blob.core.windows.net" in script
        assert "SAS" in script or "sas" in script
        assert "#!/bin/bash" in script
        assert "IMPORTANT" in script or "UPDATE" in script

    def test_file_share_terraform(self, plugin):
        """Test file share Terraform generation."""
        mock_data = MagicMock()
        mock_data.content = json.dumps(
            {
                "storage_account": "test",
                "file_shares": [
                    {"name": "share1", "quota_gb": 100},
                    {"name": "share2", "quota_gb": 50},
                ],
            }
        )

        tf_content = plugin._generate_file_share_terraform(mock_data)

        assert "terraform" in tf_content
        assert "azurerm_storage_share" in tf_content
        assert "quota" in tf_content
        assert "share1" in tf_content or "share_1" in tf_content

    def test_file_copy_script(self, plugin):
        """Test file copy script generation."""
        mock_data = MagicMock()
        mock_data.content = json.dumps(
            {
                "storage_account": "test",
                "file_shares": [{"name": "fileshare1", "used_gb": 25}],
            }
        )

        script = plugin._generate_file_copy_script(mock_data)

        assert "azcopy" in script.lower()
        assert "file.core.windows.net" in script
        assert "fileshare1" in script
        assert "#!/bin/bash" in script

    def test_table_terraform(self, plugin):
        """Test table storage Terraform generation."""
        mock_data = MagicMock()
        mock_data.content = json.dumps(
            {
                "storage_account": "test",
                "tables": [{"name": "Customers"}, {"name": "Orders"}],
            }
        )

        tf_content = plugin._generate_table_terraform(mock_data)

        assert "terraform" in tf_content
        assert "azurerm_storage_table" in tf_content
        assert "Customers" in tf_content or "customers" in tf_content

    def test_queue_terraform(self, plugin):
        """Test queue storage Terraform generation."""
        mock_data = MagicMock()
        mock_data.content = json.dumps(
            {
                "storage_account": "test",
                "queues": [
                    {"name": "order-queue", "metadata": {"purpose": "orders"}},
                    {"name": "notification-queue", "metadata": {}},
                ],
            }
        )

        tf_content = plugin._generate_queue_terraform(mock_data)

        assert "terraform" in tf_content
        assert "azurerm_storage_queue" in tf_content
        assert "order-queue" in tf_content or "order_queue" in tf_content

    def test_lifecycle_terraform(self, plugin):
        """Test lifecycle policy Terraform generation."""
        mock_data = MagicMock(content="{}")
        tf_content = plugin._generate_lifecycle_terraform(mock_data)

        assert "terraform" in tf_content
        assert "azurerm_storage_management_policy" in tf_content
        assert "tier_to_cool" in tf_content or "tierToCool" in tf_content

    def test_cors_script(self, plugin):
        """Test CORS rules script generation."""
        mock_data = MagicMock(content="{}")
        script = plugin._generate_cors_script(mock_data)

        assert "az storage cors" in script
        assert "#!/bin/bash" in script
        assert "CORS" in script

    def test_soft_delete_script(self, plugin):
        """Test soft delete script generation."""
        mock_data = MagicMock(content="{}")
        script = plugin._generate_soft_delete_script(mock_data)

        assert "soft delete" in script.lower() or "delete-policy" in script
        assert "az storage" in script
        assert "#!/bin/bash" in script

    def test_validation_script(self, plugin):
        """Test validation script generation."""
        script = plugin._generate_validation_script()

        assert "az storage container list" in script
        assert "az storage share list" in script
        assert "az storage table list" in script
        assert "az storage queue list" in script
        assert "#!/bin/bash" in script

    @pytest.mark.asyncio
    async def test_extract_blob_inventory(self, plugin, storage_account_resource, tmp_path):
        """Test blob inventory extraction."""
        data = await plugin._extract_blob_inventory(storage_account_resource, tmp_path)

        assert data.name == "blob_inventory"
        assert data.format.value == "json"
        assert data.file_path == str(tmp_path / "blob_inventory.json")
        assert (tmp_path / "blob_inventory.json").exists()

        # Validate JSON content
        content = json.loads(data.content)
        assert "storage_account" in content
        assert "containers" in content
        assert len(content["containers"]) > 0
        assert "summary" in content

    @pytest.mark.asyncio
    async def test_extract_file_share_structure(
        self, plugin, storage_account_resource, tmp_path
    ):
        """Test file share structure extraction."""
        data = await plugin._extract_file_share_structure(
            storage_account_resource, tmp_path
        )

        assert data.name == "file_share_structure"
        assert (tmp_path / "file_share_structure.json").exists()

        content = json.loads(data.content)
        assert "storage_account" in content
        assert "file_shares" in content
        assert "summary" in content

    @pytest.mark.asyncio
    async def test_extract_table_schemas(self, plugin, storage_account_resource, tmp_path):
        """Test table schema extraction."""
        data = await plugin._extract_table_schemas(storage_account_resource, tmp_path)

        assert data.name == "table_schemas"
        assert (tmp_path / "table_schemas.json").exists()

        content = json.loads(data.content)
        assert "storage_account" in content
        assert "tables" in content
        assert "summary" in content
        # Check sample data inclusion based on config
        assert content["summary"]["sample_data_included"] is True

    @pytest.mark.asyncio
    async def test_extract_table_schemas_no_sample(
        self, plugin, storage_account_resource, tmp_path
    ):
        """Test table schema extraction without sample data."""
        plugin.config["include_sample_data"] = False

        data = await plugin._extract_table_schemas(storage_account_resource, tmp_path)

        content = json.loads(data.content)
        assert content["summary"]["sample_data_included"] is False

    @pytest.mark.asyncio
    async def test_extract_queue_metadata(self, plugin, storage_account_resource, tmp_path):
        """Test queue metadata extraction."""
        data = await plugin._extract_queue_metadata(storage_account_resource, tmp_path)

        assert data.name == "queue_metadata"
        assert (tmp_path / "queue_metadata.json").exists()

        content = json.loads(data.content)
        assert "storage_account" in content
        assert "queues" in content
        assert "summary" in content
        assert "Queue messages are not replicated" in content["summary"]["note"]

    @pytest.mark.asyncio
    async def test_extract_lifecycle_policies(
        self, plugin, storage_account_resource, tmp_path
    ):
        """Test lifecycle policy extraction."""
        data = await plugin._extract_lifecycle_policies(storage_account_resource, tmp_path)

        assert data.name == "lifecycle_policies"
        assert (tmp_path / "lifecycle_policies.json").exists()

        content = json.loads(data.content)
        assert "storage_account" in content
        assert "lifecycle_policies" in content

    @pytest.mark.asyncio
    async def test_extract_cors_rules(self, plugin, storage_account_resource, tmp_path):
        """Test CORS rules extraction."""
        data = await plugin._extract_cors_rules(storage_account_resource, tmp_path)

        assert data.name == "cors_rules"
        assert (tmp_path / "cors_rules.json").exists()

        content = json.loads(data.content)
        assert "storage_account" in content
        assert "cors_rules" in content

    @pytest.mark.asyncio
    async def test_extract_soft_delete_settings(
        self, plugin, storage_account_resource, tmp_path
    ):
        """Test soft delete settings extraction."""
        data = await plugin._extract_soft_delete_settings(
            storage_account_resource, tmp_path
        )

        assert data.name == "soft_delete_settings"
        assert (tmp_path / "soft_delete_settings.json").exists()

        content = json.loads(data.content)
        assert "storage_account" in content
        assert "soft_delete_settings" in content
        assert "blob_soft_delete" in content["soft_delete_settings"]

    @pytest.mark.asyncio
    async def test_full_workflow(self, plugin, storage_account_resource, tmp_path):
        """Test complete workflow: analyze -> extract -> generate -> apply."""
        plugin.config["output_dir"] = str(tmp_path)

        # Mock connectivity
        plugin._check_storage_connectivity = AsyncMock(return_value=True)
        plugin._analyze_blob_containers = AsyncMock(
            return_value={
                "container_count": 2,
                "blob_count": 100,
                "total_size_mb": 500,
                "has_lifecycle_policy": True,
                "policy_count": 1,
            }
        )
        plugin._analyze_file_shares = AsyncMock(
            return_value={"share_count": 1, "file_count": 50, "total_size_mb": 250}
        )
        plugin._analyze_tables = AsyncMock(
            return_value={
                "table_count": 1,
                "estimated_entities": 1000,
                "estimated_size_mb": 5,
            }
        )
        plugin._analyze_queues = AsyncMock(
            return_value={"queue_count": 1, "message_count": 10, "estimated_size_mb": 0.1}
        )
        plugin._check_cors_rules = AsyncMock(return_value=True)
        plugin._check_soft_delete = AsyncMock(return_value=True)

        # Step 1: Analyze
        analysis = await plugin.analyze_source(storage_account_resource)
        assert analysis.status == AnalysisStatus.SUCCESS
        assert len(analysis.elements) > 0

        # Step 2: Extract
        extraction = await plugin.extract_data(storage_account_resource, analysis)
        assert extraction.status == AnalysisStatus.SUCCESS
        assert extraction.items_extracted > 0

        # Step 3: Generate steps
        steps = await plugin.generate_replication_steps(extraction)
        assert len(steps) > 0

        # Step 4: Apply (dry run)
        result = await plugin.apply_to_target(steps, "target-id")
        assert result.status in [
            ReplicationStatus.SUCCESS,
            ReplicationStatus.PARTIAL_SUCCESS,
        ]
        assert result.fidelity_score >= 0.0

    def test_plugin_config_defaults(self):
        """Test plugin initialization with default config."""
        plugin = StorageDataReplicationPlugin()

        assert plugin.get_config_value("dry_run", False) is False
        assert plugin.get_config_value("azcopy_path", "azcopy") == "azcopy"
        assert plugin.get_config_value("include_sample_data", True) is True

    def test_credential_sanitization(self, plugin):
        """Test that credentials are sanitized in outputs."""
        # Check in scripts
        blob_script = plugin._generate_blob_copy_script(
            MagicMock(content=json.dumps({"storage_account": "test", "containers": []}))
        )
        assert "SANITIZED" in blob_script or "UPDATE" in blob_script
        assert "?sv=" in blob_script  # SAS token format

        file_script = plugin._generate_file_copy_script(
            MagicMock(
                content=json.dumps({"storage_account": "test", "file_shares": []})
            )
        )
        assert "SANITIZED" in file_script or "UPDATE" in file_script


class TestStorageDataPluginEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def plugin(self):
        """Create plugin instance."""
        return StorageDataReplicationPlugin({"strict_validation": True})

    @pytest.mark.asyncio
    async def test_strict_validation_mode(self, plugin):
        """Test strict validation mode."""
        resource = {"id": "test", "name": "test-storage"}

        # With strict validation, connectivity check should fail
        result = await plugin._check_storage_connectivity(resource)
        assert result is False

    def test_script_generation_without_data(self, plugin):
        """Test script generation still works with empty data."""
        empty_data = MagicMock(content=json.dumps({"containers": []}))

        # All script generators should handle empty data gracefully
        scripts = [
            plugin._generate_azcopy_check_script(),
            plugin._generate_blob_container_terraform(empty_data),
            plugin._generate_blob_copy_script(empty_data),
            plugin._generate_validation_script(),
        ]

        for script in scripts:
            assert isinstance(script, str)
            assert len(script) > 0

    def test_large_transfer_time_estimation(self, plugin):
        """Test transfer time estimation for large data."""
        large_data = MagicMock()
        large_data.metadata = {"total_size_mb": 1024 * 1000}  # ~1 TB

        time = plugin._estimate_transfer_time(large_data)
        assert time > 100  # Should be hours of transfer time

    def test_complexity_score_scales_with_size(self, plugin):
        """Test complexity score increases with data size."""
        elements = [MagicMock(complexity="MEDIUM")]

        # Small data
        score_small = plugin._calculate_complexity_score(elements, 100)

        # Large data (>100 GB)
        score_large = plugin._calculate_complexity_score(elements, 150 * 1024)

        assert score_large > score_small
