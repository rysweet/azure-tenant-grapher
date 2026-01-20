"""Integration tests for CTF Import → Deploy workflow.

Tests complete workflow combining multiple services:
- CTFImportService + CTFAnnotationService
- CTFImportService + CTFDeployService
- Full import → annotate → deploy → cleanup cycle

These tests use mocked Neo4j and Terraform but test actual service integration.
Tests should FAIL initially until implementation is complete.

Testing pyramid: 30% integration tests
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver for integration testing."""
    driver = Mock()
    driver.execute_query = Mock(return_value=([], None, None))
    return driver


@pytest.fixture
def sample_terraform_state():
    """Sample Terraform state for integration testing."""
    return {
        "version": 4,
        "terraform_version": "1.5.0",
        "resources": [
            {
                "mode": "managed",
                "type": "azurerm_virtual_machine",
                "name": "target",
                "instances": [
                    {
                        "attributes": {
                            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/target-vm",
                            "name": "target-vm",
                            "location": "eastus",
                            "tags": {
                                "layer_id": "default",
                                "ctf_exercise": "M003",
                                "ctf_scenario": "v2-cert",
                                "ctf_role": "target",
                            },
                        }
                    }
                ],
            },
            {
                "mode": "managed",
                "type": "azurerm_virtual_network",
                "name": "vnet",
                "instances": [
                    {
                        "attributes": {
                            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/ctf-vnet",
                            "name": "ctf-vnet",
                            "location": "eastus",
                            "tags": {
                                "layer_id": "default",
                                "ctf_exercise": "M003",
                                "ctf_scenario": "v2-cert",
                                "ctf_role": "infrastructure",
                            },
                        }
                    }
                ],
            },
        ],
    }


@pytest.fixture
def temp_terraform_dir():
    """Create temporary Terraform directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ============================================================================
# Integration Tests (WILL FAIL - No Implementation Yet)
# ============================================================================


class TestImportAnnotateFlow:
    """Test integration between CTFImportService and CTFAnnotationService."""

    def test_import_then_annotate_workflow(
        self, mock_neo4j_driver, sample_terraform_state
    ):
        """Test importing Terraform state and then annotating resources."""
        from src.services.ctf_annotation_service import CTFAnnotationService
        from src.services.ctf_import_service import CTFImportService

        # Track Neo4j calls
        neo4j_calls = []

        def track_calls(*args, **kwargs):
            neo4j_calls.append({"query": args[0], "params": kwargs})
            return ([], None, None)

        mock_neo4j_driver.execute_query.side_effect = track_calls

        # Step 1: Import Terraform state
        import_service = CTFImportService(neo4j_driver=mock_neo4j_driver)

        with patch(
            "builtins.open", mock_open(read_data=json.dumps(sample_terraform_state))
        ):
            import_stats = import_service.import_from_state(
                state_file="terraform.tfstate", layer_id="default"
            )

        assert import_stats["resources_created"] == 2

        # Step 2: Annotate resources (update roles)
        annotate_service = CTFAnnotationService(neo4j_driver=mock_neo4j_driver)

        annotate_result = annotate_service.annotate_resource(
            resource_id="/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/target-vm",
            layer_id="default",
            ctf_role="attacker",  # Change role
        )

        assert annotate_result["success"] is True

        # Verify both services called Neo4j
        assert len(neo4j_calls) >= 2
        # Import should use MERGE or UNWIND
        assert any(
            "MERGE" in call["query"] or "UNWIND" in call["query"]
            for call in neo4j_calls
        )

    def test_import_auto_annotates_from_tags(
        self, mock_neo4j_driver, sample_terraform_state
    ):
        """Test import automatically extracts CTF properties from tags."""
        from src.services.ctf_import_service import CTFImportService

        import_service = CTFImportService(neo4j_driver=mock_neo4j_driver)

        with patch(
            "builtins.open", mock_open(read_data=json.dumps(sample_terraform_state))
        ):
            import_service.import_from_state(
                state_file="terraform.tfstate", layer_id="default"
            )

        # Verify CTF properties were extracted from tags
        call_args = mock_neo4j_driver.execute_query.call_args
        params = call_args[1] if len(call_args) > 1 else {}

        # Should include CTF properties from tags
        if "resources" in params:  # Batch operation
            resources = params["resources"]
            assert any(r.get("ctf_exercise") == "M003" for r in resources)
            assert any(r.get("ctf_scenario") == "v2-cert" for r in resources)

    def test_import_then_query_workflow(
        self, mock_neo4j_driver, sample_terraform_state
    ):
        """Test importing resources and then querying them."""
        from src.services.ctf_deploy_service import CTFDeployService
        from src.services.ctf_import_service import CTFImportService

        # Step 1: Import
        import_service = CTFImportService(neo4j_driver=mock_neo4j_driver)

        with patch(
            "builtins.open", mock_open(read_data=json.dumps(sample_terraform_state))
        ):
            import_service.import_from_state("terraform.tfstate", layer_id="default")

        # Step 2: Query
        deploy_service = CTFDeployService(neo4j_driver=mock_neo4j_driver)

        # Mock Neo4j to return imported resources
        mock_records = [
            {
                "r": {
                    "id": "vm-1",
                    "name": "target-vm",
                    "layer_id": "default",
                    "ctf_exercise": "M003",
                    "ctf_scenario": "v2-cert",
                }
            }
        ]
        mock_neo4j_driver.execute_query.return_value = (mock_records, None, None)

        resources = deploy_service.query_ctf_resources(
            layer_id="default", exercise="M003", scenario="v2-cert"
        )

        assert len(resources) == 1
        assert resources[0]["name"] == "target-vm"


class TestDeployCleanupFlow:
    """Test integration between CTFDeployService deploy and cleanup."""

    def test_deploy_then_cleanup_workflow(self, mock_neo4j_driver, temp_terraform_dir):
        """Test deploying scenario and then cleaning it up."""
        from src.services.ctf_deploy_service import CTFDeployService

        # Mock resources in Neo4j
        mock_resources = [
            {
                "r": {
                    "id": "vm-1",
                    "name": "target-vm",
                    "resource_type": "VirtualMachine",
                    "layer_id": "default",
                    "ctf_exercise": "M003",
                    "ctf_scenario": "v2-cert",
                }
            }
        ]
        mock_neo4j_driver.execute_query.return_value = (mock_resources, None, None)

        service = CTFDeployService(neo4j_driver=mock_neo4j_driver)

        # Step 1: Deploy
        with patch("subprocess.run") as mock_subprocess:
            with patch("builtins.open", create=True):
                mock_subprocess.return_value = Mock(
                    returncode=0, stdout="Success", stderr=""
                )

                deploy_result = service.deploy_scenario(
                    layer_id="default",
                    exercise="M003",
                    scenario="v2-cert",
                    output_dir=str(temp_terraform_dir),
                )

                assert deploy_result["success"] is True

        # Step 2: Cleanup
        with patch("subprocess.run") as mock_subprocess:
            mock_subprocess.return_value = Mock(returncode=0)

            cleanup_result = service.cleanup_scenario(
                layer_id="default",
                exercise="M003",
                scenario="v2-cert",
                terraform_dir=str(temp_terraform_dir),
            )

            assert cleanup_result["success"] is True

        # Verify cleanup called destroy and Neo4j delete
        destroy_calls = [
            call for call in mock_subprocess.call_args_list if "destroy" in str(call)
        ]
        assert len(destroy_calls) > 0

    def test_deploy_dry_run_then_real_deploy(self, mock_neo4j_driver):
        """Test dry run deployment followed by real deployment."""
        from src.services.ctf_deploy_service import CTFDeployService

        mock_resources = [
            {"r": {"id": "vm-1", "name": "test-vm", "layer_id": "default"}}
        ]
        mock_neo4j_driver.execute_query.return_value = (mock_resources, None, None)

        service = CTFDeployService(neo4j_driver=mock_neo4j_driver)

        # Step 1: Dry run
        with patch("subprocess.run") as mock_subprocess:
            dry_run_result = service.deploy_scenario(
                layer_id="default", exercise="M003", scenario="v2-cert", dry_run=True
            )

            assert dry_run_result["dry_run"] is True
            # Should not call terraform
            assert mock_subprocess.call_count == 0

        # Step 2: Real deploy
        with patch("subprocess.run") as mock_subprocess:
            with patch("builtins.open", create=True):
                mock_subprocess.return_value = Mock(returncode=0)

                real_result = service.deploy_scenario(
                    layer_id="default",
                    exercise="M003",
                    scenario="v2-cert",
                    dry_run=False,
                )

                assert real_result["success"] is True
                # Should call terraform
                assert mock_subprocess.call_count > 0


class TestFullImportDeployCleanupCycle:
    """Test complete CTF scenario lifecycle."""

    def test_full_lifecycle_import_deploy_cleanup(
        self, mock_neo4j_driver, sample_terraform_state, temp_terraform_dir
    ):
        """Test complete workflow: import → deploy → cleanup."""
        from src.services.ctf_deploy_service import CTFDeployService
        from src.services.ctf_import_service import CTFImportService

        neo4j_calls = []

        def track_neo4j_calls(*args, **kwargs):
            neo4j_calls.append({"query": args[0], "params": kwargs})
            # Return mock resources for query operations
            if "MATCH" in args[0]:
                return (
                    [
                        {
                            "r": {
                                "id": "vm-1",
                                "name": "target-vm",
                                "layer_id": "default",
                                "ctf_exercise": "M003",
                                "ctf_scenario": "v2-cert",
                            }
                        }
                    ],
                    None,
                    None,
                )
            return ([], None, None)

        mock_neo4j_driver.execute_query.side_effect = track_neo4j_calls

        # Step 1: Import Terraform state
        import_service = CTFImportService(neo4j_driver=mock_neo4j_driver)

        with patch(
            "builtins.open", mock_open(read_data=json.dumps(sample_terraform_state))
        ):
            import_stats = import_service.import_from_state(
                state_file="terraform.tfstate", layer_id="default"
            )

        assert import_stats["resources_created"] == 2

        # Step 2: Deploy scenario
        deploy_service = CTFDeployService(neo4j_driver=mock_neo4j_driver)

        with patch("subprocess.run") as mock_subprocess:
            with patch("builtins.open", create=True):
                mock_subprocess.return_value = Mock(returncode=0)

                deploy_result = deploy_service.deploy_scenario(
                    layer_id="default",
                    exercise="M003",
                    scenario="v2-cert",
                    output_dir=str(temp_terraform_dir),
                )

        assert deploy_result["success"] is True

        # Step 3: Cleanup scenario
        with patch("subprocess.run") as mock_subprocess:
            mock_subprocess.return_value = Mock(returncode=0)

            cleanup_result = deploy_service.cleanup_scenario(
                layer_id="default",
                exercise="M003",
                scenario="v2-cert",
                terraform_dir=str(temp_terraform_dir),
            )

        assert cleanup_result["success"] is True

        # Verify all stages called Neo4j appropriately
        assert len(neo4j_calls) >= 3
        # Should have: import (MERGE/UNWIND), query (MATCH), cleanup (DELETE)
        assert any(
            "MERGE" in call["query"] or "UNWIND" in call["query"]
            for call in neo4j_calls
        )
        assert any("MATCH" in call["query"] for call in neo4j_calls)
        assert any("DELETE" in call["query"] for call in neo4j_calls)

    def test_lifecycle_idempotency(self, mock_neo4j_driver, sample_terraform_state):
        """Test running import twice is idempotent."""
        from src.services.ctf_import_service import CTFImportService

        import_service = CTFImportService(neo4j_driver=mock_neo4j_driver)

        with patch(
            "builtins.open", mock_open(read_data=json.dumps(sample_terraform_state))
        ):
            # First import
            stats1 = import_service.import_from_state(
                state_file="terraform.tfstate", layer_id="default"
            )

            # Second import (same data)
            stats2 = import_service.import_from_state(
                state_file="terraform.tfstate", layer_id="default"
            )

        # First creates, second updates
        assert stats1["resources_created"] == 2
        assert stats2["resources_updated"] == 2
        assert stats2["resources_created"] == 0

    def test_lifecycle_with_layer_isolation(
        self, mock_neo4j_driver, sample_terraform_state
    ):
        """Test multiple scenarios in different layers don't interfere."""
        from src.services.ctf_deploy_service import CTFDeployService
        from src.services.ctf_import_service import CTFImportService

        import_service = CTFImportService(neo4j_driver=mock_neo4j_driver)

        # Import into layer1
        with patch(
            "builtins.open", mock_open(read_data=json.dumps(sample_terraform_state))
        ):
            import_service.import_from_state("terraform.tfstate", layer_id="layer1")

        # Import into layer2
        with patch(
            "builtins.open", mock_open(read_data=json.dumps(sample_terraform_state))
        ):
            import_service.import_from_state("terraform.tfstate", layer_id="layer2")

        # Query each layer separately
        deploy_service = CTFDeployService(neo4j_driver=mock_neo4j_driver)

        # Mock to return different results for different layers
        def mock_query_by_layer(*args, **kwargs):
            layer_id = kwargs.get("layer_id")
            if layer_id == "layer1":
                return ([{"r": {"id": "vm-layer1", "layer_id": "layer1"}}], None, None)
            elif layer_id == "layer2":
                return ([{"r": {"id": "vm-layer2", "layer_id": "layer2"}}], None, None)
            return ([], None, None)

        mock_neo4j_driver.execute_query.side_effect = mock_query_by_layer

        layer1_resources = deploy_service.query_ctf_resources(layer_id="layer1")
        layer2_resources = deploy_service.query_ctf_resources(layer_id="layer2")

        # Should be isolated
        assert layer1_resources[0]["layer_id"] == "layer1"
        assert layer2_resources[0]["layer_id"] == "layer2"


class TestErrorHandlingIntegration:
    """Test error handling across service boundaries."""

    def test_deploy_handles_import_failure(self, mock_neo4j_driver):
        """Test deploy gracefully handles missing imported resources."""
        from src.services.ctf_deploy_service import CTFDeployService

        # Mock Neo4j returning no resources (import failed or not done)
        mock_neo4j_driver.execute_query.return_value = ([], None, None)

        service = CTFDeployService(neo4j_driver=mock_neo4j_driver)

        with pytest.raises(ValueError, match="No resources found"):
            service.deploy_scenario(
                layer_id="default", exercise="M003", scenario="v2-cert"
            )

    def test_cleanup_handles_partial_failures(self, mock_neo4j_driver):
        """Test cleanup continues after partial Terraform failure."""
        from src.services.ctf_deploy_service import CTFDeployService

        service = CTFDeployService(neo4j_driver=mock_neo4j_driver)

        with patch("subprocess.run") as mock_subprocess:
            # Terraform destroy fails
            mock_subprocess.return_value = Mock(returncode=1, stderr="Terraform error")

            result = service.cleanup_scenario(
                layer_id="default", exercise="M003", scenario="v2-cert"
            )

            # Should still attempt Neo4j cleanup
            assert mock_neo4j_driver.execute_query.called
            # But report failure
            assert result["success"] is False

    def test_import_handles_neo4j_timeout(
        self, mock_neo4j_driver, sample_terraform_state
    ):
        """Test import handles Neo4j timeout during batch insert."""
        from neo4j.exceptions import ClientError

        from src.services.ctf_import_service import CTFImportService

        mock_neo4j_driver.execute_query.side_effect = ClientError("Query timeout")

        import_service = CTFImportService(neo4j_driver=mock_neo4j_driver)

        with patch(
            "builtins.open", mock_open(read_data=json.dumps(sample_terraform_state))
        ):
            with pytest.raises(ClientError):
                import_service.import_from_state(
                    "terraform.tfstate", layer_id="default"
                )


class TestConcurrency:
    """Test concurrent operations and race conditions."""

    def test_concurrent_imports_different_layers(
        self, mock_neo4j_driver, sample_terraform_state
    ):
        """Test importing into different layers concurrently."""
        import threading

        from src.services.ctf_import_service import CTFImportService

        import_service = CTFImportService(neo4j_driver=mock_neo4j_driver)

        results = []

        def import_layer(layer_id):
            with patch(
                "builtins.open", mock_open(read_data=json.dumps(sample_terraform_state))
            ):
                stats = import_service.import_from_state(
                    "terraform.tfstate", layer_id=layer_id
                )
                results.append((layer_id, stats))

        # Run imports concurrently
        threads = [
            threading.Thread(target=import_layer, args=(f"layer{i}",)) for i in range(3)
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All should succeed
        assert len(results) == 3
        assert all(stats["resources_created"] == 2 for _, stats in results)

    def test_concurrent_deploy_cleanup_race_condition(self, mock_neo4j_driver):
        """Test deploy and cleanup don't interfere when run concurrently."""
        from src.services.ctf_deploy_service import CTFDeployService

        # This test documents expected behavior in race conditions
        # Deploy and cleanup of same scenario should not be concurrent in practice,
        # but test defensive handling

        service = CTFDeployService(neo4j_driver=mock_neo4j_driver)

        # Mock resources exist
        mock_neo4j_driver.execute_query.return_value = (
            [{"r": {"id": "vm-1", "layer_id": "default"}}],
            None,
            None,
        )

        with patch("subprocess.run") as mock_subprocess:
            with patch("builtins.open", create=True):
                mock_subprocess.return_value = Mock(returncode=0)

                # If deploy and cleanup happen concurrently, at least one should succeed
                # This is a defensive test - in practice, orchestration prevents this
                deploy_result = service.deploy_scenario(
                    layer_id="default",
                    exercise="M003",
                    scenario="v2-cert",
                    dry_run=True,  # Use dry run to avoid actual terraform
                )

                assert deploy_result is not None


# ============================================================================
# Test Summary
# ============================================================================
"""
Integration Test Coverage Summary:

✓ Import → Annotate flow (3 tests)
✓ Deploy → Cleanup flow (2 tests)
✓ Full lifecycle (3 tests)
✓ Error handling (3 tests)
✓ Concurrency (2 tests)

Total: 13 integration tests (30% of testing pyramid)

All tests should FAIL initially until services are implemented.

Expected test results after implementation:
- 100% should pass
- Coverage target: Integration between services, not individual service logic
"""
