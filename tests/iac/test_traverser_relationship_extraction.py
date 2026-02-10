"""Tests for simplified relationship extraction in GraphTraverser (Issue #873).

This test suite validates:
- Simplified query finds abstracted node relationships
- Separate relationship query works correctly
- Relationships are returned in traverse() results
"""

from unittest.mock import MagicMock

import pytest

from src.iac.traverser import GraphTraverser, TenantGraph


class TestTraverserSimplifiedRelationshipExtraction:
    """Test simplified relationship extraction query."""

    @pytest.fixture
    def mock_driver(self):
        """Provide mock Neo4j driver."""
        driver = MagicMock()
        return driver

    @pytest.fixture
    def mock_session(self, mock_driver):
        """Provide mock Neo4j session."""
        session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = session
        return session

    @pytest.mark.asyncio
    async def test_traverse_returns_relationships(self, mock_driver, mock_session):
        """Test that traverse returns relationships in results."""
        # Mock resource with relationship
        mock_resource_node = {
            "id": "abstracted-vm-1",
            "original_id": "/subscriptions/test/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
        }

        mock_record = MagicMock()
        mock_record.__getitem__.side_effect = lambda key: {
            "r": mock_resource_node,
            "original_id": "/subscriptions/test/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "rels": [
                {
                    "type": "USES",
                    "target": "abstracted-nic-1",
                    "original_type": None,
                    "narrative_context": None,
                }
            ],
        }[key]

        mock_session.run.return_value = [mock_record]

        traverser = GraphTraverser(mock_driver)
        result = await traverser.traverse()

        # Verify result structure
        assert isinstance(result, TenantGraph)
        assert len(result.resources) == 1
        assert len(result.relationships) == 1

        # Verify relationship structure
        rel = result.relationships[0]
        assert rel["source"] == "abstracted-vm-1"
        assert rel["target"] == "abstracted-nic-1"
        assert rel["type"] == "USES"

    @pytest.mark.asyncio
    async def test_traverse_handles_multiple_relationships(
        self, mock_driver, mock_session
    ):
        """Test that traverse handles resources with multiple relationships."""
        mock_resource_node = {
            "id": "abstracted-vm-1",
            "original_id": "/subscriptions/test/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
        }

        mock_record = MagicMock()
        mock_record.__getitem__.side_effect = lambda key: {
            "r": mock_resource_node,
            "original_id": "/subscriptions/test/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "rels": [
                {"type": "USES", "target": "abstracted-nic-1"},
                {"type": "DEPENDS_ON", "target": "abstracted-storage-1"},
                {"type": "USES_IDENTITY", "target": "abstracted-identity-1"},
            ],
        }[key]

        mock_session.run.return_value = [mock_record]

        traverser = GraphTraverser(mock_driver)
        result = await traverser.traverse()

        # Should have 3 relationships
        assert len(result.relationships) == 3

        # Verify relationship types
        rel_types = {rel["type"] for rel in result.relationships}
        assert "USES" in rel_types
        assert "DEPENDS_ON" in rel_types
        assert "USES_IDENTITY" in rel_types

    @pytest.mark.asyncio
    async def test_traverse_handles_no_relationships(self, mock_driver, mock_session):
        """Test that traverse handles resources with no relationships."""
        mock_resource_node = {
            "id": "abstracted-storage-1",
            "original_id": "/subscriptions/test/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1",
            "name": "sa1",
            "type": "Microsoft.Storage/storageAccounts",
        }

        mock_record = MagicMock()
        mock_record.__getitem__.side_effect = lambda key: {
            "r": mock_resource_node,
            "original_id": "/subscriptions/test/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1",
            "rels": [],  # No relationships
        }[key]

        mock_session.run.return_value = [mock_record]

        traverser = GraphTraverser(mock_driver)
        result = await traverser.traverse()

        # Should have resource but no relationships
        assert len(result.resources) == 1
        assert len(result.relationships) == 0

    @pytest.mark.asyncio
    async def test_traverse_filters_null_relationships(self, mock_driver, mock_session):
        """Test that traverse filters out null/invalid relationships."""
        mock_resource_node = {
            "id": "abstracted-vm-1",
            "original_id": "/subscriptions/test/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
        }

        mock_record = MagicMock()
        mock_record.__getitem__.side_effect = lambda key: {
            "r": mock_resource_node,
            "original_id": "/subscriptions/test/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "rels": [
                {"type": "USES", "target": "abstracted-nic-1"},
                None,  # Null relationship
                {"type": "DEPENDS_ON", "target": None},  # Missing target
                {"type": None, "target": "abstracted-storage-1"},  # Missing type
            ],
        }[key]

        mock_session.run.return_value = [mock_record]

        traverser = GraphTraverser(mock_driver)
        result = await traverser.traverse()

        # Should only have 1 valid relationship
        assert len(result.relationships) == 1
        assert result.relationships[0]["type"] == "USES"

    @pytest.mark.asyncio
    async def test_traverse_includes_original_id(self, mock_driver, mock_session):
        """Test that traverse includes original_id in resource dict (Bug #15 fix)."""
        mock_resource_node = {
            "id": "abstracted-vm-1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
        }

        original_id = "/subscriptions/test/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1"

        mock_record = MagicMock()
        mock_record.__getitem__.side_effect = lambda key: {
            "r": mock_resource_node,
            "original_id": original_id,
            "rels": [],
        }[key]
        mock_record.get = lambda key, default=None: original_id if key == "original_id" else default

        mock_session.run.return_value = [mock_record]

        traverser = GraphTraverser(mock_driver)
        result = await traverser.traverse()

        # Resource should have original_id field
        assert len(result.resources) == 1
        resource = result.resources[0]
        assert "original_id" in resource
        assert resource["original_id"] == original_id

    @pytest.mark.asyncio
    async def test_traverse_handles_generic_relationship_properties(
        self, mock_driver, mock_session
    ):
        """Test that traverse preserves GENERIC_RELATIONSHIP properties."""
        mock_resource_node = {
            "id": "abstracted-vm-1",
            "original_id": "/subscriptions/test/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
        }

        mock_record = MagicMock()
        mock_record.__getitem__.side_effect = lambda key: {
            "r": mock_resource_node,
            "original_id": "/subscriptions/test/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "rels": [
                {
                    "type": "GENERIC_RELATIONSHIP",
                    "target": "abstracted-storage-1",
                    "original_type": "STORES_DATA_IN",
                    "narrative_context": "VM stores diagnostics in storage account",
                }
            ],
        }[key]
        mock_record.get = lambda key, default=None: (
            "/subscriptions/test/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1"
            if key == "original_id"
            else default
        )

        mock_session.run.return_value = [mock_record]

        traverser = GraphTraverser(mock_driver)
        result = await traverser.traverse()

        # Verify GENERIC_RELATIONSHIP properties are preserved
        assert len(result.relationships) == 1
        rel = result.relationships[0]
        assert rel["type"] == "GENERIC_RELATIONSHIP"
        assert rel["original_type"] == "STORES_DATA_IN"
        assert rel["narrative_context"] == "VM stores diagnostics in storage account"


class TestTraverserQueryStructure:
    """Test that query structure is correct."""

    @pytest.fixture
    def mock_driver(self):
        """Provide mock Neo4j driver."""
        driver = MagicMock()
        return driver

    @pytest.fixture
    def mock_session(self, mock_driver):
        """Provide mock Neo4j session."""
        session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = session
        return session

    @pytest.mark.asyncio
    async def test_default_query_uses_abstracted_nodes(
        self, mock_driver, mock_session
    ):
        """Test that default traverse query targets abstracted nodes."""
        mock_session.run.return_value = []

        traverser = GraphTraverser(mock_driver)
        await traverser.traverse()

        # Verify query was called
        assert mock_session.run.called
        query = mock_session.run.call_args[0][0]

        # Query should match :Resource nodes
        assert "MATCH (r:Resource)" in query

        # Query should filter out duplicates where abstracted node exists
        assert "WHERE NOT EXISTS" in query

    @pytest.mark.asyncio
    async def test_use_original_ids_flag(self, mock_driver, mock_session):
        """Test that use_original_ids=True queries Original nodes."""
        mock_session.run.return_value = []

        traverser = GraphTraverser(mock_driver)
        await traverser.traverse(use_original_ids=True)

        # Verify query targets Original nodes
        assert mock_session.run.called
        query = mock_session.run.call_args[0][0]

        # Query should match :Resource:Original nodes
        assert ":Resource:Original" in query

    @pytest.mark.asyncio
    async def test_custom_filter_cypher(self, mock_driver, mock_session):
        """Test that custom filter_cypher is used."""
        mock_session.run.return_value = []

        custom_query = "MATCH (r:Resource) WHERE r.type = 'test' RETURN r"
        traverser = GraphTraverser(mock_driver)
        await traverser.traverse(filter_cypher=custom_query)

        # Verify custom query was used
        mock_session.run.assert_called_once_with(custom_query, {})

    @pytest.mark.asyncio
    async def test_parameters_passed_to_query(self, mock_driver, mock_session):
        """Test that parameters are passed to Cypher query (Issue #524)."""
        mock_session.run.return_value = []

        params = {"resource_type": "Microsoft.Compute/virtualMachines"}

        traverser = GraphTraverser(mock_driver)
        await traverser.traverse(parameters=params)

        # Verify parameters were passed to query
        assert mock_session.run.called
        call_args = mock_session.run.call_args
        assert call_args[1] == params


class TestTraverserSourceResourceGroup:
    """Test source resource group metadata extraction (GAP-017 / Issue #313)."""

    @pytest.fixture
    def mock_driver(self):
        """Provide mock Neo4j driver."""
        driver = MagicMock()
        return driver

    @pytest.fixture
    def mock_session(self, mock_driver):
        """Provide mock Neo4j session."""
        session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = session
        return session

    @pytest.mark.asyncio
    async def test_extracts_source_rg_from_resource_id(
        self, mock_driver, mock_session
    ):
        """Test that _source_rg is extracted from Azure resource ID."""
        mock_resource_node = {
            "id": "/subscriptions/test/resourceGroups/production-rg/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
        }

        mock_record = MagicMock()
        mock_record.__getitem__.side_effect = lambda key: {
            "r": mock_resource_node,
            "rels": [],
        }[key]
        mock_record.get = lambda key, default=None: default

        mock_session.run.return_value = [mock_record]

        traverser = GraphTraverser(mock_driver)
        result = await traverser.traverse()

        # Resource should have _source_rg field
        assert len(result.resources) == 1
        resource = result.resources[0]
        assert "_source_rg" in resource
        assert resource["_source_rg"] == "production-rg"

    @pytest.mark.asyncio
    async def test_source_rg_none_for_non_rg_resources(
        self, mock_driver, mock_session
    ):
        """Test that _source_rg is None for resources without resource group in ID."""
        mock_resource_node = {
            "id": "/subscriptions/test/some-resource",  # No resourceGroups in path
            "name": "resource1",
            "type": "Some.Type",
        }

        mock_record = MagicMock()
        mock_record.__getitem__.side_effect = lambda key: {
            "r": mock_resource_node,
            "rels": [],
        }[key]
        mock_record.get = lambda key, default=None: default

        mock_session.run.return_value = [mock_record]

        traverser = GraphTraverser(mock_driver)
        result = await traverser.traverse()

        # _source_rg should be None
        assert len(result.resources) == 1
        resource = result.resources[0]
        assert "_source_rg" in resource
        assert resource["_source_rg"] is None


class TestTraverserRobustness:
    """Test error handling and edge cases."""

    @pytest.fixture
    def mock_driver(self):
        """Provide mock Neo4j driver."""
        driver = MagicMock()
        return driver

    @pytest.fixture
    def mock_session(self, mock_driver):
        """Provide mock Neo4j session."""
        session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = session
        return session

    @pytest.mark.asyncio
    async def test_traverse_handles_empty_result(self, mock_driver, mock_session):
        """Test that traverse handles empty query results."""
        mock_session.run.return_value = []

        traverser = GraphTraverser(mock_driver)
        result = await traverser.traverse()

        assert isinstance(result, TenantGraph)
        assert len(result.resources) == 0
        assert len(result.relationships) == 0

    @pytest.mark.asyncio
    async def test_traverse_handles_missing_rels_field(
        self, mock_driver, mock_session
    ):
        """Test that traverse handles records without 'rels' field."""
        mock_resource_node = {
            "id": "abstracted-vm-1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
        }

        mock_record = MagicMock()
        # Only return 'r', no 'rels' field
        mock_record.__getitem__.side_effect = lambda key: {
            "r": mock_resource_node,
        }[key]
        mock_record.__contains__ = lambda self, key: key == "r"
        mock_record.get = lambda key, default=None: default

        mock_session.run.return_value = [mock_record]

        traverser = GraphTraverser(mock_driver)
        result = await traverser.traverse()

        # Should have resource but no relationships
        assert len(result.resources) == 1
        assert len(result.relationships) == 0

    @pytest.mark.asyncio
    async def test_traverse_handles_multiple_resources(
        self, mock_driver, mock_session
    ):
        """Test that traverse handles multiple resources correctly."""
        mock_records = []

        for i in range(3):
            mock_resource_node = {
                "id": f"abstracted-vm-{i}",
                "name": f"vm{i}",
                "type": "Microsoft.Compute/virtualMachines",
            }

            mock_record = MagicMock()
            mock_record.__getitem__.side_effect = (
                lambda key, node=mock_resource_node: {
                    "r": node,
                    "rels": [],
                }[key]
            )
            mock_record.get = lambda key, default=None: default

            mock_records.append(mock_record)

        mock_session.run.return_value = mock_records

        traverser = GraphTraverser(mock_driver)
        result = await traverser.traverse()

        # Should have all 3 resources
        assert len(result.resources) == 3

        # Verify resource IDs
        resource_ids = {r["id"] for r in result.resources}
        assert "abstracted-vm-0" in resource_ids
        assert "abstracted-vm-1" in resource_ids
        assert "abstracted-vm-2" in resource_ids
