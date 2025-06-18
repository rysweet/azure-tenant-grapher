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


# All tests now use the shared neo4j_container fixture for container lifecycle.


def test_spec_file_created_and_resource_limit(neo4j_container):
    uri, user, password = neo4j_container
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


def test_names_anonymized_and_no_real_ids(neo4j_container):
    uri, user, password = neo4j_container
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


def test_relationships_preserved(neo4j_container):
    uri, user, password = neo4j_container
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
