"""
Test configuration and shared utilities for Azure Tenant Grapher tests.
"""

import os
import sys
from typing import Any, Dict, List
from unittest.mock import Mock

import pytest

# Add src directory to Python path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class MockNeo4jSession:
    """Mock Neo4j session for testing."""

    def __init__(self) -> None:
        self.queries_run: List[Dict[str, Any]] = []
        self.return_data: Dict[str, Any] = {}
        self.run = Mock()
        self._setup_default_behavior()

    def _setup_default_behavior(self) -> None:
        """Set up default behavior for the run method."""

        def flexible_run(*args: Any, **kwargs: Any) -> Any:
            if len(args) >= 1:
                query = args[0]
                if len(args) >= 2 and isinstance(args[1], dict):
                    params = args[1]
                else:
                    params = kwargs
            else:
                query = kwargs.get("query", "")
                params = {k: v for k, v in kwargs.items() if k != "query"}

            self.queries_run.append({"query": query, "params": params})

            result = Mock()
            mock_record = Mock()

            if "count(r)" in query or "count(n)" in query:
                mock_record.__getitem__ = Mock(return_value=0)
                mock_record.get = Mock(return_value=0)
                mock_record.keys = Mock(return_value=["count"])
                result.single.return_value = mock_record
            elif "llm_description" in query:
                mock_record.__getitem__ = Mock(return_value=None)
                mock_record.get = Mock(return_value=None)
                mock_record.keys = Mock(return_value=["llm_description"])
                result.single.return_value = mock_record
            elif "updated_at" in query or "processing_status" in query:
                mock_record.__getitem__ = Mock(
                    side_effect=lambda key: {
                        "updated_at": "2023-01-01T00:00:00Z",
                        "llm_description": "Test description",
                        "processing_status": "completed",
                    }.get(key)
                )
                mock_record.get = Mock(
                    side_effect=lambda key, default=None: {
                        "updated_at": "2023-01-01T00:00:00Z",
                        "llm_description": "Test description",
                        "processing_status": "completed",
                    }.get(key, default)
                )
                mock_record.keys = Mock(
                    return_value=["updated_at", "llm_description", "processing_status"]
                )
                result.single.return_value = mock_record
            else:
                result.single.return_value = {}

            return result

        self.run.side_effect = flexible_run


class MockNeo4jDriver:
    """Mock Neo4j driver for testing."""

    def __init__(self) -> None:
        self.sessions: List[MockNeo4jSession] = []
        self.closed = False

    def session(self) -> MockNeo4jSession:
        session = MockNeo4jSession()
        self.sessions.append(session)
        return session

    def close(self) -> None:
        self.closed = True


class MockAzureCredential:
    """Mock Azure credential for testing."""

    def __init__(self) -> None:
        self.token = "mock_token"  # nosec


class MockSubscriptionClient:
    """Mock Azure subscription client."""

    def __init__(self, credential: Any) -> None:
        self.credential = credential
        self.subscriptions = Mock()
        mock_sub = Mock()
        mock_sub.subscription_id = "mock-sub-id"
        mock_sub.display_name = "Mock Subscription"
        mock_sub.state = "Enabled"
        mock_sub.tenant_id = "mock-tenant-id"

        self.subscriptions.list.return_value = [mock_sub]


class MockResourceManagementClient:
    """Mock Azure resource management client."""

    def __init__(self, credential: Any, subscription_id: str) -> None:
        self.credential = credential
        self.subscription_id = subscription_id
        self.resources = Mock()
        mock_resource = Mock()
        mock_resource.id = f"/subscriptions/{subscription_id}/resourceGroups/mock-rg/providers/Microsoft.Compute/virtualMachines/mock-vm"
        mock_resource.name = "mock-vm"
        mock_resource.type = "Microsoft.Compute/virtualMachines"
        mock_resource.location = "eastus"
        mock_resource.tags = {"Environment": "Test"}
        mock_resource.kind = None
        mock_resource.sku = None

        self.resources.list.return_value = [mock_resource]


class MockLLMGenerator:
    """Mock LLM description generator for testing."""

    def __init__(self) -> None:
        self.descriptions_generated: List[str] = []

    async def generate_resource_description(self, resource: Dict[str, Any]) -> str:
        description = f"Mock description for {resource.get('name', 'unknown')} of type {resource.get('type', 'unknown')}"
        self.descriptions_generated.append(description)
        return description

    async def process_resources_batch(
        self, resources: List[Dict[str, Any]], batch_size: int = 3
    ) -> List[Dict[str, Any]]:
        enhanced_resources = []
        for resource in resources:
            resource_copy = resource.copy()
            resource_copy["llm_description"] = await self.generate_resource_description(
                resource
            )
            enhanced_resources.append(resource_copy)
        return enhanced_resources

    async def generate_tenant_specification(
        self,
        resources: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        output_path: str,
    ) -> str:
        return output_path


# Test fixtures
@pytest.fixture
def mock_neo4j_driver() -> MockNeo4jDriver:
    return MockNeo4jDriver()


@pytest.fixture
def mock_neo4j_session() -> MockNeo4jSession:
    return MockNeo4jSession()


@pytest.fixture
def mock_azure_credential() -> MockAzureCredential:
    return MockAzureCredential()


@pytest.fixture
def mock_subscription_client() -> MockSubscriptionClient:
    return MockSubscriptionClient(MockAzureCredential())


@pytest.fixture
def mock_resource_client() -> MockResourceManagementClient:
    return MockResourceManagementClient(MockAzureCredential(), "mock-sub-id")


@pytest.fixture
def mock_llm_generator() -> MockLLMGenerator:
    return MockLLMGenerator()


@pytest.fixture
def sample_resource() -> Dict[str, Any]:
    return {
        "id": "/subscriptions/mock-sub/resourceGroups/mock-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
        "name": "test-vm",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "resource_group": "mock-rg",
        "subscription_id": "mock-sub",
        "tags": {"Environment": "Test"},
        "kind": None,
        "sku": None,
    }


@pytest.fixture
def sample_subscription() -> Dict[str, Any]:
    return {
        "id": "mock-subscription-id",
        "display_name": "Mock Subscription",
        "state": "Enabled",
        "tenant_id": "mock-tenant-id",
    }


@pytest.fixture
def sample_resources() -> List[Dict[str, Any]]:
    return [
        {
            "id": "/subscriptions/mock-sub/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "location": "eastus",
            "resource_group": "rg1",
            "subscription_id": "mock-sub",
            "tags": {"Environment": "Production"},
            "kind": None,
            "sku": None,
        },
        {
            "id": "/subscriptions/mock-sub/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
            "name": "storage1",
            "type": "Microsoft.Storage/storageAccounts",
            "location": "eastus",
            "resource_group": "rg1",
            "subscription_id": "mock-sub",
            "tags": {"Environment": "Production"},
            "kind": "StorageV2",
            "sku": "Standard_LRS",
        },
    ]
