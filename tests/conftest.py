import os
from typing import Any, Dict, List
from unittest.mock import Mock

import pytest

# from testcontainers.neo4j import Neo4jContainer  # Commented out - complex setup


# ============================================================================
# Pytest Configuration for Graph Abstraction Tests (Issue #504)
# ============================================================================


def pytest_addoption(parser):
    """Add custom pytest options for graph abstraction tests."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests with testcontainers (requires Docker)",
    )
    parser.addoption(
        "--run-performance",
        action="store_true",
        default=False,
        help="Run performance benchmarking tests",
    )


# ============================================================================
# Resource Processor Test Fixtures
# ============================================================================


@pytest.fixture
def mock_neo4j_session():
    """Provide a mock Neo4j session."""
    mock_session = Mock()
    mock_session.queries_run = []  # Track queries for assertions
    mock_session.run = Mock(return_value=Mock(single=Mock(return_value={})))
    return mock_session


@pytest.fixture
def mock_llm_generator():
    """Provide a mock LLM generator."""

    class MockLLMGenerator:
        def __init__(self):
            self.descriptions_generated = []

        async def generate_resource_description(self, resource: Dict[str, Any]) -> str:
            desc = f"Mock description for {resource.get('name', 'Unknown')}"
            self.descriptions_generated.append(desc)
            return desc

        async def generate_resource_group_description(
            self, rg_name: str, subscription_id: str, resources: List[Dict[str, Any]]
        ) -> str:
            return f"Mock RG description for {rg_name}"

        async def generate_tag_description(
            self, key: str, value: str, resources: List[Dict[str, Any]]
        ) -> str:
            return f"Mock tag description for {key}:{value}"

    return MockLLMGenerator()


@pytest.fixture
def sample_resource() -> Dict[str, Any]:
    """Provide a sample resource for testing."""
    return {
        "id": "/subscriptions/test-sub-123/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
        "name": "test-vm",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "resource_group": "test-rg",
        "subscription_id": "test-sub-123",
        "tags": {"Environment": "Test"},
        "kind": None,
        "sku": None,
    }


@pytest.fixture
def sample_resources(sample_resource: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Provide a list of sample resources for testing."""
    resource1 = sample_resource.copy()
    resource2 = sample_resource.copy()
    resource2["id"] = (
        "/subscriptions/test-sub-123/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm-2"
    )
    resource2["name"] = "test-vm-2"
    return [resource1, resource2]


# ============================================================================
# Neo4j Container Fixtures
# ============================================================================


@pytest.fixture(scope="function")
def neo4j_container():
    """Provides mock Neo4j connection details for testing."""
    uri = "bolt://localhost:7687"
    user = "neo4j"
    password = "test_password"  # pragma: allowlist secret

    os.environ["NEO4J_URI"] = uri
    os.environ["NEO4J_USER"] = user
    os.environ["NEO4J_PASSWORD"] = password

    yield uri, user, password


@pytest.fixture(scope="session")
def shared_neo4j_container():
    """Provides mock Neo4j connection details for testing."""
    uri = "bolt://localhost:7687"
    user = "neo4j"
    password = "test_password"  # pragma: allowlist secret

    os.environ["NEO4J_URI"] = uri
    os.environ["NEO4J_USER"] = user
    os.environ["NEO4J_PASSWORD"] = password

    yield uri, user, password


@pytest.fixture
def mock_terraform_installed():
    """Mock terraform being installed for tests that don't need actual terraform."""
    with pytest.mock.patch(
        "src.utils.cli_installer.is_tool_installed", return_value=True
    ):
        yield


@pytest.fixture
def temp_deployments_dir(tmp_path):
    """Create a temporary deployments directory for testing."""
    deployments_dir = tmp_path / ".deployments"
    deployments_dir.mkdir()
    (deployments_dir / "registry.json").write_text("{}")
    return deployments_dir


@pytest.fixture
def mock_neo4j_connection():
    """Mock Neo4j connection for tests that don't need actual database."""
    from unittest.mock import MagicMock

    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__.return_value = mock_session
    mock_driver.session.return_value.__exit__.return_value = None

    with pytest.mock.patch("neo4j.GraphDatabase.driver", return_value=mock_driver):
        yield mock_driver, mock_session


# ============================================================================
# Documentation Testing Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def repo_root():
    """Return the repository root directory."""
    from pathlib import Path

    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def docs_root(repo_root):
    """Return the documentation root directory."""
    return repo_root / "docs"


@pytest.fixture
def temp_docs_dir(tmp_path):
    """Create a temporary documentation directory for testing."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    return docs_dir


@pytest.fixture
def sample_markdown_file(temp_docs_dir):
    """Create a sample markdown file for testing."""
    content = """# Test Document

This is a test document with various elements.

## Section 1

[Internal Link](./other.md)
[External Link](https://example.com)

## Section 2

![Alt Text](images/diagram.png)

Some code:

```python
def hello():
    print("world")
```
"""
    file_path = temp_docs_dir / "test.md"
    file_path.write_text(content)
    return file_path


@pytest.fixture
def documentation_tree(temp_docs_dir):
    """
    Create a complete documentation tree for testing.

    Structure:
        docs/
        ├── INDEX.md (links to guide.md and reference.md)
        ├── guide.md (links to reference.md)
        ├── reference.md
        ├── orphan.md (not linked from anywhere)
        ├── concepts/
        │   ├── README.md
        │   └── advanced.md
        └── images/
            └── diagram.png
    """
    # Create INDEX.md
    index = temp_docs_dir / "INDEX.md"
    index.write_text(
        """# Documentation Index

## Getting Started
- [User Guide](guide.md)
- [API Reference](reference.md)

## Concepts
- [Advanced Topics](concepts/advanced.md)
"""
    )

    # Create guide.md
    guide = temp_docs_dir / "guide.md"
    guide.write_text(
        """# User Guide

For more details, see the [API Reference](reference.md).

![Architecture](images/diagram.png)
"""
    )

    # Create reference.md
    reference = temp_docs_dir / "reference.md"
    reference.write_text(
        """# API Reference

Complete API documentation.
"""
    )

    # Create orphan.md (not linked)
    orphan = temp_docs_dir / "orphan.md"
    orphan.write_text(
        """# Orphaned Document

This file is not linked from anywhere.
"""
    )

    # Create concepts directory
    concepts_dir = temp_docs_dir / "concepts"
    concepts_dir.mkdir()

    concepts_readme = concepts_dir / "README.md"
    concepts_readme.write_text(
        """# Concepts

Overview of key concepts.
"""
    )

    advanced = concepts_dir / "advanced.md"
    advanced.write_text(
        """# Advanced Topics

Deep dive into advanced features.
"""
    )

    # Create images directory
    images_dir = temp_docs_dir / "images"
    images_dir.mkdir()

    # Create dummy image
    diagram = images_dir / "diagram.png"
    diagram.write_bytes(b"fake png data")

    return {
        "root": temp_docs_dir,
        "index": index,
        "guide": guide,
        "reference": reference,
        "orphan": orphan,
        "concepts_readme": concepts_readme,
        "advanced": advanced,
        "diagram": diagram,
    }


@pytest.fixture
def broken_links_tree(temp_docs_dir):
    """
    Create a documentation tree with broken links for testing.

    Structure:
        docs/
        ├── INDEX.md (has broken link to missing.md)
        └── page.md (has broken link to ../outside.md)
    """
    # Create INDEX.md with broken link
    index = temp_docs_dir / "INDEX.md"
    index.write_text(
        """# Documentation

[Missing Page](missing.md)
[Valid Page](page.md)
"""
    )

    # Create page.md with broken link
    page = temp_docs_dir / "page.md"
    page.write_text(
        """# Page

[Broken Link](../outside.md)
"""
    )

    return {"root": temp_docs_dir, "index": index, "page": page}


@pytest.fixture
def markdown_syntax_samples(temp_docs_dir):
    """Create markdown files with various syntax patterns for testing."""
    samples = {}

    # Valid markdown
    valid = temp_docs_dir / "valid.md"
    valid.write_text(
        """# Valid Document

[Link](page.md)
![Image](image.png)
"""
    )
    samples["valid"] = valid

    # Missing alt text
    no_alt = temp_docs_dir / "no_alt.md"
    no_alt.write_text(
        """# No Alt Text

![](image.png)
"""
    )
    samples["no_alt"] = no_alt

    # Heading hierarchy issue
    bad_headings = temp_docs_dir / "bad_headings.md"
    bad_headings.write_text(
        """# Title

### Skipped H2
"""
    )
    samples["bad_headings"] = bad_headings

    return samples
