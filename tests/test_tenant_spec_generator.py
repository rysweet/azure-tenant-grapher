import os
import random
import re
import tempfile
import uuid
from typing import Generator, Tuple

import pytest
from neo4j import GraphDatabase

from src.config_manager import SpecificationConfig
from src.container_manager import Neo4jContainerManager
from src.tenant_spec_generator import ResourceAnonymizer, TenantSpecificationGenerator


class TestTenantSpecificationGenerator:
    """
    All tests use an ephemeral, isolated Neo4j Docker container on a random port and unique volume.
    No test ever touches the main Neo4j config, port, or data.
    Tests are never skipped.
    """

    @pytest.fixture(scope="class")
    def isolated_neo4j_container(
        self,
    ) -> Generator[Tuple[str, str, str, str], None, None]:
        """
        SELF-CONTAINED FIXTURE: Creates an isolated Neo4j test container on a random port and unique volume.
        - Each test run uses a unique Docker volume and a temporary compose file.
        - No test ever touches the main Neo4j config, port, or data.
        - All resources are cleaned up after the test.
        """
        import yaml

        port = random.randint(30000, 40000)
        test_session_id = str(uuid.uuid4())[:8]
        test_database_name = f"test_tenant_spec_{test_session_id}"

        unique_volume = f"test-neo4j-data-{test_session_id}"
        temp_compose = tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False)
        with open("docker/docker-compose.yml") as f:
            compose = yaml.safe_load(f)
        compose["services"]["neo4j"]["volumes"][0] = f"{unique_volume}:/data"
        compose["services"]["neo4j"]["container_name"] = (
            f"azure-tenant-grapher-neo4j-{test_session_id}"
        )
        compose.setdefault("volumes", {})[unique_volume] = None
        yaml.dump(compose, temp_compose)
        temp_compose.close()
        temp_compose_path = temp_compose.name

        os.environ["NEO4J_CONTAINER_NAME"] = (
            f"azure-tenant-grapher-neo4j-{test_session_id}"
        )
        os.environ["NEO4J_URI"] = f"bolt://localhost:{port}"
        os.environ["NEO4J_USER"] = "neo4j"
        os.environ["NEO4J_PASSWORD"] = Neo4jContainerManager.generate_random_password()
        os.environ["NEO4J_PORT"] = str(port)

        container_manager = Neo4jContainerManager(compose_file=temp_compose_path)
        if not container_manager.is_docker_available():
            pytest.fail(
                "Docker is not available - cannot create isolated test container"
            )
        if not container_manager.is_compose_available():
            pytest.fail(
                "Docker Compose is not available - cannot create isolated test container"
            )

        if not container_manager.setup_neo4j():
            pytest.fail("Failed to start isolated Neo4j container for testing")
        if not container_manager.wait_for_neo4j_ready(timeout=60):
            pytest.fail("Isolated Neo4j container did not become ready")

        uri = f"bolt://localhost:{port}"
        user = os.environ["NEO4J_USER"]
        password = os.environ["NEO4J_PASSWORD"]

        print(
            f"✅ SAFE TEST: Using isolated database {test_database_name!r} on port {port}"
        )

        try:
            yield uri, user, password, test_database_name
        finally:
            container_manager.stop_neo4j_container()
            container_manager.cleanup()
            try:
                os.unlink(temp_compose_path)
            except Exception:
                pass

    @pytest.fixture
    def setup_test_data(
        self, isolated_neo4j_container: Tuple[str, str, str, str]
    ) -> Generator[Tuple[str, str, str, str], None, None]:
        """
        SELF-CONTAINED DATA FIXTURE: Sets up isolated test data in the test database.
        """
        uri, user, password, test_database_name = isolated_neo4j_container

        driver = GraphDatabase.driver(uri, auth=(user, password))

        try:
            with driver.session(database="neo4j") as session:
                session.run("MATCH (n:TestResource) DETACH DELETE n")
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
                        properties=f'{{"os": "linux", "ip": "10.0.0.{i}"}}',
                        tags='{"env": "test"}',
                    )
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
                        properties='{"tier": "Standard"}',
                        tags='{"env": "test"}',
                    )
                session.run("""
                    MATCH (a:TestResource {type: 'Microsoft.Compute/virtualMachines'}),
                          (b:TestResource {type: 'Microsoft.Storage/storageAccounts'})
                    WITH a, b LIMIT 5
                    CREATE (a)-[:DEPENDS_ON]->(b)
                """)
            yield uri, user, password, test_database_name
        finally:
            try:
                with driver.session(database="neo4j") as session:
                    session.run("MATCH (n:TestResource) DETACH DELETE n")
            except Exception:
                pass
            finally:
                driver.close()

    def test_spec_file_created_and_resource_limit(
        self, setup_test_data: Tuple[str, str, str, str]
    ) -> None:
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
            assert (
                len([line for line in content.splitlines() if line.startswith("### ")])
                <= 12
            )

    def test_names_anonymized_and_no_real_ids(
        self, setup_test_data: Tuple[str, str, str, str]
    ) -> None:
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
            assert not any(x in content for x in ["test-vm", "sub-1234", "rg-test"])
            assert "[anonymized]" not in content.lower()

    def test_relationships_preserved(
        self, setup_test_data: Tuple[str, str, str, str]
    ) -> None:
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
            rel_count = content.count("- DEPENDS_ON")
            assert rel_count >= 1

    def test_limit_none_generates_spec_successfully(
        self, setup_test_data: Tuple[str, str, str, str]
    ) -> None:
        uri, user, password, _ = setup_test_data
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SpecificationConfig(
                resource_limit=None,
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
                f.read()  # Verify file is readable


def test_anonymize_relationship_with_none_target_type():
    """Regression: passing target_type=None does not crash, returns res- prefix."""
    anonymizer = ResourceAnonymizer(seed="testseed")
    rel = {
        "source_id": "x",
        "type": "depends_on",
        "target_id": "abc123",
        "target_name": "test-target",
        # Simulate target_type=None (Neo4j/driver deserialized)
        "target_type": None,
        "llm_description": "",
    }
    try:
        result = anonymizer.anonymize_relationship(rel)
    except Exception as exc:
        pytest.fail(f"anonymize_relationship raised: {exc}")
    # Placeholder should be of form "res-..."
    target_placeholder = result["target_id"]
    assert target_placeholder.startswith("res-"), (
        f"Expected prefix 'res-', got {target_placeholder}"
    )
    # Optionally: check complete structure
    assert re.match(r"^res-[a-z0-9]+-[0-9a-f]{8}$", target_placeholder)
