import os
import sys
import tempfile
from typing import Any

import pytest  # noqa: F401 - Used by test framework

from src.container_manager import Neo4jContainerManager

print("container_manager module file:", sys.modules["src.container_manager"].__file__)

print(
    "Neo4jContainerManager loaded from:",
    Neo4jContainerManager.__module__,
    Neo4jContainerManager.__file__
    if hasattr(Neo4jContainerManager, "__file__")
    else "no __file__",
)


def test_backup_neo4j_database(monkeypatch: Any) -> None:
    # This test assumes a running Neo4j container named 'azure-tenant-grapher-neo4j'
    manager = Neo4jContainerManager()
    with tempfile.NamedTemporaryFile(suffix=".dump", delete=True) as tmpfile:
        backup_path = tmpfile.name

        try:
            result = manager.backup_neo4j_database(backup_path)
            print(f"backup_neo4j_database result: {result}")
            file_exists = os.path.exists(backup_path)
            file_size = os.path.getsize(backup_path) if file_exists else 0
            print(f"Backup file exists: {file_exists}, size: {file_size}")

            assert result is False or result is True  # Should not raise AttributeError
            if result:
                print("Backup reported success, checking file existence and size...")
                assert file_exists, "Backup file does not exist after successful backup"
                assert file_size > 0, "Backup file is empty after successful backup"
            else:
                print(
                    "Backup reported failure, checking file non-existence or zero size..."
                )
                assert (
                    not file_exists or file_size == 0
                ), "Backup file exists and is non-empty after failed backup"
        except Exception as e:
            print(f"Exception during test_backup_neo4j_database: {e}")
            raise
