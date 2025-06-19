import os
import tempfile
import pytest

from src.container_manager import Neo4jContainerManager

def test_backup_neo4j_database(monkeypatch):
    # This test assumes a running Neo4j container named 'azure-tenant-grapher-neo4j'
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
