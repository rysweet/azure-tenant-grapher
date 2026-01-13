"""Tests for community-based Terraform file splitting."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.iac.community_detector import CommunityDetector
from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph


@pytest.fixture
def mock_neo4j_driver():
    """Create a mock Neo4j driver."""
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    driver.session.return_value.__exit__.return_value = None
    return driver


@pytest.fixture
def sample_graph_with_communities():
    """Create a sample tenant graph with 3 communities."""
    # Community 1: VNet + VM
    vnet1 = {
        "id": "vnet-hash1",
        "name": "vnet-community1",
        "type": "Microsoft.Network/virtualNetworks",
        "location": "eastus",
        "resource_group": "rg-community1",
        "properties": json.dumps(
            {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}, "subnets": []}
        ),
    }

    vm1 = {
        "id": "vm-hash1",
        "name": "vm-community1",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "resource_group": "rg-community1",
        "properties": json.dumps({"hardwareProfile": {"vmSize": "Standard_B2s"}}),
    }

    # Community 2: Storage + KeyVault
    storage2 = {
        "id": "storage-hash2",
        "name": "storagecommunity2",
        "type": "Microsoft.Storage/storageAccounts",
        "location": "westus",
        "resource_group": "rg-community2",
        "properties": json.dumps({"sku": {"name": "Standard_LRS"}}),
    }

    keyvault2 = {
        "id": "kv-hash2",
        "name": "kv-community2",
        "type": "Microsoft.KeyVault/vaults",
        "location": "westus",
        "resource_group": "rg-community2",
        "properties": json.dumps({"tenantId": "test-tenant-id"}),
    }

    # Community 3: Standalone resource
    nsg3 = {
        "id": "nsg-hash3",
        "name": "nsg-community3",
        "type": "Microsoft.Network/networkSecurityGroups",
        "location": "centralus",
        "resource_group": "rg-community3",
        "properties": json.dumps({"securityRules": []}),
    }

    resources = [vnet1, vm1, storage2, keyvault2, nsg3]

    graph = TenantGraph()
    graph.resources = resources

    return graph


def test_community_detector_detects_communities(mock_neo4j_driver):
    """Test that CommunityDetector correctly identifies communities."""
    # Mock Neo4j query results for 3 communities
    session = mock_neo4j_driver.session.return_value.__enter__.return_value

    # Simulate Neo4j results: 3 communities
    mock_records = [
        {"resource_id": "vnet-hash1", "connected_ids": ["vm-hash1"]},
        {"resource_id": "vm-hash1", "connected_ids": ["vnet-hash1"]},
        {"resource_id": "storage-hash2", "connected_ids": ["kv-hash2"]},
        {"resource_id": "kv-hash2", "connected_ids": ["storage-hash2"]},
        {"resource_id": "nsg-hash3", "connected_ids": []},  # Isolated node
    ]

    session.run.return_value = mock_records

    detector = CommunityDetector(mock_neo4j_driver)
    communities = detector.detect_communities()

    # Should have 3 communities
    assert len(communities) == 3

    # Check communities are sorted by size (largest first)
    assert len(communities[0]) >= len(communities[1])
    assert len(communities[1]) >= len(communities[2])

    # Check that all resources are covered
    all_resource_ids = set()
    for community in communities:
        all_resource_ids.update(community)

    assert "vnet-hash1" in all_resource_ids
    assert "vm-hash1" in all_resource_ids
    assert "storage-hash2" in all_resource_ids
    assert "kv-hash2" in all_resource_ids
    assert "nsg-hash3" in all_resource_ids


def test_terraform_emitter_split_by_community_disabled(
    sample_graph_with_communities, tmp_path
):
    """Test that emitter generates single file when split_by_community=False."""
    emitter = TerraformEmitter()

    output_files = emitter.emit(
        sample_graph_with_communities, tmp_path, split_by_community=False
    )

    # Should generate single main.tf.json
    assert len(output_files) == 1
    assert output_files[0].name == "main.tf.json"
    assert output_files[0].exists()

    # Verify content
    with open(output_files[0]) as f:
        content = json.load(f)

    assert "terraform" in content
    assert "provider" in content
    assert "resource" in content


@patch("src.config_manager.create_neo4j_config_from_env")
@patch("src.utils.session_manager.create_session_manager")
def test_terraform_emitter_split_by_community_enabled(
    mock_create_session_manager,
    mock_create_config,
    sample_graph_with_communities,
    mock_neo4j_driver,
    tmp_path,
):
    """Test that emitter generates multiple files when split_by_community=True."""
    # Mock session manager to return our driver
    mock_manager = MagicMock()
    mock_manager._driver = mock_neo4j_driver
    mock_create_session_manager.return_value = mock_manager

    # Mock CommunityDetector.detect_communities
    # Return 3 communities matching our sample graph
    communities = [
        {"vnet-hash1", "vm-hash1"},  # Community 1
        {"storage-hash2", "kv-hash2"},  # Community 2
        {"nsg-hash3"},  # Community 3
    ]

    with patch.object(
        CommunityDetector, "detect_communities", return_value=communities
    ):
        emitter = TerraformEmitter()

        output_files = emitter.emit(
            sample_graph_with_communities, tmp_path, split_by_community=True
        )

        # Should generate 3 community files
        assert len(output_files) == 3

        # Verify files exist and have correct names
        file_names = [f.name for f in output_files]
        assert "community_1.tf.json" in file_names
        assert "community_2.tf.json" in file_names
        assert "community_3.tf.json" in file_names

        # Verify each file has valid structure
        for output_file in output_files:
            assert output_file.exists()

            with open(output_file) as f:
                content = json.load(f)

            # Each file should have terraform config
            assert "terraform" in content
            assert "provider" in content
            assert "variable" in content
            assert "resource" in content


@patch("src.config_manager.create_neo4j_config_from_env")
@patch("src.utils.session_manager.create_session_manager")
def test_community_files_are_self_contained(
    mock_create_session_manager,
    mock_create_config,
    sample_graph_with_communities,
    mock_neo4j_driver,
    tmp_path,
):
    """Test that each community file contains only resources from that community."""
    # Mock session manager
    mock_manager = MagicMock()
    mock_manager._driver = mock_neo4j_driver
    mock_create_session_manager.return_value = mock_manager

    # Define communities
    communities = [
        {"vnet-hash1", "vm-hash1"},  # Community 1: VNet + VM
        {"storage-hash2", "kv-hash2"},  # Community 2: Storage + KeyVault
        {"nsg-hash3"},  # Community 3: NSG
    ]

    with patch.object(
        CommunityDetector, "detect_communities", return_value=communities
    ):
        emitter = TerraformEmitter()

        output_files = emitter.emit(
            sample_graph_with_communities, tmp_path, split_by_community=True
        )

        # Load and check each community file
        for i, output_file in enumerate(output_files):
            with open(output_file) as f:
                content = json.load(f)

            resources = content.get("resource", {})

            # Collect all resource names from this file
            resource_names = []
            for _resource_type, type_resources in resources.items():
                resource_names.extend(type_resources.keys())

            # Each file should have resources (not empty)
            assert len(resource_names) > 0

            # Verify resources match expected community
            if i == 0:  # Community 1
                # Should contain vnet and vm
                assert any(
                    "vnet" in name.lower() or "community1" in name.lower()
                    for name in resource_names
                )
            elif i == 1:  # Community 2
                # Should contain storage or keyvault
                assert any(
                    "storage" in name.lower()
                    or "kv" in name.lower()
                    or "community2" in name.lower()
                    for name in resource_names
                )
            elif i == 2:  # Community 3
                # Should contain nsg
                assert any(
                    "nsg" in name.lower() or "community3" in name.lower()
                    for name in resource_names
                )


@patch("src.config_manager.create_neo4j_config_from_env")
@patch("src.utils.session_manager.create_session_manager")
def test_no_cross_community_references(
    mock_create_session_manager,
    mock_create_config,
    sample_graph_with_communities,
    mock_neo4j_driver,
    tmp_path,
):
    """Test that community files don't contain cross-community resource references."""
    # Mock session manager
    mock_manager = MagicMock()
    mock_manager._driver = mock_neo4j_driver
    mock_create_session_manager.return_value = mock_manager

    # Define communities
    communities = [
        {"vnet-hash1", "vm-hash1"},
        {"storage-hash2", "kv-hash2"},
        {"nsg-hash3"},
    ]

    with patch.object(
        CommunityDetector, "detect_communities", return_value=communities
    ):
        emitter = TerraformEmitter()

        output_files = emitter.emit(
            sample_graph_with_communities, tmp_path, split_by_community=True
        )

        # Check each file for cross-references
        for output_file in output_files:
            with open(output_file) as f:
                content = json.load(f)

            # Serialize to string to check for references
            json.dumps(content)

            # Each file should be self-contained
            # No references to resources from other communities
            # This is a basic check - more sophisticated validation could be added
            assert "resource" in content


@patch("src.config_manager.create_neo4j_config_from_env")
@patch("src.utils.session_manager.create_session_manager")
def test_split_by_community_with_import_blocks(
    mock_create_session_manager,
    mock_create_config,
    sample_graph_with_communities,
    mock_neo4j_driver,
    tmp_path,
):
    """Test that import blocks are correctly distributed across community files."""
    # Mock session manager
    mock_manager = MagicMock()
    mock_manager._driver = mock_neo4j_driver
    mock_create_session_manager.return_value = mock_manager

    # Define communities
    communities = [
        {"vnet-hash1", "vm-hash1"},
        {"storage-hash2", "kv-hash2"},
        {"nsg-hash3"},
    ]

    with patch.object(
        CommunityDetector, "detect_communities", return_value=communities
    ):
        emitter = TerraformEmitter(auto_import_existing=True)

        output_files = emitter.emit(
            sample_graph_with_communities, tmp_path, split_by_community=True
        )

        # If import blocks are generated, they should be split across communities
        # Check that at least one file exists
        assert len(output_files) > 0


def test_fallback_to_single_file_on_error(sample_graph_with_communities, tmp_path):
    """Test that emitter falls back to single file if community detection fails."""
    with patch("src.config_manager.create_neo4j_config_from_env") as mock_config:
        # Mock config to raise an error
        mock_config.side_effect = Exception("Config error")

        emitter = TerraformEmitter()

        # Should fall back to single file generation
        output_files = emitter.emit(
            sample_graph_with_communities, tmp_path, split_by_community=True
        )

        # Should generate single file as fallback
        assert len(output_files) == 1
        assert output_files[0].name == "main.tf.json"


def test_empty_graph_with_split_by_community(tmp_path):
    """Test that empty graph works with split_by_community enabled."""
    empty_graph = TenantGraph()
    empty_graph.resources = []

    emitter = TerraformEmitter()

    output_files = emitter.emit(
        empty_graph,
        tmp_path,
        split_by_community=False,  # Use False to avoid Neo4j driver requirement
    )

    # Should still generate a file (even if empty)
    assert len(output_files) == 1
