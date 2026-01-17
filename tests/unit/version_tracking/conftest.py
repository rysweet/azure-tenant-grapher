"""Pytest configuration for version_tracking unit tests.

This conftest sets up mocking to prevent real Neo4j imports during unit testing.
"""

import sys
from unittest.mock import MagicMock

import pytest


# Mock the neo4j package to prevent import errors during unit testing
@pytest.fixture(scope="session", autouse=True)
def mock_neo4j_package():
    """Mock neo4j package to prevent import errors in unit tests."""
    # Create mock neo4j package structure
    neo4j_mock = MagicMock()
    neo4j_mock.exceptions = MagicMock()
    neo4j_mock.exceptions.Neo4jError = Exception
    neo4j_mock.exceptions.ServiceUnavailable = Exception
    neo4j_mock.exceptions.SessionExpired = Exception

    # Mock azure package to prevent import errors
    azure_mock = MagicMock()
    azure_mock.identity = MagicMock()
    azure_mock.identity.DefaultAzureCredential = MagicMock
    azure_mock.core = MagicMock()
    azure_mock.core.exceptions = MagicMock()
    azure_mock.core.exceptions.AzureError = Exception
    azure_mock.mgmt = MagicMock()

    # Inject mocks into sys.modules
    sys.modules["neo4j"] = neo4j_mock
    sys.modules["neo4j.exceptions"] = neo4j_mock.exceptions
    sys.modules["azure"] = azure_mock
    sys.modules["azure.identity"] = azure_mock.identity
    sys.modules["azure.core"] = azure_mock.core
    sys.modules["azure.core.exceptions"] = azure_mock.core.exceptions
    sys.modules["azure.mgmt"] = azure_mock.mgmt

    yield

    # Cleanup (optional - usually not needed for session-scoped fixtures)
    # del sys.modules['neo4j']
    # del sys.modules['neo4j.exceptions']
