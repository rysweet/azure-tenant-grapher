"""
Fixtures and mocks for Agent Mode E2E tests.

Provides test fixtures for MCP integration, WebSocket connections,
and Azure API mocking.
"""

import asyncio
import json
import time
from typing import Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock Azure resource data for predictable testing
MOCK_AZURE_RESOURCES = {
    "subscriptions": [
        {
            "subscriptionId": "test-sub-1",
            "displayName": "Test Subscription 1",
            "state": "Enabled",
            "tenantId": "test-tenant-1",
        }
    ],
    "resource_groups": [
        {
            "id": "/subscriptions/test-sub-1/resourceGroups/test-rg-1",
            "name": "test-rg-1",
            "location": "eastus",
            "tags": {"env": "test", "owner": "team-a"},
        }
    ],
    "virtual_machines": [
        {
            "id": "/subscriptions/test-sub-1/resourceGroups/test-rg-1/providers/Microsoft.Compute/virtualMachines/test-vm-1",
            "name": "test-vm-1",
            "location": "eastus",
            "properties": {"vmSize": "Standard_B2s", "provisioningState": "Succeeded"},
        }
    ],
    "storage_accounts": [
        {
            "id": "/subscriptions/test-sub-1/resourceGroups/test-rg-1/providers/Microsoft.Storage/storageAccounts/teststorage1",
            "name": "teststorage1",
            "location": "eastus",
            "kind": "StorageV2",
            "sku": {"name": "Standard_LRS"},
        }
    ],
    "users": [
        {
            "id": "user-1",
            "displayName": "Test User 1",
            "userPrincipalName": "user1@test.com",
            "mail": "user1@test.com",
        }
    ],
    "groups": [
        {
            "id": "group-1",
            "displayName": "Test Group 1",
            "description": "Test security group",
            "members": ["user-1"],
        }
    ],
}


@pytest.fixture
def mock_azure_credentials():
    """Mock Azure credentials for testing."""
    with patch("azure.identity.DefaultAzureCredential") as mock_cred:
        mock_instance = MagicMock()
        mock_cred.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_graph_client():
    """Mock Microsoft Graph client."""
    mock_client = MagicMock()

    # Mock user listing
    users_response = MagicMock()
    users_response.value = MOCK_AZURE_RESOURCES["users"]
    mock_client.users.get.return_value = users_response

    # Mock group listing
    groups_response = MagicMock()
    groups_response.value = MOCK_AZURE_RESOURCES["groups"]
    mock_client.groups.get.return_value = groups_response

    return mock_client


@pytest.fixture
def mock_azure_clients(mock_azure_credentials):
    """Mock Azure SDK clients for testing."""
    clients = {}

    # Mock Subscription client
    with patch("azure.mgmt.resource.SubscriptionClient") as mock_sub:
        sub_client = MagicMock()
        sub_list = MagicMock()
        sub_list.list.return_value = MOCK_AZURE_RESOURCES["subscriptions"]
        sub_client.subscriptions = sub_list
        mock_sub.return_value = sub_client
        clients["subscription"] = sub_client

    # Mock Resource Management client
    with patch("azure.mgmt.resource.ResourceManagementClient") as mock_rm:
        rm_client = MagicMock()

        # Mock resource groups
        rg_list = MagicMock()
        rg_list.list.return_value = MOCK_AZURE_RESOURCES["resource_groups"]
        rm_client.resource_groups = rg_list

        # Mock resources
        resources_list = MagicMock()
        all_resources = (
            MOCK_AZURE_RESOURCES["virtual_machines"]
            + MOCK_AZURE_RESOURCES["storage_accounts"]
        )
        resources_list.list.return_value = all_resources
        rm_client.resources = resources_list

        mock_rm.return_value = rm_client
        clients["resource_management"] = rm_client

    return clients


@pytest.fixture
def mock_mcp_server():
    """Create a mock MCP server URL for testing."""
    # Return a mock URL - actual connections will be mocked in tests
    return "ws://localhost:8765/mcp"


@pytest.fixture
def test_tenant_config(tmp_path):
    """Create a test tenant configuration."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    config_file = config_dir / "test_tenant.json"
    config_data = {
        "tenant_id": "test-tenant-1",
        "tenant_name": "Test Tenant",
        "subscription_ids": ["test-sub-1"],
        "discovery_filters": {
            "resource_types": ["VirtualMachine", "StorageAccount"],
            "resource_groups": ["test-rg-1"],
            "tags": {"env": "test"},
        },
    }

    config_file.write_text(json.dumps(config_data, indent=2))
    return config_file


@pytest.fixture
async def mock_neo4j_session():
    """Mock Neo4j session for graph operations."""
    session = AsyncMock()

    # Mock query results
    async def mock_run(query, **params):
        result = AsyncMock()

        if "MATCH" in query and "VirtualMachine" in query:
            # Mock VM query results
            result.data.return_value = [
                {"n": {"name": "test-vm-1", "id": "vm-1", "location": "eastus"}}
            ]
        elif "CREATE" in query:
            # Mock node/relationship creation
            result.consume.return_value = AsyncMock(counters=MagicMock(nodes_created=1))
        else:
            result.data.return_value = []

        return result

    session.run = mock_run
    yield session


@pytest.fixture
def agent_mode_config(tmp_path, mock_mcp_server):
    """Create agent mode configuration for testing."""
    return {
        "mode": "agent",
        "mcp": {"enabled": True, "endpoint": mock_mcp_server, "timeout": 10},
        "neo4j": {
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "test_password",  # pragma: allowlist secret
            "database": "test",
        },
        "azure": {"tenant_id": "test-tenant-1", "subscription_ids": ["test-sub-1"]},
        "output_dir": str(tmp_path / "output"),
    }


@pytest.fixture
def mock_websocket_client():
    """Mock WebSocket client for agent mode communication."""
    client = AsyncMock()

    # Mock message queue
    message_queue = asyncio.Queue()

    async def mock_send(message):
        """Mock sending messages."""
        data = json.loads(message) if isinstance(message, str) else message

        # Simulate server response
        if data.get("type") == "query":
            response = {
                "type": "response",
                "query_id": data.get("query_id"),
                "result": {
                    "answer": "Found 2 virtual machines in the test environment",
                    "tools_used": ["query_graph", "discover_resources"],
                    "confidence": 0.95,
                },
            }
            await message_queue.put(json.dumps(response))

    async def mock_recv():
        """Mock receiving messages."""
        return await message_queue.get()

    client.send = mock_send
    client.recv = mock_recv
    client.close = AsyncMock()

    return client, message_queue


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for agent reasoning."""
    client = MagicMock()

    def mock_complete(prompt, **kwargs):
        """Mock LLM completion."""
        # Parse intent from prompt
        if "list all virtual machines" in prompt.lower():
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "intent": "list_resources",
                                    "resource_type": "VirtualMachine",
                                    "filters": {},
                                }
                            )
                        }
                    }
                ]
            }
        elif "security" in prompt.lower():
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"intent": "analyze_security", "scope": "all"}
                            )
                        }
                    }
                ]
            }
        else:
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"intent": "unknown", "query": prompt}
                            )
                        }
                    }
                ]
            }

    client.completions.create = mock_complete
    return client


@pytest.fixture
def cleanup_test_resources():
    """Cleanup test resources after tests."""
    resources = []

    def register(resource):
        resources.append(resource)

    yield register

    # Cleanup registered resources
    for resource in resources:
        try:
            if hasattr(resource, "close"):
                resource.close()
            elif hasattr(resource, "cleanup"):
                resource.cleanup()
        except Exception as e:
            print(f"Failed to cleanup resource: {e}")


@pytest.fixture
def performance_monitor():
    """Monitor performance metrics during tests."""
    metrics = {"start_time": None, "end_time": None, "operations": [], "errors": []}

    class PerformanceMonitor:
        def start(self):
            metrics["start_time"] = time.time()

        def end(self):
            metrics["end_time"] = time.time()

        def record_operation(self, name: str, duration: float, success: bool = True):
            metrics["operations"].append(
                {
                    "name": name,
                    "duration": duration,
                    "success": success,
                    "timestamp": time.time(),
                }
            )

        def record_error(self, error: str, context: Optional[Dict] = None):
            metrics["errors"].append(
                {"error": error, "context": context or {}, "timestamp": time.time()}
            )

        def get_metrics(self) -> Dict:
            if metrics["start_time"] and metrics["end_time"]:
                metrics["total_duration"] = metrics["end_time"] - metrics["start_time"]
            return metrics.copy()

    return PerformanceMonitor()
