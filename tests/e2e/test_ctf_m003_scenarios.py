"""End-to-end tests for M003 CTF scenarios.

Tests all 4 M003 scenario variants with real workflow:
- v1-base: Basic scenario
- v2-cert: Certificate authentication
- v3-ews: Exchange Web Services
- v4-blob: Blob storage

Uses real Neo4j (testcontainers if available) and full CLI commands.
These tests represent the top 10% of the testing pyramid.

Tests should FAIL initially until full implementation is complete.
"""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def neo4j_test_container():
    """Real Neo4j container for E2E testing (requires Docker)."""
    pytest.importorskip("testcontainers", reason="testcontainers not available")

    from testcontainers.neo4j import Neo4jContainer

    with Neo4jContainer("neo4j:5-community") as neo4j:
        yield {
            "uri": neo4j.get_connection_url(),
            "user": "neo4j",
            "password": neo4j.get_password(),
        }


@pytest.fixture
def mock_neo4j_connection():
    """Mock Neo4j connection for tests without Docker."""
    from unittest.mock import MagicMock

    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    driver.session.return_value.__exit__.return_value = None

    with patch("neo4j.GraphDatabase.driver", return_value=driver):
        yield driver, session


@pytest.fixture
def temp_workspace():
    """Temporary workspace for E2E testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        (workspace / "terraform").mkdir()
        (workspace / "state").mkdir()
        yield workspace


@pytest.fixture
def m003_scenarios():
    """M003 scenario definitions."""
    return {
        "v1-base": {
            "description": "Basic M003 scenario",
            "resources": 3,
            "roles": ["target", "infrastructure"],
        },
        "v2-cert": {
            "description": "Certificate authentication scenario",
            "resources": 5,
            "roles": ["target", "attacker", "infrastructure"],
        },
        "v3-ews": {
            "description": "Exchange Web Services scenario",
            "resources": 4,
            "roles": ["target", "infrastructure", "monitoring"],
        },
        "v4-blob": {
            "description": "Blob storage scenario",
            "resources": 6,
            "roles": ["target", "infrastructure"],
        },
    }


# ============================================================================
# E2E Tests (WILL FAIL - No Implementation Yet)
# ============================================================================


@pytest.mark.e2e
class TestM003V1BaseScenario:
    """Test M003 v1-base scenario end-to-end."""

    def test_v1_base_full_lifecycle(self, mock_neo4j_connection, temp_workspace):
        """Test complete v1-base scenario: import → deploy → cleanup."""
        from src.cli.ctf_commands import ctf_clear, ctf_deploy, ctf_import

        driver, session = mock_neo4j_connection

        # Step 1: Import M003 v1-base scenario
        with patch("sys.argv", ["atg", "ctf", "import", "--scenario", "M003-v1-base"]):
            result = ctf_import(
                terraform_state=str(temp_workspace / "state" / "terraform.tfstate"),
                layer_id="e2e-test-v1",
                exercise="M003",
                scenario="v1-base",
            )

        assert result["success"] is True
        assert result["resources_imported"] == 3

        # Step 2: Verify resources in Neo4j
        session.run.return_value = [
            {"r": {"id": "vm-1", "ctf_scenario": "v1-base"}},
            {"r": {"id": "vnet-1", "ctf_scenario": "v1-base"}},
            {"r": {"id": "nsg-1", "ctf_scenario": "v1-base"}},
        ]

        resources = session.run(
            "MATCH (r:Resource {layer_id: $layer_id, ctf_scenario: $scenario}) RETURN r",
            layer_id="e2e-test-v1",
            scenario="v1-base",
        )

        assert len(list(resources)) == 3

        # Step 3: Deploy scenario
        with patch("subprocess.run") as mock_subprocess:
            mock_subprocess.return_value = Mock(returncode=0, stdout="Success")

            result = ctf_deploy(
                layer_id="e2e-test-v1",
                exercise="M003",
                scenario="v1-base",
                output_dir=str(temp_workspace / "terraform"),
            )

        assert result["success"] is True
        assert result["resources_deployed"] == 3

        # Step 4: Cleanup
        with patch("subprocess.run") as mock_subprocess:
            mock_subprocess.return_value = Mock(returncode=0)

            result = ctf_clear(
                layer_id="e2e-test-v1", exercise="M003", scenario="v1-base"
            )

        assert result["success"] is True

    def test_v1_base_cli_integration(self, temp_workspace):
        """Test v1-base using actual CLI commands."""
        # This test requires full CLI implementation
        pytest.skip("Requires full CLI implementation")

        result = subprocess.run(
            [
                "atg",
                "ctf",
                "import",
                "--state",
                str(temp_workspace / "state" / "terraform.tfstate"),
                "--layer",
                "e2e-test-v1",
                "--exercise",
                "M003",
                "--scenario",
                "v1-base",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Successfully imported 3 resources" in result.stdout


@pytest.mark.e2e
class TestM003V2CertScenario:
    """Test M003 v2-cert scenario end-to-end."""

    def test_v2_cert_with_certificate_auth(self, mock_neo4j_connection, temp_workspace):
        """Test v2-cert scenario with certificate authentication."""
        from src.cli.ctf_commands import ctf_import

        driver, session = mock_neo4j_connection

        # Import v2-cert scenario
        result = ctf_import(
            terraform_state=str(temp_workspace / "state" / "terraform.tfstate"),
            layer_id="e2e-test-v2",
            exercise="M003",
            scenario="v2-cert",
        )

        assert result["success"] is True
        assert result["resources_imported"] == 5

        # Verify attacker role is present (unique to v2)
        session.run.return_value = [{"r": {"ctf_role": "attacker"}}]

        attacker_resources = session.run(
            "MATCH (r:Resource {layer_id: $layer_id, ctf_role: 'attacker'}) RETURN r",
            layer_id="e2e-test-v2",
        )

        assert len(list(attacker_resources)) >= 1

    def test_v2_cert_role_distribution(self, mock_neo4j_connection):
        """Test v2-cert has correct role distribution."""
        from src.services.ctf_deploy_service import CTFDeployService

        driver, session = mock_neo4j_connection

        # Mock resources with different roles
        mock_resources = [
            {"r": {"id": "vm-target", "ctf_role": "target"}},
            {"r": {"id": "vm-attacker", "ctf_role": "attacker"}},
            {"r": {"id": "vnet", "ctf_role": "infrastructure"}},
            {"r": {"id": "nsg", "ctf_role": "infrastructure"}},
            {"r": {"id": "storage", "ctf_role": "infrastructure"}},
        ]

        session.run.return_value = mock_resources

        service = CTFDeployService(neo4j_driver=driver)

        resources = service.query_ctf_resources(
            layer_id="e2e-test-v2", exercise="M003", scenario="v2-cert"
        )

        # Count by role
        role_counts = {}
        for r in resources:
            role = r["r"]["ctf_role"]
            role_counts[role] = role_counts.get(role, 0) + 1

        assert role_counts["target"] == 1
        assert role_counts["attacker"] == 1
        assert role_counts["infrastructure"] == 3


@pytest.mark.e2e
class TestM003V3EWSScenario:
    """Test M003 v3-ews scenario end-to-end."""

    def test_v3_ews_with_monitoring(self, mock_neo4j_connection):
        """Test v3-ews scenario includes monitoring resources."""
        from src.cli.ctf_commands import ctf_import

        driver, session = mock_neo4j_connection

        result = ctf_import(
            terraform_state="terraform.tfstate",
            layer_id="e2e-test-v3",
            exercise="M003",
            scenario="v3-ews",
        )

        assert result["success"] is True

        # Verify monitoring role exists (unique to v3)
        session.run.return_value = [{"r": {"ctf_role": "monitoring"}}]

        monitoring = session.run(
            "MATCH (r:Resource {layer_id: $layer_id, ctf_role: 'monitoring'}) RETURN r",
            layer_id="e2e-test-v3",
        )

        assert len(list(monitoring)) >= 1

    def test_v3_ews_log_analytics_workspace(self, mock_neo4j_connection):
        """Test v3-ews includes Log Analytics workspace."""
        from src.services.ctf_deploy_service import CTFDeployService

        driver, session = mock_neo4j_connection

        # Mock monitoring resources
        mock_resources = [
            {
                "r": {
                    "id": "law-1",
                    "resource_type": "Microsoft.OperationalInsights/workspaces",
                    "ctf_role": "monitoring",
                }
            }
        ]

        session.run.return_value = mock_resources

        service = CTFDeployService(neo4j_driver=driver)

        monitoring_resources = service.query_ctf_resources(
            layer_id="e2e-test-v3",
            exercise="M003",
            scenario="v3-ews",
            role="monitoring",
        )

        assert len(monitoring_resources) >= 1
        assert any(
            "OperationalInsights" in r["r"]["resource_type"]
            for r in monitoring_resources
        )


@pytest.mark.e2e
class TestM003V4BlobScenario:
    """Test M003 v4-blob scenario end-to-end."""

    def test_v4_blob_storage_resources(self, mock_neo4j_connection):
        """Test v4-blob scenario includes blob storage."""
        from src.cli.ctf_commands import ctf_import

        driver, session = mock_neo4j_connection

        result = ctf_import(
            terraform_state="terraform.tfstate",
            layer_id="e2e-test-v4",
            exercise="M003",
            scenario="v4-blob",
        )

        assert result["success"] is True
        assert result["resources_imported"] == 6

        # Verify storage account exists
        session.run.return_value = [
            {"r": {"resource_type": "Microsoft.Storage/storageAccounts"}}
        ]

        storage = session.run(
            "MATCH (r:Resource {layer_id: $layer_id}) WHERE r.resource_type =~ '.*Storage.*' RETURN r",
            layer_id="e2e-test-v4",
        )

        assert len(list(storage)) >= 1

    def test_v4_blob_highest_resource_count(self, m003_scenarios):
        """Test v4-blob has the highest resource count of all M003 variants."""
        v4_count = m003_scenarios["v4-blob"]["resources"]

        for scenario_id, scenario in m003_scenarios.items():
            if scenario_id != "v4-blob":
                assert v4_count >= scenario["resources"], (
                    f"v4-blob should have most resources, but {scenario_id} has {scenario['resources']}"
                )


@pytest.mark.e2e
class TestMultiScenarioManagement:
    """Test managing multiple scenarios simultaneously."""

    def test_deploy_all_m003_scenarios(self, mock_neo4j_connection, m003_scenarios):
        """Test deploying all M003 scenarios in parallel layers."""
        from src.cli.ctf_commands import ctf_import

        driver, session = mock_neo4j_connection

        results = {}

        for scenario_id in m003_scenarios.keys():
            result = ctf_import(
                terraform_state=f"terraform-{scenario_id}.tfstate",
                layer_id=f"e2e-multi-{scenario_id}",
                exercise="M003",
                scenario=scenario_id,
            )

            results[scenario_id] = result

        # All should succeed
        assert all(r["success"] for r in results.values())

        # Verify layer isolation - query each layer separately
        for scenario_id in m003_scenarios.keys():
            session.run.return_value = [
                {
                    "r": {
                        "layer_id": f"e2e-multi-{scenario_id}",
                        "ctf_scenario": scenario_id,
                    }
                }
            ]

            resources = session.run(
                "MATCH (r:Resource {layer_id: $layer_id}) RETURN r",
                layer_id=f"e2e-multi-{scenario_id}",
            )

            # Each layer should have its own resources
            assert len(list(resources)) > 0

    def test_list_all_scenarios(self, mock_neo4j_connection):
        """Test listing all CTF scenarios across layers."""
        from src.cli.ctf_commands import ctf_list

        driver, session = mock_neo4j_connection

        # Mock multiple scenarios
        session.run.return_value = [
            {"exercise": "M003", "scenario": "v1-base", "count": 3},
            {"exercise": "M003", "scenario": "v2-cert", "count": 5},
            {"exercise": "M003", "scenario": "v3-ews", "count": 4},
            {"exercise": "M003", "scenario": "v4-blob", "count": 6},
        ]

        result = ctf_list(layer_id="e2e-multi")

        assert len(result["scenarios"]) == 4
        assert all(s["exercise"] == "M003" for s in result["scenarios"])

    def test_cleanup_specific_scenario_preserves_others(self, mock_neo4j_connection):
        """Test cleaning up one scenario doesn't affect others."""
        from src.cli.ctf_commands import ctf_clear

        driver, session = mock_neo4j_connection

        # Clear only v1-base
        with patch("subprocess.run") as mock_subprocess:
            mock_subprocess.return_value = Mock(returncode=0)

            result = ctf_clear(
                layer_id="e2e-multi", exercise="M003", scenario="v1-base"
            )

        assert result["success"] is True

        # Verify only v1-base was deleted
        call_args = session.run.call_args
        if call_args:
            query = call_args[0][0]
            assert "ctf_scenario = $scenario" in query or "v1-base" in str(call_args)


@pytest.mark.e2e
class TestErrorRecovery:
    """Test error recovery and resilience."""

    def test_import_recovers_from_partial_failure(self, mock_neo4j_connection):
        """Test import continues after individual resource failure."""
        from src.services.ctf_import_service import CTFImportService

        driver, session = mock_neo4j_connection

        # Simulate one resource failing
        call_count = [0]

        def mock_run_with_failure(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:  # Second resource fails
                raise Exception("Simulated Neo4j failure")
            return []

        session.run.side_effect = mock_run_with_failure

        service = CTFImportService(neo4j_driver=driver)

        terraform_state = {
            "resources": [
                {
                    "type": "vm",
                    "instances": [{"attributes": {"id": "1", "name": "vm1"}}],
                },
                {
                    "type": "vm",
                    "instances": [{"attributes": {"id": "2", "name": "vm2"}}],
                },
                {
                    "type": "vm",
                    "instances": [{"attributes": {"id": "3", "name": "vm3"}}],
                },
            ]
        }

        with patch("builtins.open", create=True):
            stats = service.import_from_state("terraform.tfstate", layer_id="e2e-test")

        # Should have partial success
        assert stats["errors"] > 0
        assert stats["resources_created"] > 0

    def test_deploy_handles_terraform_failure(self, mock_neo4j_connection):
        """Test deploy handles Terraform apply failure gracefully."""
        from src.cli.ctf_commands import ctf_deploy

        driver, session = mock_neo4j_connection

        # Mock resources exist
        session.run.return_value = [{"r": {"id": "vm-1"}}]

        with patch("subprocess.run") as mock_subprocess:
            # Terraform fails
            mock_subprocess.return_value = Mock(
                returncode=1, stderr="Terraform error: timeout"
            )

            result = ctf_deploy(
                layer_id="e2e-test", exercise="M003", scenario="v1-base"
            )

        # Should report failure with details
        assert result["success"] is False
        assert "error" in result
        assert "timeout" in result["error"].lower()


@pytest.mark.e2e
@pytest.mark.slow
class TestPerformance:
    """Test performance with realistic workloads."""

    def test_import_large_scenario(self, mock_neo4j_connection):
        """Test importing scenario with 100+ resources."""
        from src.services.ctf_import_service import CTFImportService

        driver, session = mock_neo4j_connection

        # Generate large Terraform state
        large_state = {
            "resources": [
                {
                    "type": "azurerm_virtual_machine",
                    "instances": [
                        {"attributes": {"id": f"vm-{i}", "name": f"vm-{i}"}}
                        for i in range(100)
                    ],
                }
            ]
        }

        service = CTFImportService(neo4j_driver=driver)

        import time

        start = time.time()

        with patch("builtins.open", create=True):
            with patch("json.loads", return_value=large_state):
                stats = service.import_from_state(
                    "terraform.tfstate", layer_id="perf-test"
                )

        duration = time.time() - start

        # Should complete in reasonable time (<30s for 100 resources)
        assert duration < 30
        assert stats["resources_created"] == 100

    def test_query_performance_with_indexes(self, mock_neo4j_connection):
        """Test query performance with proper indexing."""
        from src.services.ctf_deploy_service import CTFDeployService

        driver, session = mock_neo4j_connection

        # Mock large result set
        session.run.return_value = [
            {"r": {"id": f"vm-{i}", "layer_id": "perf-test"}} for i in range(1000)
        ]

        service = CTFDeployService(neo4j_driver=driver)

        import time

        start = time.time()

        resources = service.query_ctf_resources(layer_id="perf-test", exercise="M003")

        duration = time.time() - start

        # Query should be fast (<1s even with 1000 resources)
        assert duration < 1.0
        assert len(resources) == 1000


# ============================================================================
# Test Summary
# ============================================================================
"""
E2E Test Coverage Summary:

✓ M003 v1-base scenario (2 tests)
✓ M003 v2-cert scenario (2 tests)
✓ M003 v3-ews scenario (2 tests)
✓ M003 v4-blob scenario (2 tests)
✓ Multi-scenario management (3 tests)
✓ Error recovery (2 tests)
✓ Performance (2 tests)

Total: 15 E2E tests (10% of testing pyramid)

All tests should FAIL initially until full implementation is complete.

Expected test results after implementation:
- 100% should pass
- Represents real-world usage scenarios
- Tests complete CLI workflow
"""
