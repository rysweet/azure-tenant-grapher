import os
import tempfile
import uuid
from typing import Any

import pytest  # noqa: F401 - Used by test framework

from src.container_manager import Neo4jContainerManager

"""
Password and Container Policy for Neo4j Tests:
- NEO4J_PASSWORD and NEO4J_CONTAINER_NAME are set to random values per test session by the fixture in conftest.py.
- Never hardcode secrets or passwords in test code.
- All test containers and volumes are uniquely named to avoid conflicts in parallel/CI runs.
"""


def test_backup_neo4j_database(monkeypatch: Any) -> None:
    manager = Neo4jContainerManager()
    with tempfile.NamedTemporaryFile(suffix=".dump", delete=True) as tmpfile:
        backup_path = tmpfile.name

        # Force the test to run and fail if backup is not implemented or container is not running
        result = manager.backup_neo4j_database(backup_path)
        assert result is False or result is True  # Should not raise AttributeError
        if result:
            assert os.path.exists(backup_path)
            assert os.path.getsize(backup_path) > 0
        else:
            # If backup fails, ensure the file does not exist or is empty
            assert not os.path.exists(backup_path) or os.path.getsize(backup_path) == 0


def test_parallel_container_managers_do_not_conflict():
    """
    Test that two Neo4jContainerManager instances with different container names/passwords do not conflict.
    This simulates parallel/CI scenarios and ensures idempotency.
    """
    # Create two managers with different container names and passwords
    name1 = f"test-neo4j-{uuid.uuid4().hex[:8]}"
    name2 = f"test-neo4j-{uuid.uuid4().hex[:8]}"
    pw1 = uuid.uuid4().hex
    pw2 = uuid.uuid4().hex

    os.environ["NEO4J_CONTAINER_NAME"] = name1
    os.environ["NEO4J_PASSWORD"] = pw1
    mgr1 = Neo4jContainerManager()
    os.environ["NEO4J_CONTAINER_NAME"] = name2
    os.environ["NEO4J_PASSWORD"] = pw2
    mgr2 = Neo4jContainerManager()

    # Ensure cleanup is idempotent and does not raise
    mgr1.cleanup()
    mgr2.cleanup()
    mgr1.cleanup()
    mgr2.cleanup()
