import json
import os
import re
import shutil
import tempfile

import pytest
from neo4j import GraphDatabase
import socket
import subprocess
import time
import uuid

from src.config_manager import SpecificationConfig
from src.tenant_spec_generator import ResourceAnonymizer, TenantSpecificationGenerator


@pytest.fixture(scope="module")
def neo4j_test_graph():
    """
    Ensure a Neo4j instance is running on localhost:7688 for integration tests.
    If not running, start a Docker container and clean up after.
    """
    import atexit

    host = "localhost"
    port = 7688
    user = "neo4j"
    password = "azure-grapher-2024"
    uri = f"bolt://{host}:{port}"

    def is_neo4j_up():
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except Exception:
            return False

    container_name = None
    started_container = False

    if not is_neo4j_up():
        # Start Neo4j Docker container
        container_name = f"test-neo4j-{uuid.uuid4().hex[:8]}"
        docker_cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "-p", f"{port}:7687",
            "-e", f"NEO4J_AUTH={user}/{password}",
            "neo4j:5.19"
        ]
        subprocess.check_output(docker_cmd)
        started_container = True

        # Register cleanup in case of interruption
        def cleanup():
            subprocess.run(["docker", "rm", "-f", container_name], check=False)
        atexit.register(cleanup)

        # Wait for Neo4j Bolt handshake to succeed
        bolt_ready = False
        for _ in range(90):
            try:
                # Try to connect with the Neo4j driver (handshake)
                test_driver = GraphDatabase.driver(uri, auth=(user, password))
                with test_driver.session() as session:
                    session.run("RETURN 1")
                test_driver.close()
                bolt_ready = True
                break
            except Exception:
                time.sleep(1)
        if not bolt_ready:
            cleanup()
            raise RuntimeError("Neo4j Docker container did not become Bolt-ready on port 7688")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as session:
            # Clean and create ≤50 test nodes/resources
            session.run("MATCH (n) DETACH DELETE n")
            for i in range(10):
                session.run(
                    """
                    CREATE (r:Resource {
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
            for i in range(5):
                session.run(
                    """
                    CREATE (r:Resource {
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
            # Add relationships
            session.run("""
                MATCH (a:Resource {type: 'Microsoft.Compute/virtualMachines'}), (b:Resource {type: 'Microsoft.Storage/storageAccounts'})
                WITH a, b LIMIT 5
                CREATE (a)-[:DEPENDS_ON]->(b)
            """)
        yield uri, user, password
        # Teardown: clean up
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
    finally:
        driver.close()
        # Stop the container if we started it
        if started_container and container_name:
            subprocess.run(["docker", "rm", "-f", container_name], check=False)


def test_spec_file_created_and_resource_limit(neo4j_test_graph):
    uri, user, password = neo4j_test_graph
    tmpdir = tempfile.mkdtemp()
    config = SpecificationConfig(
        resource_limit=12,
        output_directory=tmpdir,
        include_ai_summaries=True,
        include_configuration_details=True,
        anonymization_seed="testseed",
        template_style="comprehensive",
    )
    anonymizer = ResourceAnonymizer(seed="testseed")
    generator = TenantSpecificationGenerator(uri, user, password, anonymizer, config)
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
    shutil.rmtree(tmpdir)


def test_names_anonymized_and_no_real_ids(neo4j_test_graph):
    uri, user, password = neo4j_test_graph
    tmpdir = tempfile.mkdtemp()
    config = SpecificationConfig(
        resource_limit=15,
        output_directory=tmpdir,
        include_ai_summaries=True,
        include_configuration_details=True,
        anonymization_seed="testseed",
        template_style="comprehensive",
    )
    anonymizer = ResourceAnonymizer(seed="testseed")
    generator = TenantSpecificationGenerator(uri, user, password, anonymizer, config)
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
    shutil.rmtree(tmpdir)


def test_relationships_preserved(neo4j_test_graph):
    uri, user, password = neo4j_test_graph
    tmpdir = tempfile.mkdtemp()
    config = SpecificationConfig(
        resource_limit=20,
        output_directory=tmpdir,
        include_ai_summaries=True,
        include_configuration_details=True,
        anonymization_seed="testseed",
        template_style="comprehensive",
    )
    anonymizer = ResourceAnonymizer(seed="testseed")
    generator = TenantSpecificationGenerator(uri, user, password, anonymizer, config)
    output_path = generator.generate_specification()
    with open(output_path, encoding="utf-8") as f:
        content = f.read()
    # Count relationships in Markdown
    rel_count = len(re.findall(r"- DEPENDS_ON", content))
    # There should be at least 1 relationship (from test data)
    assert rel_count >= 1
    shutil.rmtree(tmpdir)
