"""
Shared test fixtures for tenant reset tests (Issue #627).

This module provides reusable fixtures for mocking Azure SDK,
Graph API, Neo4j, and Redis interactions.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_environment_vars():
    """Auto-set environment variables for all tests."""
    import os

    original_env = os.environ.copy()

    # Set required environment variables with proper GUID formats
    os.environ["AZURE_CLIENT_ID"] = "87654321-4321-4321-4321-210987654321"
    os.environ["AZURE_TENANT_ID"] = "12345678-1234-1234-1234-123456789abc"
    os.environ["AZURE_CLIENT_SECRET"] = "mock-secret"  # pragma: allowlist secret

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture(autouse=True)
def mock_azure_clients():
    """Auto-mock all Azure SDK clients globally for all tests."""
    from azure.core.exceptions import HttpResponseError

    with patch("azure.identity.DefaultAzureCredential") as mock_cred, patch(
        "src.services.tenant_reset_service.SubscriptionClient"
    ) as mock_sub_client, patch(
        "src.services.tenant_reset_service.ResourceManagementClient"
    ) as mock_rmc:
        # Mock credential
        mock_cred_instance = Mock()
        mock_cred_instance.get_token = Mock(return_value=Mock(token="mock-token"))
        mock_cred.return_value = mock_cred_instance

        # Mock subscription client
        mock_sub_instance = Mock()

        # Mock subscription list with sample data
        mock_subscriptions = [
            Mock(
                subscription_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                display_name="Mock Subscription 1",
                tenant_id="12345678-1234-1234-1234-123456789abc",
            ),
            Mock(
                subscription_id="ffffffff-eeee-dddd-cccc-bbbbbbbbbbbb",
                display_name="Mock Subscription 2",
                tenant_id="12345678-1234-1234-1234-123456789abc",
            ),
        ]
        mock_sub_instance.subscriptions.list.return_value = iter(mock_subscriptions)

        # Mock subscriptions.get() to validate GUID format
        def mock_get_subscription(sub_id):
            # Check if it looks like a GUID
            import re

            if not re.match(
                r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                sub_id,
                re.IGNORECASE,
            ):
                # Non-GUID IDs get an error response
                error = HttpResponseError(
                    message=f"The provided subscription identifier '{sub_id}' is malformed or invalid."
                )
                error.status_code = 400
                error.error = Mock(
                    code="InvalidSubscriptionId",
                    message=f"The provided subscription identifier '{sub_id}' is malformed or invalid.",
                )
                raise error

            # Return subscription if GUID format
            return Mock(
                subscription_id=sub_id,
                display_name=f"Mock Subscription {sub_id}",
                tenant_id="12345678-1234-1234-1234-123456789abc",
            )

        mock_sub_instance.subscriptions.get = Mock(side_effect=mock_get_subscription)
        mock_sub_client.return_value = mock_sub_instance

        # Mock resource management client
        mock_rmc_instance = Mock()

        # Mock resource listing
        mock_resources = [
            Mock(
                id="/subscriptions/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/vm-1",
                name="vm-1",
                type="Microsoft.Compute/virtualMachines",
                tags={"environment": "test"},
            ),
        ]
        mock_rmc_instance.resources.list.return_value = iter(mock_resources)
        mock_rmc_instance.resources.list_by_resource_group.return_value = iter(
            mock_resources
        )

        # Mock get_by_id to return resource details
        def mock_get_by_id(resource_id, api_version=None):
            return Mock(
                id=resource_id,
                name=resource_id.split("/")[-1],
                type="Microsoft.Compute/virtualMachines",
                location="eastus",
            )

        mock_rmc_instance.resources.get_by_id = Mock(side_effect=mock_get_by_id)

        # Mock resource group listing
        mock_resource_groups = [
            Mock(
                name="test-rg",
                id="/subscriptions/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/resourceGroups/test-rg",
                location="eastus",
            ),
        ]
        mock_rmc_instance.resource_groups.list.return_value = iter(mock_resource_groups)
        mock_rmc_instance.resource_groups.get = Mock(
            return_value=mock_resource_groups[0]
        )

        # Mock deletion operations with poller that has wait() and result()
        mock_delete_poller = Mock()
        mock_delete_poller.wait = Mock(return_value=None)
        mock_delete_poller.result = Mock(return_value=None)

        mock_rmc_instance.resources.begin_delete = Mock(return_value=mock_delete_poller)
        mock_rmc_instance.resources.begin_delete_by_id = Mock(
            return_value=mock_delete_poller
        )
        mock_rmc_instance.resource_groups.begin_delete = Mock(
            return_value=mock_delete_poller
        )

        mock_rmc.return_value = mock_rmc_instance

        yield {
            "credential": mock_cred_instance,
            "subscription_client": mock_sub_instance,
            "resource_client": mock_rmc_instance,
        }


@pytest.fixture(autouse=True)
def mock_graph_api():
    """Auto-mock Microsoft Graph API globally for all tests."""
    with patch("src.services.tenant_reset_service.MSGRAPH_AVAILABLE", True), patch(
        "src.services.tenant_reset_service.GraphServiceClient"
    ) as mock_graph:
        mock_graph_instance = Mock()

        # Create mock accessor objects for chaining
        mock_sp_accessor = Mock()
        mock_sp_accessor.by_service_principal_id = Mock()
        mock_sp_delete = Mock()
        mock_sp_delete.delete = AsyncMock(return_value=None)
        mock_sp_accessor.by_service_principal_id.return_value = mock_sp_delete

        mock_users_accessor = Mock()
        mock_users_accessor.by_user_id = Mock()
        mock_user_delete = Mock()
        mock_user_delete.delete = AsyncMock(return_value=None)
        mock_users_accessor.by_user_id.return_value = mock_user_delete

        mock_groups_accessor = Mock()
        mock_groups_accessor.by_group_id = Mock()
        mock_group_delete = Mock()
        mock_group_delete.delete = AsyncMock(return_value=None)
        mock_groups_accessor.by_group_id.return_value = mock_group_delete

        # Attach to main instance
        mock_graph_instance.service_principals = mock_sp_accessor
        mock_graph_instance.users = mock_users_accessor
        mock_graph_instance.groups = mock_groups_accessor

        mock_graph.return_value = mock_graph_instance

        yield mock_graph_instance


@pytest.fixture(autouse=True)
def mock_neo4j():
    """Auto-mock Neo4j driver globally for all tests."""
    with patch("neo4j.AsyncGraphDatabase") as mock_neo4j:
        mock_driver = Mock()
        mock_session = AsyncMock()

        # Mock session context manager
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_driver.session.return_value = mock_session

        # Mock query execution with dynamic results
        def mock_run_query(query, *args, **kwargs):
            mock_result = AsyncMock()

            # Return different results based on query type
            if "MATCH" in query and "DELETE" in query:
                # Deletion query - return affected count
                mock_result.single = AsyncMock(return_value={"deleted_count": 2})
                mock_result.data = AsyncMock(return_value=[{"deleted_count": 2}])
            elif "atg_sp_id" in query:
                # ATG SP ID query
                mock_result.single = AsyncMock(
                    return_value={"atg_sp_id": "87654321-4321-4321-4321-210987654321"}
                )
                mock_result.data = AsyncMock(
                    return_value=[{"atg_sp_id": "87654321-4321-4321-4321-210987654321"}]
                )
            else:
                # Default empty result
                mock_result.single = AsyncMock(return_value=None)
                mock_result.data = AsyncMock(return_value=[])

            return mock_result

        mock_session.run = Mock(side_effect=mock_run_query)

        mock_neo4j.driver = Mock(return_value=mock_driver)

        yield mock_driver


@pytest.fixture(autouse=True)
def mock_redis_module():
    """Auto-mock Redis module globally for all tests."""
    import sys

    # Create a mock Redis module
    mock_redis_mod = Mock()

    # Create mock Redis client class
    mock_redis_instance = Mock()
    mock_redis_instance.set = Mock(return_value=True)
    mock_redis_instance.delete = Mock(return_value=1)
    mock_redis_instance.get = Mock(return_value=None)
    mock_redis_instance.setex = Mock(return_value=True)
    mock_redis_instance.ttl = Mock(return_value=-1)

    mock_redis_mod.Redis = Mock(return_value=mock_redis_instance)
    mock_redis_mod.ConnectionError = type("ConnectionError", (Exception,), {})

    # Patch redis module in sys.modules before any imports
    original_redis = sys.modules.get("redis")
    sys.modules["redis"] = mock_redis_mod

    # Also patch the redis attribute in tenant_reset_service
    with patch("src.services.tenant_reset_service.redis", mock_redis_mod):
        yield mock_redis_instance

    # Restore original redis module
    if original_redis is None:
        sys.modules.pop("redis", None)
    else:
        sys.modules["redis"] = original_redis


@pytest.fixture
def mock_azure_credential():
    """Mock Azure DefaultAzureCredential."""
    credential = Mock()
    credential.get_token = Mock(return_value=Mock(token="mock-token"))
    return credential


@pytest.fixture
def mock_tenant_id():
    """Mock Azure tenant ID."""
    return "12345678-1234-1234-1234-123456789abc"


@pytest.fixture
def mock_atg_sp_id():
    """Mock ATG Service Principal object ID."""
    return "87654321-4321-4321-4321-210987654321"


@pytest.fixture
def mock_subscription_id():
    """Mock Azure subscription ID."""
    return "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


@pytest.fixture
def mock_resource_group():
    """Mock Azure resource group name."""
    return "test-rg"


@pytest.fixture
def mock_resource_management_client(mock_subscription_id):
    """Mock Azure ResourceManagementClient with detailed resource operations."""
    mock_client = Mock()

    # Mock resources list operation
    mock_resources = [
        Mock(
            id=f"/subscriptions/{mock_subscription_id}/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-{i}",
            name=f"vm-{i}",
            type="Microsoft.Compute/virtualMachines",
            tags={"environment": "test"},
        )
        for i in range(1, 6)
    ]

    mock_client.resources.list.return_value = mock_resources
    mock_client.resources.list_by_resource_group.return_value = mock_resources
    mock_client.resources.begin_delete = AsyncMock()
    mock_client.resource_groups.list.return_value = []
    mock_client.resource_groups.begin_delete = AsyncMock()

    return mock_client


@pytest.fixture
def mock_graph_client(mock_atg_sp_id):
    """Mock Microsoft Graph API client with detailed identity operations."""
    mock_client = Mock()

    # Mock service principals
    mock_service_principals = [
        Mock(id="sp-1", app_id="app-1", display_name="SP 1"),
        Mock(id=mock_atg_sp_id, app_id="atg-app-id", display_name="ATG SP"),
        Mock(id="sp-3", app_id="app-3", display_name="SP 3"),
    ]

    mock_client.service_principals.list = AsyncMock(
        return_value=mock_service_principals
    )
    mock_client.service_principals.get = AsyncMock()
    mock_client.service_principals.delete = AsyncMock()

    # Mock users
    mock_users = [
        Mock(
            id="user-1", user_principal_name="user1@example.com", display_name="User 1"
        ),
        Mock(
            id="user-2", user_principal_name="user2@example.com", display_name="User 2"
        ),
    ]

    mock_client.users.list = AsyncMock(return_value=mock_users)
    mock_client.users.delete = AsyncMock()

    # Mock groups
    mock_groups = [
        Mock(id="group-1", display_name="Group 1"),
    ]

    mock_client.groups.list = AsyncMock(return_value=mock_groups)
    mock_client.groups.delete = AsyncMock()

    return mock_client


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver with detailed query operations."""
    mock_driver = Mock()

    # Mock session
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()
    mock_driver.session.return_value = mock_session

    # Mock query execution
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(
        return_value={"atg_sp_id": "87654321-4321-4321-4321-210987654321"}
    )
    mock_result.data = AsyncMock(return_value=[])
    mock_session.run = AsyncMock(return_value=mock_result)

    return mock_driver


@pytest.fixture
def mock_redis_client():
    """Mock Redis client with lock operations."""
    mock_redis = Mock()

    # Mock lock operations
    mock_redis.set = Mock(return_value=True)  # Lock acquired
    mock_redis.delete = Mock(return_value=1)  # Lock released
    mock_redis.get = Mock(return_value=None)  # No existing lock
    mock_redis.setex = Mock(return_value=True)  # Set with expiration

    return mock_redis


@pytest.fixture
def mock_scope_data(mock_atg_sp_id):
    """Mock scope data from TenantResetService."""
    return {
        "to_delete": [
            f"/subscriptions/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/"
            f"resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-{i}"
            for i in range(1, 11)
        ]
        + [f"user-{i}" for i in range(1, 6)],
        "to_preserve": [
            mock_atg_sp_id,
            "/subscriptions/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/"
            "providers/Microsoft.Authorization/roleAssignments/atg-role-assignment",
        ],
    }


@pytest.fixture
def mock_deletion_waves():
    """Mock deletion waves ordered by dependencies."""
    return [
        # Wave 1: VMs
        [
            "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-1",
            "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-2",
        ],
        # Wave 2: NICs
        [
            "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Network/networkInterfaces/nic-1",
            "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Network/networkInterfaces/nic-2",
        ],
        # Wave 3: VNets
        [
            "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/vnet-1",
        ],
    ]


@pytest.fixture
def mock_deletion_results():
    """Mock deletion results."""
    return {
        "deleted": [
            f"/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-{i}"
            for i in range(1, 10)
        ],
        "failed": [
            "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-10"
        ],
        "errors": {
            "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-10": "Resource has delete lock"
        },
    }


@pytest.fixture
def mock_environment_variables(mock_atg_sp_id, mock_tenant_id):
    """Mock environment variables for Azure authentication."""
    import os

    original_env = os.environ.copy()

    os.environ["AZURE_CLIENT_ID"] = mock_atg_sp_id
    os.environ["AZURE_TENANT_ID"] = mock_tenant_id
    os.environ["AZURE_CLIENT_SECRET"] = "mock-secret"  # pragma: allowlist secret

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


# Export exceptions for tests
class SecurityError(Exception):
    """Mock SecurityError exception."""

    pass


class RateLimitError(Exception):
    """Mock RateLimitError exception."""

    pass


__all__ = ["RateLimitError", "SecurityError"]
