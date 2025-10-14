"""Tests for File Server replication plugin."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.iac.plugins.file_server_plugin import FileServerReplicationPlugin
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


class TestFileServerReplicationPlugin:
    """Test suite for FileServerReplicationPlugin."""

    @pytest.fixture
    def plugin(self):
        """Create plugin instance with test configuration."""
        config = {
            "output_dir": "/tmp/test_fs_extraction",
            "dry_run": True,
            "max_depth": 3,
            "include_file_metadata": True,
            "strict_validation": False,
        }
        return FileServerReplicationPlugin(config)

    @pytest.fixture
    def file_server_resource(self):
        """Create mock file server resource."""
        return {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/atevet12fs001",
            "name": "atevet12fs001",
            "type": "Microsoft.Compute/virtualMachines",
            "location": "eastus",
            "tags": {
                "role": "file-server",
                "environment": "production",
            },
            "properties": {
                "osProfile": {
                    "computerName": "atevet12fs001",
                    "windowsConfiguration": {},
                },
                "storageProfile": {
                    "osDisk": {
                        "osType": "Windows",
                    }
                },
            },
        }

    @pytest.fixture
    def non_file_server_resource(self):
        """Create mock non-file server resource."""
        return {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
            "name": "test-vm",
            "type": "Microsoft.Compute/virtualMachines",
            "location": "eastus",
            "tags": {
                "role": "web-server",
            },
            "properties": {
                "osProfile": {
                    "computerName": "test-vm",
                }
            },
        }

    def test_plugin_metadata(self, plugin):
        """Test plugin metadata is correctly defined."""
        metadata = plugin.metadata

        assert metadata.name == "file_server"
        assert metadata.version == "1.0.0"
        assert "Microsoft.Compute/virtualMachines" in metadata.resource_types
        assert metadata.requires_credentials is True
        assert metadata.requires_network_access is True
        assert metadata.complexity == "HIGH"
        assert "windows" in metadata.tags
        assert "file-server" in metadata.tags

    def test_can_handle_file_server_by_tag(self, plugin, file_server_resource):
        """Test plugin recognizes file server by role tag."""
        assert plugin.can_handle(file_server_resource) is True

    def test_can_handle_file_server_by_name(self, plugin):
        """Test plugin recognizes file server by naming convention."""
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "prodfs001",
            "properties": {
                "osProfile": {"computerName": "windows-server"},
                "storageProfile": {"osDisk": {"osType": "Windows"}},
            },
        }
        assert plugin.can_handle(resource) is True

    def test_cannot_handle_non_file_server(self, plugin, non_file_server_resource):
        """Test plugin rejects non-file server resources."""
        assert plugin.can_handle(non_file_server_resource) is False

    def test_cannot_handle_wrong_resource_type(self, plugin):
        """Test plugin rejects wrong resource types."""
        resource = {
            "type": "Microsoft.Storage/storageAccounts",
            "name": "testfs001",
        }
        assert plugin.can_handle(resource) is False

    @pytest.mark.asyncio
    async def test_analyze_source_success(self, plugin, file_server_resource):
        """Test successful analysis of file server."""
        # Mock connectivity and counting methods
        plugin._check_winrm_connectivity = AsyncMock(return_value=True)
        plugin._count_smb_shares = AsyncMock(return_value=8)
        plugin._estimate_acl_count = AsyncMock(return_value=400)
        plugin._check_dfs_enabled = AsyncMock(return_value=True)
        plugin._count_fsrm_quotas = AsyncMock(return_value=5)
        plugin._count_fsrm_screens = AsyncMock(return_value=3)
        plugin._check_vss_enabled = AsyncMock(return_value=True)

        analysis = await plugin.analyze_source(file_server_resource)

        assert isinstance(analysis, DataPlaneAnalysis)
        assert analysis.status == AnalysisStatus.SUCCESS
        assert len(analysis.elements) == 8  # All elements discovered
        assert analysis.requires_credentials is True
        assert analysis.requires_network_access is True
        assert "WinRM" in analysis.connection_methods
        assert analysis.complexity_score > 0

        # Check specific elements
        element_names = [e.name for e in analysis.elements]
        assert "smb_shares" in element_names
        assert "share_permissions" in element_names
        assert "ntfs_acls" in element_names
        assert "dfs_configuration" in element_names
        assert "fsrm_quotas" in element_names
        assert "fsrm_file_screens" in element_names
        assert "volume_shadow_copies" in element_names
        assert "directory_structure" in element_names

        # Check warnings
        assert len(analysis.warnings) > 0
        assert any("SID translation" in w for w in analysis.warnings)

    @pytest.mark.asyncio
    async def test_analyze_source_no_connectivity(self, plugin, file_server_resource):
        """Test analysis failure when WinRM is not accessible."""
        # Mock connectivity check to raise ConnectionError directly
        plugin._check_winrm_connectivity = AsyncMock(side_effect=ConnectionError("Cannot connect to File Server via WinRM"))

        # This should propagate the ConnectionError
        analysis = await plugin.analyze_source(file_server_resource)

        # Should return failed analysis, not raise
        assert analysis.status == AnalysisStatus.FAILED
        assert len(analysis.errors) > 0
        assert "Cannot connect" in str(analysis.errors[0])

    @pytest.mark.asyncio
    async def test_analyze_source_no_shares(self, plugin, file_server_resource):
        """Test analysis when no shares are found."""
        # Disable file metadata to prevent directory_structure element
        plugin.config["include_file_metadata"] = False
        plugin._check_winrm_connectivity = AsyncMock(return_value=True)
        plugin._count_smb_shares = AsyncMock(return_value=0)
        plugin._estimate_acl_count = AsyncMock(return_value=0)
        plugin._check_dfs_enabled = AsyncMock(return_value=False)
        plugin._count_fsrm_quotas = AsyncMock(return_value=0)
        plugin._count_fsrm_screens = AsyncMock(return_value=0)
        plugin._check_vss_enabled = AsyncMock(return_value=False)

        analysis = await plugin.analyze_source(file_server_resource)

        assert analysis.status == AnalysisStatus.SUCCESS
        assert len(analysis.elements) == 0
        assert analysis.total_estimated_size_mb == 0

    @pytest.mark.asyncio
    async def test_analyze_source_exception_handling(
        self, plugin, file_server_resource
    ):
        """Test analysis handles exceptions gracefully."""
        plugin._check_winrm_connectivity = AsyncMock(
            side_effect=Exception("Connection timeout")
        )

        analysis = await plugin.analyze_source(file_server_resource)

        assert analysis.status == AnalysisStatus.FAILED
        assert len(analysis.errors) > 0
        assert "Connection timeout" in analysis.errors[0]

    @pytest.mark.asyncio
    async def test_extract_data_success(self, plugin, file_server_resource, tmp_path):
        """Test successful data extraction."""
        # Update plugin config to use tmp_path
        plugin.config["output_dir"] = str(tmp_path)

        # Create mock analysis
        analysis = DataPlaneAnalysis(
            resource_id=file_server_resource["id"],
            resource_type=file_server_resource["type"],
            status=AnalysisStatus.SUCCESS,
            elements=[
                MagicMock(name="smb_shares"),
                MagicMock(name="share_permissions"),
                MagicMock(name="ntfs_acls"),
                MagicMock(name="dfs_configuration"),
                MagicMock(name="fsrm_quotas"),
                MagicMock(name="fsrm_file_screens"),
                MagicMock(name="volume_shadow_copies"),
                MagicMock(name="directory_structure"),
            ],
        )

        # Mock extraction methods
        plugin._has_element = MagicMock(return_value=True)

        extraction = await plugin.extract_data(file_server_resource, analysis)

        assert isinstance(extraction, ExtractionResult)
        assert extraction.status == AnalysisStatus.SUCCESS
        assert extraction.items_extracted == 8
        assert extraction.items_failed == 0
        assert len(extraction.extracted_data) == 8

        # Check output directory was created
        assert tmp_path.exists()

        # Check files were created
        expected_files = [
            "smb_shares.json",
            "share_permissions.json",
            "ntfs_acls.sddl",
            "ntfs_acls.csv",
            "dfs_config.json",
            "fsrm_quotas.json",
            "fsrm_file_screens.json",
            "vss_config.json",
            "directory_structure.json",
        ]

        for filename in expected_files:
            assert (tmp_path / filename).exists()

        # Check warnings about SID translation
        assert any("SID" in w for w in extraction.warnings)

    @pytest.mark.asyncio
    async def test_extract_data_partial_failure(
        self, plugin, file_server_resource, tmp_path
    ):
        """Test extraction with partial failures."""
        plugin.config["output_dir"] = str(tmp_path)

        # Create analysis with multiple elements
        analysis = DataPlaneAnalysis(
            resource_id=file_server_resource["id"],
            resource_type=file_server_resource["type"],
            status=AnalysisStatus.SUCCESS,
            elements=[
                MagicMock(name="smb_shares"),
                MagicMock(name="share_permissions"),
            ],
        )

        # Mock extraction methods - one succeeds, one fails
        plugin._has_element = MagicMock(return_value=True)
        plugin._extract_share_permissions = AsyncMock(
            side_effect=Exception("Permission denied")
        )

        extraction = await plugin.extract_data(file_server_resource, analysis)

        assert extraction.status == AnalysisStatus.PARTIAL
        assert extraction.items_extracted > 0
        assert extraction.items_failed > 0
        assert len(extraction.errors) > 0

    @pytest.mark.asyncio
    async def test_extract_data_no_elements(
        self, plugin, file_server_resource, tmp_path
    ):
        """Test extraction when no elements need extraction."""
        plugin.config["output_dir"] = str(tmp_path)

        analysis = DataPlaneAnalysis(
            resource_id=file_server_resource["id"],
            resource_type=file_server_resource["type"],
            status=AnalysisStatus.SUCCESS,
            elements=[],
        )

        extraction = await plugin.extract_data(file_server_resource, analysis)

        assert extraction.status == AnalysisStatus.SUCCESS
        assert extraction.items_extracted == 0
        assert extraction.items_failed == 0

    @pytest.mark.asyncio
    async def test_generate_replication_steps(self, plugin, tmp_path):
        """Test replication step generation."""
        # Create mock extraction result with proper naming
        share_mock = MagicMock()
        share_mock.name = "smb_shares"
        share_mock.content = "{}"

        perm_mock = MagicMock()
        perm_mock.name = "share_permissions"
        perm_mock.content = "{}"

        acl_mock = MagicMock()
        acl_mock.name = "ntfs_acls"
        acl_mock.content = ""

        dfs_mock = MagicMock()
        dfs_mock.name = "dfs_config"
        dfs_mock.content = "{}"

        quota_mock = MagicMock()
        quota_mock.name = "fsrm_quotas"
        quota_mock.content = "{}"

        screen_mock = MagicMock()
        screen_mock.name = "fsrm_file_screens"
        screen_mock.content = "{}"

        vss_mock = MagicMock()
        vss_mock.name = "vss_config"
        vss_mock.content = "{}"

        dir_mock = MagicMock()
        dir_mock.name = "directory_structure"
        dir_mock.content = "{}"

        extraction = ExtractionResult(
            resource_id="test-resource-id",
            status=AnalysisStatus.SUCCESS,
            extracted_data=[
                share_mock,
                perm_mock,
                acl_mock,
                dfs_mock,
                quota_mock,
                screen_mock,
                vss_mock,
                dir_mock,
            ],
        )

        steps = await plugin.generate_replication_steps(extraction)

        assert isinstance(steps, list)
        assert len(steps) > 0

        # Check step types
        step_types = [s.step_type for s in steps]
        assert StepType.PREREQUISITE in step_types
        assert StepType.CONFIGURATION in step_types or StepType.POST_CONFIG in step_types
        assert StepType.VALIDATION in step_types

        # Check specific steps
        step_ids = [s.step_id for s in steps]
        assert "prereq_file_server_features" in step_ids
        assert "create_smb_shares" in step_ids
        assert "apply_share_permissions" in step_ids
        assert "apply_ntfs_acls" in step_ids
        assert "validate_file_server" in step_ids

        # Check dependencies
        prereq_step = next(s for s in steps if s.step_id == "prereq_file_server_features")
        assert len(prereq_step.depends_on) == 0

        create_shares = next(s for s in steps if s.step_id == "create_smb_shares")
        assert "prereq_file_server_features" in create_shares.depends_on

        # Check manual execution flag for file copy
        file_copy_step = next(
            (s for s in steps if s.step_id == "generate_file_copy_script"), None
        )
        if file_copy_step:
            assert file_copy_step.metadata.get("manual_execution_required") is True

        # Check scripts are generated
        for step in steps:
            assert len(step.script_content) > 0
            assert "Write-Host" in step.script_content or "# " in step.script_content

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
        assert "prereq_file_server_features" in step_ids
        assert "validate_file_server" in step_ids

    @pytest.mark.asyncio
    async def test_apply_to_target_success(self, plugin):
        """Test successful application to target."""
        steps = [
            ReplicationStep(
                step_id="test_step_1",
                step_type=StepType.PREREQUISITE,
                description="Test step 1",
                script_content="Write-Host 'Test'",
                depends_on=[],
                is_critical=True,
            ),
            ReplicationStep(
                step_id="test_step_2",
                step_type=StepType.CONFIGURATION,
                description="Test step 2",
                script_content="Write-Host 'Test 2'",
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
    async def test_apply_to_target_with_skipped_steps(self, plugin):
        """Test application with manual execution steps."""
        steps = [
            ReplicationStep(
                step_id="auto_step",
                step_type=StepType.PREREQUISITE,
                description="Auto step",
                script_content="Write-Host 'Auto'",
                depends_on=[],
                is_critical=False,  # Make non-critical so partial success is valid
            ),
            ReplicationStep(
                step_id="manual_step",
                step_type=StepType.POST_CONFIG,
                description="Manual step",
                script_content="Write-Host 'Manual'",
                depends_on=["auto_step"],
                is_critical=False,
                metadata={"manual_execution_required": True},
            ),
        ]

        result = await plugin.apply_to_target(steps, "target-resource-id")

        # With skipped steps, status is PARTIAL_SUCCESS
        assert result.status in [ReplicationStatus.SUCCESS, ReplicationStatus.PARTIAL_SUCCESS]
        assert result.steps_succeeded == 1
        assert result.steps_skipped == 1

    @pytest.mark.asyncio
    async def test_apply_to_target_dependency_failure(self, plugin):
        """Test handling of dependency failures."""
        steps = [
            ReplicationStep(
                step_id="step_1",
                step_type=StepType.PREREQUISITE,
                description="Step 1",
                script_content="Write-Host 'Test'",
                depends_on=[],
            ),
            ReplicationStep(
                step_id="step_2",
                step_type=StepType.CONFIGURATION,
                description="Step 2",
                script_content="Write-Host 'Test'",
                depends_on=["nonexistent_step"],  # Dependency not met
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
                script_content="Write-Host 'Test'",
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
            MagicMock(complexity="HIGH"),
        ]

        score = plugin._calculate_complexity_score(elements)

        assert isinstance(score, int)
        assert 1 <= score <= 10

    def test_calculate_complexity_score_empty(self, plugin):
        """Test complexity score with no elements."""
        score = plugin._calculate_complexity_score([])
        assert score == 1

    def test_has_element(self, plugin):
        """Test element checking in analysis."""
        # Create mock elements with proper name attributes
        elem1 = MagicMock()
        elem1.name = "smb_shares"

        elem2 = MagicMock()
        elem2.name = "ntfs_acls"

        analysis = DataPlaneAnalysis(
            resource_id="test",
            resource_type="test",
            elements=[elem1, elem2],
        )

        assert plugin._has_element(analysis, "smb_shares") is True
        assert plugin._has_element(analysis, "ntfs_acls") is True
        assert plugin._has_element(analysis, "nonexistent") is False

    def test_find_extracted_data(self, plugin):
        """Test finding extracted data by pattern."""
        # Create mock data with proper name attributes
        data1 = MagicMock()
        data1.name = "smb_shares"

        data2 = MagicMock()
        data2.name = "share_permissions"

        data3 = MagicMock()
        data3.name = "ntfs_acls"

        extraction = ExtractionResult(
            resource_id="test",
            extracted_data=[data1, data2, data3],
        )

        # Test exact matches
        result = plugin._find_extracted_data(extraction, "smb_share")
        assert result is not None
        assert result.name == "smb_shares"

        # Test partial matches
        result = plugin._find_extracted_data(extraction, "permission")
        assert result is not None

        # Test no match
        result = plugin._find_extracted_data(extraction, "nonexistent")
        assert result is None

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
        assert plugin.get_config_value("max_depth") == 3
        assert plugin.get_config_value("nonexistent", "default") == "default"

    def test_feature_install_script(self, plugin):
        """Test feature installation script generation."""
        script = plugin._generate_feature_install_script()

        assert "Install-WindowsFeature" in script
        assert "FS-FileServer" in script
        assert "FS-Resource-Manager" in script
        assert "FS-DFS" in script
        assert "Import-Module" in script

    def test_share_creation_script(self, plugin):
        """Test share creation script generation."""
        mock_data = MagicMock(content='{"shares": []}')
        script = plugin._generate_share_creation_script(mock_data)

        assert "New-SmbShare" in script
        assert "FolderEnumerationMode AccessBased" in script
        assert "Shared" in script
        assert "Projects" in script
        assert "Finance" in script

    def test_share_permission_script(self, plugin):
        """Test share permission script generation."""
        mock_data = MagicMock(content='{"permissions": []}')
        script = plugin._generate_share_permission_script(mock_data)

        assert "Grant-SmbShareAccess" in script
        assert "SID translation" in script or "sidMap" in script
        assert "IMPORTANT" in script

    def test_acl_application_script(self, plugin):
        """Test ACL application script generation."""
        mock_data = MagicMock(content="")
        script = plugin._generate_acl_application_script(mock_data)

        assert "Get-Acl" in script or "Set-Acl" in script
        assert "SID" in script
        assert "Translate" in script or "translation" in script

    def test_dfs_config_script(self, plugin):
        """Test DFS configuration script generation."""
        mock_data = MagicMock(content='{"namespaces": []}')
        script = plugin._generate_dfs_config_script(mock_data)

        assert "New-DfsnRoot" in script or "DFS" in script
        assert "namespace" in script.lower()

    def test_quota_config_script(self, plugin):
        """Test FSRM quota configuration script generation."""
        mock_data = MagicMock(content='{"quotas": []}')
        script = plugin._generate_quota_config_script(mock_data)

        assert "New-FsrmQuota" in script or "FsrmQuota" in script
        assert "200 GB" in script

    def test_screen_config_script(self, plugin):
        """Test FSRM file screen configuration script generation."""
        mock_data = MagicMock(content='{"screens": []}')
        script = plugin._generate_screen_config_script(mock_data)

        assert "New-FsrmFileScreen" in script or "FsrmFileScreen" in script
        assert "Executable" in script

    def test_vss_config_script(self, plugin):
        """Test VSS configuration script generation."""
        mock_data = MagicMock(content='{"volumes": []}')
        script = plugin._generate_vss_config_script(mock_data)

        assert "vssadmin" in script or "Shadow" in script
        assert "New-ScheduledTask" in script

    def test_robocopy_script(self, plugin):
        """Test robocopy script generation."""
        mock_data = MagicMock(content='{"directories": []}')
        script = plugin._generate_robocopy_script(mock_data)

        assert "robocopy" in script.lower()
        assert "/MIR" in script or "/COPYALL" in script
        assert "WARNING" in script or "IMPORTANT" in script
        assert "39 GB" in script  # Data size from mock

    def test_validation_script(self, plugin):
        """Test validation script generation."""
        script = plugin._generate_validation_script()

        assert "Get-SmbShare" in script
        assert "Get-FsrmQuota" in script or "FSRM" in script
        assert "Test-Path" in script or "Validate" in script.lower()
        assert "ConvertTo-Json" in script

    @pytest.mark.asyncio
    async def test_extract_smb_shares(self, plugin, file_server_resource, tmp_path):
        """Test SMB share extraction."""
        data = await plugin._extract_smb_shares(file_server_resource, tmp_path)

        assert data.name == "smb_shares"
        assert data.format.value == "json"
        assert data.file_path == str(tmp_path / "smb_shares.json")
        assert (tmp_path / "smb_shares.json").exists()

        # Validate JSON content
        content = json.loads(data.content)
        assert "shares" in content
        assert len(content["shares"]) > 0
        assert "Access-Based Enumeration" in content["note"]

    @pytest.mark.asyncio
    async def test_extract_share_permissions(
        self, plugin, file_server_resource, tmp_path
    ):
        """Test share permission extraction."""
        data = await plugin._extract_share_permissions(file_server_resource, tmp_path)

        assert data.name == "share_permissions"
        assert data.metadata.get("requires_sid_translation") is True
        assert (tmp_path / "share_permissions.json").exists()

        # Validate JSON content
        content = json.loads(data.content)
        assert "share_permissions" in content
        assert len(content["share_permissions"]) > 0
        assert "SID" in content["note"]

    @pytest.mark.asyncio
    async def test_extract_ntfs_acls(self, plugin, file_server_resource, tmp_path):
        """Test NTFS ACL extraction."""
        data = await plugin._extract_ntfs_acls(file_server_resource, tmp_path)

        assert data.name == "ntfs_acls"
        assert data.metadata.get("requires_sid_translation") is True
        assert (tmp_path / "ntfs_acls.sddl").exists()
        assert (tmp_path / "ntfs_acls.csv").exists()

        # Check SDDL content
        assert "O:" in data.content  # Owner
        assert "G:" in data.content  # Group
        assert "D:" in data.content  # DACL
        assert "S-1-5-21" in data.content  # SID format

    @pytest.mark.asyncio
    async def test_extract_dfs_config(self, plugin, file_server_resource, tmp_path):
        """Test DFS configuration extraction."""
        data = await plugin._extract_dfs_config(file_server_resource, tmp_path)

        assert data.name == "dfs_config"
        assert (tmp_path / "dfs_config.json").exists()

        content = json.loads(data.content)
        assert "dfs_namespaces" in content
        assert "dfs_replication_groups" in content

    @pytest.mark.asyncio
    async def test_extract_fsrm_quotas(self, plugin, file_server_resource, tmp_path):
        """Test FSRM quota extraction."""
        data = await plugin._extract_fsrm_quotas(file_server_resource, tmp_path)

        assert data.name == "fsrm_quotas"
        assert (tmp_path / "fsrm_quotas.json").exists()

        content = json.loads(data.content)
        assert "quota_templates" in content
        assert "quotas" in content

    @pytest.mark.asyncio
    async def test_extract_fsrm_screens(self, plugin, file_server_resource, tmp_path):
        """Test FSRM file screen extraction."""
        data = await plugin._extract_fsrm_screens(file_server_resource, tmp_path)

        assert data.name == "fsrm_file_screens"
        assert (tmp_path / "fsrm_file_screens.json").exists()

        content = json.loads(data.content)
        assert "file_groups" in content
        assert "file_screens" in content

    @pytest.mark.asyncio
    async def test_extract_vss_config(self, plugin, file_server_resource, tmp_path):
        """Test VSS configuration extraction."""
        data = await plugin._extract_vss_config(file_server_resource, tmp_path)

        assert data.name == "vss_config"
        assert (tmp_path / "vss_config.json").exists()

        content = json.loads(data.content)
        assert "volumes" in content
        assert "existing_snapshots" in content

    @pytest.mark.asyncio
    async def test_extract_directory_structure(
        self, plugin, file_server_resource, tmp_path
    ):
        """Test directory structure extraction."""
        data = await plugin._extract_directory_structure(file_server_resource, tmp_path)

        assert data.name == "directory_structure"
        assert data.metadata.get("content_included") is False
        assert (tmp_path / "directory_structure.json").exists()

        content = json.loads(data.content)
        assert "directories" in content
        assert "summary" in content
        assert content["metadata"]["includes_file_content"] is False

    @pytest.mark.asyncio
    async def test_full_workflow(self, plugin, file_server_resource, tmp_path):
        """Test complete workflow: analyze -> extract -> generate -> apply."""
        plugin.config["output_dir"] = str(tmp_path)

        # Mock connectivity
        plugin._check_winrm_connectivity = AsyncMock(return_value=True)
        plugin._count_smb_shares = AsyncMock(return_value=3)
        plugin._estimate_acl_count = AsyncMock(return_value=100)
        plugin._check_dfs_enabled = AsyncMock(return_value=True)
        plugin._count_fsrm_quotas = AsyncMock(return_value=2)
        plugin._count_fsrm_screens = AsyncMock(return_value=1)
        plugin._check_vss_enabled = AsyncMock(return_value=True)

        # Step 1: Analyze
        analysis = await plugin.analyze_source(file_server_resource)
        assert analysis.status == AnalysisStatus.SUCCESS
        assert len(analysis.elements) > 0

        # Step 2: Extract
        extraction = await plugin.extract_data(file_server_resource, analysis)
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
        plugin = FileServerReplicationPlugin()

        assert plugin.get_config_value("dry_run", False) is False
        assert plugin.get_config_value("max_depth", 3) == 3
        assert plugin.get_config_value("include_file_metadata", True) is True

    def test_sid_translation_warnings(self, plugin):
        """Test that SID translation warnings are included appropriately."""
        # Check in scripts
        share_perm_script = plugin._generate_share_permission_script(MagicMock())
        assert "SID" in share_perm_script
        assert "translation" in share_perm_script.lower()

        acl_script = plugin._generate_acl_application_script(MagicMock())
        assert "SID" in acl_script
        assert "translation" in acl_script.lower() or "Translate" in acl_script


class TestFileServerPluginEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def plugin(self):
        """Create plugin instance."""
        return FileServerReplicationPlugin({"strict_validation": True})

    @pytest.mark.asyncio
    async def test_strict_validation_mode(self, plugin):
        """Test strict validation mode."""
        resource = {"id": "test", "name": "test-fs"}

        # With strict validation, connectivity check should fail
        result = await plugin._check_winrm_connectivity(resource)
        assert result is False

    @pytest.mark.asyncio
    async def test_large_acl_count_estimation(self, plugin):
        """Test ACL count estimation with many shares."""
        resource = {"id": "test"}
        share_count = 50

        acl_count = await plugin._estimate_acl_count(resource, share_count)

        # Should scale with shares and depth
        assert acl_count > 0
        assert acl_count > share_count  # More ACLs than shares

    def test_script_generation_without_data(self, plugin):
        """Test script generation still works with empty data."""
        empty_data = MagicMock(content="{}")

        # All script generators should handle empty data gracefully
        scripts = [
            plugin._generate_feature_install_script(),
            plugin._generate_share_creation_script(empty_data),
            plugin._generate_share_permission_script(empty_data),
            plugin._generate_acl_application_script(empty_data),
            plugin._generate_dfs_config_script(empty_data),
            plugin._generate_quota_config_script(empty_data),
            plugin._generate_screen_config_script(empty_data),
            plugin._generate_vss_config_script(empty_data),
            plugin._generate_robocopy_script(empty_data),
            plugin._generate_validation_script(),
        ]

        for script in scripts:
            assert isinstance(script, str)
            assert len(script) > 0
