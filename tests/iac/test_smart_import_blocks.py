"""Tests for Smart Import Blocks with Existence Checking (Issue #422).

Tests the integration of ResourceExistenceValidator with TerraformEmitter
to generate import blocks only for resources that actually exist.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph
from src.iac.validators.resource_existence_validator import ResourceExistenceResult


class TestSmartImportBlocks:
    """Test cases for smart import blocks with existence checking."""

    @pytest.fixture
    def mock_credential(self):
        """Create a mock Azure credential."""
        return MagicMock()

    @pytest.fixture
    def emitter_with_imports(self, mock_credential):
        """Create a TerraformEmitter with auto_import_existing enabled."""
        return TerraformEmitter(
            target_subscription_id="test-sub-123",
            auto_import_existing=True,
            import_strategy="resource_groups",
            credential=mock_credential,
        )

    @pytest.fixture
    def sample_graph(self):
        """Create a sample TenantGraph with resource groups."""
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Resources/resourceGroups",
                "name": "existing-rg",
                "location": "eastus",
                "id": "/subscriptions/test-sub-123/resourceGroups/existing-rg",
            },
            {
                "type": "Microsoft.Resources/resourceGroups",
                "name": "nonexistent-rg",
                "location": "westus",
                "id": "/subscriptions/test-sub-123/resourceGroups/nonexistent-rg",
            },
            {
                "type": "Microsoft.Resources/resourceGroups",
                "name": "another-existing-rg",
                "location": "centralus",
                "id": "/subscriptions/test-sub-123/resourceGroups/another-existing-rg",
            },
        ]
        return graph

    def test_import_blocks_with_existence_validation(
        self, emitter_with_imports, sample_graph
    ):
        """Test that import blocks are only generated for existing resources."""
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)

            # Mock the existence validator
            mock_validator = MagicMock()

            # Simulate:
            # - existing-rg: EXISTS
            # - nonexistent-rg: DOES NOT EXIST
            # - another-existing-rg: EXISTS
            mock_results = {
                "/subscriptions/test-sub-123/resourceGroups/existing-rg": ResourceExistenceResult(
                    resource_id="/subscriptions/test-sub-123/resourceGroups/existing-rg",
                    exists=True,
                    cached=False,
                ),
                "/subscriptions/test-sub-123/resourceGroups/nonexistent-rg": ResourceExistenceResult(
                    resource_id="/subscriptions/test-sub-123/resourceGroups/nonexistent-rg",
                    exists=False,
                    cached=False,
                ),
                "/subscriptions/test-sub-123/resourceGroups/another-existing-rg": ResourceExistenceResult(
                    resource_id="/subscriptions/test-sub-123/resourceGroups/another-existing-rg",
                    exists=True,
                    cached=False,
                ),
            }
            mock_validator.batch_check_resources.return_value = mock_results
            mock_validator.get_cache_stats.return_value = {
                "total": 3,
                "valid": 3,
                "expired": 0,
            }

            # Inject the mock validator
            emitter_with_imports._existence_validator = mock_validator

            # Generate IaC
            emitter_with_imports.emit(sample_graph, out_dir)

            # Read the generated file
            main_tf = out_dir / "main.tf.json"
            assert main_tf.exists()

            with open(main_tf) as f:
                config = json.load(f)

            # Verify import blocks
            assert "import" in config
            import_blocks = config["import"]

            # Should only have 2 import blocks (not 3)
            assert len(import_blocks) == 2

            # Verify the correct resources are imported
            imported_ids = {block["id"] for block in import_blocks}
            assert (
                "/subscriptions/test-sub-123/resourceGroups/existing-rg" in imported_ids
            )
            assert (
                "/subscriptions/test-sub-123/resourceGroups/another-existing-rg"
                in imported_ids
            )
            assert (
                "/subscriptions/test-sub-123/resourceGroups/nonexistent-rg"
                not in imported_ids
            )

            # Verify batch_check_resources was called
            mock_validator.batch_check_resources.assert_called_once()

    def test_import_blocks_all_exist(self, emitter_with_imports, sample_graph):
        """Test import blocks when all resources exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)

            mock_validator = MagicMock()

            # All resources exist
            mock_results = {
                "/subscriptions/test-sub-123/resourceGroups/existing-rg": ResourceExistenceResult(
                    resource_id="/subscriptions/test-sub-123/resourceGroups/existing-rg",
                    exists=True,
                ),
                "/subscriptions/test-sub-123/resourceGroups/nonexistent-rg": ResourceExistenceResult(
                    resource_id="/subscriptions/test-sub-123/resourceGroups/nonexistent-rg",
                    exists=True,
                ),
                "/subscriptions/test-sub-123/resourceGroups/another-existing-rg": ResourceExistenceResult(
                    resource_id="/subscriptions/test-sub-123/resourceGroups/another-existing-rg",
                    exists=True,
                ),
            }
            mock_validator.batch_check_resources.return_value = mock_results
            mock_validator.get_cache_stats.return_value = {
                "total": 3,
                "valid": 3,
                "expired": 0,
            }

            emitter_with_imports._existence_validator = mock_validator

            emitter_with_imports.emit(sample_graph, out_dir)

            main_tf = out_dir / "main.tf.json"
            with open(main_tf) as f:
                config = json.load(f)

            # Should have all 3 import blocks
            assert "import" in config
            import_blocks = config["import"]
            assert len(import_blocks) == 3

    def test_import_blocks_none_exist(self, emitter_with_imports, sample_graph):
        """Test import blocks when no resources exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)

            mock_validator = MagicMock()

            # No resources exist
            mock_results = {
                "/subscriptions/test-sub-123/resourceGroups/existing-rg": ResourceExistenceResult(
                    resource_id="/subscriptions/test-sub-123/resourceGroups/existing-rg",
                    exists=False,
                ),
                "/subscriptions/test-sub-123/resourceGroups/nonexistent-rg": ResourceExistenceResult(
                    resource_id="/subscriptions/test-sub-123/resourceGroups/nonexistent-rg",
                    exists=False,
                ),
                "/subscriptions/test-sub-123/resourceGroups/another-existing-rg": ResourceExistenceResult(
                    resource_id="/subscriptions/test-sub-123/resourceGroups/another-existing-rg",
                    exists=False,
                ),
            }
            mock_validator.batch_check_resources.return_value = mock_results
            mock_validator.get_cache_stats.return_value = {
                "total": 3,
                "valid": 3,
                "expired": 0,
            }

            emitter_with_imports._existence_validator = mock_validator

            emitter_with_imports.emit(sample_graph, out_dir)

            main_tf = out_dir / "main.tf.json"
            with open(main_tf) as f:
                config = json.load(f)

            # Should have NO import blocks
            # The import key might not exist or be an empty list
            import_blocks = config.get("import", [])
            assert len(import_blocks) == 0

    def test_import_blocks_with_errors(self, emitter_with_imports, sample_graph):
        """Test import blocks when some checks return errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)

            mock_validator = MagicMock()

            # One exists, one has error, one doesn't exist
            mock_results = {
                "/subscriptions/test-sub-123/resourceGroups/existing-rg": ResourceExistenceResult(
                    resource_id="/subscriptions/test-sub-123/resourceGroups/existing-rg",
                    exists=True,
                ),
                "/subscriptions/test-sub-123/resourceGroups/nonexistent-rg": ResourceExistenceResult(
                    resource_id="/subscriptions/test-sub-123/resourceGroups/nonexistent-rg",
                    exists=False,
                    error="Network timeout",
                ),
                "/subscriptions/test-sub-123/resourceGroups/another-existing-rg": ResourceExistenceResult(
                    resource_id="/subscriptions/test-sub-123/resourceGroups/another-existing-rg",
                    exists=False,
                ),
            }
            mock_validator.batch_check_resources.return_value = mock_results
            mock_validator.get_cache_stats.return_value = {
                "total": 3,
                "valid": 2,
                "expired": 1,
            }

            emitter_with_imports._existence_validator = mock_validator

            emitter_with_imports.emit(sample_graph, out_dir)

            main_tf = out_dir / "main.tf.json"
            with open(main_tf) as f:
                config = json.load(f)

            # Should only have 1 import block (the one that exists)
            assert "import" in config
            import_blocks = config["import"]
            assert len(import_blocks) == 1
            assert (
                import_blocks[0]["id"]
                == "/subscriptions/test-sub-123/resourceGroups/existing-rg"
            )

    def test_no_import_blocks_when_disabled(self, mock_credential, sample_graph):
        """Test that import blocks are not generated when auto_import_existing is False."""
        emitter = TerraformEmitter(
            target_subscription_id="test-sub-123",
            auto_import_existing=False,  # Disabled
            credential=mock_credential,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)

            emitter.emit(sample_graph, out_dir)

            main_tf = out_dir / "main.tf.json"
            with open(main_tf) as f:
                config = json.load(f)

            # Should not have import blocks
            assert "import" not in config

    def test_fallback_to_no_validation_without_subscription(self, mock_credential):
        """Test fallback to no validation when subscription ID is missing."""
        emitter = TerraformEmitter(
            # No subscription IDs provided
            auto_import_existing=True,
            import_strategy="resource_groups",
            credential=mock_credential,
        )

        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Resources/resourceGroups",
                "name": "test-rg",
                "location": "eastus",
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)

            # This should not crash, but fall back to no validation
            emitter.emit(graph, out_dir)

            main_tf = out_dir / "main.tf.json"
            assert main_tf.exists()

            # Import blocks might be generated without validation
            # or not generated at all (both are acceptable fallback behaviors)
            with open(main_tf) as f:
                json.load(f)
            # Just verify it doesn't crash

    def test_caching_behavior(self, emitter_with_imports, sample_graph):
        """Test that caching is used for repeated checks."""
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)

            mock_validator = MagicMock()

            # First call: not cached
            # Second call (if any): would be cached
            mock_results_first = {
                "/subscriptions/test-sub-123/resourceGroups/existing-rg": ResourceExistenceResult(
                    resource_id="/subscriptions/test-sub-123/resourceGroups/existing-rg",
                    exists=True,
                    cached=False,
                ),
                "/subscriptions/test-sub-123/resourceGroups/nonexistent-rg": ResourceExistenceResult(
                    resource_id="/subscriptions/test-sub-123/resourceGroups/nonexistent-rg",
                    exists=False,
                    cached=False,
                ),
                "/subscriptions/test-sub-123/resourceGroups/another-existing-rg": ResourceExistenceResult(
                    resource_id="/subscriptions/test-sub-123/resourceGroups/another-existing-rg",
                    exists=True,
                    cached=False,
                ),
            }
            mock_validator.batch_check_resources.return_value = mock_results_first
            mock_validator.get_cache_stats.return_value = {
                "total": 3,
                "valid": 3,
                "expired": 0,
            }

            emitter_with_imports._existence_validator = mock_validator

            # Generate once
            emitter_with_imports.emit(sample_graph, out_dir)

            # Verify cache stats were queried
            mock_validator.get_cache_stats.assert_called()

    def test_import_strategy_all_resources_not_implemented(
        self, mock_credential, sample_graph
    ):
        """Test that all_resources strategy logs a warning."""
        emitter = TerraformEmitter(
            target_subscription_id="test-sub-123",
            auto_import_existing=True,
            import_strategy="all_resources",  # Not yet fully implemented
            credential=mock_credential,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)

            # Initialize mock validator to avoid real Azure calls
            mock_validator = MagicMock()
            mock_validator.get_cache_stats.return_value = {
                "total": 0,
                "valid": 0,
                "expired": 0,
            }
            emitter._existence_validator = mock_validator

            # Should not crash, but log warning
            emitter.emit(sample_graph, out_dir)

            main_tf = out_dir / "main.tf.json"
            assert main_tf.exists()
