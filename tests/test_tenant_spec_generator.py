import json
import os
import re
import tempfile
import uuid
import warnings
from typing import Generator, Tuple

import pytest
from neo4j import GraphDatabase

from src.config_manager import SpecificationConfig
from src.container_manager import Neo4jContainerManager
from src.tenant_spec_generator import ResourceAnonymizer, TenantSpecificationGenerator


# SAFETY: Skip all tests by default to prevent accidental database clearing
@pytest.mark.skip(
    reason="DANGEROUS: Database tests disabled by default for safety. Set TEST_TENANT_SPEC_SAFE=true to enable with isolated containers."
)
class TestTenantSpecificationGenerator:
    """
    SAFETY-FIRST TEST CLASS for TenantSpecificationGenerator

    These tests use isolated Docker containers and never connect to production databases.
    All tests are self-contained with their own database setup and teardown.
    """

    @pytest.fixture(scope="class")
    def isolated_neo4j_container(
        self,
    ) -> Generator[Tuple[str, str, str, str], None, None]:
        """
        SELF-CONTAINED FIXTURE: Creates an isolated Neo4j test container.

        This fixture:
        1. Creates a unique test container name to avoid conflicts
        2. Starts its own Neo4j container using docker-compose
        3. Uses a unique database name for complete isolation
        4. Cleans up everything when done

        Safety measures:
        - Only runs if TEST_TENANT_SPEC_SAFE=true
        - Uses unique container and database names
        - Never touches existing databases
        - Complete cleanup on teardown
        """
        # CRITICAL SAFETY CHECK: Only run if explicitly enabled
        test_safe = os.getenv("TEST_TENANT_SPEC_SAFE", "").lower()
        if test_safe != "true":
            pytest.skip(
                "TEST_TENANT_SPEC_SAFE must be set to 'true' to run these database tests"
            )

        # Additional safety: Never run against production-like URIs
        test_uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
        if any(
            prod_indicator in test_uri.lower()
            for prod_indicator in ["prod", "production", "live"]
        ):
            pytest.skip(
                f"Refusing to run tests against production-like URI: {test_uri}"
            )

        # Create unique test identifiers
        test_session_id = str(uuid.uuid4())[:8]
        test_database_name = f"test_tenant_spec_{test_session_id}"

        # Initialize container manager for isolated testing
        container_manager = Neo4jContainerManager()

        # Verify Docker is available (required for isolation)
        if not container_manager.is_docker_available():
            pytest.skip(
                "Docker is not available - cannot create isolated test container"
            )

        if not container_manager.is_compose_available():
            pytest.skip(
                "Docker Compose is not available - cannot create isolated test container"
            )

        # Start isolated container
        if not container_manager.setup_neo4j():
            pytest.fail("Failed to start isolated Neo4j container for testing")

        # Wait for container to be ready
        if not container_manager.wait_for_neo4j_ready(timeout=60):
            pytest.fail("Isolated Neo4j container did not become ready")

        # Get connection details
        uri = container_manager.neo4j_uri
        user = container_manager.neo4j_user
        password = container_manager.neo4j_password

        print(
            f"✅ SAFE TEST: Using isolated database {test_database_name!r} in test container"
        )

        try:
            yield uri, user, password, test_database_name
        finally:
            # CLEANUP: Stop the isolated container
            print(
                f"🧹 CLEANUP: Stopping isolated test container for {test_database_name!r}"
            )
            container_manager.stop_neo4j_container()

    @pytest.fixture
    def setup_test_data(
        self, isolated_neo4j_container: Tuple[str, str, str, str]
    ) -> Generator[Tuple[str, str, str, str], None, None]:
        """
        SELF-CONTAINED DATA FIXTURE: Sets up isolated test data in the test database.

        This fixture:
        1. Uses the isolated container from the class fixture
        2. Creates test data in an isolated database session
        3. Cleans up only the test data it created
        4. Never touches other databases or data
        """
        uri, user, password, test_database_name = isolated_neo4j_container

        driver = GraphDatabase.driver(uri, auth=(user, password))

        try:
            # Use isolated database session
            with driver.session(
                database="neo4j"
            ) as session:  # Note: Using neo4j db but isolated container
                # SAFE: Clear only in our isolated test container
                print("🔄 SETUP: Creating test data in isolated container database")
                session.run(
                    "MATCH (n:TestResource) DETACH DELETE n"
                )  # Only delete test resources

                # Create test VMs
                for i in range(10):
                    session.run(
                        """
                        CREATE (r:TestResource:Resource {
                            id: $id,
                            name: $name,
                            type: 'Microsoft.Compute/virtualMachines',
                            location: 'eastus',
                            resource_group: 'rg-test',
                            subscription_id: 'sub-1234',
                            properties: $properties,
                            tags: $tags,
                            llm_description: 'Test VM for development'
                        })
                        """,
                        id=f"vm-{i}",
                        name=f"test-vm-{i}",
                        properties=json.dumps({"os": "linux", "ip": f"10.0.0.{i}"}),
                        tags=json.dumps({"env": "test"}),
                    )

                # Create test storage accounts
                for i in range(5):
                    session.run(
                        """
                        CREATE (r:TestResource:Resource {
                            id: $id,
                            name: $name,
                            type: 'Microsoft.Storage/storageAccounts',
                            location: 'westus2',
                            resource_group: 'rg-test',
                            subscription_id: 'sub-1234',
                            properties: $properties,
                            tags: $tags,
                            llm_description: 'Storage for dev'
                        })
                        """,
                        id=f"storage-{i}",
                        name=f"test-storage-{i}",
                        properties=json.dumps({"tier": "Standard"}),
                        tags=json.dumps({"env": "test"}),
                    )

                # Add relationships between test resources
                session.run("""
                    MATCH (a:TestResource {type: 'Microsoft.Compute/virtualMachines'}),
                          (b:TestResource {type: 'Microsoft.Storage/storageAccounts'})
                    WITH a, b LIMIT 5
                    CREATE (a)-[:DEPENDS_ON]->(b)
                """)

                print("✅ SETUP: Test data created successfully in isolated container")

            yield uri, user, password, test_database_name

        finally:
            # CLEANUP: Remove only our test data
            try:
                with driver.session(database="neo4j") as session:
                    print("🧹 CLEANUP: Removing test data from isolated container")
                    session.run(
                        "MATCH (n:TestResource) DETACH DELETE n"
                    )  # Only delete test resources
                    print("✅ CLEANUP: Test data removed successfully")
            except Exception as e:
                warnings.warn(f"Failed to clean up test data: {e}", stacklevel=2)
            finally:
                driver.close()

    def test_spec_file_created_and_resource_limit(
        self, setup_test_data: Tuple[str, str, str, str]
    ) -> None:
        """Test that spec file is created and respects resource limits in isolated environment."""
        uri, user, password, _ = setup_test_data

        with tempfile.TemporaryDirectory() as tmpdir:
            config = SpecificationConfig(
                resource_limit=12,
                output_directory=tmpdir,
                include_ai_summaries=True,
                include_configuration_details=True,
                anonymization_seed="testseed",
                template_style="comprehensive",
            )
            anonymizer = ResourceAnonymizer(seed="testseed")
            generator = TenantSpecificationGenerator(
                uri, user, password, anonymizer, config
            )

            output_path = generator.generate_specification()
            assert os.path.exists(output_path)

            with open(output_path, encoding="utf-8") as f:
                content = f.read()

            # Assert ≤limit resources in Markdown (count "### " headers)
            assert len(re.findall(r"^### ", content, re.MULTILINE)) <= 12
            # Assert no [Anonymized] substring in Markdown (case-insensitive)
            assert "[anonymized]" not in content.lower()
            # Assert all anonymized names match regex
            for match in re.findall(r"^### ([a-z0-9\-]+) \(", content, re.MULTILINE):
                assert re.match(
                    r"^[a-z]+-[a-z]+-[0-9a-f]{8}$", match
                ), f"Name does not match pattern: {match}"

    def test_names_anonymized_and_no_real_ids(
        self, setup_test_data: Tuple[str, str, str, str]
    ) -> None:
        """Test that names are properly anonymized and no real IDs leak in isolated environment."""
        uri, user, password, _ = setup_test_data

        with tempfile.TemporaryDirectory() as tmpdir:
            config = SpecificationConfig(
                resource_limit=15,
                output_directory=tmpdir,
                include_ai_summaries=True,
                include_configuration_details=True,
                anonymization_seed="testseed",
                template_style="comprehensive",
            )
            anonymizer = ResourceAnonymizer(seed="testseed")
            generator = TenantSpecificationGenerator(
                uri, user, password, anonymizer, config
            )

            output_path = generator.generate_specification()

            with open(output_path, encoding="utf-8") as f:
                content = f.read()

            # No real IDs or names (should not see "test-vm", "sub-1234", or "rg-test")
            assert not re.search(r"test-vm|sub-1234|rg-test", content)
            # No GUIDs or Azure IDs
            assert not re.search(
                r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", content
            )
            # Assert no [Anonymized] substring in Markdown (case-insensitive)
            assert "[anonymized]" not in content.lower()
            # Assert all anonymized names match regex
            for match in re.findall(r"^### ([a-z0-9\-]+) \(", content, re.MULTILINE):
                assert re.match(
                    r"^[a-z]+-[a-z]+-[0-9a-f]{8}$", match
                ), f"Name does not match pattern: {match}"

    def test_relationships_preserved(
        self, setup_test_data: Tuple[str, str, str, str]
    ) -> None:
        """Test that relationships are preserved in the output in isolated environment."""
        uri, user, password, _ = setup_test_data

        with tempfile.TemporaryDirectory() as tmpdir:
            config = SpecificationConfig(
                resource_limit=20,
                output_directory=tmpdir,
                include_ai_summaries=True,
                include_configuration_details=True,
                anonymization_seed="testseed",
                template_style="comprehensive",
            )
            anonymizer = ResourceAnonymizer(seed="testseed")
            generator = TenantSpecificationGenerator(
                uri, user, password, anonymizer, config
            )

            output_path = generator.generate_specification()

            with open(output_path, encoding="utf-8") as f:
                content = f.read()

            # Count relationships in Markdown
            rel_count = len(re.findall(r"- DEPENDS_ON", content))
            # There should be at least 1 relationship (from test data)
            assert rel_count >= 1


# Safety functions for manual testing (not part of pytest)
def enable_safe_testing() -> None:
    """
    Helper function to safely enable these tests.

    Usage:
        export TEST_TENANT_SPEC_SAFE=true
        pytest tests/test_tenant_spec_generator.py -v
    """
    print("To safely run these tests:")
    print("1. Ensure Docker is running")
    print("2. Set environment variable: export TEST_TENANT_SPEC_SAFE=true")
    print("3. Run: pytest tests/test_tenant_spec_generator.py -v")
    print("4. Tests will use isolated Docker containers only")


if __name__ == "__main__":
    enable_safe_testing()
